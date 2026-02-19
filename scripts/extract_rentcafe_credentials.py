#!/usr/bin/env python
"""
RentCafe credential management for moxie-buildings.

VoyagerPropertyCode (per building): extracted automatically from building
homepages. RentCafe buildings embed a securecafe.com link (Apply Now, Floor
Plans, etc.) — the subdomain IS the VoyagerPropertyCode.
  e.g. https://fisherbuildingchicago.securecafe.com/ -> "fisherbuildingchicago"

apiToken (per management company): extracted by Playwright network interception.
The script navigates to each building's RentCafe widget page and listens for
the api.rentcafe.com/rentcafeapi.aspx request that the widget fires on load.

Strategy for token extraction (in order):
  1. If VoyagerPropertyCode is known: navigate directly to code.securecafe.com
     — this is the widget page itself, guaranteed to fire the API call.
  2. Scan building homepage for securecafe.com links, follow the best one.
  3. Score all homepage links for "availability/floor plans" keywords, follow best.

Note: previous headless attempts returned 0/236 due to Cloudflare blocking headless
browsers on floor plans pages. extract-tokens defaults to headed (visible) mode which
bypasses Cloudflare. Use --headless to force headless if headed mode is unavailable.

Sub-commands:
  extract-codes   Fetch homepages, extract VoyagerPropertyCode, write to DB
  extract-tokens  Playwright network intercept to extract apiToken per building
  set-token       Set apiToken for all buildings of a management company (manual)
  status          Show credential coverage grouped by management company

Examples:
  uv run rentcafe-creds extract-codes
  uv run rentcafe-creds extract-codes --dry-run
  uv run rentcafe-creds extract-codes --building "Fisher Building"

  uv run rentcafe-creds extract-tokens
  uv run rentcafe-creds extract-tokens --company "Reside"
  uv run rentcafe-creds extract-tokens --building "Fisher Building" --dry-run
  uv run rentcafe-creds extract-tokens --headless --concurrency 3

  uv run rentcafe-creds set-token --company "Reside" --token "abc123..."
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
# Captures just the subdomain (VoyagerPropertyCode)
_SECURECAFE_RE = re.compile(
    r'https?://([a-z0-9][a-z0-9-]*[a-z0-9])\.securecafe\.com',
    re.IGNORECASE,
)

# Extracts (subdomain, property_slug) from any securecafe.com URL that has the
# /residentservices/PROPERTY_SLUG/ path — present in login, search, and other pages.
# Used to construct the apartment search URL:
#   https://SUBDOMAIN.securecafe.com/residentservices/PROPERTY_SLUG/en-US/apartment/search.aspx
_SECURECAFE_SLUG_RE = re.compile(
    r'https?://([a-z0-9][a-z0-9-]*[a-z0-9])\.securecafe\.com/residentservices/([a-z0-9][a-z0-9-]*[a-z0-9])/',
    re.IGNORECASE,
)


def _build_search_url(html: str) -> str | None:
    """
    Return the RentCafe apartment search URL for this page, or None.

    Strategy:
    1. Find any securecafe.com/residentservices/SLUG/ URL in the page HTML.
    2. Construct: https://SUBDOMAIN.securecafe.com/residentservices/SLUG/en-US/apartment/search.aspx
       This is the standard RentCafe search page and will fire the rentcafeapi.aspx request.
    """
    m = _SECURECAFE_SLUG_RE.search(html)
    if m:
        subdomain, slug = m.group(1).lower(), m.group(2).lower()
        return f"https://{subdomain}.securecafe.com/residentservices/{slug}/en-US/apartment/search.aspx"
    return None

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
# Token extraction — Playwright network interception
# ---------------------------------------------------------------------------

_RENTCAFE_API_HOST = "api.rentcafe.com"

# The marketing/tracking API fires on page load for every RentCafe-hosted building.
# The PropertyAPIKey parameter IS the apiToken used for the availability API.
# URL: marketingapi.rentcafe.com/marketingapi/api/leadattributionanddni/getdnidetails?PropertyAPIKey=TOKEN
_MARKETING_API_HOST = "marketingapi.rentcafe.com"

_AVAILABILITY_KEYWORDS: frozenset[str] = frozenset({
    "floor", "floorplan", "floor-plan", "availab", "apartment",
    "units", "rent", "leasing", "pricing", "search", "listing",
})
_SKIP_KEYWORDS: frozenset[str] = frozenset({
    "blog", "news", "gallery", "photo", "contact", "about",
    "team", "careers", "press", "event", "social", "privacy",
    "terms", "sitemap", "login", "register", "resident",
})


_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2"})
_CDN_HOSTS = frozenset({"cdngeneralmvc.rentcafe.com", "cdngeneralcf.rentcafe.com", "cdn.rentcafe.com", "resource.rentcafe.com"})


def _score_link(href: str, text: str) -> int:
    lower = href.lower()
    # Skip image and font files — filenames can contain keywords ("floor plan.jpg")
    if any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS):
        return 0
    # Skip RentCafe CDN URLs — these are assets, not pages
    if any(cdn in lower for cdn in _CDN_HOSTS):
        return 0
    combined = (href + " " + text).lower()
    if any(s in combined for s in _SKIP_KEYWORDS):
        return 0
    return sum(1 for kw in _AVAILABILITY_KEYWORDS if kw in combined)


def _parse_credentials(request_url: str) -> tuple[str | None, str | None]:
    """Extract (api_token, voyager_code) from a rentcafeapi.aspx request URL."""
    from urllib.parse import parse_qs, urlparse
    params = parse_qs(urlparse(request_url).query)
    token = params.get("apiToken", [None])[0]
    code = (
        params.get("VoyagerPropertyCode", [None])[0]
        or params.get("propertyCode", [None])[0]
        or params.get("PropertyCode", [None])[0]
    )
    return token, code


def _parse_marketing_token(request_url: str) -> str | None:
    """
    Extract apiToken from a marketingapi.rentcafe.com/getdnidetails request.

    The PropertyAPIKey parameter is the apiToken for the availability API.
    Returns the URL-decoded value (with literal '=' signs, not '%3d').
    """
    from urllib.parse import parse_qs, urlparse, unquote
    params = parse_qs(urlparse(request_url).query)
    raw = params.get("PropertyAPIKey", [None])[0]
    return unquote(raw) if raw else None


_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
"""


