"""
One-time bootstrap: write DB platform values into the Google Sheet's Platform column.

Run this ONCE before switching to the "sheet wins" sync model so that Alex starts
with pre-populated platform values to review and correct, rather than 400+ blank cells.

Usage:
    uv run export-platforms

Behavior:
- Reads every building from the DB (url → platform).
- Opens the configured Google Sheet tab.
- Adds a "Platform" header in the next available column if the column doesn't exist.
- Writes the DB platform value (or "needs_classification" if null) next to each row
  matched by URL. Overwrites any existing values in the Platform column.
- Rows with no Website URL are skipped (nothing to match on).

After this runs:
1. CC confirms the sheet looks right.
2. Alex reviews/corrects platform values at his own pace.
3. The next `sheets-sync` run picks up sheet values as authoritative (sheet wins).

Entrypoint: moxie.sync.export_platforms:main (registered as `export-platforms`)
"""

import gspread
import gspread.utils
from sqlalchemy.orm import Session

from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH, GOOGLE_SHEETS_TAB_NAME
from moxie.db.models import Building
from moxie.db.session import get_db


def export_platforms(db: Session) -> dict:
    """
    Write building platform values from the DB into the Google Sheet.

    Returns dict with keys 'written' (rows updated) and 'skipped' (no URL match).

    Raises:
        ValueError: if the sheet is empty or has no Website column.
    """
    # 1. Authenticate and open sheet
    gc = gspread.service_account(filename=GOOGLE_SHEETS_KEY_PATH)
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)
    worksheet = sh.worksheet(GOOGLE_SHEETS_TAB_NAME)

    raw = worksheet.get_all_values()
    if not raw:
        raise ValueError("Sheet is empty — nothing to export to.")

    headers = [h.strip() for h in raw[0]]

    if "Website" not in headers:
        raise ValueError(
            f"'Website' column not found in sheet tab '{GOOGLE_SHEETS_TAB_NAME}'. "
            "Check the tab name in your .env file."
        )
    url_col = headers.index("Website")

    # 2. Find or create Platform column
    if "Platform" in headers:
        platform_col = headers.index("Platform")
    else:
        # Append as the next column after existing headers
        platform_col = len(headers)
        worksheet.update_cell(1, platform_col + 1, "Platform")

    # 3. Build URL → platform map from DB
    url_to_platform: dict[str, str] = {
        b.url: (b.platform or "needs_classification")
        for b in db.query(Building).all()
        if b.url
    }

    # 4. Build batch updates (one cell per data row with a matching URL)
    updates: list[dict] = []
    skipped = 0

    for sheet_row_idx, row in enumerate(raw[1:], start=2):  # 1-indexed; row 1 is header
        url = row[url_col].strip() if url_col < len(row) else ""
        if not url:
            skipped += 1
            continue

        platform_value = url_to_platform.get(url)
        if platform_value is None:
            # URL is in sheet but not in DB — skip rather than guess
            skipped += 1
            continue

        cell_a1 = gspread.utils.rowcol_to_a1(sheet_row_idx, platform_col + 1)
        updates.append({"range": cell_a1, "values": [[platform_value]]})

    if updates:
        worksheet.batch_update(updates)

    return {"written": len(updates), "skipped": skipped}


def main() -> None:
    """CLI entrypoint registered as `export-platforms` in pyproject.toml."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        result = export_platforms(db)
        print(
            f"Platform column written: {result['written']} rows. "
            f"Skipped (no URL match): {result['skipped']}."
        )
    except Exception as e:
        print(f"Export failed: {e}")
        raise SystemExit(1)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
