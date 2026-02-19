#!/usr/bin/env python
"""
RentCafe credential management for moxie-buildings.

VoyagerPropertyCode (per building): extracted automatically from building
homepages. RentCafe buildings embed a securecafe.com link (Apply Now, Floor
Plans, etc.) — the subdomain IS the VoyagerPropertyCode.
  e.g. https://fisherbuildingchicago.securecafe.com/ -> "fisherbuildingchicago"

apiToken (per management company): server-side only, cannot be extracted
automatically. Capture once per management company via browser DevTools:
  1. Open any building page in Chrome
  2. DevTools -> Network tab -> filter "rentcafeapi"
  3. Click the request -> copy apiToken from the URL query string
  4. One token typically covers all buildings of that management company.

Architecture note (2026-02-19): apiToken is a server-to-server credential —
it never appears in client-side HTML, JavaScript bundles, or network requests
visible to the browser. Three extraction approaches were attempted (HTML
scraping, two-pass link-following, Playwright request interception) and all
returned 0/236. The only path is DevTools capture per management company.

Sub-commands:
  extract-codes   Fetch homepages, extract VoyagerPropertyCode, write to DB
  set-token       Set apiToken for all buildings of a management company
  status          Show credential coverage grouped by management company

Examples:
  uv run rentcafe-creds extract-codes
  uv run rentcafe-creds extract-codes --dry-run
  uv run rentcafe-creds extract-codes --building "Fisher Building"
  uv run rentcafe-creds extract-codes --concurrency 10 --force

  uv run rentcafe-creds set-token --company "Reside" --token "abc123..."
  uv run rentcafe-creds set-token --company "Reside" --token "abc123..." --dry-run

  uv run rentcafe-creds status
"""
import argparse
import asyncio
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

import httpx

from moxie.db.models import Building
from moxie.db.session import SessionLocal


# ---------------------------------------------------------------------------
# VoyagerPropertyCode extraction
# ---------------------------------------------------------------------------

# Matches any securecafe.com subdomain URL in page HTML (static or JS-rendered).
# VoyagerPropertyCode = the subdomain.
_SECURECAFE_RE = re.compile(
    r'https?://([a-z0-9][a-z0-9-]*[a-z0-9])\.securecafe\.com',
    re.IGNORECASE,
)

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _find_voyager_code(html: str) -> str | None:
    """Return VoyagerPropertyCode from first securecafe.com URL in html, or None."""
    m = _SECURECAFE_RE.search(html)
    return m.group(1).lower() if m else None


@dataclass
class ExtractResult:
    building_id: int
    name: str
    url: str
    voyager_code: str | None = None
    source: str = "miss"  # "httpx", "playwright", "miss", "error"
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.voyager_code is not None


# ---------------------------------------------------------------------------
# Pass 1: httpx (fast — no browser overhead)
# ---------------------------------------------------------------------------

async def _fetch_httpx(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        resp = await client.get(url, headers=_HTTP_HEADERS, follow_redirects=True, timeout=15.0)
        return resp.text if resp.status_code < 400 else None
    except Exception:
        return None


async def _pass1_httpx(
    buildings: list[Building],
    concurrency: int,
) -> list[ExtractResult]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[ExtractResult] = []

    async def _one(b: Building) -> ExtractResult:
        res = ExtractResult(building_id=b.id, name=b.name, url=b.url or "")
        if not b.url:
            res.source = "error"
            res.error = "no URL"
            return res
        async with semaphore:
            html = await _fetch_httpx(b.url, client)
        if html:
            code = _find_voyager_code(html)
            if code:
                res.voyager_code = code
                res.source = "httpx"
        return res

    async with httpx.AsyncClient() as client:
        tasks = [_one(b) for b in buildings]
        results = list(await asyncio.gather(*tasks))

    return results


# ---------------------------------------------------------------------------
# Pass 2: Playwright (JS-rendered fallback for httpx misses)
# ---------------------------------------------------------------------------

async def _pass2_playwright(
    misses: list[ExtractResult],
    concurrency: int,
) -> None:
    """Mutate misses in-place: load each page in Playwright and grep full DOM for securecafe."""
    from playwright.async_api import async_playwright

    semaphore = asyncio.Semaphore(concurrency)

    async def _one(res: ExtractResult) -> None:
        async with semaphore:
            page = await context.new_page()
            try:
                await page.goto(res.url, wait_until="domcontentloaded", timeout=20_000)
                # Extra wait — some widgets render asynchronously
                await asyncio.sleep(1.5)
                html = await page.content()
                code = _find_voyager_code(html)
                if code:
                    res.voyager_code = code
                    res.source = "playwright"
            except Exception as e:
                res.error = str(e)[:100]
                res.source = "error"
            finally:
                await page.close()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=_HTTP_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
        )
        await asyncio.gather(*[_one(r) for r in misses])
        await browser.close()


