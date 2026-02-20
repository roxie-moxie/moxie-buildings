"""
LLM fallback scraper -- Tier 3 (Crawl4AI + Claude Haiku).

Covers:
- ~50-70 custom/long-tail sites with no recognized platform pattern
- All Entrata buildings (~30-40) -- routed here per CONTEXT.md decision
  (no Entrata API scraper; revisit as Phase 2.x if LLM struggles)

How it works:
1. Crawl4AI fetches and renders the building's URL (handles JS)
2. Explicit well-known subpages are tried first (/floorplans, /floor-plans,
   /floorplans/all, /apartments) -- if one contains availability content it
   becomes the extraction target without going through link scoring.
3. Internal links are scanned for an availability/floor-plans subpage;
   if one is found it becomes the extraction target (two-pass approach)
4. Crawl4AI converts HTML to markdown (5-10x token reduction vs raw HTML)
5. LLMExtractionStrategy sends markdown to Claude Haiku with a Pydantic schema
6. Claude Haiku returns a JSON list of UnitRecord objects
7. Scraper returns the list for normalize() / save_scrape_result()

Cost estimate (Claude Haiku 3, as of 2026-02-18):
- ~5,000-20,000 tokens per page -> ~$0.15-$0.30/day for 60 buildings
- ~$4.50-$9/month -- well under the $120/month target

Provider: "anthropic/claude-3-haiku-20240307" (via LiteLLM in Crawl4AI)
Requires: ANTHROPIC_API_KEY in environment

Platform: 'llm'
Coverage: ~80-110 buildings (custom sites + Entrata)
"""
import asyncio
import json
import os
from typing import Optional
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

from moxie.db.models import Building

# Claude Haiku model via LiteLLM provider string
_HAIKU_PROVIDER = "anthropic/claude-3-haiku-20240307"

# Keywords used to score internal links for availability relevance.
# Matched against both the href path and the link text (both lowercased).
_AVAILABILITY_KEYWORDS = frozenset({
    "availability", "available", "apartments", "floor-plan", "floorplan",
    "floor_plan", "floor plan", "units", "rentals", "rent", "rates",
    "pricing", "leasing",
})

# Reject links that match these — navigation/footer noise
_SKIP_KEYWORDS = frozenset({
    "blog", "news", "gallery", "photos", "contact", "about", "careers",
    "residents", "login", "apply", "faq", "events", "press",
    # Entrata module paths — these are application/portal modules, not content pages
    "/apartments/module/", "/module/legal", "/module/application",
})

# Well-known subpage paths to probe before falling back to link scoring.
# Ordered by priority: most common Entrata paths first.
_EXPLICIT_SUBPAGES = (
    "/floorplans",
    "/floor-plans",
    "/floorplans/all",
    "/apartments",
)

# Keywords that indicate a page has availability/unit content.
# Used to validate explicit subpage probes.
_CONTENT_KEYWORDS = frozenset({
    "available", "unit", "bed", "studio", "floor plan",
    "sq ft", "sqft", "move-in", "$", "rent", "lease",
})

# Delay (seconds) before extracting HTML from a JS-rendered page.
# Entrata/MRI pages load unit data asynchronously — we must wait for it.
_JS_LOAD_DELAY = 3.0


# Structured extraction schema -- matches UnitInput fields in normalizer.py
class _UnitRecord(BaseModel):
    unit_number: str
    bed_type: str
    rent: str  # raw string; normalizer handles "$1,500/mo", "1500", etc.
    availability_date: str  # raw string; normalizer parses all formats
    floor_plan_name: Optional[str] = None
    baths: Optional[str] = None
    sqft: Optional[str] = None


_EXTRACTION_INSTRUCTION = (
    "Extract every available apartment listing from this page. "
    "A listing may be an individual unit (preferred) or a floor plan with available units. "
    "\n\n"
    "unit_number: Use the specific apartment unit identifier if visible (e.g. '101', '1405', 'B203'). "
    "If no individual unit numbers are shown but floor plan names are listed with availability "
    "(e.g. '1x1 North', '0x1 West', 'S01', 'The Lakeview'), use the floor plan name as the unit_number. "
    "Do NOT use generic category labels like 'Studio', '1 Bedroom', 'Two Bedroom' as the unit_number — "
    "those are bedroom types, not identifiers. "
    "Skip any listing where neither a unit number nor a floor plan name is visible. "
    "\n\n"
    "bed_type: bedroom type, e.g. 'Studio', '1 Bedroom', '2BR', 'Convertible'. "
    "\n\n"
    "rent: the actual listed monthly price as a string, e.g. '$2,340/mo', '2340'. "
    "If shown as a range like 'From $2,174', use the lower bound (e.g. '$2,174'). "
    "Do NOT include listings where rent is missing, unlisted, or says 'Call for pricing'. "
    "\n\n"
    "availability_date: move-in date as a string, e.g. 'Available Now', 'March 1, 2026', '2026-04-01'. "
    "If the listing says 'Available Now' or shows no specific date, use 'Available Now'. "
    "\n\n"
    "floor_plan_name: the floor plan label if one is shown (e.g. 'E2a', 'The Lakeview'), otherwise null. "
    "baths: bathroom count if shown, otherwise null. "
    "sqft: square footage if shown, otherwise null. "
    "\n\n"
    "Only include listings that are available for immediate or future scheduled rental. "
    "Exclude waitlisted, leased, occupied, or 'coming soon' listings. "
    "Return an empty list if no available listings with a price are found."
)

