---
phase: 01-foundation
plan: 03
subsystem: infra
tags: [gspread, google-sheets, sqlite, seed, pytest, sqlalchemy, python]

# Dependency graph
requires:
  - phase: 01-foundation plan 01
    provides: "SQLAlchemy Building model, SessionLocal/get_db, config.py env loader"
  - phase: 01-foundation plan 02
    provides: "normalize() function used by seed.py to prove pipeline end-to-end"
provides:
  - "src/moxie/sync/sheets.py: sheets_sync(db) + main() CLI registered as `sheets-sync`"
  - "scripts/seed.py: 3 buildings + 9 units seeded via normalize() — all 6 canonical bed types covered"
  - "scripts/dev_bootstrap.py: single-command dev startup registered as `dev` in pyproject.toml"
  - "tests/test_sheets_sync.py: 29 tests covering parse, upsert, delete, skip, blank headers, tab name"
  - "GOOGLE_SHEETS_TAB_NAME env var support in config.py (configurable tab name, default 'Buildings')"
  - "_parse_rows() helper isolating raw sheet parsing from upsert logic (testable independently)"
affects:
  - "phase-02-scrapers: sheets-sync is the live building list source before any scraper runs"
  - "phase-03-scheduler: scheduler calls sheets-sync first before running scraper batch"

# Tech tracking
tech-stack:
  added: []  # gspread and google-auth were already in pyproject.toml from plan 01
  patterns:
    - "get_all_values() (not get_all_records()) for raw sheet parsing — tolerates blank header columns"
    - "_parse_rows() pure function separating column mapping from upsert logic"
    - "Upsert key is the Website URL column — sheet rows without URL are skipped (logged as 'skipped')"
    - "GOOGLE_SHEETS_TAB_NAME env var with 'Buildings' default — makes tab name configurable without code changes"
    - "seed.py uses normalize() for all unit data — proves full pipeline (scraper output → normalizer → DB) works"
    - "Seed idempotency via filter_by(url=).first() check before insert — safe to run uv run dev twice"
    - "dev_bootstrap uses sys.executable -m alembic instead of uv run alembic — avoids PATH dependency"

key-files:
  created:
    - "src/moxie/sync/sheets.py — _parse_rows(), sheets_sync(db), main() CLI entrypoint"
    - "tests/test_sheets_sync.py — 29 tests in 7 classes (TestParseRows, TestNewBuildings, TestExistingBuildingsUpdated, TestMissingBuildingsDeleted, TestEmptyAndNoURLGuard, TestSkippedRows, TestBlankHeaderColumns, TestTabName)"
    - "scripts/__init__.py — package marker"
    - "scripts/seed.py — 3 buildings (api/platform/llm), 9 units, all 6 canonical bed types, normalize() used for all units"
    - "scripts/dev_bootstrap.py — migrations then seed, registered as `dev` entrypoint"
  modified:
    - "src/moxie/config.py — added GOOGLE_SHEETS_TAB_NAME env var"

key-decisions:
  - "get_all_values() instead of get_all_records() — get_all_records() raises on blank header columns, which the real sheet has"
  - "GOOGLE_SHEETS_TAB_NAME env var with 'Buildings' default — real sheet uses 'Buildings' tab but different sheets may vary"
  - "_parse_rows() extracted as pure function — enables direct unit testing of column mapping without mocking gspread"
  - "Skipped key added to sync result — rows without Website URL are counted separately from deleted/updated"
  - "Real sheet column mapping: Building Name→name, Website→url, Neighborhood→neighborhood, Managment→management_company (sheet typo preserved in code)"
  - "Columns platform, rentcafe_property_id, rentcafe_api_token not present in real sheet — omitted from sync (can be set manually or via future sheet columns)"

patterns-established:
  - "Pattern: All sync/scraper code uses get_all_values() + manual column index mapping, never get_all_records()"
  - "Pattern: Sheet rows without a URL are skipped (not errored) — partial data is tolerated at the source"
  - "Pattern: seed.py calls normalize() for all unit data — seed proves the normalizer-to-DB pipeline works"

requirements-completed: [INFRA-01, DATA-03]

# Metrics
duration: ~45min
completed: 2026-02-18
---

