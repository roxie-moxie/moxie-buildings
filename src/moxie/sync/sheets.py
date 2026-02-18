"""
Google Sheets sync — pulls building list from the configured tab and upserts into the DB.

Real sheet schema (Building Prices tab):
  Column A (no header)  → building name
  Website               → url (upsert key)
  Neighborhood          → neighborhood
  Managment             → management_company  (note: typo in source sheet)
  All other columns (pricing, contact info, etc.) are ignored.

Entrypoint: moxie.sync.sheets:main (registered as `sheets-sync` in pyproject.toml)
"""

from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH, GOOGLE_SHEETS_TAB_NAME
from moxie.db.models import Building
from moxie.db.session import get_db

import gspread
from sqlalchemy.orm import Session


def _parse_rows(raw: list[list]) -> list[dict]:
    """Parse get_all_values() output into a list of building dicts.

    Sheet structure:
    - Column A (index 0) has no header; contains the building name.
    - Remaining columns are identified by their header text.
    - Columns with blank headers (e.g. trailing empty columns) are skipped.
    - Rows where both name and Website are blank are skipped (empty rows).

    Returns list of dicts with keys: name, url, neighborhood, management_company.
    Rows without a Website URL are included with url="" so the caller can decide
    whether to skip or log them.
    """
    if not raw:
        return []

    headers = raw[0]
    # Map header text → column index, ignoring blank headers
    col = {h.strip(): i for i, h in enumerate(headers) if h.strip()}

    def cell(row: list, key: str) -> str:
        idx = col.get(key)
        if idx is None or idx >= len(row):
            return ""
        return str(row[idx]).strip()

    buildings = []
    for row in raw[1:]:
        name = str(row[0]).strip() if row else ""
        url = cell(row, "Website")

        if not name and not url:
            continue  # blank row

        buildings.append({
            "name": name,
            "url": url,
            "neighborhood": cell(row, "Neighborhood") or None,
            "management_company": cell(row, "Managment") or None,  # sheet typo
        })

    return buildings


def sheets_sync(db: Session) -> dict:
    """
    Pull all rows from the configured tab and upsert them into the buildings table.
    Deletes any DB buildings whose URL no longer appears in the sheet.
    Skips rows that have no Website URL (can't upsert without a unique key).

    Returns:
        dict with keys 'added', 'updated', 'deleted', 'skipped'.

    Raises:
        ValueError: if no buildings with a URL are found (wrong tab name,
                    sheet not shared, or Website column missing).
    """
    # 1. Authenticate using service account key file
    gc = gspread.service_account(filename=GOOGLE_SHEETS_KEY_PATH)

    # 2. Open sheet by ID
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)

    # 3. Get the configured tab (case-sensitive)
    worksheet = sh.worksheet(GOOGLE_SHEETS_TAB_NAME)

    # 4. Parse using the real sheet schema
    raw = worksheet.get_all_values()
    buildings = _parse_rows(raw)

    # 5. Guard: need at least one building with a URL to do anything useful
    syncable = [b for b in buildings if b["url"]]
    if not syncable:
        raise ValueError(
            f"Sheets sync found no buildings with a URL in tab '{GOOGLE_SHEETS_TAB_NAME}'. "
            "Check that column A has building names and the 'Website' column has URLs."
        )

    # 6. Build set of all sheet URLs for deletion detection
    sheet_urls = {b["url"] for b in syncable}

    added = updated = deleted = skipped = 0

    # 7. Upsert each building that has a URL; skip those without
    for b in buildings:
        if not b["url"]:
            skipped += 1
            continue

        existing = db.query(Building).filter_by(url=b["url"]).first()
        if existing:
            existing.name = b["name"]
            existing.neighborhood = b["neighborhood"]
            existing.management_company = b["management_company"]
            updated += 1
        else:
            db.add(Building(
                name=b["name"],
                url=b["url"],
                neighborhood=b["neighborhood"],
                management_company=b["management_company"],
                last_scrape_status="never",
            ))
            added += 1

    # 8. Delete DB buildings whose URL is no longer in the sheet
    for building in db.query(Building).all():
        if building.url not in sheet_urls:
            db.delete(building)
            deleted += 1

    # 9. Commit all changes
    db.commit()

    return {"added": added, "updated": updated, "deleted": deleted, "skipped": skipped}


def main():
    """CLI entrypoint registered as `sheets-sync` in pyproject.toml."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        result = sheets_sync(db)
        print(
            f"Added: {result['added']}, Updated: {result['updated']}, "
            f"Deleted: {result['deleted']}, Skipped (no URL): {result['skipped']}"
        )
    except Exception as e:
        print(f"Sync failed: {e}")
        raise SystemExit(1)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
