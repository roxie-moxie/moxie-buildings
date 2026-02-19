"""
Bozzuto scraper — Tier 2 HTML.

Bozzuto manages a custom property website platform used across ~13 buildings.
No public API — HTML scraping is required.

Approach: httpx + BeautifulSoup with realistic browser headers.
Upgrade path: If sites return 403 or bot-detection pages, switch to Crawl4AI
(same pattern as groupfox.py). Uncomment the Crawl4AI block in _fetch_html()
and remove the httpx block.

SELECTOR NOTE: Bozzuto listing page HTML structure was not directly inspectable
during research. CSS selectors MUST be verified against a real bozzuto.com
property URL before trusting output. Common Bozzuto patterns include
.available-apartments, .unit-listing, [data-available] attributes.

Platform: 'bozzuto'
Coverage: ~13 buildings
"""
import httpx
from bs4 import BeautifulSoup
from moxie.db.models import Building

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# HTTP status codes that suggest bot detection (should trigger Crawl4AI upgrade)
_BOT_DETECTION_STATUSES = {403, 429, 503}


class BozzutoScraperError(RuntimeError):
    """Raised on HTTP error or bot detection. Signals scrape_succeeded=False."""


def _fetch_html(url: str) -> str:
    """
    Fetch Bozzuto listing page HTML with browser-like headers.

    If a bot-detection status code is received, raises BozzutoScraperError
    with a message recommending Crawl4AI upgrade.

    CRAWL4AI UPGRADE: If httpx consistently returns 403, replace with:
      import asyncio
      from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
      async def _async_fetch(url):
          config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
          async with AsyncWebCrawler() as crawler:
              result = await crawler.arun(url, config=config)
          return result.html or ""
      return asyncio.run(_async_fetch(url))
    """
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        response = client.get(url)

    if response.status_code in _BOT_DETECTION_STATUSES:
        raise BozzutoScraperError(
            f"Bozzuto site returned HTTP {response.status_code} (likely bot detection) "
            f"for {url}. Upgrade _fetch_html() to use Crawl4AI (see inline comment)."
        )
    if response.status_code != 200:
        raise BozzutoScraperError(
            f"Bozzuto listing page returned HTTP {response.status_code} for {url}"
        )
    return response.text


def _parse_html(html: str) -> list[dict]:
    """
    Parse unit data from Bozzuto listing page HTML.

    SELECTOR VERIFICATION REQUIRED: Verify these selectors against a real
    bozzuto.com property URL before production use.

    Common Bozzuto page patterns observed:
    - Unit cards with class 'available-apartment' or 'fp-apartment'
    - Bed type in '.fp-bedrooms', '.bed-count', or '[data-beds]'
    - Rent in '.fp-rent', '.price', or '[data-price]'
    - Unit number in '.fp-unit', '.unit-number'
    - Availability in '.fp-available', '.availability-date'
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    selectors = [
        "[class*='available-apartment']",
        "[class*='fp-apartment']",
        "[class*='unit-card']",
        "[class*='apartment-item']",
    ]

    unit_elements = []
    for sel in selectors:
        unit_elements = soup.select(sel)
        if unit_elements:
            break  # use first selector that matches

    for unit_el in unit_elements:
        bed_el = unit_el.select_one("[class*='bedroom'], [class*='bed'], [data-beds]")
        rent_el = unit_el.select_one("[class*='rent'], [class*='price'], [data-price]")
        avail_el = unit_el.select_one("[class*='avail'], [class*='available'], [class*='move-in']")
        num_el = unit_el.select_one("[class*='unit-number'], [class*='unit-name'], [class*='fp-unit']")

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
    Scrape unit availability from a Bozzuto property page.

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Raises BozzutoScraperError on HTTP error or bot detection.
    """
    html = _fetch_html(building.url)
    return _parse_html(html)
