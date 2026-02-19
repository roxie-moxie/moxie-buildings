#!/usr/bin/env python
"""
Automated RentCafe credential extraction.

For every building with platform='rentcafe', fetches the building's page using
Crawl4AI (JS-rendered, bypasses 403), searches the rendered HTML for embedded
apiToken and VoyagerPropertyCode, and writes them to the DB.

Extraction strategies (tried in order):
  1. rentcafeapi.aspx URLs in HTML — most reliable (params parsed directly from URL)
  2. JS variable / JSON property patterns — fallback for inline script embeds

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
from urllib.parse import parse_qs

# Make moxie importable when run as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from moxie.db.models import Building
from moxie.db.session import SessionLocal


# ---------------------------------------------------------------------------
# Regex patterns for credential extraction
# ---------------------------------------------------------------------------

# Strategy 1: rentcafeapi.aspx URL anywhere in rendered HTML
# Captures the full URL so we can parse its query string
_RENTCAFE_URL_RE = re.compile(
    r'https?://[^\s"\'<>]*rentcafeapi\.aspx[^\s"\'<>]+',
    re.IGNORECASE,
)

# Strategy 2a: apiToken as JS variable or JSON/object property
# Matches: apiToken: "TOKEN", "apiToken": "TOKEN", apiToken = "TOKEN", apiToken='TOKEN'
_API_TOKEN_RE = re.compile(
    r"""["\']?apiToken["\']?\s*[:=]\s*["']([^"']{8,})["']""",
    re.IGNORECASE,
)

# Strategy 2b: VoyagerPropertyCode as JS variable or JSON/object property
# Matches: VoyagerPropertyCode: "dey", VoyagerPropertyCode = 'dey'
_VOYAGER_CODE_RE = re.compile(
    r"""["\']?VoyagerPropertyCode["\']?\s*[:=]\s*["']([^"']{1,40})["']""",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Extraction logic
# ---------------------------------------------------------------------------

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


def _extract_from_html(html: str) -> tuple[str | None, str | None]:
    """
    Try to extract (api_token, voyager_property_code) from rendered page HTML.

    Strategy 1: scan for rentcafeapi.aspx URLs and parse their query strings.
    Strategy 2: regex for JS variable / JSON property patterns.

    Returns (api_token, voyager_code) — either may be None if not found.
    """
    api_token: str | None = None
    voyager_code: str | None = None

    # Strategy 1: parse rentcafeapi.aspx URLs
    for url_match in _RENTCAFE_URL_RE.finditer(html):
        url_fragment = url_match.group(0)
        query_str = url_fragment.split("?", 1)[-1] if "?" in url_fragment else ""
        params = parse_qs(query_str)

        token = params.get("apiToken", [None])[0]
        code = (
            params.get("VoyagerPropertyCode", [None])[0]
            or params.get("propertyCode", [None])[0]
            or params.get("PropertyCode", [None])[0]
        )

        if token and not api_token:
            api_token = token
        if code and not voyager_code:
            voyager_code = code

        if api_token and voyager_code:
            return api_token, voyager_code

    # Strategy 2: JS variable / JSON property patterns
    if not api_token:
        m = _API_TOKEN_RE.search(html)
        if m:
            api_token = m.group(1)

    if not voyager_code:
        m = _VOYAGER_CODE_RE.search(html)
        if m:
            voyager_code = m.group(1)

    return api_token, voyager_code


async def _extract_one(
    crawler: AsyncWebCrawler,
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
        try:
            config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
            crawl_result = await crawler.arun(building.url, config=config)
            html = crawl_result.html or ""
            if not html:
                result.error = "empty HTML (possible bot block)"
                return result
            api_token, voyager_code = _extract_from_html(html)
            result.api_token = api_token
            result.voyager_property_code = voyager_code
        except Exception as e:
            result.error = str(e)[:120]

    return result


async def _run_extraction(
    buildings: list[Building],
    concurrency: int,
) -> list[ExtractionResult]:
    semaphore = asyncio.Semaphore(concurrency)
    async with AsyncWebCrawler() as crawler:
        tasks = [_extract_one(crawler, b, semaphore) for b in buildings]
        return await asyncio.gather(*tasks)


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
        query = db.query(Building).filter_by(platform="rentcafe")
        if args.building:
            query = query.filter(Building.name.ilike(f"%{args.building}%"))
        all_buildings = query.all()
    except Exception as e:
        print(f"DB error: {e}")
        raise SystemExit(1)

    if not all_buildings:
        print("No rentcafe buildings found in DB. Run `sheets-sync` first.")
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