# Rent values from the LLM that signal the price was not actually extracted
_RENT_PLACEHOLDER_VALUES = frozenset({
    "", "n/a", "tbd", "call", "contact", "call for pricing",
    "contact for pricing", "call for rent", "varies",
})


def _score_link(href: str, text: str) -> int:
    """Return a relevance score for an internal link. Higher = more likely to be the availability page."""
    href_l = href.lower()
    text_l = text.lower()

    if any(kw in href_l or kw in text_l for kw in _SKIP_KEYWORDS):
        return 0

    return sum(1 for kw in _AVAILABILITY_KEYWORDS if kw in href_l or kw in text_l)


def _base_url(url: str) -> str:
    """Extract scheme + netloc from a URL (e.g. 'https://example.com')."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _probe_subpage(crawler: AsyncWebCrawler, url: str) -> bool:
    """
    Fetch a URL via Crawl4AI and return True if it appears to contain
    availability/unit content.

    Uses a short JS load delay so dynamically-rendered content (Entrata
    React widgets, etc.) has time to populate before we check.
    """
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        delay_before_return_html=_JS_LOAD_DELAY,
        page_timeout=20000,
    )
    try:
        result = await crawler.arun(url, config=config)
    except Exception:
        return False

    if not result.success or result.status_code not in (200, 301, 302):
        return False

    content_lower = (result.markdown or "").lower()
    return any(kw in content_lower for kw in _CONTENT_KEYWORDS)


async def _find_availability_link(base_url: str) -> str | None:
    """
    Return the URL most likely to contain availability / floor-plan data.

    Strategy (in order):
    1. Try explicit well-known subpage patterns (e.g. /floorplans, /floor-plans).
       Uses Crawl4AI so JS-rendered pages are properly evaluated.
       Returns on the first hit (HTTP 200 + availability keywords in content).
    2. Fall back to scoring internal links from the homepage, skipping any
       URLs that were already probed and didn't contain availability content.

    Returns an absolute URL string, or None if no good match is found.
    """
    root = _base_url(base_url)
    probed_urls: set[str] = set()

    # Step 1: Try explicit subpages (handles Entrata /floorplans and similar)
    config_fast = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        for path in _EXPLICIT_SUBPAGES:
            candidate = root + path
            probed_urls.add(candidate)
            hit = await _probe_subpage(crawler, candidate)
            if hit:
                return candidate

        # Step 2: Score internal links from the homepage
        result = await crawler.arun(base_url, config=config_fast)

    internal_links: list[dict] = []
    if result.links:
        internal_links = result.links.get("internal", []) or []

    best_href: str | None = None
    best_score = 0

    for link in internal_links:
        raw_href = (link.get("href") or "").strip()
        text = (link.get("text") or "").strip()

        if not raw_href or raw_href.startswith("#") or raw_href.startswith("mailto:"):
            continue

        # Resolve relative URLs against the base
        href = urljoin(base_url, raw_href)

        # Skip URLs already probed without availability content
        if href in probed_urls or href.rstrip("/") in probed_urls:
            continue
        # Also skip if the probed path matches (handles trailing slash variants)
        probed_paths = {_base_url(base_url) + path for path in _EXPLICIT_SUBPAGES}
        if href in probed_paths:
            continue

        score = _score_link(href, text)
        if score > best_score:
            best_score = score
            best_href = href

    return best_href if best_score > 0 else None


async def _scrape_with_llm(url: str) -> list[dict]:
    """
    Use Crawl4AI LLMExtractionStrategy to extract unit data from a building URL.

    Pass 1: try explicit subpages, then score internal links (no LLM cost).
    Pass 2: crawl the best URL found (or the original URL) with LLM extraction,
            using a JS load delay so asynchronously-rendered content is present.

    Returns list of raw dicts (matching _UnitRecord schema).
    Returns empty list on extraction failure or no units found.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or environment before running the LLM scraper."
        )

    # Pass 1: find the best availability subpage (no LLM cost)
    target_url = await _find_availability_link(url) or url

    # Pass 2: extract units from the target page.
    # delay_before_return_html ensures JS-rendered unit listings (Entrata, MRI
    # React widgets) have loaded before Crawl4AI captures the markdown.
    strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider=_HAIKU_PROVIDER,
            api_token=api_key,
        ),
        schema=_UnitRecord.model_json_schema(),
        extraction_type="schema",
        instruction=_EXTRACTION_INSTRUCTION,
    )
    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode=CacheMode.BYPASS,
        delay_before_return_html=_JS_LOAD_DELAY,
        page_timeout=30000,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(target_url, config=config)

    raw_content = getattr(result, "extracted_content", None) or ""
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        # Malformed output from LLM -- treat as empty (not a crash)
        return []

    if not isinstance(parsed, list):
        return []

    # Filter to records with the minimum required fields and a real rent value
    units = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        unit_number = (item.get("unit_number") or "").strip()
        bed_type = (item.get("bed_type") or "").strip()
        rent = (item.get("rent") or "").strip()

        if not unit_number or not bed_type:
            continue
        if rent.lower() in _RENT_PLACEHOLDER_VALUES:
            continue

        units.append(item)

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability using LLM extraction (Crawl4AI + Claude Haiku).

    Works for any building URL -- custom sites, Entrata buildings, and any
    platform that cannot be classified into a specific scraper.

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Returns empty list if LLM finds no available units.

    Raises EnvironmentError if ANTHROPIC_API_KEY is not set.
    """
    return asyncio.run(_scrape_with_llm(building.url))
