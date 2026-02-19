"""
LLM fallback scraper -- Tier 3 (Crawl4AI + Claude Haiku).

Covers:
- ~50-70 custom/long-tail sites with no recognized platform pattern
- All Entrata buildings (~30-40) -- routed here per CONTEXT.md decision
  (no Entrata API scraper; revisit as Phase 2.x if LLM struggles)

How it works:
1. Crawl4AI fetches and renders the building's URL (handles JS)
2. Internal links are scanned for an availability/floor-plans subpage;
   if one is found it becomes the extraction target (two-pass approach)
3. Crawl4AI converts HTML to markdown (5-10x token reduction vs raw HTML)
4. LLMExtractionStrategy sends markdown to Claude Haiku with a Pydantic schema
5. Claude Haiku returns a JSON list of UnitRecord objects
6. Scraper returns the list for normalize() / save_scrape_result()

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
from urllib.parse import urljoin

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
    "floor_plan", "units", "rentals", "rent", "rates", "pricing", "leasing",
})

# Reject links that match these — navigation/footer noise
_SKIP_KEYWORDS = frozenset({
    "blog", "news", "gallery", "photos", "contact", "about", "careers",
    "residents", "login", "apply", "faq", "events", "press",
})


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
    "Extract every individual apartment unit currently listed as available for rent on this page. "
    "Return one record per unit, not one record per floor plan or bedroom type. "
    "\n\n"
    "unit_number: the specific apartment identifier, e.g. '101', '1405', 'B203'. "
    "This must be a unit number, NOT a floor plan name or bedroom category. "
    "Do NOT use values like 'E2a', 'A1', 'C3', 'Studio', '1 Bedroom', 'Two Bedroom' as the unit_number. "
    "If no individual unit number is visible for a listing, skip it entirely. "
    "\n\n"
    "bed_type: bedroom type, e.g. 'Studio', '1 Bedroom', '2BR', 'Convertible'. "
    "\n\n"
    "rent: the actual listed monthly price as a string, e.g. '$2,340/mo', '2340'. "
    "Do NOT include units where the rent is missing, unlisted, or says 'Call for pricing'. "
    "\n\n"
    "availability_date: move-in date as a string, e.g. 'Available Now', 'March 1, 2026', '2026-04-01'. "
    "\n\n"
    "floor_plan_name: the floor plan label if one is shown (e.g. 'E2a', 'The Lakeview'), otherwise null. "
    "baths: bathroom count if shown, otherwise null. "
    "sqft: square footage if shown, otherwise null. "
    "\n\n"
    "Only include units that are available for immediate or future scheduled rental. "
    "Exclude waitlisted, leased, occupied, or 'coming soon' units. "
    "Return an empty list if no individual available units with specific unit numbers and rents are found."
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


async def _find_availability_link(base_url: str) -> str | None:
    """
    Crawl the building's landing page (no LLM) and return the internal link
    that most likely leads to the availability / floor-plans subpage.

    Returns an absolute URL string, or None if no good match is found.
    """
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(base_url, config=config)

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

        score = _score_link(href, text)
        if score > best_score:
            best_score = score
            best_href = href

    return best_href if best_score > 0 else None


async def _scrape_with_llm(url: str) -> list[dict]:
    """
    Use Crawl4AI LLMExtractionStrategy to extract unit data from a building URL.

    Pass 1: crawl the landing page (no LLM) to find an availability subpage.
    Pass 2: crawl the best URL found (or the original URL) with LLM extraction.

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

    # Pass 2: extract units from the target page
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
