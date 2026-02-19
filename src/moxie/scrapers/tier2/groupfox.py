"""
Groupfox scraper — Tier 2 JS-rendered HTML with bot-bypass.

Groupfox returns HTTP 403 to non-browser HTTP clients (confirmed in research).
Crawl4AI with Playwright browser fingerprint bypasses this detection.

Two-step scrape:
1. Fetch ``/floorplans`` index to discover floor plan sub-pages and bed/bath metadata.
2. Follow each sub-page (e.g. ``/floorplans/studio``) to get individual unit rows
   from ``tr.unit-container`` elements with APT#, rent, and availability date.

Floor plans whose button says "Contact Us" (no availability) are skipped.

Platform: 'groupfox'
Coverage: ~12 buildings (verified against axis.groupfox.com 2026-02-19)
"""
import asyncio
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from moxie.db.models import Building


class GroupfoxScraperError(RuntimeError):
    """Raised when Crawl4AI fails or returns empty HTML."""


def _normalize_floorplans_url(building_url: str) -> str:
    """Ensure the URL points to the /floorplans path."""
    parsed = urlparse(building_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith("/floorplans") or "/floorplans/" in path:
        return building_url
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/floorplans"


def _base_url(building_url: str) -> str:
    parsed = urlparse(building_url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _fetch_rendered_html(url: str) -> str:
    """Use Crawl4AI (Playwright browser) to bypass Groupfox bot detection."""
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)
    return result.html or ""


def _parse_floorplan_index(html: str) -> list[dict]:
    """
    Parse the /floorplans index page.  Returns metadata per floor plan:
    ``{'name': str, 'beds': str, 'baths': str, 'href': str}``

    Only includes floor plans with an "Availability" link (skips "Contact Us").
    """
    soup = BeautifulSoup(html, "html.parser")
    plans = []

    for card in soup.select("div.card.text-center"):
        # Floor plan name
        title_el = card.select_one("h2.card-title")
        name = title_el.get_text(strip=True) if title_el else None
        if not name:
            continue

        # Bed/bath from list-inline items
        items = card.select("ul.list-inline li.list-inline-item")
        beds = ""
        baths = ""
        for item in items:
            text = item.get_text(strip=True)
            if "Bed" in text or "Studio" in text:
                beds = text
            elif "Bath" in text:
                baths = text

        # Availability link (skip "Contact Us")
        btn = card.select_one("a.floorplan-action-button")
        if not btn:
            continue
        btn_text = btn.get_text(strip=True)
        if "Contact" in btn_text:
            continue  # no availability
        href = btn.get("href", "")
        if not href or href.startswith("#"):
            continue

        plans.append({"name": name, "beds": beds, "baths": baths, "href": href})

    return plans


def _parse_unit_rows(html: str, fp_name: str, beds: str, baths: str) -> list[dict]:
    """
    Parse individual unit rows from a floor plan sub-page.

    Each ``tr.unit-container`` has:
    - ``td.td-card-name``: "Apartment:#NNNN"
    - ``td.td-card-rent``: "Rent:$X,XXX"
    - ``td.td-card-available``: "Date:M/D/YYYY"
    """
    soup = BeautifulSoup(html, "html.parser")
    units = []

    for row in soup.select("tr.unit-container"):
        name_td = row.select_one("td.td-card-name")
        rent_td = row.select_one("td.td-card-rent")
        avail_td = row.select_one("td.td-card-available")

        unit_number = "N/A"
        if name_td:
            text = name_td.get_text(strip=True)
            # Extract number after # — e.g. "Apartment:#4414307"
            m = re.search(r"#(\S+)", text)
            unit_number = m.group(1) if m else text.replace("Apartment:", "").strip()

        rent = "N/A"
        if rent_td:
            rent = rent_td.get_text(strip=True).replace("Rent:", "").strip()

        avail = "Available Now"
        if avail_td:
            avail = avail_td.get_text(strip=True).replace("Date:", "").strip()

        units.append({
            "unit_number": unit_number,
            "floor_plan_name": fp_name,
            "bed_type": beds,
            "baths": baths,
            "rent": rent,
            "availability_date": avail,
        })

    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a Groupfox site.

    1. Fetches /floorplans to discover floor plan sub-pages.
    2. Follows each sub-page to collect individual unit rows.
    """
    base = _base_url(building.url)
    floorplans_url = _normalize_floorplans_url(building.url)

    index_html = asyncio.run(_fetch_rendered_html(floorplans_url))
    if not index_html:
        raise GroupfoxScraperError(
            f"Crawl4AI returned empty HTML for Groupfox building: {floorplans_url}"
        )

    plans = _parse_floorplan_index(index_html)
    if not plans:
        return []

    all_units: list[dict] = []
    for fp in plans:
        sub_url = urljoin(base, fp["href"])
        sub_html = asyncio.run(_fetch_rendered_html(sub_url))
        if not sub_html:
            continue
        units = _parse_unit_rows(sub_html, fp["name"], fp["beds"], fp["baths"])
        all_units.extend(units)

    return all_units
