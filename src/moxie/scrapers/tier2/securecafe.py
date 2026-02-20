"""
SecureCafe scraper — Tier 2 JS-rendered HTML with Crawl4AI.

SecureCafe (securecafe.com) is a leasing portal used by many RentCafe buildings.
Marketing sites link to ``{subdomain}.securecafe.com/onlineleasing/{path}/``.
The ``availableunits.aspx`` page lists units grouped by floor plan in HTML tables.

Discovery: render the building's marketing site with Crawl4AI, extract the
``securecafe.com/onlineleasing/`` URL, then replace the page with
``availableunits.aspx``.

Platform: 'rentcafe' (reuses existing platform classification)
Coverage: ~218 RentCafe buildings with SecureCafe leasing portals
"""
import asyncio
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from moxie.db.models import Building


class SecureCafeScraperError(RuntimeError):
    """Raised on discovery or fetch failure."""


async def _fetch_rendered_html(url: str) -> str:
    """Use Crawl4AI (Playwright browser) to render JS-heavy pages."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)
    return result.html or ""


def _discover_securecafe_url(html: str) -> str | None:
    """Extract the SecureCafe onlineleasing base URL from rendered HTML.

    Looks for links matching:
      ``https://{subdomain}.securecafe.com/onlineleasing/{path}/...``

    Returns the base path up to and including the property slug, e.g.:
      ``https://8easthuron.securecafe.com/onlineleasing/8-east-huron``
    """
    matches = re.findall(
        r"https?://[a-z0-9.-]+\.securecafe\.com/onlineleasing/([^/]+)",
        html,
        re.IGNORECASE,
    )
    if not matches:
        return None

    # Find the full URL for the first match
    full = re.search(
        r"(https?://[a-z0-9.-]+\.securecafe\.com/onlineleasing/[^/]+)",
        html,
        re.IGNORECASE,
    )
    return full.group(1) if full else None


def _parse_available_units(html: str) -> list[dict]:
    """Parse the availableunits.aspx page for unit data.

    Uses two data sources:
      1. ``tr.AvailUnitRow`` elements with ``data-label`` cells for sqft, rent.
      2. ``ApplyNowClick(...)`` in the Select button's onclick for the availability date.
         Format: ``ApplyNowClick("unitId","fpId","propId","M/D/YYYY",...)``

    Floor plan bed/bath comes from section headers:
      "Apartment Details and Selection for Floor Plan: 1 Bed / 1 Bath - ..."
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.availableunits")
    if not container:
        return []

    # Build a map of floor plan bed/bath from section headers
    # Each table.availableUnits has a caption with the floor plan info
    table_fp: dict[str, dict] = {}  # table id -> {beds, baths, fp_name}
    for caption in container.select("caption"):
        text = caption.get_text(strip=True)
        fp_match = re.search(r"Floor Plan:\s*(.+?)(?:\s*-\s*|\s*$)", text)
        fp_name = fp_match.group(1).strip() if fp_match else ""

        bed_match = re.search(r"(\d+)\s*Bed", text)
        bath_match = re.search(r"([\d.]+)\s*Bath", text)
        studio_match = re.search(r"Studio", text, re.IGNORECASE)

        beds = "Studio" if studio_match else ""
        if not studio_match and bed_match:
            beds = f"{bed_match.group(1)}BR" if bed_match.group(1) != "1" else "1BR"
        baths = bath_match.group(1) if bath_match else ""

        table = caption.parent
        if table:
            table_fp[id(table)] = {"beds": beds, "baths": baths, "fp_name": fp_name}

    units: list[dict] = []

    for row in container.select("tr.AvailUnitRow"):
        # Unit number from th or td with data-label="Apartment"
        apt_cell = row.find(attrs={"data-label": "Apartment"})
        if not apt_cell:
            apt_cell = row.find("th")
        if not apt_cell:
            continue

        apt_text = apt_cell.get_text(strip=True)
        # Some templates use "#buildingId-unitNum" (e.g. "#1435-406"),
        # others use plain "#unitNum" (e.g. "#512").
        apt_match = re.search(r"#\d+-(\w+)", apt_text) or re.search(r"#(\w+)", apt_text)
        if not apt_match:
            continue
        unit_number = apt_match.group(1)

        # SqFt from data-label="Sq.Ft."
        sqft_cell = row.find(attrs={"data-label": "Sq.Ft."})
        sqft = None
        if sqft_cell:
            sqft_text = sqft_cell.get_text(strip=True).replace(",", "")
            if sqft_text.isdigit():
                sqft = int(sqft_text)

        # Rent from data-label="Rent"
        rent_cell = row.find(attrs={"data-label": "Rent"})
        rent = "N/A"
        if rent_cell:
            rent = rent_cell.get_text(strip=True)

        # Date Available: check data-label="Date Available" cell first
        avail = "Available Now"
        date_cell = row.find(attrs={"data-label": "Date Available"})
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            if re.search(r"\d+/\d+/\d+", date_text):
                avail = date_text
            elif date_text.lower() in ("available", "available now", ""):
                avail = "Available Now"

        # Fallback: extract date from ApplyNowClick button onclick
        if avail == "Available Now":
            select_btn = row.find(attrs={"class": "UnitSelect"})
            if select_btn:
                onclick = select_btn.get("onclick", "")
                date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", onclick)
                if date_match:
                    date_str = date_match.group(1)
                    # 12/31/9999 = no date / available now
                    if date_str != "12/31/9999":
                        avail = date_str

        # Bed/bath from parent table's caption
        table = row.find_parent("table")
        fp_info = table_fp.get(id(table), {}) if table else {}
        bed_type = fp_info.get("beds", "")
        baths = fp_info.get("baths", "")
        fp_name = fp_info.get("fp_name", "")

        units.append({
            "unit_number": unit_number,
            "floor_plan_name": fp_name,
            "bed_type": bed_type,
            "baths": baths,
            "sqft": sqft,
            "rent": rent,
            "availability_date": avail,
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a SecureCafe-powered building.

    1. Renders the marketing site (and subpages) to discover the SecureCafe URL.
    2. Constructs and fetches the availableunits.aspx page.
    3. Parses floor plan sections and unit rows from rendered HTML.
    """
    # Step 1: Discover SecureCafe URL from marketing site.
    # Try homepage first, then common floor plan subpages — some buildings only
    # link to SecureCafe from their floorplans/floor-plans page.
    base_url: str | None = None
    base_site = building.url.rstrip("/")
    candidate_urls = [
        building.url,
        f"{base_site}/floorplans",
        f"{base_site}/floor-plans",
    ]

    for candidate in candidate_urls:
        marketing_html = asyncio.run(_fetch_rendered_html(candidate))
        if not marketing_html:
            continue
        base_url = _discover_securecafe_url(marketing_html)
        if base_url:
            break

    if not base_url:
        raise SecureCafeScraperError(
            f"No SecureCafe URL found on {building.url} or its floorplans subpages"
        )

    # Step 2: Construct and fetch availableunits page
    available_url = f"{base_url}/availableunits.aspx"
    units_html = asyncio.run(_fetch_rendered_html(available_url))
    if not units_html:
        raise SecureCafeScraperError(
            f"Crawl4AI returned empty HTML for {available_url}"
        )

    # Step 3: Parse units
    return _parse_available_units(units_html)
