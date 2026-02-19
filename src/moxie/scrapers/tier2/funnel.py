"""
Funnel/Nestio scraper — Tier 2 HTML.

Funnel's REST API (nestiolistings.com/api/v2/) requires per-property API keys
which are not publicly available. This scraper fetches the public listing page HTML
directly and parses unit data with BeautifulSoup.

SELECTOR NOTE: CSS selectors in _parse_html() were written based on common Funnel
listing page patterns. They MUST be verified against a real Funnel building URL
before relying on the output. Run the scraper against a known nestiolistings.com
or funnelleasing.com URL and inspect the output.

Platform: 'funnel'
Coverage: ~15-20 buildings
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
}


class FunnelScraperError(RuntimeError):
    """Raised on HTTP error or failed parse that signals scrape failure."""


def _fetch_html(url: str) -> str:
    """Fetch the listing page HTML. Raises FunnelScraperError on non-2xx."""
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise FunnelScraperError(
            f"Funnel listing page returned HTTP {response.status_code} for {url}"
        )
    return response.text


def _parse_html(html: str) -> list[dict]:
    """
    Parse unit data from Funnel/Nestio listing page HTML.

    SELECTOR VERIFICATION REQUIRED: These selectors are heuristic based on
    common Funnel page structure. Verify against a real building URL.

    Expected Funnel HTML patterns (approximate):
    - Unit rows in elements with class containing 'unit', 'listing', or 'floorplan'
    - Bed type in element with class 'bedrooms' or data-attribute 'beds'
    - Rent in element with class 'price' or 'rent'
    - Availability in element with class 'available' or 'availability'
    - Unit number in element with class 'unit-number' or 'unit'
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    # Strategy 1: Look for structured unit listing elements
    # Adjust selectors based on real page inspection
    for unit_el in soup.select("[class*='unit-listing'], [class*='unit-row'], [class*='floorplan-row']"):
        bed_el = unit_el.select_one("[class*='bed'], [class*='bedroom']")
        rent_el = unit_el.select_one("[class*='price'], [class*='rent']")
        avail_el = unit_el.select_one("[class*='avail'], [class*='available']")
        num_el = unit_el.select_one("[class*='unit-number'], [class*='number']")

        if not (bed_el and rent_el):
            continue  # skip incomplete rows

        unit_number = num_el.get_text(strip=True) if num_el else "N/A"
        rent_text = rent_el.get_text(strip=True)
        bed_text = bed_el.get_text(strip=True)
        avail_text = avail_el.get_text(strip=True) if avail_el else "Available Now"

        if not rent_text or not bed_text:
            continue

        units.append({
            "unit_number": unit_number,
            "bed_type": bed_text,
            "rent": rent_text,
            "availability_date": avail_text,
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a Funnel/Nestio listing page.

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Raises FunnelScraperError on HTTP error (caller should pass scrape_succeeded=False
    to save_scrape_result).
    """
    html = _fetch_html(building.url)
    return _parse_html(html)
