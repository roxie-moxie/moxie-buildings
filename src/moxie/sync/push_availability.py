"""
Push scraped availability data to a Google Sheets "Availability" tab.

Reads unit records from the DB (joined with buildings) and writes them to a new
"Availability" worksheet in the configured Google Sheet. Also provides a
`validate-building` CLI that scrapes a single building, saves to DB, and pushes
the results to the sheet for visual validation.

Entrypoint: moxie.sync.push_availability:main (registered as `validate-building` in pyproject.toml)
"""

import argparse
import importlib
import sys

import gspread
from sqlalchemy.orm import Session

from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH
from moxie.db.models import Building, Unit
from moxie.db.session import get_db
from moxie.scrapers.base import save_scrape_result
from moxie.scrapers.platform_detect import detect_platform

# Duplicated from scrape.py — keep in sync
PLATFORM_SCRAPERS = {
    "rentcafe": "moxie.scrapers.tier1.rentcafe",
    "ppm":      "moxie.scrapers.tier1.ppm",
    "funnel":   "moxie.scrapers.tier2.funnel",
    "appfolio": "moxie.scrapers.tier2.appfolio",
    "bozzuto":  "moxie.scrapers.tier2.bozzuto",
    "realpage":  "moxie.scrapers.tier2.realpage",
    "groupfox": "moxie.scrapers.tier2.groupfox",
    # Entrata, MRI: no dedicated scraper yet — use LLM as fallback
    "entrata":  "moxie.scrapers.tier3.llm",
    "mri":      "moxie.scrapers.tier3.llm",
    "llm":      "moxie.scrapers.tier3.llm",
}


def _format_rent(rent_cents: int) -> str:
    """Format rent in cents as a dollar string (e.g., 150000 -> '$1,500')."""
    if rent_cents == 0:
        return "N/A"
    dollars = rent_cents / 100
    return f"${dollars:,.0f}"


def push_availability(db: Session, building_ids: list[int] | None = None) -> int:
    """
    Push unit availability data from the DB to a Google Sheets "Availability" tab.

    Queries the units table joined with buildings, formats the data, and writes it
    to the "Availability" worksheet (creating it if it doesn't exist).

    Args:
        db: SQLAlchemy session.
        building_ids: If provided, only include units from these building IDs.

    Returns:
        Number of data rows written (excluding header).
    """
    # 1. Query units joined with buildings
    query = db.query(Unit, Building).join(Building, Unit.building_id == Building.id)
    if building_ids is not None:
        query = query.filter(Building.id.in_(building_ids))
    results = query.all()

    # 2. Build rows sorted by building name then unit number
    rows = []
    for unit, building in results:
        rows.append({
            "building_name": building.name or "",
            "neighborhood": building.neighborhood or "",
            "unit_number": unit.unit_number or "",
            "beds": unit.bed_type or "",
            "rent": _format_rent(unit.rent_cents),
            "available_date": unit.availability_date or "",
            "floor_plan": unit.floor_plan_name or "",
            "baths": unit.baths or "",
            "sqft": str(unit.sqft) if unit.sqft else "",
            "management_company": building.management_company or "",
            "scraped_at": unit.scrape_run_at.strftime("%Y-%m-%d %H:%M UTC") if unit.scrape_run_at else "",
            "url": building.url or "",
        })

    rows.sort(key=lambda r: (r["building_name"].lower(), r["unit_number"]))

    # 3. Authenticate to Google Sheets
    gc = gspread.service_account(filename=GOOGLE_SHEETS_KEY_PATH)
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)

    # 4. Create or get the "Availability" worksheet
    try:
        ws = sh.worksheet("Availability")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="Availability", rows=1000, cols=12)

    # 5. Clear and write data
    ws.clear()

    header = [
        "Building Name", "Neighborhood", "Unit #", "Beds", "Rent",
        "Available Date", "Floor Plan", "Baths", "SqFt",
        "Management Company", "Scraped At", "URL",
    ]

    data_rows = []
    for r in rows:
        data_rows.append([
            r["building_name"],
            r["neighborhood"],
            r["unit_number"],
            r["beds"],
            r["rent"],
            r["available_date"],
            r["floor_plan"],
            r["baths"],
            r["sqft"],
            r["management_company"],
            r["scraped_at"],
            r["url"],
        ])

    # Write header + data in one batch
    all_rows = [header] + data_rows
    if all_rows:
        ws.update(all_rows, value_input_option="RAW")

    return len(data_rows)


