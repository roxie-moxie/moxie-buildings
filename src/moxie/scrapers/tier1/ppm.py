"""
PPM Apartments scraper — Tier 1 single-page availability.

PPM publishes all units for all buildings on one page:
https://ppmapartments.com/availability/

The page is JavaScript-rendered — unit rows are injected by JS after load.
Crawl4AI (AsyncWebCrawler) renders the page, then BeautifulSoup parses the HTML.

Design: Call the page ONCE per scraper run, cache in memory, filter per building.
Do NOT call the page once per building (18 buildings x 1 call = wasteful).

Platform: 'ppm'
Coverage: ~18 buildings
"""
import asyncio
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from moxie.db.models import Building

PPM_URL = "https://ppmapartments.com/availability/"

# Table column indices (0-based) from the confirmed PPM table structure:
# Neighborhood | Building | Unit | Availability | Unit Type | Floorplan | Features | Price
_COL_BUILDING = 1
_COL_UNIT = 2
_COL_AVAILABILITY = 3
_COL_UNIT_TYPE = 4
_COL_FLOORPLAN = 5
_COL_PRICE = 7


async def _fetch_ppm_html() -> str:
    """Fetch and JS-render the PPM availability page. Returns full rendered HTML."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(PPM_URL, config=config)
    return result.html or ""


def _parse_ppm_html(html: str) -> list[dict]:
    """
    Parse the PPM availability table from rendered HTML.
    Returns a list of raw unit dicts (with 'building_name' field for filtering).
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []
    # Find all table rows; skip header rows (th cells only)
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 8:
            continue  # header row or empty row
        unit_type = cells[_COL_UNIT_TYPE].get_text(strip=True)
        if not unit_type:
            continue  # skip rows without unit type data
        units.append({
            "building_name": cells[_COL_BUILDING].get_text(strip=True),
            "unit_number": cells[_COL_UNIT].get_text(strip=True),
            "availability_date": cells[_COL_AVAILABILITY].get_text(strip=True) or "Available Now",
            "bed_type": unit_type,
            "floor_plan_name": cells[_COL_FLOORPLAN].get_text(strip=True) or None,
            "rent": cells[_COL_PRICE].get_text(strip=True),
        })
    return units


def _matches_building(unit_building_name: str, building_name: str) -> bool:
    """
    Case-insensitive partial match: does the unit's building name contain
    (or is contained by) the DB building name?

    Handles cases where PPM uses "Streeterville Tower" but DB has "PPM - Streeterville Tower"
    or vice versa.
    """
    unit_lower = unit_building_name.lower().strip()
    db_lower = building_name.lower().strip()
    return unit_lower in db_lower or db_lower in unit_lower


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
