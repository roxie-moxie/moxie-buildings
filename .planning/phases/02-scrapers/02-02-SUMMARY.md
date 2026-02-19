---
phase: 02-scrapers
plan: 02
subsystem: testing
tags: [pytest, sqlalchemy, sqlite, in-memory-db, parametrize, behavioral-tests]

# Dependency graph
requires:
  - phase: 02-scrapers
    plan: 01
    provides: save_scrape_result(), detect_platform(), CONSECUTIVE_ZERO_THRESHOLD, Building/Unit/ScrapeRun models

provides:
  - 18 parametrized tests for detect_platform() covering all 8 known platforms, subdomains, case-insensitive, path-vs-hostname, unknown, empty string
  - 26 behavioral tests for save_scrape_result() covering success+units, success+zero, zero-at-threshold, failure paths
  - In-memory SQLite fixture pattern for all future scraper integration tests
  - Regression protection for consecutive_zero_count, needs_attention threshold, unit retention on failure

affects: [02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09]

# Tech tracking
tech-stack:
  added: []
  patterns: [in-memory SQLite fixture via create_engine("sqlite:///:memory:"), pytest class-based test organization by behavior path, parametrize for URL pattern coverage]

key-files:
  created:
    - tests/test_platform_detect.py
    - tests/test_save_scrape_result.py
  modified: []

key-decisions:
  - "In-memory SQLite per test (not shared session) — each test gets a fresh DB, no state leakage between tests"
  - "Class-based test grouping by behavior path (TestSaveSuccessWithUnits, etc.) — mirrors the 4-path behavioral spec from RESEARCH.md"
  - "Real normalize() used in tests (not mocked) — tests also validate normalization pipeline end-to-end"

patterns-established:
  - "In-memory SQLite fixture: create_engine('sqlite:///:memory:'), Base.metadata.create_all(engine), fresh session per test"
  - "Helper _insert_unit() for pre-existing unit setup in failure/retention tests"
  - "CONSECUTIVE_ZERO_THRESHOLD imported from moxie.scrapers.base — tests pin the constant, not a hardcoded 5"

requirements-completed: [INFRA-03]

# Metrics
duration: 8min
completed: 2026-02-18
---

# Phase 02 Plan 02: Behavioral Tests for detect_platform() and save_scrape_result() Summary

**44 pytest tests covering all 8 platform URL patterns and 4 save_scrape_result() behavior paths using in-memory SQLite — zero failures, zero regressions across 116-test suite**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-18T19:45:11Z
- **Completed:** 2026-02-18T19:53:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- 18 parametrized detect_platform() tests: all 8 known platform domains, subdomain variants, case-insensitive matching, path-not-hostname guard, unknown URLs, empty string
- 26 save_scrape_result() behavioral tests organized into 5 classes: success+units (6), success+zero (5), zero-at-threshold (5), failure path (8), multi-call behavior (2)
- All tests run with in-memory SQLite — no .env, no file DB, no external services needed
- Full 116-test suite passes with zero regressions against Phase 1 tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for detect_platform() and save_scrape_result()** - `9fc1029` (test)

**Plan metadata:** `[docs commit hash]` (docs: complete plan)

## Files Created/Modified
- `tests/test_platform_detect.py` - 18 tests: parametrized URL-to-platform mapping, edge cases (case-insensitive, path-not-hostname, empty string)
- `tests/test_save_scrape_result.py` - 26 tests: 4 behavior paths with in-memory SQLite fixtures, pre-insert helpers, multi-call scenarios

## Decisions Made
- In-memory SQLite per test (not shared): each test creates its own engine and session via the `db` fixture, preventing any state leakage between tests
- Class-based grouping by path (TestSaveSuccessWithUnits, TestSaveSuccessZeroUnits, TestSaveZeroUnitsAtThreshold, TestSaveFailureRetainsUnits, TestMultipleCallBehavior) matches the behavioral specification structure
- `CONSECUTIVE_ZERO_THRESHOLD` imported from source (not hardcoded 5) — test_threshold_constant_is_five pins the value, any future change to the constant will fail the test

## Deviations from Plan

None - plan executed exactly as written. Tests were written as behavioral specification (as plan directed), and all passed immediately because the 02-01 implementation was correct.

## Issues Encountered
- `uv` not on PATH in the Bash shell environment on Windows. Located at `C:\Users\eimil\AppData\Local\Programs\Python\Python313\Scripts\uv.exe` and used via PowerShell invocation. Tests ran and passed successfully.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- tests/test_platform_detect.py and tests/test_save_scrape_result.py serve as living documentation of the behavioral contracts
- Any future change to detect_platform() PLATFORM_PATTERNS or save_scrape_result() logic will fail these tests immediately
- The in-memory SQLite fixture pattern (db + building fixtures) can be reused by future scraper integration tests in plans 02-03 through 02-09

---
*Phase: 02-scrapers*
*Completed: 2026-02-18*

## Self-Check: PASSED

- tests/test_platform_detect.py: FOUND
- tests/test_save_scrape_result.py: FOUND
- .planning/phases/02-scrapers/02-02-SUMMARY.md: FOUND
- Commit 9fc1029: FOUND (test(02-02): add behavioral tests for detect_platform() and save_scrape_result())
