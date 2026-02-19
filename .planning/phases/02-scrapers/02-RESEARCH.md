# Phase 2: Scrapers - Research

**Researched:** 2026-02-18
**Domain:** Multi-tier web scraping — REST APIs, HTML scraping with httpx + BeautifulSoup, LLM extraction with Crawl4AI + Claude Haiku
**Confidence:** MEDIUM-HIGH (core stack verified via official docs and live API responses; platform-specific HTML structures LOW due to access restrictions)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Platform Assignment**
- Hybrid strategy: URL pattern detection fills blanks; Google Sheets Platform column value always wins on conflict
- Sheets as source of truth: if a Platform column exists in the sheet, sheets-sync writes the value directly to the `platform` field — same as any other sheet column
- Detection fills blanks only: auto-detection only runs when `platform` is null/empty after sheets-sync. Sheets-sourced values are never overwritten by detection
- Integrated into sheets-sync: platform detection runs as part of every sheets-sync pass, classifying any newly synced building that lacks a platform value
- Platform strings: Claude decides exact values — consistent with codebase conventions
- Entrata: skip entirely. Route Entrata buildings to `llm` platform. Revisit only if LLM fallback struggles.

**Tier Execution Order**
- Sequential by tier: Tier 1 first (RentCafe/Yardi + PPM), then Tier 2 platforms, then Tier 3 LLM fallback
- Each tier's implementation informs the next

**RentCafe / Yardi Scraper**
- Build now with stubbed API call: write the full scraper module now; stub the actual API request. Swap in real credentials once confirmed.
- Public API first: pursue the public JSON API at predictable URLs — no vendor enrollment. If public API fully covers unit data needs, vendor access is never required.

**Failure & Stale Flagging**
- Zero units = trust and delete: when a scraper succeeds and returns zero units, delete the building's existing unit records
- Consecutive zero safeguard: track a `consecutive_zero_count` field on the Building model. Increment on each zero-unit return; reset to 0 on any non-zero return.
- Needs-attention threshold: after 5 consecutive zero-unit scrapes, flag the building for review
- `consecutive_zero_count` requires a schema migration — new field on the buildings table

### Claude's Discretion

- Scraper invocation style (async vs sync functions)
- Scraper input shape (Building ORM vs minimal dataclass)
- Scraper return shape (list of UnitInput vs side effects)
- Whether to use an abstract base class (ABC) or documented convention
- Exact platform string values
- HTTP error handling: immediate stale vs retry-then-stale
- Whether scrape_runs logging belongs in Phase 2 scrapers or Phase 3 scheduler

### Deferred Ideas (OUT OF SCOPE)

- Entrata API scraper — deferred indefinitely. LLM fallback handles those ~30-40 buildings.
- Vendor enrollment for Yardi — dropped entirely in favor of public RentCafe API.
- Retry logic (N retries before marking stale) — deferred to Phase 3 scheduler.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-03 | On scrape failure, last known unit data is retained and the building is marked as stale | `last_scrape_status` field on Building already exists; research establishes the write_units() pattern that only deletes units on success |
| SCRAP-01 | Yardi/RentCafe buildings (~220 buildings, 55%) scraped via API | RentCafe public API confirmed at `api.rentcafe.com/rentcafeapi.aspx`; returns `requestType=floorplan` (floor plan + unit summaries) and `requestType=apartmentavailability` (individual unit records). Parameters: `companyCode`, `propertyCode`/`VoyagerPropertyCode`, `apiToken`, `showallunit=1`. Fields: `Beds`, `Baths`, `MinimumRent`, `MaximumRent`, `FloorplanName`, `AvailableUnitsCount`, `AvailabilityURL`. NOTE: public endpoint returns Error:1020 without valid credentials — apiToken is required. This means the "public API" requires per-property tokens embedded in building pages. Investigation task required before full implementation. |
| SCRAP-02 | Entrata buildings (~30-40) — NOTE: context decision overrides this. Route to `llm` platform instead. | Entrata API scraper not built. LLM fallback (SCRAP-09) covers Entrata buildings. |
| SCRAP-03 | PPM buildings (~18) scraped via ppmapartments.com/availability | Page confirmed to exist with table structure: Neighborhood, Building, Unit, Availability, Unit Type, Floorplan, Features, Price columns. Unit data is JavaScript-rendered (not in static HTML). Crawl4AI or Playwright headless browser required to render JS before parsing. |
| SCRAP-04 | Funnel/Nestio buildings (~15-20) | Funnel has a documented API at `nestiolistings.com/api/v2/`. API requires auth key. Key fields: `bedrooms` (0=studio), `bathrooms`, `price`, `date_available`, `unit_number`, `layout`, `status`. Since API key required per-property, must either scrape public listing pages OR obtain keys for each FLATS-brand property. HTML scraping likely required. |
| SCRAP-05 | RealPage/G5 buildings (~10-15) | RealPage has developer APIs but access requires credentials. G5 is RealPage's marketing platform — unit data typically in embedded widgets. HTML scraping via Crawl4AI (JS rendering) required. |
| SCRAP-06 | Bozzuto buildings (~13) | No public API found. Custom platform — HTML scraping required. Crawl4AI or httpx + BeautifulSoup depending on JS rendering needs. |
| SCRAP-07 | Groupfox buildings (~12) via /floorplans HTML pages | URL pattern confirmed: `{subdomain}.groupfox.com/floorplans`. Floor plan categories visible in URL paths (e.g., `/floorplans/studio`). Returns 403 to web fetch, suggesting bot detection. Crawl4AI stealth mode may be required. |
| SCRAP-08 | AppFolio buildings (~5-10) | AppFolio Stack API exists but requires 50+ unit minimum and credentials. Public listing pages are the scraping target. HTML scraping required. |
| SCRAP-09 | Long-tail custom sites (~50-70) via Crawl4AI + Claude Haiku | Crawl4AI v0.8.x confirmed. LLM extraction strategy uses `LLMExtractionStrategy` with `LLMConfig(provider="anthropic/claude-3-haiku-20240307")`. Pydantic schema extraction supported. Haiku 3 cost: $0.25/$1.25 per MTok in/out; with batch API: $0.125/$0.625 per MTok. |
</phase_requirements>

