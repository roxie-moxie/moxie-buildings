#!/usr/bin/env python
"""
Automated RentCafe credential extraction.

For every building with platform='rentcafe', fetches the building's page using
Crawl4AI (JS-rendered, bypasses 403), searches the rendered HTML for embedded
apiToken and VoyagerPropertyCode, and writes them to the DB.

Architecture note (discovered 2026-02-19):
  - VoyagerPropertyCode = securecafe.com subdomain (e.g. "fisherbuildingchicago")
    Reliably extractable from the building homepage HTML.
  - apiToken = server-side only. RentCafe's platform calls api.rentcafe.com
    server-to-server; the token never appears in any client-side resource.
    The floor plans page is Cloudflare-protected for headless browsers.
    apiToken must be captured manually via DevTools (one per management company).

This script extracts VoyagerPropertyCode for all rentcafe buildings.
For apiToken, see the DevTools instructions printed for each building.

Usage:
    uv run python scripts/extract_rentcafe_credentials.py
    uv run python scripts/extract_rentcafe_credentials.py --dry-run
    uv run python scripts/extract_rentcafe_credentials.py --building "Fisher Building"
    uv run python scripts/extract_rentcafe_credentials.py --force
    uv run python scripts/extract_rentcafe_credentials.py --concurrency 3

Flags:
    --dry-run       Print what would be written without touching the DB
    --force         Re-extract even for buildings that already have credentials
    --building NAME Process only buildings whose name matches (case-insensitive)
    --concurrency N Max concurrent page fetches (default: 5)

DB columns written:
    rentcafe_property_id  ← VoyagerPropertyCode (e.g. "dey", "grandcentral")
    rentcafe_api_token    ← apiToken (UUID-like string)
"""
import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

# Make moxie importable when run as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright, BrowserContext, Page

from moxie.db.models import Building
from moxie.db.session import SessionLocal


# ---------------------------------------------------------------------------
# Extraction logic — Playwright network request interception
# ---------------------------------------------------------------------------
# The RentCafe unit listing widget loads credentials from a property-specific
# CDN bundle (cdngeneralmvc.rentcafe.com/ysi.bsn.*.js, 403 on direct fetch)
# and then fires an XHR/fetch to:
#   api.rentcafe.com/rentcafeapi.aspx?requestType=apartmentavailability
#       &VoyagerPropertyCode=CODE&apiToken=TOKEN&...
#
# HTML scraping cannot capture this — the credentials only exist as request
# parameters in the live network call. Playwright request interception is the
# only reliable extraction method.
# ---------------------------------------------------------------------------

_RENTCAFE_API_HOST = "api.rentcafe.com"

# Availability-page link scoring (for pass 2 fallback)
_AVAILABILITY_KEYWORDS: frozenset[str] = frozenset({
    "floor", "floorplan", "floor-plan", "availab", "apartment",
    "units", "rent", "leasing", "pricing", "search", "listing",
})
_SKIP_KEYWORDS: frozenset[str] = frozenset({
    "blog", "news", "gallery", "photo", "contact", "about",
    "team", "careers", "press", "event", "social", "privacy",
    "terms", "sitemap", "login", "register", "resident",
})


def _score_link(href: str, text: str) -> int:
    combined = (href + " " + text).lower()
    if any(s in combined for s in _SKIP_KEYWORDS):
        return 0
    return sum(1 for kw in _AVAILABILITY_KEYWORDS if kw in combined)


def _parse_credentials(request_url: str) -> tuple[str | None, str | None]:
    """Extract (api_token, voyager_code) from a rentcafeapi.aspx request URL."""
    params = parse_qs(urlparse(request_url).query)
    token = params.get("apiToken", [None])[0]
    code = (
        params.get("VoyagerPropertyCode", [None])[0]
        or params.get("propertyCode", [None])[0]
        or params.get("PropertyCode", [None])[0]
    )
    return token, code


