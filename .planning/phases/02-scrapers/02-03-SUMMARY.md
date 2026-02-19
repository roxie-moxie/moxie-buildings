---
phase: 02-scrapers
plan: 03
subsystem: sync
tags: [sqlalchemy, gspread, platform-detection, sheets-sync, sqlite, pytest]

# Dependency graph
requires:
  - phase: 02-scrapers
    plan: 01
    provides: detect_platform(), Building model with platform field
  - phase: 01-foundation
    plan: 03
    provides: sheets_sync(), _parse_rows(), Building upsert logic

provides:
  - sheets_sync() extended with post-upsert platform detection pass
  - Platform detection integration: fills Building.platform for all null-platform buildings after every sync
  - "Fills blanks only" contract: existing non-null platform values are never overwritten by detection
  - 5 new TestPlatformDetection tests covering rentcafe, llm fallback, preserved existing, new buildings, pre-existing unclassified

affects: [02-04, 02-05, 02-06, 02-07, 02-08, 02-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "db.flush() before cross-session query: newly-added ORM objects must be flushed before they appear in subsequent filter() queries when autoflush=False"
    - "Platform detection as post-upsert pass: classify all null-platform buildings in one query after upsert loop completes"

key-files:
  created: []
  modified:
    - src/moxie/sync/sheets.py
    - tests/test_sheets_sync.py

key-decisions:
  - "db.flush() required before detection query — SQLite in-memory sessions with autoflush=False do not auto-flush newly-added objects before a filter() query"
  - "Detection pass queries all Building rows with platform IS NULL (not just those just upserted) — catches buildings from prior sync passes that were missed"
  - "detect_platform() returns None for unrecognized URLs; sheets_sync assigns 'llm' to those — caller assigns llm, consistent with 02-01 decision"

patterns-established:
  - "Post-upsert classification pass: flush() then query(Model).filter(col.is_(None)) to classify all unclassified rows in one pass"

requirements-completed: [SCRAP-01, SCRAP-02, SCRAP-03, SCRAP-04, SCRAP-05, SCRAP-06, SCRAP-07, SCRAP-08, SCRAP-09]

# Metrics
duration: 12min
completed: 2026-02-18
---

# Phase 02 Plan 03: Platform Detection Integration in sheets_sync() Summary

**sheets_sync() extended with a post-upsert platform detection pass that classifies all null-platform buildings using URL pattern matching — 32 tests pass, zero regressions across 121-test suite**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-18T20:09:48Z
- **Completed:** 2026-02-18T20:21:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added `from moxie.scrapers.platform_detect import detect_platform` import to sheets.py
- Inserted platform detection pass after upsert loop (step 7b): `db.flush()` then query all buildings with `platform IS NULL`, classify each via `detect_platform(url)`, assign result or 'llm'
- "Fills blanks only" contract enforced: the query only touches buildings where `platform IS NULL`, so existing values are never touched
- Updated module and function docstrings to document platform detection behavior
- Added 5 tests in `TestPlatformDetection`: rentcafe URL, llm fallback, existing platform preserved, new building classified immediately, pre-existing unclassified building classified
- Full 121-test suite passes with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend sheets_sync() with platform detection and add tests** - `6b9fa00` (feat)

**Plan metadata:** `[docs commit hash]` (docs: complete plan)

## Files Created/Modified
- `src/moxie/sync/sheets.py` - Added detect_platform import, db.flush() + detection loop after upsert, updated docstrings
- `tests/test_sheets_sync.py` - Added TestPlatformDetection class with 5 behavioral tests

## Decisions Made
- `db.flush()` needed before detection query: with `autoflush=False` (used by test fixture), newly-added Building objects from step 7's `db.add()` calls are not visible to subsequent `db.query().filter()` until flushed. Three tests failed without this — the flush was added as a Rule 1 auto-fix.
- Detection pass queries all null-platform buildings (not just newly upserted ones): buildings from prior sync passes that were missed also get classified on the next sync run. This matches the plan's intent exactly.
- `detect_platform()` returns `None` for unrecognized URLs; `sheets_sync()` assigns `'llm'` — consistent with the [02-01] decision that callers assign 'llm', not the detector.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added db.flush() before detection query**
- **Found during:** Task 1 (platform detection integration)
- **Issue:** 3 of 5 new tests failed because newly-added Building objects (via `db.add()`) were not visible to the subsequent `db.query(Building).filter(Building.platform.is_(None))` query. The test session uses `autoflush=False`, so ORM objects weren't flushed before the filter query ran.
- **Fix:** Added `db.flush()` immediately before the detection loop. This ensures all upserted buildings from step 7 are visible in the detection pass without fully committing.
- **Files modified:** src/moxie/sync/sheets.py
- **Verification:** All 5 new tests pass after adding flush; all 121 tests pass.
- **Committed in:** 6b9fa00 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix is essential for correctness — without flush(), detection silently skips newly-added buildings in autoflush=False sessions (the default for production via `get_db()`). No scope creep.

## Issues Encountered
- `uv` not on PATH in Bash shell on Windows — used full path `C:\Users\eimil\AppData\Local\Programs\Python\Python313\Scripts\uv.exe` via PowerShell, consistent with previous plans.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `sheets_sync()` now fully implements the locked "detection fills blanks only" decision from pre-phase planning
- Every buildings row that lands in the DB from a sync pass has its platform classified immediately
- Phase 2 scrapers (plans 04-09) can `db.query(Building).filter_by(platform='rentcafe')` to get the right buildings for each scraper
- The `TestPlatformDetection` class serves as a regression guard for the "fills blanks only" contract

---
*Phase: 02-scrapers*
*Completed: 2026-02-18*

## Self-Check: PASSED

- src/moxie/sync/sheets.py: FOUND
- tests/test_sheets_sync.py: FOUND
- .planning/phases/02-scrapers/02-03-SUMMARY.md: FOUND
- Commit 6b9fa00: FOUND (feat(02-03): integrate platform detection into sheets_sync())
