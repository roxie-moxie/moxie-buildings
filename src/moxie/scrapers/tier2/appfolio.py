"""
AppFolio scraper — Tier 2 HTML.

Two discovery modes:

1. **Subdomain mode** (recommended for Sedgwick Properties buildings):
   - ``building.rentcafe_api_token`` stores the AppFolio subdomain
     (e.g. ``sedgwickproperties``)
   - ``building.rentcafe_property_id`` stores an address keyword to filter
     results to this building (e.g. ``1325 N Wells``)
   - Fetches ``https://{subdomain}.appfolio.com/listings`` and returns only
     units whose address contains the filter string.

2. **Direct URL mode**: The building's URL is already the AppFolio listings
   page (e.g. sedgwickproperties.appfolio.com/listings).
   Fetches the page directly.  No address filter is applied unless
   ``building.rentcafe_property_id`` is set.

AppFolio listing cards use these CSS selectors (verified against
sedgwickproperties.appfolio.com/listings on 2026-02-20):
  - Container: .js-listing-item
  - Unit number: img[alt] → extract "Unit NNN" from address alt text
  - Price: first .detail-box__value containing "$"
  - Bed/bath: .detail-box__value containing 'bd' or 'ba'
  - Availability: .js-listing-available

Platform: 'appfolio'
Coverage: ~5-10 buildings (Sedgwick Properties confirmed working)
"""
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

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
    """Fetch an AppFolio page HTML. Raises AppFolioScraperError on non-2xx."""
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise AppFolioScraperError(
            f"AppFolio page returned HTTP {response.status_code} for {url}"
        )
    return response.text


def _parse_listings_html(html: str, address_filter: str | None = None) -> list[dict]:
    """
    Parse AppFolio listings page HTML into unit dicts.

    The listings page (e.g. sedgwickproperties.appfolio.com/listings) shows
    all properties managed by that company.  Each card has:
    - img[alt]: full address including "Unit NNN"
    - .detail-box__value: price, sqft, beds/baths, availability

    If ``address_filter`` is provided (e.g. "1325 N Wells"), only cards whose
    address contains that string (case-insensitive) are included.
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    for card in soup.select(".js-listing-item"):
        # Extract unit number and address from the image alt text
        img = card.select_one("img")
        alt = img.get("alt", "") if img else ""

        # Alt text format: "1552 N North Park Ave , Unit 201, Chicago, IL 60610"
        unit_match = re.search(r"Unit\s+(\w+)", alt)
        unit_number = unit_match.group(1) if unit_match else None

        # Address is everything before ", Unit" or ", Chicago"
        addr_match = re.search(r"^(.+?)(?:\s*,\s*Unit|\s*,\s*Chicago)", alt)
        address = addr_match.group(1).strip() if addr_match else alt.split(",")[0].strip()

        # Apply address filter
        if address_filter and address_filter.lower() not in address.lower():
            continue

        if not unit_number:
            continue

        # Extract detail values (price, sqft, beds/baths, availability)
        detail_values = [d.get_text(strip=True) for d in card.select(".detail-box__value")]

        # Price is the first dollar-containing value
        price = next(
            (v for v in detail_values if "$" in v),
            "N/A",
        )

        # Beds/baths is the value containing "bd" or "ba"
        bed_bath = next(
            (v for v in detail_values if "bd" in v.lower() or "ba" in v.lower()),
            "N/A",
        )

        # Availability date
        avail_el = card.select_one(".js-listing-available")
        avail_text = avail_el.get_text(strip=True) if avail_el else "Available Now"
        if avail_text.upper() == "NOW":
            avail_text = "Available Now"

        units.append({
            "unit_number": unit_number,
            "bed_type": bed_bath,
            "rent": price,
            "availability_date": avail_text,
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from an AppFolio listing page.

    Two paths:
    1. Subdomain mode: ``building.rentcafe_api_token`` holds the AppFolio
       subdomain (e.g. ``sedgwickproperties``).  Builds the listings URL as
       ``https://{subdomain}.appfolio.com/listings`` and filters results by
       ``building.rentcafe_property_id`` (street address keyword).

    2. Direct URL mode: ``building.url`` already points to an AppFolio
       listings page (contains ``appfolio.com``).

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Raises AppFolioScraperError on HTTP error or missing configuration.
    """
    address_filter = building.rentcafe_property_id or None

    if building.rentcafe_api_token:
        # Subdomain mode: build listings URL from stored subdomain
        subdomain = building.rentcafe_api_token.strip()
        listings_url = f"https://{subdomain}.appfolio.com/listings"
    elif "appfolio.com" in (building.url or ""):
        # Direct URL mode
        listings_url = building.url
    else:
        raise AppFolioScraperError(
            f"AppFolio scraper: no subdomain configured for {building.name}. "
            "Set building.rentcafe_api_token to the AppFolio subdomain "
            "(e.g. 'sedgwickproperties') and building.rentcafe_property_id "
            "to the building's street address for filtering."
        )

    html = _fetch_html(listings_url)
    return _parse_listings_html(html, address_filter=address_filter)
