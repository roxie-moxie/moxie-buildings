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

    Structure:
      - Floor plan sections with header like
        "Apartment Details and Selection for Floor Plan: 1 Bed / 1 Bath - ..."
      - Within each section: a table with columns
        Apartment | Sq.Ft. | Rent | Date Available | Action
      - Unit rows contain: #NNNN | sqft | $X,XXX | date or "Available"
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.availableunits")
    if not container:
        return []

    units: list[dict] = []
    current_beds = ""
    current_baths = ""
    current_fp_name = ""

    # Walk through text content to find floor plan headers and unit data
    # The page has sections like:
    #   "Floor Plan : X Bed / Y Bath - ..."
    #   followed by table rows with unit data
    for section_header in container.find_all(string=re.compile(r"Apartment Details and Selection for Floor Plan:")):
        header_text = section_header.strip()
        # Extract bed/bath from header
        # Format: "... Floor Plan: 1 Bed / 1 Bath - 1 Bedroom, 1 Bathroom"
        # or "... Floor Plan: 2 Bed / 2.5 Bath - ..."
        fp_match = re.search(
            r"Floor Plan:\s*(.+?)(?:\s*-\s*|\s*$)", header_text
        )
        if fp_match:
            current_fp_name = fp_match.group(1).strip()

        bed_match = re.search(r"(\d+)\s*Bed", header_text)
        bath_match = re.search(r"([\d.]+)\s*Bath", header_text)
        studio_match = re.search(r"Studio", header_text, re.IGNORECASE)

        if studio_match:
            current_beds = "Studio"
        elif bed_match:
            current_beds = f"{bed_match.group(1)}BR" if bed_match.group(1) != "1" else "1BR"
        current_baths = bath_match.group(1) if bath_match else ""

        # Find the parent element and look for the unit table within it
        parent = section_header.parent
        while parent and parent.name not in ("div", "section", "fieldset"):
            parent = parent.parent

        if not parent:
            continue

        # Find unit rows — look for apartment numbers (#NNNN)
        for apt_el in parent.find_all(string=re.compile(r"#\w+")):
            apt_text = apt_el.strip()
            apt_match = re.search(r"#(\w+)", apt_text)
            if not apt_match:
                continue

            unit_number = apt_match.group(1)

            # Navigate to sibling cells to get sqft, rent, date
            # The data follows the unit number in subsequent text nodes/elements
            row = apt_el.parent
            while row and row.name not in ("tr", "div", "li"):
                row = row.parent

            if not row:
                continue

            row_text = row.get_text(separator="|", strip=True)
            parts = [p.strip() for p in row_text.split("|") if p.strip()]

            sqft = None
            rent = "N/A"
            avail = "Available Now"

            for part in parts:
                # Skip the apartment number itself
                if part.startswith("#"):
                    continue
                # Rent: starts with $ or contains digits with $
                if "$" in part:
                    rent = part
                # SqFt: pure number (3-5 digits)
                elif re.match(r"^\d{3,5}$", part):
                    sqft = int(part)
                # Date: contains / (like 4/5/2026)
                elif re.search(r"\d+/\d+/\d+", part):
                    avail = part
                # "Available" text
                elif part.lower() in ("available", "available now"):
                    avail = "Available Now"

            units.append({
                "unit_number": unit_number,
                "floor_plan_name": current_fp_name,
                "bed_type": current_beds,
                "baths": current_baths,
                "sqft": sqft,
                "rent": rent,
                "availability_date": avail,
            })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a SecureCafe-powered building.

    1. Renders the marketing site to discover the SecureCafe URL.
    2. Constructs and fetches the availableunits.aspx page.
    3. Parses floor plan sections and unit rows from rendered HTML.
    """
    # Step 1: Discover SecureCafe URL from marketing site
    marketing_html = asyncio.run(_fetch_rendered_html(building.url))
    if not marketing_html:
        raise SecureCafeScraperError(
            f"Crawl4AI returned empty HTML for {building.url}"
        )

    base_url = _discover_securecafe_url(marketing_html)
    if not base_url:
        raise SecureCafeScraperError(
            f"No SecureCafe URL found on {building.url}"
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