# ---------------------------------------------------------------------------
# Sub-command: extract-codes
# ---------------------------------------------------------------------------

def cmd_extract_codes(args) -> None:
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
        print("No rentcafe buildings found. Run `sheets-sync` first.")
        db.close()
        return

    to_process = [b for b in all_buildings if args.force or not b.rentcafe_property_id]
    skip_count = len(all_buildings) - len(to_process)

    mode = "dry-run" if args.dry_run else "live"
    print(f"RentCafe buildings : {len(all_buildings)} total")
    print(f"  To process       : {len(to_process)}")
    print(f"  Already set      : {skip_count}  (--force to re-extract)")
    print(f"  Concurrency      : {args.concurrency}")
    print(f"  Mode             : {mode}")
    print()

    if not to_process:
        print("Nothing to do.")
        db.close()
        return

    # --- Pass 1: httpx ---
    print(f"Pass 1: httpx ({len(to_process)} pages)...")
    results = asyncio.run(_pass1_httpx(to_process, concurrency=args.concurrency))

    p1_ok = [r for r in results if r.ok]
    p1_miss = [r for r in results if not r.ok and r.source != "error"]
    p1_err = [r for r in results if r.source == "error"]
    print(f"  Found: {len(p1_ok)}  Miss: {len(p1_miss)}  Error: {len(p1_err)}")

    # --- Pass 2: Playwright fallback ---
    if p1_miss:
        pw_concurrency = min(args.concurrency, 3)
        print(f"\nPass 2: Playwright fallback ({len(p1_miss)} pages, concurrency={pw_concurrency})...")
        asyncio.run(_pass2_playwright(p1_miss, concurrency=pw_concurrency))
        p2_ok = [r for r in p1_miss if r.ok]
        still_miss = [r for r in p1_miss if not r.ok]
        print(f"  Found: {len(p2_ok)}  Still missing: {len(still_miss)}")

    # --- Print full results ---
    print()
    print("-" * 76)
    all_ok = [r for r in results if r.ok]
    all_miss = [r for r in results if not r.ok]

    for r in all_ok:
        print(f"  OK     {r.name[:44]:<44}  code={r.voyager_code!r} ({r.source})")
    for r in all_miss:
        tag = "ERROR" if r.error else "MISS "
        detail = (r.error or "securecafe.com link not found in page HTML")[:52]
        print(f"  {tag}  {r.name[:44]:<44}  {detail}")

    print("-" * 76)
    ok_count = len(all_ok)
    miss_count = sum(1 for r in all_miss if not r.error)
    err_count = sum(1 for r in all_miss if r.error)
    print(f"  {ok_count} extracted   {miss_count} not found   {err_count} errors   {skip_count} skipped")
    print()

    # --- Write to DB ---
    if not args.dry_run and ok_count > 0:
        written = 0
        for r in all_ok:
            b = db.query(Building).filter_by(id=r.building_id).first()
            if b:
                b.rentcafe_property_id = r.voyager_code
                written += 1
        db.commit()
        print(f"Wrote VoyagerPropertyCode for {written} buildings to DB.")
    elif args.dry_run and ok_count > 0:
        print("(dry-run: no DB writes)")

    if miss_count + err_count > 0:
        print(
            f"\n{miss_count + err_count} buildings had no securecafe.com link in their page.\n"
            "These may use an iframe embed or custom widget — inspect manually:\n"
            "  View source -> Ctrl+F 'securecafe'\n"
            "  If not found, check if the building URL is correct."
        )

    db.close()


# ---------------------------------------------------------------------------
# Sub-command: set-token
# ---------------------------------------------------------------------------

def cmd_set_token(args) -> None:
    db = SessionLocal()
    try:
        buildings = (
            db.query(Building)
            .filter(
                Building.platform == "rentcafe",
                Building.management_company.ilike(f"%{args.company}%"),
            )
            .all()
        )
    except Exception as e:
        print(f"DB error: {e}")
        raise SystemExit(1)

    if not buildings:
        print(f"No rentcafe buildings found with management_company matching '{args.company}'.")
        print("Tip: run `uv run rentcafe-creds status` to see company names.")
        db.close()
        return

    to_update = [b for b in buildings if args.force or not b.rentcafe_api_token]
    skip_count = len(buildings) - len(to_update)

    token_preview = f"{args.token[:8]}...{args.token[-4:]}" if len(args.token) > 12 else args.token
    print(f"Company match '{args.company}': {len(buildings)} buildings")
    if skip_count:
        print(f"  Skipping {skip_count} with existing token  (--force to overwrite)")
    print(f"  Updating : {len(to_update)} buildings")
    print(f"  Token    : {token_preview}")
    print(f"  Mode     : {'dry-run' if args.dry_run else 'live'}")
    print()

    for b in to_update:
        code_str = f"code={b.rentcafe_property_id!r}" if b.rentcafe_property_id else "NO_CODE (run extract-codes first)"
        print(f"  {b.name[:52]:<52}  {code_str}")

    if not args.dry_run:
        for b in to_update:
            b.rentcafe_api_token = args.token
        db.commit()
        print(f"\nSet apiToken for {len(to_update)} buildings.")
        no_code = [b for b in to_update if not b.rentcafe_property_id]
        if no_code:
            print(f"  Warning: {len(no_code)} buildings still missing VoyagerPropertyCode.")
            print("  Run `uv run rentcafe-creds extract-codes` to fill those in.")
    else:
        print("\n(dry-run: no DB writes)")

    db.close()


