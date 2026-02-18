"""
Google Sheets sync — pulls building list from the configured tab and upserts into the DB.

Entrypoint: moxie.sync.sheets:main (registered as `sheets-sync` in pyproject.toml)
"""

from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH, GOOGLE_SHEETS_TAB_NAME
from moxie.db.models import Building
from moxie.db.session import get_db

import gspread
from sqlalchemy.orm import Session


def sheets_sync(db: Session) -> dict:
    """
    Pull all rows from the 'Buildings' tab of the configured Google Sheet and
    upsert them into the buildings table. Deletes any DB buildings whose URL
    no longer appears in the Sheet.

    Returns:
        dict with keys 'added', 'updated', 'deleted'.

    Raises:
        ValueError: if the sheet returns suspiciously few rows (wrong tab name or
                    sheet not shared with the service account).
    """
    # 1. Authenticate using service account key file
    gc = gspread.service_account(filename=GOOGLE_SHEETS_KEY_PATH)

    # 2. Open sheet by ID
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)

    # 3. Get the configured tab (case-sensitive; defaults to "Buildings")
    worksheet = sh.worksheet(GOOGLE_SHEETS_TAB_NAME)

    # 4. Read all values and build dicts manually, skipping blank-header columns.
    # get_all_records() raises on duplicate headers (including multiple empty ones),
    # which breaks on sheets that have trailing blank columns.
    raw = worksheet.get_all_values()
    if raw:
        headers = raw[0]
        valid_indices = [i for i, h in enumerate(headers) if h.strip()]
        valid_headers = [headers[i] for i in valid_indices]
        rows = [
            {valid_headers[j]: (row[i] if i < len(row) else "")
             for j, i in enumerate(valid_indices)}
            for row in raw[1:]
        ]
    else:
        rows = []

    # 5. Guard against silent empty return (wrong tab name or not shared)
    if len(rows) < 1:
        raise ValueError(
            f"Sheets sync returned suspiciously few rows: {len(rows)}. "
            f"Check tab name '{GOOGLE_SHEETS_TAB_NAME}' and that the sheet is shared with the service account."
        )

    # 6. Build set of all Sheet URLs for deletion detection
    sheet_urls = {row["url"] for row in rows}

    added = 0
    updated = 0

    # 7. Upsert each row
    for row in rows:
        existing = db.query(Building).filter_by(url=row["url"]).first()
        if existing:
            existing.name = row["name"]
            existing.neighborhood = row.get("neighborhood") or None
            existing.management_company = row.get("management_company") or None
            existing.platform = row.get("platform") or None
            existing.rentcafe_property_id = row.get("rentcafe_property_id") or None
            existing.rentcafe_api_token = row.get("rentcafe_api_token") or None
            updated += 1
        else:
            db.add(Building(
                name=row["name"],
                url=row["url"],
                neighborhood=row.get("neighborhood") or None,
                management_company=row.get("management_company") or None,
                platform=row.get("platform") or None,
                rentcafe_property_id=row.get("rentcafe_property_id") or None,
                rentcafe_api_token=row.get("rentcafe_api_token") or None,
                last_scrape_status="never",
            ))
            added += 1

    # 8. Delete DB buildings whose URL is no longer in the Sheet
    deleted = 0
    all_db_buildings = db.query(Building).all()
    for building in all_db_buildings:
        if building.url not in sheet_urls:
            db.delete(building)
            deleted += 1

    # 9. Commit all changes
    db.commit()

    return {"added": added, "updated": updated, "deleted": deleted}


def main():
    """CLI entrypoint registered as `sheets-sync` in pyproject.toml."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        result = sheets_sync(db)
        print(f"Added: {result['added']}, Updated: {result['updated']}, Deleted: {result['deleted']}")
    except Exception as e:
        print(f"Sync failed: {e}")
        raise SystemExit(1)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
