"""Push batch scrape status to Google Sheets 'Scrape Status' tab."""
import logging
from datetime import datetime, timezone

import gspread

from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH

logger = logging.getLogger("moxie.scheduler")


def push_batch_status(results: list[dict]) -> None:
    """
    Write batch results to a 'Scrape Status' tab in the configured Google Sheet.

    Creates the tab if it doesn't exist. Overwrites all rows each run (latest only,
    no history accumulation — per user decision).

    Tab layout:
    - Row 1: Summary — date, total buildings, successes, failures, total units
    - Row 2: blank separator
    - Row 3: Column headers
    - Row 4+: One row per building (building name, platform, status, units, last scraped, error)

    Uses a single ws.update() call for all data — counts as one API request.
    """
    if not results:
        logger.info("No results to push to Scrape Status sheet")
        return

    now = datetime.now(timezone.utc)
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    total_units = sum(r["unit_count"] for r in results)

    # Sort by building name for consistent display
    sorted_results = sorted(results, key=lambda r: r["building_name"].lower())

    # Build all rows in memory
    rows = []

    # Summary row
    rows.append([
        f"Last Run: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Buildings: {len(results)}",
        f"Success: {successes}",
        f"Failed: {failures}",
        f"Total Units: {total_units}",
        "",
    ])

    # Blank separator
    rows.append(["", "", "", "", "", ""])

    # Header
    rows.append(["Building", "Platform", "Status", "Units", "Last Scraped", "Error"])

    # Per-building rows
    for r in sorted_results:
        rows.append([
            r["building_name"],
            r["platform"],
            r["status"],
            r["unit_count"],
            r.get("scraped_at", ""),
            (r.get("error") or "")[:200],  # Truncate long errors
        ])

    # Push to Google Sheets
    try:
        gc = gspread.service_account(filename=GOOGLE_SHEETS_KEY_PATH)
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)

        try:
            ws = sh.worksheet("Scrape Status")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(
                title="Scrape Status",
                rows=max(len(rows) + 10, 500),
                cols=6,
            )

        ws.clear()
        ws.update(rows, value_input_option="RAW")  # Single API call for all rows
        logger.info(f"Pushed {len(sorted_results)} rows to 'Scrape Status' sheet tab")

    except Exception as e:
        # Sheet push failure should not crash the batch — it's monitoring, not core function
        logger.error(f"Failed to push batch status to Google Sheets: {e}")