# ---------------------------------------------------------------------------
# Sub-command: status
# ---------------------------------------------------------------------------

def cmd_status(_args) -> None:
    db = SessionLocal()
    try:
        buildings = db.query(Building).filter(Building.platform == "rentcafe").all()
    except Exception as e:
        print(f"DB error: {e}")
        raise SystemExit(1)

    total = len(buildings)
    has_code = sum(1 for b in buildings if b.rentcafe_property_id)
    has_token = sum(1 for b in buildings if b.rentcafe_api_token)
    has_both = sum(1 for b in buildings if b.rentcafe_property_id and b.rentcafe_api_token)

    print(f"RentCafe credential coverage: {total} buildings total")
    print(f"  VoyagerPropertyCode  : {has_code:>3}/{total}  ({has_code/total*100:.0f}%)")
    print(f"  apiToken             : {has_token:>3}/{total}  ({has_token/total*100:.0f}%)")
    print(f"  Both (ready to run)  : {has_both:>3}/{total}  ({has_both/total*100:.0f}%)")
    print()

    by_company: dict[str, list[Building]] = defaultdict(list)
    for b in buildings:
        by_company[b.management_company or "(unknown)"].append(b)

    rows = sorted(by_company.items(), key=lambda x: -len(x[1]))

    print(f"  {'Management Company':<40} {'Bldgs':>5}  {'Code':>5}  {'Token':>7}  {'Ready':>5}")
    print("  " + "-" * 68)
    running = 0
    for company, bldgs in rows:
        count = len(bldgs)
        codes = sum(1 for b in bldgs if b.rentcafe_property_id)
        tokens = sum(1 for b in bldgs if b.rentcafe_api_token)
        ready = sum(1 for b in bldgs if b.rentcafe_property_id and b.rentcafe_api_token)
        running += count
        cumul = running / total * 100
        # Token column: checkmark if all buildings have it, number if partial, dash if none
        if tokens == count:
            token_str = "ok"
        elif tokens > 0:
            token_str = str(tokens)
        else:
            token_str = "-"
        print(
            f"  {company:<40} {count:>5}  {codes:>5}  {token_str:>7}  {ready:>5}  ({cumul:.0f}%)"
        )

    db.close()


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage RentCafe credentials (VoyagerPropertyCode + apiToken).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "DevTools instructions for capturing apiToken:\n"
            "  1. Open any building's website in Chrome\n"
            "  2. DevTools (F12) -> Network tab -> filter 'rentcafeapi'\n"
            "  3. Navigate to Floor Plans or Availability page\n"
            "  4. Click any 'rentcafeapi.aspx' request\n"
            "  5. Copy apiToken from the Request URL query string\n"
            "  6. Run: uv run rentcafe-creds set-token --company 'Name' --token 'VALUE'"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # extract-codes
    p_ec = sub.add_parser("extract-codes", help="Extract VoyagerPropertyCode from building homepages")
    p_ec.add_argument("--building", metavar="NAME", help="Filter: only buildings whose name contains this string")
    p_ec.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    p_ec.add_argument("--force", action="store_true", help="Re-extract even for buildings that already have a code")
    p_ec.add_argument("--concurrency", type=int, default=8, metavar="N",
                      help="Max concurrent HTTP fetches (default: 8)")

    # set-token
    p_st = sub.add_parser("set-token", help="Set apiToken for all buildings of a management company")
    p_st.add_argument("--company", required=True, metavar="NAME",
                      help="Management company name (partial match, case-insensitive)")
    p_st.add_argument("--token", required=True, metavar="UUID",
                      help="apiToken captured from browser DevTools Network tab")
    p_st.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    p_st.add_argument("--force", action="store_true", help="Overwrite existing tokens")

    # status
    sub.add_parser("status", help="Show credential coverage grouped by management company")

    args = parser.parse_args()

    if args.cmd == "extract-codes":
        cmd_extract_codes(args)
    elif args.cmd == "set-token":
        cmd_set_token(args)
    elif args.cmd == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