def _lookup_building(db: Session, query: str) -> Building:
    """Look up a building by name (partial match) or URL. Same logic as scrape.py."""
    if query.startswith("http"):
        building = db.query(Building).filter_by(url=query).first()
        if building is None:
            print(f"ERROR: No building found with URL: {query}")
            raise SystemExit(1)
        return building

    matches = (
        db.query(Building)
        .filter(Building.name.ilike(f"%{query}%"))
        .all()
    )
    if not matches:
        print(f'ERROR: No building found matching "{query}"')
        raise SystemExit(1)
    if len(matches) > 1:
        print(f'Multiple buildings match "{query}":')
        for i, b in enumerate(matches, 1):
            platform_label = b.platform or "unknown"
            print(f"  {i}. {b.name} -- {b.url} (platform: {platform_label})")
        print()
        print("Use --building with a more specific name or pass the URL directly.")
        raise SystemExit(1)
    return matches[0]


def main() -> None:
    """CLI entrypoint registered as `validate-building` in pyproject.toml."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate a building end-to-end: scrape it, save to DB, "
            "and push results to the Google Sheets Availability tab."
        )
    )
    parser.add_argument(
        "--building",
        required=True,
        metavar="NAME_OR_URL",
        help="Building name (partial match) or full URL",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=True,
        help="Save scrape results to the database (default: True)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        default=False,
        help="Skip saving scrape results to the database",
    )
    parser.add_argument(
        "--platform",
        metavar="PLATFORM",
        help="Override scraper platform (e.g., 'llm' to force LLM fallback)",
    )
    parser.add_argument(
        "--sheet-only",
        action="store_true",
        default=False,
        help="Skip scraping; just push existing DB data to the Availability sheet tab",
    )
    args = parser.parse_args()

    # --no-save overrides --save
    save = args.save and not args.no_save

    db_gen = get_db()
    db = next(db_gen)
    try:
        building = _lookup_building(db, args.building.strip())

        if args.sheet_only:
            # Just push existing DB data to the sheet
            print(f"Building:  {building.name}")
            print(f"Mode:      sheet-only (no scraping)")
            count = push_availability(db, building_ids=[building.id])
            print(f"Pushed {count} unit(s) to Availability tab.")
        else:
            # Full pipeline: scrape -> save -> push
            # 1. Determine platform (--platform override wins)
            if args.platform:
                platform = args.platform
            else:
                raw_platform = building.platform
                if raw_platform in (None, "needs_classification"):
                    raw_platform = detect_platform(building.url or "")
                platform = raw_platform or "llm"

            # 2. Validate platform is supported
            if platform not in PLATFORM_SCRAPERS:
                print(f'ERROR: Unknown platform "{platform}" for building "{building.name}".')
                print(f"       Supported platforms: {', '.join(sorted(PLATFORM_SCRAPERS))}")
                raise SystemExit(1)

            print(f"Building:  {building.name}")
            print(f"Platform:  {platform}")
            print(f"URL:       {building.url}")

            # 3. Dispatch to scraper
            mod = importlib.import_module(PLATFORM_SCRAPERS[platform])
            raw_units: list[dict] = mod.scrape(building)
            print(f"Units scraped: {len(raw_units)}")

            # 4. Save to DB
            if save:
                save_scrape_result(db, building, raw_units, scrape_succeeded=True)
                db.commit()
                print("Saved to database.")

            # 5. Push to sheet
            count = push_availability(db, building_ids=[building.id])
            print(f"Pushed {count} unit(s) to Availability tab.")

            # 6. Summary
            print()
            print(f"--- Validation Summary ---")
            print(f"Building:     {building.name}")
            print(f"Platform:     {platform}")
            print(f"Units scraped: {len(raw_units)}")
            print(f"Units in sheet: {count}")
            if save:
                print("DB status:    saved")
            else:
                print("DB status:    not saved (--no-save)")

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
