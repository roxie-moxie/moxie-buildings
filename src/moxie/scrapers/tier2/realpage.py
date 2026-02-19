"""
RealPage/G5 scraper — Tier 2 JS-rendered HTML.

RealPage is the underlying platform for several management groups.
G5 (g5searchmarketing.com) is RealPage's marketing CMS — unit data is
typically embedded in JS-rendered widgets.

Approach: Crawl4AI AsyncWebCrawler renders the page, BeautifulSoup parses the HTML.

SELECTOR NOTE: RealPage listing structures vary by property configuration.
Common patterns include data-unit attributes, .available-unit elements, and
structured JSON-LD on the page. Selectors MUST be verified against real URLs.

Platform: 'realpage'
Coverage: ~10-15 buildings
"""
import asyncio
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from moxie.db.models import Building


class RealPageScraperError(RuntimeError):
    """Raised when Crawl4AI fails to render or returns empty HTML."""


async def _fetch_rendered_html(url: str) -> str:
    """Use Crawl4AI to fetch and JS-render the RealPage listing page."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)
    return result.html or ""


def _parse_html(html: str) -> list[dict]:
    """
    Parse unit data from rendered RealPage/G5 listing HTML.

    SELECTOR VERIFICATION REQUIRED: Verify against real realpage.com and
    g5searchmarketing.com property URLs.

    Common RealPage patterns:
    - .floorplan-item, .available-unit, [data-unit-type]
    - .unit-number in data-unit or text node
    - .unit-price, .unit-rent
    - .unit-beds, [data-beds]
    - .unit-availability, [data-available]
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    for unit_el in soup.select(
        "[class*='available-unit'], [class*='floorplan-item'], [class*='unit-row']"
    ):
        bed_el = unit_el.select_one("[class*='bed'], [data-beds], [class*='bedroom']")
        rent_el = unit_el.select_one("[class*='price'], [class*='rent'], [data-price]")
        avail_el = unit_el.select_one("[class*='avail'], [class*='available'], [data-available]")
        num_el = unit_el.select_one("[class*='unit-number'], [data-unit], [class*='number']")

        if not (bed_el and rent_el):
            continue

        units.append({
            "unit_number": num_el.get_text(strip=True) if num_el else "N/A",
            "bed_type": bed_el.get_text(strip=True),
            "rent": rent_el.get_text(strip=True),
            "availability_date": avail_el.get_text(strip=True) if avail_el else "Available Now",
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a RealPage/G5 listing page.

    Uses Crawl4AI for JS rendering. Raises RealPageScraperError if
    rendering fails or returns empty HTML.
    """
    html = asyncio.run(_fetch_rendered_html(building.url))
    if not html:
        raise RealPageScraperError(
            f"Crawl4AI returned empty HTML for RealPage building: {building.url}"
        )
    return _parse_html(html)
