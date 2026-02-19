#!/usr/bin/env python
"""
Platform detection via page content inspection.

For buildings classified as 'needs_classification' (custom domains that URL-pattern
matching couldn't identify), fetches the page via Crawl4AI (JS-rendered) and scans
the rendered HTML for platform-specific signatures — script URLs, API endpoints,
iframe sources, JS variable patterns, etc.

Unlike URL-based detect_platform(), this catches buildings with custom domains
that embed a known platform (e.g., an Entrata-powered building at myapts.com).

Usage:
    uv run python scripts/detect_platforms.py
    uv run python scripts/detect_platforms.py --save
    uv run python scripts/detect_platforms.py --building "Fisher Building"
    uv run python scripts/detect_platforms.py --all
    uv run python scripts/detect_platforms.py --concurrency 3

Flags:
    --save          Write detected platforms to DB (default: dry-run, print only)
    --all           Include buildings already classified, not just needs_classification
    --building NAME Process only buildings whose name matches (case-insensitive)
    --concurrency N Max concurrent page fetches (default: 5)

Output:
    DETECTED  Building Name            entrata   (entrata.com, entratacdn.com)
    UNKNOWN   Building Name            (no signatures found → assign llm manually)
    ERROR     Building Name            connection timeout
"""
import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Make moxie importable when run as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from moxie.db.models import Building
from moxie.db.session import SessionLocal


# ---------------------------------------------------------------------------
# Platform signatures
# ---------------------------------------------------------------------------
# Each platform maps to a list of strings to search for in rendered HTML.
# Patterns are matched case-insensitively anywhere in the full document.
# Order within each platform: most specific / reliable first.
# Platforms are checked in order — first match wins for the classification.
# ---------------------------------------------------------------------------

PLATFORM_SIGNATURES: dict[str, list[str]] = {
    # Tier 1: direct API platforms (most reliable to detect)
    "rentcafe": [
        "rentcafeapi.aspx",       # API call URL — definitive
        "securecafe.com",          # RentCafe application portal
        "rentcafe.com",            # General presence
        "VoyagerPropertyCode",     # Yardi/RentCafe JS variable
    ],
    "ppm": [
        "ppmapartments.com",
    ],

    # Tier 2: property management platform portals
    "entrata": [
        "entratacdn.com",          # CDN for Entrata scripts/assets — definitive
        "myentrata.com",           # Entrata resident/prospect portal
        "entrata.com",             # General Entrata presence
    ],
    "appfolio": [
        "appfolioproperty.com",    # AppFolio application portal
        "appfolio.com",            # General AppFolio presence
    ],
    "realpage": [
        "realpage.com",
        "g5searchmarketing.com",   # G5/RealPage marketing sites
        "leasingdesk.com",         # RealPage leasing platform
    ],
    "funnel": [
        "nestiolistings.com",      # Funnel/Nestio listing embed
        "funnelleasing.com",       # Funnel direct
    ],

    # Tier 2: management company portals
    "bozzuto": [
        "bozzuto.com",
    ],
    "groupfox": [
        "groupfox.com",
    ],

    # Other platforms we may encounter
    "mri": [
        "residentportal.com",      # MRI Software resident portal — definitive
        "mrisoftware.com",         # MRI direct reference
        "mri software",            # MRI brand mention
    ],
    "knock": [
        "knockcrm.com",            # Knock CRM tour scheduling
    ],
    "yardi": [
        "yardi.com",               # Generic Yardi (not RentCafe-specific)
        "yardirentcafe.com",       # Yardi-branded RentCafe subdomain
    ],
}

# Ordered list of platforms to check — determines precedence when multiple signatures match.
# More specific / higher-confidence platforms first.
PLATFORM_CHECK_ORDER: list[str] = [
    "rentcafe",
    "ppm",
    "entrata",
    "appfolio",
    "realpage",
    "funnel",
    "bozzuto",
    "groupfox",
    "mri",
    "knock",
    "yardi",
]


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    building_id: int
    building_name: str
    url: str
    current_platform: str | None
    detected_platform: str | None = None
    matched_signatures: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.detected_platform is not None and self.error is None


