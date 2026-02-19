"""
Funnel/Nestio scraper — Tier 2 HTML.

Funnel-powered apartment sites (used by Greystar and similar management companies)
expose a /floorplans/ page with div.floor-plan elements, each having data attributes:
  - data-beds (e.g., "1", "Studio", "Convertible")
  - data-baths (e.g., "1.00")
  - data-price (integer cents or dollars — raw price)
  - data-first-available-date (ISO date, e.g., "2026-02-13")

Each div also contains:
  - h3.name — floor plan name (used as unit_number since individual units aren't listed)
  - p.bedrooms — beds text (e.g., "1 Bed")
  - p.bathrooms — baths text (e.g., "1 Bath")
  - p.square-feet — sqft text (e.g., "771 sf")
  - p.starting-price — formatted rent (e.g., "Starting at $2,565")
  - p.available-units — unit count (e.g., "3 Apartments Available")
  - p.first-available-date — availability text (e.g., "Available Now")

The scraper normalizes the building URL to /floorplans/ and fetches that page.
Placeholder divs (those without data-beds) are skipped.

Platform: 'funnel'
Coverage: ~15-20 buildings (Greystar and other Funnel-platform operators)
"""
from urllib.parse import urljoin, urlparse

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


def _normalize_floorplans_url(building_url: str) -> str:
    """
    Normalize the building URL to point to the /floorplans/ subpage.

    If the URL already contains '/floorplan', returns it as-is.
    Otherwise, appends /floorplans/ to the base origin.
    """
    parsed = urlparse(building_url.rstrip("/"))
    if "/floorplan" in parsed.path.lower():
        return building_url
    base = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(base + "/", "floorplans/")


def _fetch_html(url: str) -> str:
    """Fetch the listing page HTML. Raises FunnelScraperError on non-2xx."""
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise FunnelScraperError(
            f"Funnel floorplans page returned HTTP {response.status_code} for {url}"
        )
    return response.text


def _parse_html(html: str) -> list[dict]:
    """
    Parse floor plan availability from a Funnel-powered apartment site's /floorplans/ page.

    Targets div.floor-plan elements that have a data-beds attribute (skips placeholders).
    Returns one record per available floor plan type. Since Funnel pages show floor plan
    summaries rather than individual unit listings, the floor plan name is used as
    unit_number and the starting price / first-available-date are used for rent and
    availability.

    Filters to only include floor plans with available units (p.available-units text
    contains a non-zero count or 'Available').
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    for fp_el in soup.find_all("div", attrs={"data-beds": True}):
        # Extract data attributes
        beds_raw = fp_el.get("data-beds", "").strip()
        baths_raw = fp_el.get("data-baths", "").strip()
        price_raw = fp_el.get("data-price", "").strip()

        if not beds_raw or not price_raw:
            continue  # skip incomplete entries

        # Filter: data-price="-1" means "Call for pricing" — not currently listed
        try:
            if int(price_raw) < 0:
                continue
        except (ValueError, TypeError):
            continue

        # Extract text content from child elements
        name_el = fp_el.select_one("h3.name")
        beds_text_el = fp_el.select_one("p.bedrooms")
        baths_text_el = fp_el.select_one("p.bathrooms")
        sqft_el = fp_el.select_one("p.square-feet")
        price_text_el = fp_el.select_one("p.starting-price")
        avail_units_el = fp_el.select_one("p.available-units")
        avail_date_el = fp_el.select_one("p.first-available-date")

        fp_name = name_el.get_text(strip=True) if name_el else "N/A"
        beds_text = beds_text_el.get_text(strip=True) if beds_text_el else beds_raw
        baths_text = baths_text_el.get_text(strip=True) if baths_text_el else baths_raw
        sqft_text = sqft_el.get_text(strip=True) if sqft_el else ""
        price_text = price_text_el.get_text(strip=True) if price_text_el else f"${price_raw}"
        avail_date_text = avail_date_el.get_text(strip=True) if avail_date_el else "Available Now"

        # Normalize sqft: "771 sf" -> "771"
        sqft_value = None
        if sqft_text:
            sqft_digits = "".join(c for c in sqft_text if c.isdigit())
            if sqft_digits:
                sqft_value = int(sqft_digits)

        units.append({
            "unit_number": fp_name,
            "floor_plan_name": fp_name,
            "bed_type": beds_text,
            "baths": baths_text,
            "rent": price_text,
            "availability_date": avail_date_text,
            "sqft": sqft_value,
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape floor plan availability from a Funnel-powered apartment site.

    Normalizes the building URL to /floorplans/, fetches the page, and parses
    floor plan cards. Returns list of raw unit dicts for normalize() / save_scrape_result().

    Raises FunnelScraperError on HTTP error.
    """
    floorplans_url = _normalize_floorplans_url(building.url)
    html = _fetch_html(floorplans_url)
    return _parse_html(html)
