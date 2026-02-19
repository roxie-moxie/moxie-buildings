"""
Funnel/Nestio scraper — Tier 2 HTML.

Funnel-powered apartment sites (used by Greystar and similar management companies)
expose a /floorplans/ page with two data sections:

1. **Unit availability table** (preferred): ``table#apartments tr.unit`` rows with
   individual apartment numbers, floor plan names, beds, baths, size, price, and
   availability date.  Data is available as both cell text and ``data-*`` attributes
   on the ``<tr>`` and on the Inquire ``<a>`` button.

2. **Floor plan summary cards** (fallback): ``div.floor-plan`` elements with
   ``data-beds``, ``data-price``, etc.  These show starting prices per floor plan
   type, not individual units.

The scraper normalizes the building URL to /floorplans/, fetches the page, and
tries the unit table first.  If no ``table#apartments`` is found it falls back to
floor plan cards.

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


def _parse_unit_table(soup: BeautifulSoup) -> list[dict] | None:
    """
    Try to parse the individual unit availability table (``table#apartments``).

    Returns a list of unit dicts if the table is found and has rows, or None if
    no table is present (so the caller can fall back to floor plan cards).
    """
    rows = soup.select("table#apartments tr.unit")
    if not rows:
        return None

    units = []
    for row in rows:
        # --- unit number ---
        # Prefer data-apartment from the Inquire button; fall back to td.apt text
        inquire_btn = row.select_one("td.inquire a.button-2")
        if inquire_btn and inquire_btn.get("data-apartment"):
            unit_number = inquire_btn["data-apartment"].strip()
        else:
            apt_td = row.select_one("td.apt")
            unit_number = apt_td.get_text(strip=True).replace("Apt #:", "").strip() if apt_td else "N/A"

        # --- floor plan name ---
        if inquire_btn and inquire_btn.get("data-name"):
            fp_name = inquire_btn["data-name"].strip()
        else:
            plan_td = row.select_one("td.plan")
            fp_name = plan_td.get_text(strip=True).replace("Floor Plan:", "").strip() if plan_td else ""

        # --- beds / baths from <tr> data attrs ---
        beds_raw = row.get("data-beds", "").strip()
        baths_raw = row.get("data-baths", "").strip()

        # Prefer human-readable text from cells
        beds_td = row.select_one("td.beds")
        beds_text = beds_td.get_text(strip=True).replace("Beds:", "").strip() if beds_td else beds_raw
        baths_td = row.select_one("td.baths")
        baths_text = baths_td.get_text(strip=True).replace("Baths:", "").strip() if baths_td else baths_raw

        # --- price ---
        price_raw = row.get("data-price", "").strip()
        price_td = row.select_one("td.price")
        price_text = price_td.get_text(strip=True).replace("Price:", "").strip() if price_td else f"${price_raw}"

        # Skip units with no valid price
        try:
            if price_raw and int(price_raw) < 0:
                continue
        except (ValueError, TypeError):
            pass

        # --- availability date ---
        avail_date_raw = row.get("data-available-date", "").strip()  # YYYY/MM/DD
        avail_td = row.select_one("td.availability")
        avail_text = avail_td.get_text(strip=True).replace("Available:", "").strip() if avail_td else avail_date_raw

        # --- sqft ---
        size_td = row.select_one("td.size")
        sqft_text = size_td.get_text(strip=True).replace("Size:", "").strip() if size_td else ""
        sqft_value = None
        if sqft_text:
            sqft_digits = "".join(c for c in sqft_text if c.isdigit())
            if sqft_digits:
                sqft_value = int(sqft_digits)

        units.append({
            "unit_number": unit_number,
            "floor_plan_name": fp_name,
            "bed_type": beds_text,
            "baths": baths_text,
            "rent": price_text,
            "availability_date": avail_text,
            "sqft": sqft_value,
        })

    return units


def _parse_floorplan_cards(soup: BeautifulSoup) -> list[dict]:
    """
    Fallback: parse floor plan summary cards (``div.floor-plan``).

    Returns one record per available floor plan type.  The floor plan name is
    used as unit_number since individual units aren't listed in this view.
    """
    units = []

    for fp_el in soup.find_all("div", attrs={"data-beds": True}):
        beds_raw = fp_el.get("data-beds", "").strip()
        price_raw = fp_el.get("data-price", "").strip()

        if not beds_raw or not price_raw:
            continue

        try:
            if int(price_raw) < 0:
                continue
        except (ValueError, TypeError):
            continue

        baths_raw = fp_el.get("data-baths", "").strip()
        name_el = fp_el.select_one("h3.name")
        beds_text_el = fp_el.select_one("p.bedrooms")
        baths_text_el = fp_el.select_one("p.bathrooms")
        sqft_el = fp_el.select_one("p.square-feet")
        price_text_el = fp_el.select_one("p.starting-price")
        avail_date_el = fp_el.select_one("p.first-available-date")

        fp_name = name_el.get_text(strip=True) if name_el else "N/A"
        beds_text = beds_text_el.get_text(strip=True) if beds_text_el else beds_raw
        baths_text = baths_text_el.get_text(strip=True) if baths_text_el else baths_raw
        sqft_text = sqft_el.get_text(strip=True) if sqft_el else ""
        price_text = price_text_el.get_text(strip=True) if price_text_el else f"${price_raw}"
        avail_date_text = avail_date_el.get_text(strip=True) if avail_date_el else "Available Now"

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


def _parse_html(html: str) -> list[dict]:
    """
    Parse availability from a Funnel-powered apartment site's /floorplans/ page.

    Tries the individual unit table first (``table#apartments``).  If not present,
    falls back to floor plan summary cards (``div.floor-plan``).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Prefer individual unit rows when available
    units = _parse_unit_table(soup)
    if units is not None:
        return units

    return _parse_floorplan_cards(soup)


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