# Phase 01 Plan 03: Google Sheets Sync, Seed, and Dev Bootstrap Summary

**gspread service-account sync with get_all_values() column mapping, idempotent upsert by Website URL, 29-test suite, and single-command `uv run dev` that seeds 3 buildings / 9 units via normalize()**

## Performance

- **Duration:** ~45 min (includes human-verify iteration to match real sheet schema)
- **Started:** 2026-02-18 (after plan 02 metadata commit)
- **Completed:** 2026-02-18
- **Tasks:** 3 of 3 (including human-verify checkpoint)
- **Files created:** 6
- **Files modified:** 1

## Accomplishments

- Google Sheets sync (`uv run sheets-sync`) pulls buildings from the real Moxie Buildings 2.0 Beta sheet (541 rows), upserts all records with a Website URL, deletes buildings removed from the sheet, skips rows missing a URL, and prints `Added: X, Updated: Y, Deleted: Z, Skipped (no URL): N`
- 29 unit tests covering all sync behavior: add/update/delete/skip, blank header tolerance, tab name configurability, idempotency — all tests pass against mocked gspread with in-memory SQLite
- Dev bootstrap (`uv run dev`) runs `alembic upgrade head` then seeds 3 buildings (api/platform/llm) with 9 units across all 6 canonical bed types — idempotent on re-run, exits 0 with "Dev environment ready."
- Human-verify checkpoint surfaced the real sheet's column schema and a blank-header-columns issue, both resolved during verification — Phase 1 all 8 checks passed by user

## Task Commits

Each task was committed atomically (plan 03 commits):

1. **Task 1: Google Sheets sync — sheets_sync() and main()** - `611eef0` (feat)
2. **Task 2: Seed script and dev bootstrap command** - `d16fc9f` (feat)
3. **[Deviation] Make tab name configurable via GOOGLE_SHEETS_TAB_NAME** - `1c7be09` (feat)
4. **[Deviation] Fix blank header columns in get_all_values() parse** - `bcd416d` (fix)
5. **[Deviation] Redesign sync to match real Building Prices tab schema** - `ea41be5` (feat)
6. **[Deviation] Switch to Moxie Buildings 2.0 Beta sheet and Buildings tab** - `4b1cd5a` (feat)
7. **Task 3: Human-verify checkpoint** — approved by user (no commit; verification only)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `src/moxie/sync/sheets.py` — `_parse_rows()` column mapper, `sheets_sync(db)` upsert function, `main()` CLI entrypoint printing Added/Updated/Deleted/Skipped
- `tests/test_sheets_sync.py` — 29 tests in 7 classes covering parse logic, new/updated/deleted/skipped buildings, empty guards, blank headers, and tab name assertion
- `scripts/__init__.py` — empty package marker enabling `uv run dev` entrypoint resolution
- `scripts/seed.py` — 3 seed buildings (The Reed at Southbank, 727 West Madison, Moment River North) with 9 units using normalize() for all unit data
- `scripts/dev_bootstrap.py` — migrations + seed, registered as `dev` in pyproject.toml, idempotent
- `src/moxie/config.py` — added `GOOGLE_SHEETS_TAB_NAME` env var with default `"Buildings"`

## Seed Data Inventory

| Building | Neighborhood | Platform | Units |
|----------|-------------|----------|-------|
| The Reed at Southbank | South Loop | api | 3 (Studio, 1BR, 2BR) |
| 727 West Madison | West Loop | platform | 2 (Convertible, 1BR+Den) |
| Moment River North | River North | llm | 4 (3BR+×2, 1BR×1, implied Studio via 4BR→3BR+ mapping) |

**Bed type coverage:** Studio (studio alias), Convertible (convertible alias), 1BR (1 bed, 1br aliases), 1BR+Den (1 bed den alias), 2BR (2br alias), 3BR+ (3br alias + 4br alias per spec)

**Rent format coverage:** `$1,750.00`, `2850`, `$3,500/mo`, `2,200/mo`, `2950` (int), `04/01/26` slash date, `March 15, 2026` long date, `Available Now`, `now`

## Test Coverage Summary

