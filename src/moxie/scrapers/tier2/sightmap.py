"""
SightMap scraper — Tier 2 JSON API.

SightMap (sightmap.com) is a third-party interactive unit map widget embedded
via iframe on apartment websites.  The embed page contains a
``window.__APP_CONFIG__`` object with an API URL pointing to
``sightmap.com/app/api/v1/.../sightmaps/NNNN``.  That endpoint returns a JSON
payload with all available units, floor plans, and floor metadata.

Discovery: scrape the building's marketing site, look for a
``sightmap.com/embed/<ID>`` iframe src, then resolve the API URL from the embed
page's ``__APP_CONFIG__``.

Platform: 'sightmap'
Coverage: ~10 buildings (AMLI, LUXE, EMME, Trio, Next — verified 2026-02-19)
"""
import json
import re

import httpx

from moxie.db.models import Building

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class SightMapScraperError(RuntimeError):
    """Raised on HTTP error or missing SightMap configuration."""


def _extract_embed_id(building_url: str) -> str:
    """Fetch the building's marketing site and extract the SightMap embed ID.

    Checks the root URL first, then common subpages where the map widget
    is typically embedded (``/floorplans``, ``/floor-plans``, ``/availability``).
    """
    from urllib.parse import urlparse, urljoin

    parsed = urlparse(building_url.rstrip("/"))
    base = f"{parsed.scheme}://{parsed.netloc}"
    urls_to_try = [building_url]
    for subpath in ["/floorplans", "/floorplans/", "/floor-plans", "/availability", "/sightmap"]:
        candidate = urljoin(base + "/", subpath.lstrip("/"))
        if candidate not in urls_to_try:
            urls_to_try.append(candidate)

    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        for url in urls_to_try:
            try:
                r = client.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code != 200:
                continue
            # Exclude the loader script sightmap.com/embed/api.js — we want the embed ID
            match = re.search(r"sightmap\.com/embed/(?!api(?:\.js)?)([a-z0-9]+)", r.text, re.IGNORECASE)
            if match:
                return match.group(1)

    raise SightMapScraperError(
        f"No SightMap embed found on {building_url} (checked {len(urls_to_try)} pages)"
    )


def _resolve_api_url(embed_id: str) -> str:
    """Fetch the SightMap embed page and extract the API URL from __APP_CONFIG__."""
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        r = client.get(f"https://sightmap.com/embed/{embed_id}")
    if r.status_code != 200:
        raise SightMapScraperError(
            f"SightMap embed page returned HTTP {r.status_code} for embed ID {embed_id}"
        )
    idx = r.text.find("__APP_CONFIG__")
    if idx < 0:
        raise SightMapScraperError(
            f"No __APP_CONFIG__ found in SightMap embed page for {embed_id}"
        )
    eq_idx = r.text.index("=", idx)
    json_start = r.text.index("{", eq_idx)
    depth = 0
    for i in range(json_start, len(r.text)):
        if r.text[i] == "{":
            depth += 1
        elif r.text[i] == "}":
            depth -= 1
            if depth == 0:
                config = json.loads(r.text[json_start : i + 1])
                return config["sightmaps"][0]["href"]
    raise SightMapScraperError(
        f"Failed to parse __APP_CONFIG__ JSON for embed ID {embed_id}"
    )


def _fetch_units(api_url: str) -> list[dict]:
    """Call the SightMap API and return raw unit dicts."""
    with httpx.Client(timeout=30.0, headers=_HEADERS) as client:
        r = client.get(api_url)
    if r.status_code != 200:
        raise SightMapScraperError(
            f"SightMap API returned HTTP {r.status_code} for {api_url}"
        )
    data = r.json()["data"]
    floor_plans = {fp["id"]: fp for fp in data.get("floor_plans", [])}

    units = []
    for u in data.get("units", []):
        fp = floor_plans.get(u.get("floor_plan_id"), {})
        area = u.get("area")
        # Skip placeholder units (e.g. floor plan "TEMP" with area=1)
        if area is not None and area <= 1:
            continue
        units.append({
            "unit_number": u.get("unit_number", "N/A"),
            "floor_plan_name": fp.get("name", ""),
            "bed_type": fp.get("bedroom_label", ""),
            "baths": fp.get("bathroom_label", ""),
            "sqft": area,
            "rent": f"${u['price']}" if u.get("price") else "N/A",
            "availability_date": u.get("display_available_on", "Available Now"),
        })
    return units


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability from a SightMap-powered building.

    1. Fetches the building's marketing site to find the SightMap embed ID.
    2. Resolves the SightMap API URL from the embed page.
    3. Fetches unit data from the JSON API.
    """
    embed_id = _extract_embed_id(building.url)
    api_url = _resolve_api_url(embed_id)
    return _fetch_units(api_url)
