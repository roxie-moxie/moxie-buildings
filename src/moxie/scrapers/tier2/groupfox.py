"""
Groupfox scraper — Tier 2 JS-rendered HTML with bot-bypass.

Groupfox returns HTTP 403 to non-browser HTTP clients (confirmed in research).
Crawl4AI with Playwright browser fingerprint bypasses this detection.

URL pattern: {subdomain}.groupfox.com/floorplans
This scraper normalizes the building URL to always point to /floorplans.

SELECTOR NOTE: Groupfox floorplan pages expose unit listings per floorplan category.
URL paths like /floorplans/studio, /floorplans/one-bedroom may exist.
The main /floorplans page typically lists all floorplans with unit counts.
Selectors MUST be verified against a real Groupfox building URL.

Platform: 'groupfox'
Coverage: ~12 buildings
"""
import asyncio
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from moxie.db.models import Building


class GroupfoxScraperError(RuntimeError):
    """Raised when Crawl4AI fails or returns empty HTML."""


def _normalize_floorplans_url(building_url: str) -> str:
    """
    Ensure the URL points to the /floorplans path.
    If url already ends with /floorplans or /floorplans/, return as-is.
    Otherwise, append /floorplans to the base URL.
    """
    parsed = urlparse(building_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith("/floorplans") or "/floorplans/" in path:
        return building_url
    # Construct floorplans URL: scheme://netloc/floorplans
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/floorplans"


async def _fetch_rendered_html(url: str) -> str:
    """Use Crawl4AI (Playwright browser) to bypass Groupfox bot detection."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)
    return result.html or ""


def _parse_html(html: str) -> list[dict]:
    """
    Parse unit data from Groupfox /floorplans page.

    SELECTOR VERIFICATION REQUIRED: Verify against a real Groupfox subdomain URL.

    Groupfox /floorplans patterns (approximate):
    - Floorplan cards: .floorplan-card, .floorplan-item
    - Bed count: .fp-beds, [data-beds], .bedrooms
    - Rent: .fp-rent, .price, [data-price]
    - Unit number: may be per-floorplan availability count, not individual unit numbers
    - Availability: 'Available Now', date, or 'Available [count] units'
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    for fp_el in soup.select(
        "[class*='floorplan-card'], [class*='floorplan-item'], [class*='floor-plan']"
    ):
        bed_el = fp_el.select_one("[class*='bed'], [data-beds], [class*='bedroom']")
        rent_el = fp_el.select_one("[class*='rent'], [class*='price'], [data-price]")
        name_el = fp_el.select_one("[class*='fp-name'], [class*='floorplan-name'], h3, h4")
        avail_el = fp_el.select_one("[class*='avail'], [class*='available']")

        if not (bed_el and rent_el):
            continue

        # Groupfox may list floorplans rather than individual units;
        # use floorplan name as unit_number if no unit number is present
        fp_name = name_el.get_text(strip=True) if name_el else "N/A"
        units.append({
            "unit_number": fp_name,
            "floor_plan_name": fp_name,
            "bed_type": bed_el.get_text(strip=True),
            "rent": rent_el.get_text(strip=True),
            "availability_date": avail_el.get_text(strip=True) if avail_el else "Available Now",
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a Groupfox /floorplans page.

    Normalizes URL to /floorplans, uses Crawl4AI to bypass bot detection,
    parses with BeautifulSoup.
    """
    floorplans_url = _normalize_floorplans_url(building.url)
    html = asyncio.run(_fetch_rendered_html(floorplans_url))
    if not html:
        raise GroupfoxScraperError(
            f"Crawl4AI returned empty HTML for Groupfox building: {floorplans_url}"
        )
    return _parse_html(html)
