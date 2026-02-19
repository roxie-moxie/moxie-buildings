"""
AppFolio scraper — Tier 2 HTML.

AppFolio's Stack API requires 50+ units and credentials. This scraper fetches
the public AppFolio listing page (typically {subdomain}.appfolio.com/listings)
and parses available unit data.

SELECTOR NOTE: AppFolio listing pages typically render unit cards with structured
data-attributes or class names. Selectors MUST be verified against a real AppFolio
building URL before relying on output.

Platform: 'appfolio'
Coverage: ~5-10 buildings
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
}


class AppFolioScraperError(RuntimeError):
    """Raised on HTTP error that signals scrape failure."""


def _fetch_html(url: str) -> str:
    """Fetch the AppFolio listing page HTML. Raises AppFolioScraperError on non-2xx."""
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise AppFolioScraperError(
            f"AppFolio listing page returned HTTP {response.status_code} for {url}"
        )
    return response.text


def _parse_html(html: str) -> list[dict]:
    """
    Parse available units from AppFolio listing page HTML.

    SELECTOR VERIFICATION REQUIRED: Common AppFolio listing patterns include
    data attributes like data-unit-type, data-bedrooms, data-price, or
    class names like 'listing-item', 'unit-card', 'available-unit'.
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    # Strategy: Try data-attribute selectors first, then class-based
    for unit_el in soup.select("[class*='listing-item'], [class*='unit-card'], [class*='available-unit']"):
        bed_el = unit_el.select_one("[class*='bedroom'], [class*='bed-count'], [data-bedrooms]")
        rent_el = unit_el.select_one("[class*='price'], [class*='rent'], [class*='rate']")
        avail_el = unit_el.select_one("[class*='avail'], [class*='move-in'], [class*='available']")
        num_el = unit_el.select_one("[class*='unit-number'], [class*='unit-name'], [class*='number']")

        if not (bed_el and rent_el):
            continue

        unit_number = (
            num_el.get("data-unit", num_el.get_text(strip=True))
            if num_el else "N/A"
        )
        units.append({
            "unit_number": unit_number,
            "bed_type": bed_el.get_text(strip=True),
            "rent": rent_el.get_text(strip=True),
            "availability_date": avail_el.get_text(strip=True) if avail_el else "Available Now",
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from an AppFolio public listing page.

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Raises AppFolioScraperError on HTTP error.
    """
    html = _fetch_html(building.url)
    return _parse_html(html)