@dataclass
class TokenResult:
    building_id: int
    name: str
    url: str
    api_token: str | None = None
    voyager_code: str | None = None
    source: str = "miss"   # "securecafe-direct", "link-follow", "miss", "error"
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.api_token is not None


async def _extract_token_one(
    context,   # BrowserContext
    building: Building,
    semaphore: asyncio.Semaphore,
    timeout_ms: int,
) -> TokenResult:
    """
    Navigate to the building's website, find the floor plans / availability page
    (where the RentCafe widget is embedded), and intercept the rentcafeapi.aspx
    request the widget fires on load.

    Note: securecafe.com/  (root) is the RESIDENT PORTAL login page — it does NOT
    load the apartment search widget. We must navigate to the building's own page
    where the widget is embedded via iframe.
    """
    result = TokenResult(
        building_id=building.id,
        name=building.name,
        url=building.url or "",
    )

    if not building.url:
        result.source = "error"
        result.error = "no URL"
        return result

    found_event = asyncio.Event()
    captured_token: list[str] = []
    captured_code: list[str] = []

    debug: bool = getattr(building, "_debug", False)
    rentcafe_requests: list[str] = []  # all rentcafe-related requests seen (for debug)

    def on_request(request):
        url = request.url
        if "rentcafe" in url.lower():
            rentcafe_requests.append(url)
        if captured_token:
            return  # already captured, skip further processing

        # Primary: marketingapi.rentcafe.com/getdnidetails?PropertyAPIKey=TOKEN
        # Fires on page load for every RentCafe-hosted building homepage.
        # PropertyAPIKey IS the apiToken for the availability API.
        if _MARKETING_API_HOST in url and "PropertyAPIKey" in url:
            token = _parse_marketing_token(url)
            if token:
                captured_token.append(token)
                found_event.set()
                return

        # Fallback: api.rentcafe.com/rentcafeapi.aspx?apiToken=TOKEN
        # Used by buildings that embed the RentCafe JS widget client-side.
        if _RENTCAFE_API_HOST in url and "rentcafeapi.aspx" in url:
            token, code = _parse_credentials(url)
            if token:
                captured_token.append(token)
                if code:
                    captured_code.append(code)
                found_event.set()

    wait_secs = timeout_ms / 1000

    async with semaphore:
        page = await context.new_page()
        page.on("request", on_request)
        try:
            # --- Step 1: load the building homepage and wait for the marketing API call ---
            # marketingapi.rentcafe.com/getdnidetails?PropertyAPIKey=TOKEN fires on
            # page load for buildings using RentCafe's tracking script.
            # Wait the full timeout here — this is the primary extraction path.
            if debug:
                print(f"  [debug] navigating to homepage: {building.url}")
            await page.goto(building.url, wait_until="load", timeout=timeout_ms)
            try:
                await asyncio.wait_for(found_event.wait(), timeout=wait_secs)
            except asyncio.TimeoutError:
                pass

            if not found_event.is_set():
                # --- Step 2: collect candidate pages to try ---
                #
                # Try in order:
                # A. Building's own floor plans / availability page (scored link)
                #    — if the building has an embedded RentCafe widget on their own
                #    domain, the iframe fires the API call when that page loads.
                # B. RentCafe search URL constructed from the property slug
                #    — securecafe.com/residentservices/SLUG/en-US/apartment/search.aspx
                #    Works for full RentCafe-hosted sites IF they use client-side rendering.
                html = await page.content()

                # Collect scored link (building's own site, not securecafe.com)
                try:
                    links = await page.eval_on_selector_all(
                        "a[href]",
                        "els => els.map(e => ({href: e.href, text: e.innerText || ''}))",
                    )
                except Exception:
                    links = []

                scored_href: str | None = None
                scored_score = 0
                for link in (links or []):
                    href = (link.get("href") or "").strip()
                    text = (link.get("text") or "").strip()
                    if not href or "mailto:" in href or "securecafe.com" in href:
                        continue  # securecafe links handled separately
                    score = _score_link(href, text)
                    if score > scored_score:
                        scored_score = score
                        scored_href = href

                # Construct the RentCafe search URL from property slug in page HTML
                search_url = _build_search_url(html)

                # Build candidate list: building's own page first, securecafe fallback
                candidates: list[tuple[str, str]] = []
                if scored_href and scored_score > 0:
                    candidates.append(("scored", scored_href))
                if search_url:
                    candidates.append(("securecafe", search_url))

                if debug:
                    print(f"  [debug] candidates: {[c[1] for c in candidates]}")

                sub_secs = max(wait_secs, 15.0)
                for _ctype, candidate_url in candidates:
                    if found_event.is_set():
                        break
                    found_event.clear()
                    try:
                        await page.goto(candidate_url, wait_until="load", timeout=timeout_ms)
                        # Scroll down — lazy-loaded widgets trigger on scroll
                        await page.evaluate("window.scrollTo(0, Math.max(500, document.body.scrollHeight / 3))")
                        await asyncio.wait_for(found_event.wait(), timeout=sub_secs)
                    except (asyncio.TimeoutError, Exception):
                        pass

        except Exception as e:
            result.source = "error"
            result.error = str(e)[:100]
            if debug:
                print(f"  [debug] exception: {e}")
            return result
        finally:
            if debug and rentcafe_requests:
                print(f"  [debug] rentcafe requests seen ({len(rentcafe_requests)}):")
                for r in rentcafe_requests[:10]:
                    print(f"    {r[:120]}")
            elif debug:
                print(f"  [debug] no requests containing 'rentcafe' were seen")
            page.remove_listener("request", on_request)
            await page.close()

    if captured_token:
        result.api_token = captured_token[0]
        result.voyager_code = captured_code[0] if captured_code else building.rentcafe_property_id
        result.source = "found"
    return result