---

## Summary

Phase 2 builds the scraper layer that fills the unit data gap across all ~400 buildings. The work splits cleanly into three tiers: Tier 1 uses REST JSON APIs (RentCafe and PPM), Tier 2 uses platform-specific HTML scrapers (Funnel/Nestio, RealPage/G5, Bozzuto, Groupfox, AppFolio), and Tier 3 uses the LLM fallback (Crawl4AI + Claude Haiku for custom sites and all Entrata buildings). Each scraper is an independent Python module that accepts a Building record and returns a list of normalized `UnitInput` dicts.

The most significant discovery from research is that the RentCafe public API requires a per-property `apiToken` or `companyCode`/`propertyCode` pair that is not guessable from the building URL alone. These credentials are embedded in the JavaScript of each building's RentCafe listing page and must be extracted via a crawl of that page first, or sourced from the existing `rentcafe_property_id` and `rentcafe_api_token` columns already on the Building model. This means the RentCafe scraper needs a credential-discovery sub-step before it can call the availability API. A spike task to confirm the credential extraction pattern is required before full implementation.

For all HTML-based Tier 2 scrapers, the key decision is whether a site renders unit data via server-side HTML (httpx + BeautifulSoup is sufficient) or via JavaScript (Crawl4AI or Playwright headless browser required). PPM, Groupfox, and likely RealPage/G5 render via JavaScript. Funnel/Nestio, Bozzuto, and AppFolio require investigation. The LLM tier (Crawl4AI + Claude Haiku) also handles Entrata buildings, reducing the custom scraper count by ~30-40 buildings.