async def _intercept_page(page: Page, url: str, timeout_ms: int = 15_000) -> tuple[str | None, str | None]:
    """
    Navigate to `url` with Playwright request interception active.
    Returns (api_token, voyager_code) from the first rentcafeapi.aspx request
    fired by the page, or (None, None) if none is seen before timeout.
    """
    api_token: str | None = None
    voyager_code: str | None = None
    found_event = asyncio.Event()

    def on_request(request):
        nonlocal api_token, voyager_code
        if _RENTCAFE_API_HOST in request.url and "rentcafeapi.aspx" in request.url:
            token, code = _parse_credentials(request.url)
            if token and code:
                api_token = token
                voyager_code = code
                found_event.set()

    page.on("request", on_request)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Wait up to timeout for the API call to fire after DOM is ready
        try:
            await asyncio.wait_for(found_event.wait(), timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            pass
    except Exception:
        pass
    finally:
        page.remove_listener("request", on_request)

    return api_token, voyager_code


@dataclass
class ExtractionResult:
    building_id: int
    building_name: str
    url: str
    api_token: str | None = None
    voyager_property_code: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return bool(self.api_token and self.voyager_property_code)


async def _extract_one(
    context: BrowserContext,
    building: Building,
    semaphore: asyncio.Semaphore,
) -> ExtractionResult:
    result = ExtractionResult(
        building_id=building.id,
        building_name=building.name,
        url=building.url or "",
    )

    if not building.url:
        result.error = "no URL on building record"
        return result

    async with semaphore:
        page = await context.new_page()
        try:
            # Pass 1: try the homepage
            api_token, voyager_code = await _intercept_page(page, building.url)

            # Pass 2: if not found, look for the availability subpage in the
            # current DOM and try that page
            if not (api_token and voyager_code):
                links = await page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(e => ({href: e.href, text: e.innerText}))"
                )
                best_href: str | None = None
                best_score = 0
                for link in (links or []):
                    href = (link.get("href") or "").strip()
                    text = (link.get("text") or "").strip()
                    if not href or href.startswith("mailto:") or href == building.url:
                        continue
                    score = _score_link(href, text)
                    if score > best_score:
                        best_score = score
                        best_href = href

                if best_href and best_score > 0:
                    api_token, voyager_code = await _intercept_page(page, best_href)

            result.api_token = api_token
            result.voyager_property_code = voyager_code
            if not result.success:
                result.error = None  # not an error, just a miss
        except Exception as e:
            result.error = str(e)[:120]
        finally:
            await page.close()

    return result


async def _run_extraction(
    buildings: list[Building],
    concurrency: int,
) -> list[ExtractionResult]:
    semaphore = asyncio.Semaphore(concurrency)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        tasks = [_extract_one(context, b, semaphore) for b in buildings]
        results = await asyncio.gather(*tasks)
        await browser.close()
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract RentCafe VoyagerPropertyCode + apiToken from building pages."
    )
    parser.add_argument(
        "--building", metavar="NAME",
        help="Only process buildings whose name contains this string (case-insensitive)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print results without writing to the database",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-extract and overwrite even for buildings that already have credentials",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, metavar="N",
        help="Max concurrent page fetches (default: 5; lower if hitting rate limits)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Building).filter(Building.platform == "rentcafe")
        if args.building:
            query = query.filter(Building.name.ilike(f"%{args.building}%"))
        all_buildings = query.all()
    except Exception as e:
        print(f"DB error: {e}")
        raise SystemExit(1)

    if not all_buildings:
        print("No buildings with platform='rentcafe' found in DB. Run `sheets-sync` first.")
        db.close()
        return

    # Split into buildings to process vs already-credentialed
    to_process: list[Building] = []
    skip_count = 0
    for b in all_buildings:
        has_both = bool(b.rentcafe_property_id and b.rentcafe_api_token)
        if has_both and not args.force:
            skip_count += 1
        else:
            to_process.append(b)

    mode = "dry-run" if args.dry_run else "live"
    print(f"RentCafe buildings: {len(all_buildings)} total")
    print(f"  To process:      {len(to_process)}")
    print(f"  Already set:     {skip_count} (use --force to re-extract)")
    print(f"  Concurrency:     {args.concurrency}")
    print(f"  Mode:            {mode}")
    print()

    if not to_process:
        print("Nothing to do.")
        db.close()
        return

    print(f"Fetching {len(to_process)} pages...")
    print("-" * 72)

    results = asyncio.run(_run_extraction(to_process, concurrency=args.concurrency))

    # Print results
    ok = miss = err = 0
    for res in results:
        if res.error:
            status = "ERROR"
            detail = res.error[:55]
            err += 1
        elif res.success:
            status = "OK"
            detail = f"code={res.voyager_property_code!r}  token={res.api_token[:8]}..."
            ok += 1
        else:
            status = "MISS"
            missing = []
            if not res.voyager_property_code:
                missing.append("VoyagerPropertyCode")
            if not res.api_token:
                missing.append("apiToken")
            detail = "not found: " + ", ".join(missing)
            miss += 1

        name_col = res.building_name[:42]
        print(f"  {status:<6} {name_col:<42}  {detail}")

    print("-" * 72)
    print(f"  {ok} extracted   {miss} not found   {err} errors   {skip_count} skipped")
    print()

    if not args.dry_run and ok > 0:
        # Write successful extractions back to DB
        written = 0
        for res in results:
            if not res.success:
                continue
            b = db.query(Building).filter_by(id=res.building_id).first()
            if b:
                b.rentcafe_property_id = res.voyager_property_code
                b.rentcafe_api_token = res.api_token
                written += 1
        db.commit()
        print(f"Wrote credentials for {written} buildings to DB.")
    elif args.dry_run and ok > 0:
        print("(dry-run: no DB writes)")

    if miss > 0:
        print()
        print(f"{miss} buildings had no credentials in their page HTML.")
        print("For these, manually inspect the page in browser DevTools:")
        print("  Network tab -> filter for 'rentcafeapi' -> copy apiToken and VoyagerPropertyCode")
        print("  Then set rentcafe_property_id and rentcafe_api_token directly in the DB.")

    db.close()


if __name__ == "__main__":
    main()
