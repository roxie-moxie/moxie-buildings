"""
PPM Apartments scraper — Tier 1 single-page availability.

PPM publishes all units for all buildings on one page:
https://ppmapartments.com/availability/

The page is JavaScript-rendered — unit cards are injected by JS after load.
Crawl4AI (AsyncWebCrawler) renders the page, then BeautifulSoup parses the HTML.

DOM structure (confirmed 2026-02-19):
  div.rm-listings-container > div.unit (one per unit)
    div.spec.spec-building  → Building name (link text)
    div.spec (Unit:)        → Unit number
    div.spec (Availability:)→ Availability date
    div.spec (Unit Type:)   → Bed/bath type
    div.spec (Floorplan)    → Floor plan link
    div.spec.spec-sm (Price:) → Rent price
    div.spec.spec-feature   → Features

Design: Call the page ONCE per scraper run, cache in memory, filter per building.
Do NOT call the page once per building (18 buildings x 1 call = wasteful).

Platform: 'ppm'
Coverage: ~18 buildings
"""
import asyncio
import re
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from moxie.db.models import Building

PPM_URL = "https://ppmapartments.com/availability/"


async def _fetch_ppm_html() -> str:
    """Fetch and JS-render the PPM availability page. Returns full rendered HTML."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(PPM_URL, config=config)
    return result.html or ""


def _get_spec_value(unit_div, label: str) -> str:
    """Extract the value from a div.spec by its label text (e.g., 'Unit:', 'Price:')."""
    for spec in unit_div.select("div.spec"):
        text = spec.get_text(strip=True)
        if text.startswith(label):
            return text[len(label):].strip()
    return ""


def _parse_ppm_html(html: str) -> list[dict]:
    """
    Parse the PPM availability page from rendered HTML (card layout).
    Returns a list of raw unit dicts (with 'building_name' field for filtering).
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []
    for card in soup.select("div.unit"):
        building_spec = card.select_one("div.spec-building")
        if not building_spec:
            continue
        building_name = building_spec.get_text(strip=True).replace("Building:", "").strip()
        unit_number = _get_spec_value(card, "Unit:")
        unit_type = _get_spec_value(card, "Unit Type:")
        if not unit_type:
            continue
        price_text = _get_spec_value(card, "Price:")
        availability = _get_spec_value(card, "Availability:") or "Available Now"
        # Extract floor plan name from the Floorplan link if present
        floorplan_spec = None
        for spec in card.select("div.spec"):
            if "Floorplan" in spec.get_text():
                link = spec.select_one("a")
                floorplan_spec = link.get_text(strip=True) if link else None
                break
        units.append({
            "building_name": building_name,
            "unit_number": unit_number,
            "availability_date": availability,
            "bed_type": unit_type,
            "floor_plan_name": floorplan_spec,
            "rent": price_text,
        })
    return units


def _normalize_name(name: str) -> str:
    """Strip punctuation and collapse whitespace for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower().strip())


def _matches_building(unit_building_name: str, building_name: str) -> bool:
    """
    Case-insensitive partial match with punctuation normalization.
    Handles "100 W. Chestnut" matching "100 W Chestnut".
    """
    unit_norm = _normalize_name(unit_building_name)
    db_norm = _normalize_name(building_name)
    return unit_norm in db_norm or db_norm in unit_norm


def _fetch_all_ppm_units() -> list[dict]:
    """Fetch and parse all PPM units. Run once, filter per building."""
    html = asyncio.run(_fetch_ppm_html())
    return _parse_ppm_html(html)


def scrape(building: Building) -> list[dict]:
    """
    Return units for this PPM building from the shared availability page.

    IMPORTANT: This function calls the PPM availability page every time it is invoked.
    Phase 3 scheduler should call this once per full PPM batch and pass the cached
    result if needed. For now, each individual call fetches the full page.

    Returns list of raw unit dicts (without 'building_name' field) for normalize().
    """
    all_units = _fetch_all_ppm_units()
    matched = [
        {k: v for k, v in unit.items() if k != "building_name"}
        for unit in all_units
        if _matches_building(unit["building_name"], building.name)
    ]
    return matched