**Primary recommendation:** Build all scrapers as synchronous functions that accept a `Building` ORM object and return `list[dict]` (raw dicts for UnitInput). Use a `typing.Protocol` to define the scraper interface for type checking without ABC inheritance overhead. Centralize the "write units to DB" logic in a shared `save_scrape_result()` function that handles the delete-then-insert pattern, updates `last_scrape_status`/`last_scraped_at`, and manages `consecutive_zero_count`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Sync/async HTTP client for REST API and HTML scraping | HTTP/1.1 + HTTP/2 support; async client available; superior to `requests` for async use; active maintenance |
| beautifulsoup4 | 4.14.3 | HTML parsing for Tier 2 platform scrapers | The standard Python HTML parser; works with any HTTP client; `html.parser` (stdlib) sufficient for most sites |
| crawl4ai | 0.8.x | Headless browser + LLM extraction for Tier 2 JS sites and Tier 3 long-tail | Built on Playwright; handles JS rendering automatically; LiteLLM integration supports Anthropic natively |
| anthropic | latest | Claude Haiku API access for LLM extraction | Crawl4AI uses LiteLLM which routes to Anthropic via `ANTHROPIC_API_KEY` env var |
| lxml | latest | Fast HTML/XML parser (optional, speeds up BeautifulSoup) | Optional but recommended for Tier 2 scrapers with large HTML payloads |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-httpx | latest | Mock httpx calls in tests | Required for unit tests of Tier 1 API scrapers without real network calls |
| pydantic | 2.x (already installed) | UnitInput validation via existing normalizer.py | Already in stack; all scrapers use existing `normalize()` function |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests | requests lacks async support; httpx provides both sync and async; either works for Tier 1 REST APIs but httpx is more consistent with async Crawl4AI usage |
| beautifulsoup4 | parsel (Scrapy's extractor) | parsel is XPath + CSS selector focused; BeautifulSoup is more forgiving with malformed HTML; parsel faster but BeautifulSoup better for one-off platform scrapers |
| crawl4ai | Playwright directly | Crawl4AI wraps Playwright with LLM extraction and markdown generation built in; direct Playwright gives more control but requires more code for the LLM pipeline |
| crawl4ai LLM extraction | openai API directly | LiteLLM routing in Crawl4AI simplifies provider switching; Anthropic API directly also works if simpler integration preferred |

**Installation:**
```bash
uv add httpx beautifulsoup4 crawl4ai lxml anthropic
uv add --dev pytest-httpx
crawl4ai-setup  # installs Playwright browsers after pip install
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/moxie/
├── db/
│   ├── models.py          # Building + Unit + ScrapeRun (existing)
│   └── session.py         # get_db() (existing)
├── normalizer.py           # UnitInput + normalize() (existing)
├── sync/
│   └── sheets.py          # sheets_sync() with platform detection added (existing, to be extended)
└── scrapers/
    ├── __init__.py        # exports: ScraperProtocol, save_scrape_result()
    ├── base.py            # ScraperProtocol (typing.Protocol) + save_scrape_result()
    ├── platform_detect.py # URL pattern → platform string detection
    ├── tier1/
    │   ├── __init__.py
    │   ├── rentcafe.py    # RentCafe/Yardi API scraper
    │   └── ppm.py         # PPM single-page scraper
    ├── tier2/
    │   ├── __init__.py
    │   ├── funnel.py      # Funnel/Nestio HTML scraper
    │   ├── realpage.py    # RealPage/G5 scraper
    │   ├── bozzuto.py     # Bozzuto scraper
    │   ├── groupfox.py    # Groupfox /floorplans scraper
    │   └── appfolio.py    # AppFolio scraper
    └── tier3/
        ├── __init__.py
        └── llm.py         # Crawl4AI + Claude Haiku LLM scraper
```

### Pattern 1: Scraper Protocol (Claude's Discretion Recommendation)

**What:** Define a `typing.Protocol` that all scrapers satisfy structurally (duck typing), rather than requiring inheritance from an ABC. The protocol is used only for type annotations — no runtime enforcement overhead.

**When to use:** For type-checking the scraper dispatch table in Phase 3. Keeps scrapers as plain functions (or classes) without mandatory inheritance.

**Recommendation:** Use `typing.Protocol` over ABC. ABCs require explicit `super().__init__()` and `@abstractmethod` ceremony; Protocol gives the same type-safety without coupling scrapers to a base class. At this scraper count, documented convention alone would also work — Protocol adds value because Phase 3 will dispatch scrapers by platform string.

**Example:**
```python
# src/moxie/scrapers/base.py
from typing import Protocol
from moxie.db.models import Building

class ScraperProtocol(Protocol):
    def scrape(self, building: Building) -> list[dict]:
        """Return list of raw unit dicts (pre-normalization). Empty list = no units available."""
        ...
```

**Invocation style recommendation:** Synchronous functions for Tier 1 and Tier 2 scrapers; Crawl4AI is inherently async so Tier 3 uses `asyncio.run()` internally. The scraper dispatch layer (Phase 3 scheduler) calls all scrapers synchronously — simpler, easier to test, avoids event loop management complexity at this stage.

```python
# Simple synchronous scraper function (not a class)
def scrape(building: Building) -> list[dict]:
    ...

# Tier 3 internally runs async Crawl4AI via asyncio.run()
import asyncio
from crawl4ai import AsyncWebCrawler

def scrape(building: Building) -> list[dict]:
    return asyncio.run(_async_scrape(building))

async def _async_scrape(building: Building) -> list[dict]:
    async with AsyncWebCrawler() as crawler:
        ...
```

### Pattern 2: Centralized Unit Write (save_scrape_result)

**What:** A shared function that all scrapers call after returning their unit list. Handles: delete old units on success, insert new units, update `last_scrape_status`/`last_scraped_at`, manage `consecutive_zero_count`.

**When to use:** Always — scrapers never write to DB directly. They return unit dicts; the shared function writes them.

**Why centralize:** Every scraper needs the same delete-then-insert transactional pattern, the same stale flagging logic, and the same `consecutive_zero_count` increment/reset logic. Duplicating this across 8+ scrapers guarantees divergence.

```python
# src/moxie/scrapers/base.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from moxie.db.models import Building, Unit, ScrapeRun
from moxie.normalizer import normalize

CONSECUTIVE_ZERO_THRESHOLD = 5

def save_scrape_result(
    db: Session,
    building: Building,
    raw_units: list[dict],
    *,
    scrape_succeeded: bool,
    error_message: str | None = None,
) -> None:
    """
    Write scrape results to the database.

    On success (scrape_succeeded=True):
    - If raw_units is non-empty: delete old units, insert new normalized units,
      reset consecutive_zero_count to 0
    - If raw_units is empty: delete old units (zero units = trust and delete),
      increment consecutive_zero_count; flag building if threshold exceeded
    - Updates last_scrape_status='success', last_scraped_at=now

    On failure (scrape_succeeded=False):
    - Retains existing units (no delete)
    - Updates last_scrape_status='failed', last_scraped_at=now
    - Does NOT increment consecutive_zero_count (errors ≠ zero-unit success)
    """
    now = datetime.now(timezone.utc)

    if scrape_succeeded:
        # Delete existing units regardless of zero/non-zero result
        db.query(Unit).filter_by(building_id=building.id).delete()

        if raw_units:
            # Insert normalized units
            for raw in raw_units:
                unit_dict = normalize(raw, building.id)
                db.add(Unit(**unit_dict))
            building.consecutive_zero_count = 0
        else:
            # Zero units: increment counter
            building.consecutive_zero_count = (building.consecutive_zero_count or 0) + 1
            if building.consecutive_zero_count >= CONSECUTIVE_ZERO_THRESHOLD:
                building.needs_attention = True  # or a separate flag field

        building.last_scrape_status = "success"
        building.last_scraped_at = now
    else:
        # Failure: retain existing units, mark failed
        building.last_scrape_status = "failed"
        building.last_scraped_at = now

    db.add(ScrapeRun(
        building_id=building.id,
        run_at=now,
        status="success" if scrape_succeeded else "failed",
        unit_count=len(raw_units) if scrape_succeeded else 0,
        error_message=error_message,
    ))
    db.commit()
```

### Pattern 3: RentCafe API Scraper (Tier 1)

**What:** Two-endpoint approach. The `requestType=floorplan` endpoint returns floor-plan-level summaries (MinimumRent, MaximumRent, Beds, AvailableUnitsCount). The `requestType=apartmentavailability` endpoint returns individual unit records. The floorplan endpoint is confirmed to require `companyCode` + `propertyCode` (or `VoyagerPropertyCode`) + `apiToken`.

**Credential discovery:** These values are embedded in building page HTML/JS (in `<script>` tags or data attributes). The scraper must either: (a) read `rentcafe_property_id` and `rentcafe_api_token` from the Building record (already schema columns), or (b) fetch the building's URL and extract credentials from the page. Option (a) is preferred — it is what `rentcafe_property_id` and `rentcafe_api_token` were designed for. The spike task is to confirm the exact JSON fields returned by the real API.

**Stubbed implementation:**
```python
# src/moxie/scrapers/tier1/rentcafe.py
import httpx
from moxie.db.models import Building

RENTCAFE_API_BASE = "https://api.rentcafe.com/rentcafeapi.aspx"

def _fetch_floorplans(company_code: str, property_code: str, api_token: str) -> list[dict]:
    """STUBBED: Replace with real httpx call once credentials confirmed."""
    # Real call would be:
    # response = httpx.get(RENTCAFE_API_BASE, params={
    #     "requestType": "apartmentavailability",
    #     "companyCode": company_code,
    #     "propertyCode": property_code,
    #     "apiToken": api_token,
    #     "showallunit": "1",
    # })
    # response.raise_for_status()
    # return response.json()
    raise NotImplementedError("RentCafe API credentials not yet confirmed — stub")

def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from RentCafe/Yardi API.
    Requires building.rentcafe_property_id and building.rentcafe_api_token.
    Returns list of raw unit dicts for normalize().
    """
    if not building.rentcafe_property_id or not building.rentcafe_api_token:
        raise ValueError(f"Building {building.id} missing RentCafe credentials")

    raw_response = _fetch_floorplans(
        company_code=building.management_company or "",  # TBD: may be separate field
        property_code=building.rentcafe_property_id,
        api_token=building.rentcafe_api_token,
    )

    units = []
    for item in raw_response:
        # Field names confirmed from GitHub JS analysis:
        # Beds, Baths, MinimumRent, MaximumRent, FloorplanName, FloorplanImageURL,
        # AvailableUnitsCount, AvailabilityURL
        # Unit-level fields from apartmentavailability endpoint: TBD (spike required)
        pass  # Map API fields → UnitInput dict shape

    return units
```

**Known API fields (from source code analysis, MEDIUM confidence):**
- `requestType=floorplan`: `Beds`, `Baths`, `MinimumSQFT`, `MaximumSQFT`, `MinimumRent`, `MaximumRent`, `FloorplanName`, `FloorplanImageURL`, `AvailableUnitsCount`, `AvailabilityURL`
- `requestType=apartmentavailability`: individual unit records — exact field names TBD (spike needed)
- Parameters: `companyCode`, `propertyCode` or `VoyagerPropertyCode`, `apiToken`, `showallunit=1`

### Pattern 4: PPM Scraper (Tier 1)

**What:** A single HTTP GET to `https://ppmapartments.com/availability/` that renders a table with all PPM buildings' units. Unit data is JavaScript-rendered (loaded dynamically), so Crawl4AI is required for this page.

**Implementation approach:** Use Crawl4AI's `AsyncWebCrawler` to render the page, then parse the resulting HTML. The table columns are: Neighborhood, Building, Unit, Availability, Unit Type, Floorplan, Features, Price. CSS or XPath extraction (not LLM) because the structure is consistent and known.

```python
# src/moxie/scrapers/tier1/ppm.py
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

PPM_URL = "https://ppmapartments.com/availability/"

async def _fetch_ppm_units() -> list[dict]:
    config = CrawlerRunConfig(cache_mode="BYPASS")
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(PPM_URL, config=config)
    # Parse result.html with BeautifulSoup
    # Table columns: Neighborhood, Building, Unit, Availability, Unit Type, Floorplan, Features, Price
    ...

def scrape(building: Building) -> list[dict]:
    """Return only units belonging to this building from the PPM availability page."""
    all_units = asyncio.run(_fetch_ppm_units())
    # Filter by building name match
    return [u for u in all_units if u["building_name"] == building.name]
```

**Note:** PPM scraper is called once per run, caches results in memory, and filters by building name for each building record. Calling the URL 18 times would be wasteful.

### Pattern 5: Crawl4AI LLM Extraction (Tier 3)

**What:** Use Crawl4AI's `LLMExtractionStrategy` with Claude Haiku to extract unit data from arbitrary HTML pages. Crawl4AI converts the page to markdown first (reducing token consumption), then sends to Claude with a structured extraction instruction.

**Provider string for Claude Haiku:** `"anthropic/claude-3-haiku-20240307"` (via LiteLLM). Newer Haiku models: `"anthropic/claude-haiku-4-5-20251001"`.

**Token cost estimate (Claude Haiku 3 — cheapest option):**
- Input: $0.25/MTok, Output: $1.25/MTok
- Average apartment page: ~50-150KB HTML → Crawl4AI markdown: ~5,000-20,000 tokens
- Per building per day at 60 buildings: ~600K-1.2M input tokens → ~$0.15-$0.30/day → ~$4.50-$9/month
- Far below the $120/month estimate from PROJECT.md (that estimate may have used a more expensive model)

**With Claude Haiku 4.5 ($1/$5 per MTok):** ~$18-36/month at same volume. Still well under $120.

**With Batch API (50% discount on Haiku 3):** ~$2.25-$4.50/month.

```python
# src/moxie/scrapers/tier3/llm.py
import asyncio, os
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai import LLMExtractionStrategy
from moxie.db.models import Building

class UnitRecord(BaseModel):
    unit_number: str
    bed_type: str
    rent: str  # raw string, normalizer handles parsing
    availability_date: str
    floor_plan_name: str | None = None
    baths: str | None = None
    sqft: str | None = None

EXTRACTION_INSTRUCTION = """
Extract all available apartment units from this page.
For each unit, extract: unit number, bed type (Studio/1BR/2BR/etc),
monthly rent, availability date, floor plan name (if shown),
bathrooms (if shown), square footage (if shown).
Only include units that are available for rent (not waitlist or leased).
Return an empty list if no units are available.
"""

async def _scrape_with_llm(url: str) -> list[dict]:
    strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="anthropic/claude-3-haiku-20240307",
            api_token=os.environ["ANTHROPIC_API_KEY"],
        ),
        schema=UnitRecord.model_json_schema(),
        extraction_type="schema",
        instruction=EXTRACTION_INSTRUCTION,
    )
    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode="BYPASS",
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)

    import json
    raw = json.loads(result.extracted_content or "[]")
    return raw if isinstance(raw, list) else []

def scrape(building: Building) -> list[dict]:
    return asyncio.run(_scrape_with_llm(building.url))
```

### Pattern 6: Platform Detection (integrated into sheets-sync)

**What:** URL pattern matching to classify buildings by platform string when `building.platform` is null. Runs after every sheets-sync pass.

**Platform string values (recommendation):**
- `rentcafe` — RentCafe/Yardi buildings (identified by `rentcafe.com` in URL or domain)
- `ppm` — PPM buildings (identified by `ppmapartments.com`)
- `funnel` — Funnel/Nestio buildings (identified by `nestiolistings.com`, `funnelleasing.com`, or FLATS brand patterns)
- `realpage` — RealPage/G5 buildings (identified by `realpage.com`, `g5searchmarketing.com`, or known management company patterns)
- `bozzuto` — Bozzuto buildings (identified by `bozzuto.com` URL or management company = "Bozzuto")
- `groupfox` — Groupfox buildings (identified by `groupfox.com` domain)
- `appfolio` — AppFolio buildings (identified by `appfolio.com` in URL)
- `llm` — everything else (custom sites, Entrata, unclassified)

```python
# src/moxie/scrapers/platform_detect.py
from urllib.parse import urlparse

PLATFORM_PATTERNS: list[tuple[str, str]] = [
    ("rentcafe", "rentcafe.com"),
    ("ppm", "ppmapartments.com"),
    ("funnel", "nestiolistings.com"),
    ("funnel", "funnelleasing.com"),
    ("realpage", "realpage.com"),
    ("realpage", "g5searchmarketing.com"),
    ("bozzuto", "bozzuto.com"),
    ("groupfox", "groupfox.com"),
    ("appfolio", "appfolio.com"),
]

def detect_platform(url: str) -> str | None:
    """
    Return platform string for a given URL, or None if unrecognized.
    None triggers fallback to 'llm'.
    """
    if not url:
        return None
    parsed = urlparse(url.lower())
    hostname = parsed.netloc or parsed.path
    for platform, pattern in PLATFORM_PATTERNS:
        if pattern in hostname:
            return platform
    return None  # caller assigns 'llm'
```

### Pattern 7: Schema Migration for consecutive_zero_count

**What:** New Alembic migration to add `consecutive_zero_count` (Integer, default 0) to the buildings table. This is a Phase 2 prerequisite before any scraper can run.

```python
# alembic/versions/XXXX_add_consecutive_zero_count.py
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    with op.batch_alter_table("buildings") as batch_op:
        batch_op.add_column(
            sa.Column("consecutive_zero_count", sa.Integer(), server_default="0", nullable=False)
        )

def downgrade() -> None:
    with op.batch_alter_table("buildings") as batch_op:
        batch_op.drop_column("consecutive_zero_count")
```

**Also add to Building model in models.py:**
```python
consecutive_zero_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
```

### Anti-Patterns to Avoid

- **Scraper writes units directly:** Never. All DB writes go through `save_scrape_result()`. Scrapers are pure functions: Building → list[dict].
- **Delete units before scrape:** The delete happens inside `save_scrape_result()` only after scrape returns successfully. Never delete before calling the scraper.
- **Calling PPM URL once per building:** PPM is a single shared availability page. Call once per scraper run, cache in memory, filter per building. Calling 18 times is wasteful.
- **Using ABC instead of Protocol:** ABCs force inheritance on all scrapers. Protocol is structural — any module with a `scrape(building)` function satisfies it without importing the base.
- **Parsing JavaScript-rendered content with httpx alone:** httpx fetches the raw HTTP response; if unit data is injected by JavaScript, it will be missing. Use Crawl4AI for JS-rendered sites.
- **Ignoring Error:1020 from RentCafe:** The `api.rentcafe.com` endpoint returns `[{"Error":"1020"}]` for invalid credentials. Check for this error in the response and raise a clear exception rather than returning an empty list (which would trigger the consecutive_zero_count logic).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Headless browser JS rendering | Custom Playwright wrapper | Crawl4AI | Crawl4AI wraps Playwright with markdown generation and LLM pipeline built in; handles stealth mode, caching, and content filtering |
| LLM extraction prompt engineering | Ad-hoc prompts per site | Crawl4AI `LLMExtractionStrategy` with Pydantic schema | Schema-constrained extraction produces consistent JSON; Crawl4AI handles chunking for long pages automatically |
| HTML parsing | Regex on HTML strings | BeautifulSoup | BeautifulSoup handles malformed HTML; regex on HTML is famously fragile |
| HTTP sessions with connection pooling | Manual connection management | `httpx.Client()` context manager | httpx client handles connection pooling, retry headers, timeout, and keep-alive automatically |
| Token counting for LLM cost control | Manual character counting | Crawl4AI's `chunk_token_threshold` and `PruningContentFilter` | Built-in chunking respects model context limits; pruning filter removes boilerplate before LLM sees content |
| Platform string validation | DB enum or CHECK constraint | Application-layer constant set | Already decided: plain String column; validate against a frozenset in the detect function |

**Key insight:** The JS rendering problem is the single most common reason apartment site scrapers break. Sites that load unit tables via XHR after page load look empty to httpx. Crawl4AI solves this for free; building a custom Playwright wrapper takes days and needs maintenance.

---

## Common Pitfalls

### Pitfall 1: RentCafe Error:1020 Treated as Empty Unit List

**What goes wrong:** The scraper gets `[{"Error":"1020"}]` from the RentCafe API and incorrectly interprets this as "no units available," deleting the building's existing units and incrementing `consecutive_zero_count`.

**Why it happens:** The response is a list, and the code iterates it expecting unit objects. An "Error" key object doesn't parse as a unit, producing an empty result silently.

**How to avoid:** Always check for `"Error"` key in API responses before processing. Raise a `ScraperError` when an error response is detected.

**Warning signs:** Buildings with `last_scrape_status='success'` and `consecutive_zero_count` incrementing are actually failing silently.

---

### Pitfall 2: PPM Page Returns JS-Rendered Table (Not in Static HTML)

**What goes wrong:** `httpx.get("https://ppmapartments.com/availability/")` returns HTML with JavaScript variable declarations (`arrayNeighborhoods`, `arrayUnitTypes`) but no actual unit table rows — they are rendered by JavaScript after page load.

**Why it happens:** The unit data is loaded via JavaScript on the client side, not present in the initial HTML response.

**How to avoid:** Use Crawl4AI (or Playwright directly) instead of httpx for PPM. Verify the rendered content contains actual unit rows before parsing.

**Warning signs:** BeautifulSoup finds the table headers but zero data rows.

---

### Pitfall 3: Groupfox and Other Sites Return 403 to Plain httpx

**What goes wrong:** `httpx.get("https://axis.groupfox.com/floorplans")` returns HTTP 403 Forbidden. The scraper raises an exception or returns empty.

**Why it happens:** Sites detect non-browser HTTP clients by missing headers (User-Agent, Accept-Encoding, cookie state). Crawl4AI's Playwright session has a full browser fingerprint that bypasses basic bot detection.

**How to avoid:** Use Crawl4AI for Groupfox and any other Tier 2 scraper that returns 403 to plain httpx. Set realistic User-Agent headers as a first attempt before escalating to Crawl4AI.

**Warning signs:** 403 status code in response; sometimes 200 but empty body or redirect to CAPTCHA page.

---

### Pitfall 4: Crawl4AI Playwright Not Available After Install

**What goes wrong:** `crawl4ai-setup` was not run after `pip install crawl4ai`, so Playwright browsers are not installed. `AsyncWebCrawler` raises an error about missing browser executables.

**Why it happens:** Crawl4AI's Playwright dependency requires a post-install setup step. `pip install crawl4ai` installs the Python package but does not install browser binaries.

**How to avoid:** Add `crawl4ai-setup` to the dev bootstrap script (after `uv sync`). Run `crawl4ai-doctor` to verify installation.

**Warning signs:** `playwright._impl._api_types.Error: Executable doesn't exist at ...` on first Crawl4AI run.

---

### Pitfall 5: Building Name Mismatch in PPM Filter

**What goes wrong:** The PPM scraper filters all-buildings response by `building_name == building.name`, but the name in the PPM table doesn't exactly match `Building.name` from Google Sheets (e.g., "Streeterville Tower" vs "PPM - Streeterville Tower").

**Why it happens:** The Building.name value comes from Google Sheets and may include management company prefixes or abbreviations that PPM's own availability page does not use.

**How to avoid:** Implement PPM filtering by URL or partial name match (contains) rather than exact equality. Consider storing a PPM-specific building identifier if names diverge significantly.

**Warning signs:** PPM scraper returns 0 units for buildings that definitely have available units.

---

### Pitfall 6: consecutive_zero_count Not on Building Model

**What goes wrong:** `save_scrape_result()` tries to set `building.consecutive_zero_count` but the attribute doesn't exist — the Alembic migration wasn't run or the model wasn't updated.

**Why it happens:** Phase 2 adds a new column to buildings. If the migration runs before the model is updated, or vice versa, AttributeError or column-not-found errors occur.

**How to avoid:** Update both `models.py` AND the Alembic migration in the same task. Run `alembic upgrade head` before running any scraper.

**Warning signs:** `AttributeError: 'Building' object has no attribute 'consecutive_zero_count'` at runtime.

---

### Pitfall 7: Funnel/Nestio API Key Not Available Per-Building

**What goes wrong:** Funnel's REST API at `nestiolistings.com/api/v2/` requires an API key. If individual property keys are not obtainable, the API approach fails entirely and HTML scraping of the public listing page is required instead.

**Why it happens:** Funnel is a private, authenticated API — each property has its own key. The keys are not embedded in public pages.

**How to avoid:** Plan HTML scraping as the primary approach for Funnel, not API access. Check whether Funnel listing pages expose unit data in static HTML or via XHR. If XHR, intercept the request URL and parameters from browser DevTools.

**Warning signs:** Receiving HTTP 401 or 403 from `nestiolistings.com/api/v2/` without a key.

---

## Code Examples

Verified patterns from official sources and live API investigation:

### RentCafe API — Confirmed Working Endpoint Pattern (MEDIUM confidence)

```python
# Source: Confirmed from GitHub JS analysis (scibettas1/rentCafe-API)
# Field names verified from JS source code accessing the response
import httpx

def fetch_rentcafe_floorplans(
    company_code: str,
    property_code: str,
    api_token: str,
) -> list[dict]:
    """
    Call RentCafe floorplan endpoint. Returns list of floor plan dicts.
    Known response fields: Beds, Baths, MinimumSQFT, MaximumSQFT,
    MinimumRent, MaximumRent, FloorplanName, FloorplanImageURL,
    AvailableUnitsCount, AvailabilityURL
    """
    response = httpx.get(
        "https://api.rentcafe.com/rentcafeapi.aspx",
        params={
            "requestType": "floorplan",
            "companyCode": company_code,
            "propertyCode": property_code,
            "apiToken": api_token,
            "showallunit": "1",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    # Guard against error response: [{"Error": "1020"}]
    if isinstance(data, list) and data and "Error" in data[0]:
        raise RuntimeError(f"RentCafe API error: {data[0]['Error']}")
    return data
```

### Crawl4AI Basic Scrape with BeautifulSoup Parsing

```python
# Source: https://docs.crawl4ai.com/core/quickstart/
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from bs4 import BeautifulSoup

async def scrape_js_rendered_page(url: str) -> str:
    """Fetch JS-rendered HTML, return full rendered HTML string."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)
    return result.html  # fully rendered HTML

def parse_ppm_table(html: str) -> list[dict]:
    """Parse PPM availability table from rendered HTML."""
    soup = BeautifulSoup(html, "html.parser")
    # Find table with unit data — columns: Neighborhood, Building, Unit,
    # Availability, Unit Type, Floorplan, Features, Price
    units = []
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 8:
            continue
        units.append({
            "neighborhood": cells[0].get_text(strip=True),
            "building_name": cells[1].get_text(strip=True),
            "unit_number": cells[2].get_text(strip=True),
            "availability_date": cells[3].get_text(strip=True),
            "bed_type": cells[4].get_text(strip=True),
            "floor_plan_name": cells[5].get_text(strip=True),
            "rent": cells[7].get_text(strip=True),
        })
    return units
```

### Crawl4AI LLM Extraction with Pydantic Schema

```python
# Source: https://docs.crawl4ai.com/extraction/llm-strategies/
import asyncio, os, json
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai import LLMExtractionStrategy

class UnitRecord(BaseModel):
    unit_number: str
    bed_type: str
    rent: str
    availability_date: str
    floor_plan_name: str | None = None
    baths: str | None = None
    sqft: str | None = None

async def extract_units_with_llm(url: str) -> list[dict]:
    strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="anthropic/claude-3-haiku-20240307",
            api_token=os.environ["ANTHROPIC_API_KEY"],
        ),
        schema=UnitRecord.model_json_schema(),
        extraction_type="schema",
        instruction=(
            "Extract all apartment units available for rent. "
            "For each unit: unit_number, bed_type (e.g. Studio, 1BR, 2BR), "
            "rent (monthly price as string), availability_date, "
            "floor_plan_name, baths, sqft. "
            "Return empty list if no units found."
        ),
    )
    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode="BYPASS",
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)
    raw = json.loads(result.extracted_content or "[]")
    return raw if isinstance(raw, list) else []
```

### httpx Async Client Pattern

```python
# Source: https://www.python-httpx.org/async/
import httpx
import asyncio

async def fetch_json(url: str, params: dict) -> dict | list:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

# For sync scraper context, run with:
result = asyncio.run(fetch_json(url, params))
```

### Alembic Migration — Adding consecutive_zero_count

```python
# alembic/versions/XXXX_add_consecutive_zero_count.py
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    with op.batch_alter_table("buildings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "consecutive_zero_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )

def downgrade() -> None:
    with op.batch_alter_table("buildings") as batch_op:
        batch_op.drop_column("consecutive_zero_count")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests` + manual Selenium | `httpx` + Crawl4AI (Playwright-based) | 2023-2024 | httpx supports async natively; Crawl4AI handles browser automation + LLM extraction in one library |
| LLM prompting raw HTML | LLM prompting markdown (converted from HTML) | 2024 | Markdown is ~5-10x more token-efficient than raw HTML; Crawl4AI does the conversion automatically |
| Per-scraper ABC inheritance | `typing.Protocol` structural typing | Python 3.8+ / widespread adoption 2022+ | Protocol gives type safety without requiring inheritance; scrapers remain simple functions |
| Entrata-specific scraper | LLM fallback (decided in context) | Phase 2 planning 2026 | Entrata deprecated its legacy gateway April 2025; routing to LLM avoids building against unstable API |
| Vendor API enrollment for Yardi | RentCafe public API (per-property tokens) | Phase 2 planning 2026 | Vendor enrollment dropped; public API tokens discoverable from building pages |

**Deprecated/outdated:**
- `Scrapy`: Full crawling framework; overkill for targeted single-building scrapers. Not used.
- `Selenium`: Replaced by Playwright (which Crawl4AI wraps). More stable, faster, better DevTools protocol support.
- `oauth2client`: Not relevant here, but noted in Phase 1 — deprecated Google auth library.
- Entrata legacy gateway: Deprecated April 2025 per requirement note. Do not build against it.

---

## Open Questions

1. **RentCafe API credentials: per-property extraction strategy**
   - What we know: API requires `companyCode` + `propertyCode` + `apiToken`. These are per-property values. The Building model already has `rentcafe_property_id` and `rentcafe_api_token` columns.
   - What's unclear: Are `rentcafe_property_id`/`rentcafe_api_token` populated in the current DB? If not, how do we discover them? Do we extract from each building's page HTML? Is there a predictable URL pattern (e.g., Yardi property codes visible in URL)?
   - Recommendation: **Spike task required** — fetch 2-3 known RentCafe building URLs from the DB, inspect their HTML/JS for embedded credentials, confirm field names, verify the API returns unit-level data with the `requestType=apartmentavailability` endpoint.

2. **RentCafe apartmentavailability vs floorplan endpoint**
   - What we know: `requestType=floorplan` returns floor-plan-level data (MinimumRent, MaximumRent, AvailableUnitsCount). `requestType=apartmentavailability` presumably returns individual unit records.
   - What's unclear: Exact field names for unit-level availability data (UnitNumber, AvailableDate, Rent per unit). The Scribd API guide would have this but is inaccessible.
   - Recommendation: The spike task above will confirm these fields by hitting the real endpoint.

3. **Funnel/Nestio: API key vs HTML scraping**
   - What we know: Funnel's REST API requires a per-property key. Keys are not publicly available.
   - What's unclear: Do FLATS-brand building public listing pages render unit data in static HTML or via XHR? If XHR, what endpoint pattern?
   - Recommendation: Before building the Funnel scraper, manually inspect 2 FLATS building pages in browser DevTools (Network tab) to find the data source. If it's an XHR to a predictable JSON endpoint, scrape that directly. If static HTML, parse with BeautifulSoup.

4. **PPM: exact CSS selectors for unit table**
   - What we know: Page exists, has a table with correct columns, data is JS-rendered.
   - What's unclear: Exact CSS class names, table IDs, or data attributes used by the unit rows.
   - Recommendation: Render the PPM page with Crawl4AI during the PPM scraper spike, inspect `result.html`, then hardcode the selectors. The page structure is a single consistent page so selectors will be stable.

5. **Platform detection: is "Scraper Quality" column in Sheet related to platform?**
   - What we know: The Google Sheet has a "Scraper Quality" column. The context notes this may be related to or replaceable by the Platform column.
   - What's unclear: What values does "Scraper Quality" contain? Does it already encode platform information?
   - Recommendation: Inspect the actual Sheet before building platform detection to avoid duplicate work.

6. **scrape_runs logging: Phase 2 or Phase 3?**
   - What we know: Context leaves this as Claude's discretion. The `scrape_runs` table already exists in Phase 1 schema.
   - Recommendation: Include `ScrapeRun` logging in `save_scrape_result()` in Phase 2. Phase 3's scheduler will wrap scrapers but the logging belongs with the data-write logic, not the scheduling logic. This way Phase 2 is testable end-to-end without needing Phase 3.

---

## Sources

### Primary (HIGH confidence)

- [Crawl4AI v0.8.x Quick Start](https://docs.crawl4ai.com/core/quickstart/) — `AsyncWebCrawler`, `CrawlerRunConfig`, `CacheMode` verified
- [Crawl4AI LLM Strategies](https://docs.crawl4ai.com/extraction/llm-strategies/) — `LLMExtractionStrategy`, `LLMConfig`, provider format `"anthropic/model-name"`, Pydantic schema extraction
- [Anthropic Pricing — official](https://platform.claude.com/docs/en/about-claude/pricing) — Claude Haiku 3: $0.25/$1.25 per MTok; Claude Haiku 4.5: $1/$5 per MTok; Batch API 50% discount confirmed
- [httpx PyPI](https://pypi.org/project/httpx/) — version 0.28.1 confirmed current; sync + async APIs
- [beautifulsoup4 PyPI](https://pypi.org/project/beautifulsoup4/) — version 4.14.3, Python 3.12 compatible
- Existing codebase (`src/moxie/db/models.py`) — Building model confirmed: `rentcafe_property_id`, `rentcafe_api_token`, `platform`, `last_scrape_status`, `last_scraped_at`, `consecutive_zero_count` NOT YET PRESENT (migration needed)
- Existing codebase (`src/moxie/normalizer.py`) — `UnitInput` Pydantic model confirmed; `normalize()` function is the target for all scraper output

### Secondary (MEDIUM confidence)

- [GitHub: scibettas1/rentCafe-API — script.js](https://raw.githubusercontent.com/scibettas1/rentCafe-API/main/script.js) — Live JS source code confirms API field names: `Beds`, `Baths`, `MinimumSQFT`, `MaximumSQFT`, `MinimumRent`, `MaximumRent`, `FloorplanName`, `FloorplanImageURL`, `AvailableUnitsCount`, `AvailabilityURL`. Parameters: `requestType=floorplan`, `apiToken`, `VoyagerPropertyCode`. MEDIUM because these are field names from the floorplan endpoint, not apartmentavailability.
- [Funnel Developer API Docs](https://developers.funnelleasing.com/api/v2/listings.html) — confirmed Funnel API is authenticated; fields `bedrooms`, `bathrooms`, `price`, `date_available`, `unit_number`, `layout`, `status` verified
- [PPM availability page](https://ppmapartments.com/availability/) — confirmed page structure, table columns, JS rendering confirmed via WebFetch analysis
- [Crawl4AI GitHub](https://github.com/unclecode/crawl4ai) — v0.8.0 released Jan 16 2026; requires `crawl4ai-setup` post-install
- [Groupfox floorplans URL pattern](https://axis.groupfox.com/floorplans) — URL pattern `{subdomain}.groupfox.com/floorplans` confirmed; 403 response to non-browser clients (bot detection confirmed)

### Tertiary (LOW confidence)

- RentCafe `requestType=apartmentavailability` field names — exact fields unknown; only floorplan endpoint fields confirmed. Spike required.
- Bozzuto, AppFolio, RealPage/G5 specific HTML structures — not accessible during research; require direct inspection.
- Funnel/Nestio public listing page HTML structure — not confirmed; may use XHR or static HTML.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — httpx, beautifulsoup4, crawl4ai, anthropic all verified via PyPI/official docs with current versions
- Architecture patterns: HIGH — `save_scrape_result()` pattern and Protocol recommendation are well-established Python practices; scraper structure derived from existing codebase analysis
- RentCafe API: MEDIUM — floorplan endpoint fields confirmed from real JS source; apartmentavailability fields require spike; Error:1020 behavior confirmed from live API call
- Platform HTML structures (Funnel, Bozzuto, Groupfox, AppFolio, RealPage): LOW — direct HTML inspection blocked by 403/bot-detection during research; structures must be confirmed during implementation spikes
- LLM cost estimates: HIGH — based on official Anthropic pricing page and reasonable token estimates for apartment pages
- PPM page structure: MEDIUM — table columns confirmed from page content; exact CSS selectors unknown (JS-rendered)

**Research date:** 2026-02-18
**Valid until:** 2026-05-18 (Crawl4AI moves fast; recheck before implementation if >30 days; Anthropic pricing stable but verify before cost projections)
