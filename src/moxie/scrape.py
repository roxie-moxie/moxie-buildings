"""
Single-building spot-check scraper CLI.

Looks up a building by name or URL, routes to the correct scraper, and prints
normalized units to the terminal. Does not write to the database by default.

Usage:
    scrape --building "Fisher Building"
    scrape --building "https://fisherbuildingapts.com"
    scrape --building "Fisher"
    scrape --building "Fisher Building" --save

Entrypoint: moxie.scrape:main (registered as `scrape` in pyproject.toml)
"""

import argparse
import importlib
import sys

from moxie.db.models import Building
from moxie.db.session import get_db
from moxie.scrapers.base import save_scrape_result
from moxie.scrapers.platform_detect import detect_platform

PLATFORM_SCRAPERS = {
    "rentcafe": "moxie.scrapers.tier1.rentcafe",
    "ppm":      "moxie.scrapers.tier1.ppm",
    "funnel":   "moxie.scrapers.tier2.funnel",
    "appfolio": "moxie.scrapers.tier2.appfolio",
    "bozzuto":  "moxie.scrapers.tier2.bozzuto",
    "realpage":  "moxie.scrapers.tier2.realpage",
    "groupfox": "moxie.scrapers.tier2.groupfox",
    "llm":      "moxie.scrapers.tier3.llm",
}


def _format_rent(rent_cents: int) -> str:
    """Format rent in cents as a dollar string."""
    if rent_cents == 0:
        return "N/A"
    dollars = rent_cents / 100
    return f"${dollars:,.0f}/mo"


def _print_table(building: Building, platform: str, raw_units: list[dict], saved: bool) -> None:
    """Print a formatted table of scraped units."""
    print(f"\nBuilding:  {building.name}")
    print(f"Platform:  {platform}")
    print(f"URL:       {building.url}")
    print(f"Units found: {len(raw_units)}")

    if not raw_units:
        print("\n(No units returned by scraper.)")
    else:
        # Determine column widths
        col_unit = max(len("Unit"), max(len(str(u.get("unit_number", ""))) for u in raw_units))
        col_beds = max(len("Beds"), max(len(str(u.get("bed_type", ""))) for u in raw_units))
        col_rent = max(len("Rent"), max(
            len(_format_rent(u.get("rent_cents", 0))) for u in raw_units
        ))
        col_avail = max(len("Available"), max(
            len(str(u.get("availability_date", ""))) for u in raw_units
        ))

        header = (
            f" {'Unit':<{col_unit}}  {'Beds':<{col_beds}}  "
            f"{'Rent':<{col_rent}}  {'Available':<{col_avail}}"
        )
        divider = " " + "\u2500" * (len(header) - 1)

        print(f"\n{header}")
        print(divider)
        for u in raw_units:
            unit_num = str(u.get("unit_number", ""))
            bed_type = str(u.get("bed_type", ""))
            rent = _format_rent(u.get("rent_cents", 0))
            avail = str(u.get("availability_date", ""))
            print(
                f" {unit_num:<{col_unit}}  {bed_type:<{col_beds}}  "
                f"{rent:<{col_rent}}  {avail:<{col_avail}}"
            )

    print()
    if saved:
        print("(Saved to database.)")
    else:
        print("(Not saved to database. Run with --save to persist.)")


def main() -> None:
    """CLI entrypoint registered as `scrape` in pyproject.toml."""
    parser = argparse.ArgumentParser(
        description="Spot-check a single building by running its scraper and printing results."
    )
    parser.add_argument(
        "--building",
        required=True,
        metavar="NAME_OR_URL",
        help="Building name (partial match) or full URL (auto-detected if starts with http)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Persist scrape results to the database (default: dry-run, no DB write)",
    )
    args = parser.parse_args()

    db_gen = get_db()
    db = next(db_gen)
    try:
        query = args.building.strip()

        # 1. Look up building
        if query.startswith("http"):
            building = db.query(Building).filter_by(url=query).first()
            if building is None:
                print(f"ERROR: No building found with URL: {query}")
                raise SystemExit(1)
        else:
            matches = (
                db.query(Building)
                .filter(Building.name.ilike(f"%{query}%"))
                .all()
            )
            if not matches:
                print(f"ERROR: No building found matching \"{query}\"")
                raise SystemExit(1)
            if len(matches) > 1:
                print(f"Multiple buildings match \"{query}\":")
                for i, b in enumerate(matches, 1):
                    platform_label = b.platform or "unknown"
                    print(f"  {i}. {b.name} \u2014 {b.url} (platform: {platform_label})")
                print()
                print("Use --building with a more specific name or pass the URL directly.")
                raise SystemExit(1)
            building = matches[0]

        # 2. Determine platform
        platform = building.platform or detect_platform(building.url or "") or "llm"

        # 3. Validate platform is supported
        if platform not in PLATFORM_SCRAPERS:
            print(f"ERROR: Unknown platform \"{platform}\" for building \"{building.name}\".")
            print(f"       Supported platforms: {', '.join(sorted(PLATFORM_SCRAPERS))}")
            raise SystemExit(1)

        # 4. Dispatch to scraper
        mod = importlib.import_module(PLATFORM_SCRAPERS[platform])
        raw_units: list[dict] = mod.scrape(building)

        # 5. Optionally save
        if args.save:
            save_scrape_result(db, building, raw_units, scrape_succeeded=True)
            db.commit()

        # 6. Print results
        _print_table(building, platform, raw_units, saved=args.save)

    except SystemExit:
        raise
    except Exception as e:
        exc_type = type(e).__name__
        print(f"ERROR: [{exc_type}] {e}")
        raise SystemExit(1)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