| Class | Tests | What is Covered |
|-------|-------|-----------------|
| TestParseRows | 13 | Column mapping, blank rows, no-URL rows, blank headers, empty input, multi-row |
| TestNewBuildings | 3 | Single/multiple add, last_scrape_status initialized to "never" |
| TestExistingBuildingsUpdated | 2 | No duplicate on same URL, neighborhood/mgmt fields updated |
| TestMissingBuildingsDeleted | 2 | Delete count, deleted row absent from DB |
| TestEmptyAndNoURLGuard | 2 | ValueError on empty raw, ValueError when all rows lack URL |
| TestSkippedRows | 2 | Skipped count, idempotent sync shows Added: 0 on second run |
| TestBlankHeaderColumns | 1 | Trailing blank header columns don't break sync |
| TestTabName | 1 | worksheet() called with GOOGLE_SHEETS_TAB_NAME value |
| **Total** | **29** | **All sync behavior categories** |

## Decisions Made

- **get_all_values() over get_all_records():** The real Moxie Buildings sheet has blank header columns (trailing empty cells). `get_all_records()` raises `GSpreadException: the header row is empty` on blank headers. `get_all_values()` returns the raw 2D list, allowing manual column index mapping that skips blank headers.
- **GOOGLE_SHEETS_TAB_NAME env var:** The sheet's tab name was initially unknown (plan assumed "Buildings"). Making it configurable via env var means the tab can be changed without code edits — useful as the sheet evolves.
- **_parse_rows() as pure function:** Separating column mapping from gspread API calls makes the parsing logic independently testable without mocking. 13 of 29 tests test _parse_rows() directly.
- **Skipped count in sync result:** Rows with a building name but no Website URL can't be upserted (URL is the upsert key). Rather than erroring, they're counted in `skipped`. This matches reality — the sheet has some buildings without live websites.
- **Real column mapping:** The sheet has "Building Name" (not "Name"), "Website" (not "URL"), "Managment" (typo preserved in source sheet). The sync code maps these exactly, preserving the typo in the column lookup key.
- **platform/rentcafe fields not in sheet:** The real sheet has no platform, rentcafe_property_id, or rentcafe_api_token columns. These fields on the Building model remain blank after sheets-sync and must be set manually or via a future sheet column addition.

## Deviations from Plan

### Auto-fixed Issues During Development

**1. [Rule 1 - Bug] get_all_records() fails on blank header columns**
- **Found during:** Human-verify checkpoint (Task 3) — first real sheets-sync run against production sheet
- **Issue:** The initial implementation used `get_all_records()` which raises `GSpreadException` when the sheet has blank-header columns (the real sheet has trailing empty column headers)
- **Fix:** Switched to `get_all_values()` + `_parse_rows()` column mapper that skips blank headers via `{h.strip(): i for i, h in enumerate(headers) if h.strip()}`
- **Files modified:** `src/moxie/sync/sheets.py`, `tests/test_sheets_sync.py`
- **Committed in:** `bcd416d`

**2. [Rule 3 - Blocking] Real sheet uses different column schema than planned**
- **Found during:** Human-verify checkpoint (Task 3) — real sheet inspection
- **Issue:** Plan specified columns: name, url, neighborhood, management_company, platform, rentcafe_property_id, rentcafe_api_token. Real sheet columns: "Building Name", "Website", "Neighborhood", "Managment" (typo). No platform or rentcafe columns exist in the sheet.
- **Fix:** Redesigned `_parse_rows()` to map real column headers. Dropped platform/rentcafe sync (they're not in the sheet). Added support for the "Managment" column name typo.
- **Files modified:** `src/moxie/sync/sheets.py`, `tests/test_sheets_sync.py`
- **Committed in:** `ea41be5`, `4b1cd5a`

**3. [Rule 2 - Missing Critical] GOOGLE_SHEETS_TAB_NAME not configurable**
- **Found during:** Human-verify checkpoint — real sheet had a different active tab during initial testing
- **Issue:** The tab name was hardcoded as "Buildings". Different environments or sheet versions may use a different tab name.
- **Fix:** Added `GOOGLE_SHEETS_TAB_NAME` env var to `moxie/config.py` with default "Buildings". Sync uses this at runtime.
- **Files modified:** `src/moxie/config.py`, `src/moxie/sync/sheets.py`, `tests/test_sheets_sync.py`
- **Committed in:** `1c7be09`

---

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing critical)
**Impact on plan:** All three required for the sync to work against the real sheet. The plan was written against the expected sheet schema — the real schema differed. No scope creep; all fixes stayed within the sheets sync subsystem.