async def _run_token_extraction(
    buildings: list[Building],
    concurrency: int,
    headless: bool,
    timeout_ms: int,
) -> list[TokenResult]:
    from playwright.async_api import async_playwright

    semaphore = asyncio.Semaphore(concurrency)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=_HTTP_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
        )
        await context.add_init_script(_STEALTH_SCRIPT)
        tasks = [_extract_token_one(context, b, semaphore, timeout_ms) for b in buildings]
        results = list(await asyncio.gather(*tasks))
        await browser.close()
    return results


# ---------------------------------------------------------------------------
# Sub-command: extract-tokens
# ---------------------------------------------------------------------------

def cmd_extract_tokens(args) -> None:
    db = SessionLocal()
    try:
        query = db.query(Building).filter(Building.platform == "rentcafe")
        if args.building:
            query = query.filter(Building.name.ilike(f"%{args.building}%"))
        if args.company:
            query = query.filter(Building.management_company.ilike(f"%{args.company}%"))
        all_buildings = query.all()
    except Exception as e:
        print(f"DB error: {e}")
        raise SystemExit(1)

    if not all_buildings:
        print("No matching rentcafe buildings found.")
        db.close()
        return

    to_process = [b for b in all_buildings if args.force or not b.rentcafe_api_token]
    skip_count = len(all_buildings) - len(to_process)

    mode_str = "dry-run" if args.dry_run else "live"
    head_str = "headless" if args.headless else "headed (visible browser)"
    print(f"RentCafe buildings  : {len(all_buildings)} total")
    print(f"  To process        : {len(to_process)}")
    print(f"  Already have token: {skip_count}  (--force to re-extract)")
    print(f"  Concurrency       : {args.concurrency}")
    print(f"  Timeout per page  : {args.timeout}s")
    print(f"  Browser mode      : {head_str}")
    print(f"  Mode              : {mode_str}")
    print()

    if not to_process:
        print("Nothing to do.")
        db.close()
        return

    if not args.headless:
        print("Opening browser windows — Cloudflare bypass via headed mode.")
        print("Do not close the browser windows while the script is running.")
        print()

    print(f"Extracting tokens for {len(to_process)} buildings...")
    print("-" * 76)

    if args.debug:
        for b in to_process:
            b._debug = True  # type: ignore[attr-defined]

    results = asyncio.run(
        _run_token_extraction(
            to_process,
            concurrency=args.concurrency,
            headless=args.headless,
            timeout_ms=args.timeout * 1000,
        )
    )

    ok = [r for r in results if r.ok]
    miss = [r for r in results if not r.ok and r.source != "error"]
    err = [r for r in results if r.source == "error"]

    for r in ok:
        print(f"  OK     {r.name[:44]:<44}  token={r.api_token[:8]}... ({r.source})")
    for r in miss:
        print(f"  MISS   {r.name[:44]:<44}  no token found (try set-token for manual capture)")
    for r in err:
        print(f"  ERROR  {r.name[:44]:<44}  {(r.error or '')[:40]}")

    print("-" * 76)
    print(f"  {len(ok)} extracted   {len(miss)} not found   {len(err)} errors   {skip_count} skipped")
    print()

    if not args.dry_run and ok:
        written = 0
        for r in ok:
            b = db.query(Building).filter_by(id=r.building_id).first()
            if b:
                b.rentcafe_api_token = r.api_token
                # If we captured the code from the request URL and it differs, update it
                if r.voyager_code and not b.rentcafe_property_id:
                    b.rentcafe_property_id = r.voyager_code
                written += 1
        db.commit()
        print(f"Wrote apiToken for {written} buildings to DB.")
    elif args.dry_run and ok:
        print("(dry-run: no DB writes)")

    if miss:
        print(
            f"\n{len(miss)} buildings had no auto-extractable token.\n"
            "These likely use RentCafe's full-site platform (Essence template)\n"
            "which renders availability server-side — the token is never sent to the browser.\n"
            "Options:\n"
            "  1. Try manual DevTools capture on a building in the same management company\n"
            "     and use: set-token --company NAME --token VALUE\n"
            "  2. Check building URL is correct (may have changed)"
        )

    db.close()


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

    # extract-tokens
    p_et = sub.add_parser(
        "extract-tokens",
        help="Playwright network intercept to auto-extract apiToken from building pages",
    )
    p_et.add_argument("--building", metavar="NAME", help="Filter: only buildings whose name contains this string")
    p_et.add_argument("--company", metavar="NAME", help="Filter: only buildings of this management company")
    p_et.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    p_et.add_argument("--force", action="store_true", help="Re-extract even for buildings that already have a token")
    p_et.add_argument("--concurrency", type=int, default=2, metavar="N",
                      help="Max concurrent browser pages (default: 2; headed mode is resource-intensive)")
    p_et.add_argument("--timeout", type=int, default=20, metavar="SECS",
                      help="Max seconds to wait for API call per page (default: 20)")
    p_et.add_argument("--headless", action="store_true",
                      help="Run browser headless (default: headed to bypass Cloudflare)")
    p_et.add_argument("--debug", action="store_true",
                      help="Print all rentcafe-related requests seen per page (for diagnosing misses)")

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
    elif args.cmd == "extract-tokens":
        cmd_extract_tokens(args)
    elif args.cmd == "set-token":
        cmd_set_token(args)
    elif args.cmd == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