def _detect_from_html(html: str) -> tuple[str | None, list[str]]:
    """
    Scan rendered HTML for platform-specific signatures.

    Returns (platform, matched_signatures) where platform is the first match
    or None if nothing was found. matched_signatures lists every pattern found.
    """
    html_lower = html.lower()
    for platform in PLATFORM_CHECK_ORDER:
        signatures = PLATFORM_SIGNATURES[platform]
        matched = [sig for sig in signatures if sig.lower() in html_lower]
        if matched:
            return platform, matched
    return None, []


async def _detect_one(
    crawler: AsyncWebCrawler,
    building: Building,
    semaphore: asyncio.Semaphore,
) -> DetectionResult:
    result = DetectionResult(
        building_id=building.id,
        building_name=building.name,
        url=building.url or "",
        current_platform=building.platform,
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
            platform, matched = _detect_from_html(html)
            result.detected_platform = platform
            result.matched_signatures = matched
        except Exception as e:
            result.error = str(e)[:120]

    return result


async def _run_detection(
    buildings: list[Building],
    concurrency: int,
) -> list[DetectionResult]:
    semaphore = asyncio.Semaphore(concurrency)
    async with AsyncWebCrawler() as crawler:
        tasks = [_detect_one(crawler, b, semaphore) for b in buildings]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect platform from page HTML for buildings that couldn't be classified by URL."
    )
    parser.add_argument(
        "--building", metavar="NAME",
        help="Only process buildings whose name contains this string (case-insensitive)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Include all buildings, not just those with platform='needs_classification'",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Write detected platforms to the database (default: dry-run, print only)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, metavar="N",
        help="Max concurrent page fetches (default: 5; lower if hitting rate limits)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Building)
        if not args.all:
            query = query.filter(Building.platform == "needs_classification")
        if args.building:
            query = query.filter(Building.name.ilike(f"%{args.building}%"))
        buildings = query.all()
    except Exception as e:
        print(f"DB error: {e}")
        raise SystemExit(1)

    if not buildings:
        scope = "all buildings" if args.all else "buildings with platform='needs_classification'"
        print(f"No {scope} found in DB.")
        if not args.all:
            print("Run `sheets-sync` first to populate the DB, then re-run this script.")
        db.close()
        return

    mode = "SAVE" if args.save else "DRY-RUN"
    scope_label = "all" if args.all else "needs_classification"
    print(f"Platform detection — scope: {scope_label}  mode: {mode}")
    print(f"  Buildings to inspect: {len(buildings)}")
    print(f"  Concurrency:          {args.concurrency}")
    print()
    print(f"Fetching {len(buildings)} pages...")
    print("-" * 80)

    results = asyncio.run(_run_detection(buildings, concurrency=args.concurrency))

    # Print results
    detected = missed = errors = 0
    for res in results:
        name_col = res.building_name[:40]
        if res.error:
            status = "ERROR"
            detail = res.error[:55]
            errors += 1
        elif res.success:
            status = "DETECTED"
            sigs = ", ".join(res.matched_signatures[:3])  # show up to 3
            detail = f"{res.detected_platform:<12}  ({sigs})"
            detected += 1
        else:
            status = "UNKNOWN"
            detail = "(no signatures found)"
            missed += 1

        print(f"  {status:<8}  {name_col:<40}  {detail}")

    print("-" * 80)
    print(f"  {detected} detected   {missed} unknown   {errors} errors")
    print()

    if not args.save:
        if detected > 0:
            print(f"Run with --save to write {detected} detected platform(s) to DB.")
        db.close()
        return

    # Write to DB
    if detected == 0:
        print("Nothing to write.")
        db.close()
        return

    written = 0
    for res in results:
        if not res.success:
            continue
        b = db.query(Building).filter_by(id=res.building_id).first()
        if b:
            b.platform = res.detected_platform
            written += 1
    db.commit()
    print(f"Wrote platform for {written} buildings to DB.")

    if missed > 0:
        print()
        print(f"{missed} buildings had no recognizable platform signatures.")
        print("For these, inspect the page manually or assign platform='llm' in the sheet.")

    db.close()


if __name__ == "__main__":
    main()