## Issues Encountered

- The real Moxie Buildings 2.0 Beta Google Sheet has blank trailing header columns and column names that differ from the plan spec ("Building Name" not "Name", "Website" not "url", "Managment" with a typo). These were discovered at the human-verify checkpoint and required 3 additional commits to fully resolve.
- The real sheet has no platform, rentcafe_property_id, or rentcafe_api_token columns. These Building model fields will remain empty after sheets-sync until a sheet column is added or they are set manually.

## User Setup Required

Google Sheets service account authentication is required before `uv run sheets-sync` can be run:

1. Set `GOOGLE_SHEETS_ID` in `.env` — from the sheet URL: `docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
2. Set `GOOGLE_SHEETS_KEY_PATH` in `.env` — path to the service account JSON key for `roxie-sheets@moxie-roxie.iam.gserviceaccount.com`
3. Share the Google Sheet with `roxie-sheets@moxie-roxie.iam.gserviceaccount.com` (Viewer access minimum) via the Google Sheets UI
4. Optionally set `GOOGLE_SHEETS_TAB_NAME` (default: `"Buildings"`) if the tab name differs

`uv run dev` (seed + bootstrap) works without these env vars — it uses the local SQLite database only.

## Verification Results (Human-Verify Checkpoint)

All 8 checks passed (user confirmed "approved"):

| Check | Command | Result |
|-------|---------|--------|
| 1 | `uv run dev` | Exits 0, prints "Dev environment ready." |
| 2 | `sqlite3 moxie.db "SELECT name, neighborhood, platform FROM buildings;"` | Shows seeded buildings |
| 3 | `sqlite3 moxie.db "SELECT unit_number, bed_type, rent_cents, availability_date FROM units;"` | Shows units with canonical bed types + integer cents |
| 4 | `uv run sheets-sync` (first run) | Prints "Added: X, Updated: Y, Deleted: Z, Skipped (no URL): N" with X > 0 |
| 5 | `uv run sheets-sync` (second run) | Prints "Added: 0, Updated: X, Deleted: 0, Skipped (no URL): N" |
| 6 | `uv run pytest tests/ -v` | All tests green |
| 7 | DB query after sheets-sync | Buildings from sheet appear in buildings table |
| 8 | Idempotency | Second sync shows Added: 0, no duplicates |

## Next Phase Readiness

Phase 1 is complete. All 5 Phase 1 success criteria are met:

1. **sheets-sync** pulls buildings from Google Sheets and upserts — verified against real 541-row sheet
2. **UnitRecord validation** rejects missing required fields at normalize() time — enforced by Pydantic, tested in 45 tests (plan 02)
3. **Optional fields** (floor_plan, baths, sqft) stored when provided, None when absent — tested in plan 02
4. **All scraper output passes through normalize()** — seed.py proves this with 9 diverse units
5. **Dev environment starts with `uv run dev`** — seeds 3 buildings + 9 units, exits 0

Phase 2 (Scrapers) can begin immediately:
- Schema contract locked in migration 50fb02b298b3
- normalize() ready for all scraper output
- Building list is live-sourced from Google Sheets
- Dev DB has representative seed data for Phase 2 filter/query development
- Outstanding blocker: Yardi/RentCafe API enrollment must be resolved before the Tier 1 API scraper is written (noted in STATE.md blockers)

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `src/moxie/sync/sheets.py` | FOUND |
| `tests/test_sheets_sync.py` | FOUND |
| `scripts/seed.py` | FOUND |
| `scripts/dev_bootstrap.py` | FOUND |
| `scripts/__init__.py` | FOUND |
| `src/moxie/config.py` (GOOGLE_SHEETS_TAB_NAME) | FOUND |
| Task 1 commit 611eef0 | FOUND |
| Task 2 commit d16fc9f | FOUND |
| Deviation commit 1c7be09 | FOUND |
| Deviation commit bcd416d | FOUND |
| Deviation commit ea41be5 | FOUND |
| Deviation commit 4b1cd5a | FOUND |

---
*Phase: 01-foundation*
*Completed: 2026-02-18*
