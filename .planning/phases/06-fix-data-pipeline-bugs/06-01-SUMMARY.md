---
phase: 06-fix-data-pipeline-bugs
plan: 01
subsystem: api, testing
tags: [sqlalchemy, fastapi, pytest, sqlite, mocking]

# Dependency graph
requires:
  - phase: 05-scheduler
    provides: runner.py scrape_one_building and save_scrape_result base infrastructure
  - phase: 04-api-layer
    provides: units.py API endpoint and test_units.py regression tests
provides:
  - Corrected available_before filter using simple <= comparison (no dead-code or_ branch)
  - Unified failure handler in runner.py delegating to save_scrape_result(scrape_succeeded=False)
  - Updated regression test seeding today's YYYY-MM-DD (matching normalizer output)
  - 3 new regression tests proving runner retains units and marks building stale on failure
affects: [07-coverage-expansion, any phase using units API or batch runner]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "save_scrape_result() as the single source of truth for all DB failure writes"
    - "Runner exception handler delegates to base layer, not reimplementing DB logic inline"
    - "Test inspection sessions: use fresh Session() after runner closes its own session"
    - "Patch moxie.scheduler.runner.importlib.import_module to trigger scraper exceptions"

key-files:
  created:
    - tests/test_runner_failure.py
  modified:
    - src/moxie/api/routers/units.py
    - src/moxie/scheduler/runner.py
    - tests/api/test_units.py

key-decisions:
  - "Normalizer stores 'Available Now' as today's YYYY-MM-DD — or_() branch in units.py was dead code; simple <= suffices"
  - "Runner failure path delegates to save_scrape_result(scrape_succeeded=False) — units retained, building marked stale, ScrapeRun logged"
  - "Test uses fresh inspection session after _run_with_failure() because runner.close() detaches objects from the patched session"

patterns-established:
  - "Regression test pattern: seed today's date (not literal 'Available Now') to test normalizer-aligned filter behavior"
  - "Runner test pattern: patch SessionLocal as factory (not return_value=session) so runner.close() doesn't break test inspection"

requirements-completed: [AGENT-01, INFRA-03]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 06 Plan 01: Fix Data Pipeline Bugs Summary

**Corrected Available Now API filter (dead or_() replaced with <=) and unified batch runner failure path to delegate to save_scrape_result(scrape_succeeded=False), retaining units instead of deleting them**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-22T04:01:42Z
- **Completed:** 2026-02-22T04:04:39Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Fixed `available_before` filter in `units.py`: removed dead `or_(Unit.availability_date == "Available Now", ...)` branch; normalizer already converts "Available Now" to today's YYYY-MM-DD before storing, so a simple `<=` comparison is correct and complete
- Unified runner.py failure handler: replaced inline delete+mark+log with a single `save_scrape_result(db, building, raw_units=[], scrape_succeeded=False, error_message=...)` call — both entry points (runner + individual scrapers) now produce identical retain-and-stale DB state on failure
- Updated `test_available_now_included_with_date_filter` to seed `availability_date=date.today().strftime("%Y-%m-%d")` instead of literal "Available Now", matching normalizer output
- Created `tests/test_runner_failure.py` with 3 regression tests proving scraper exceptions retain units, mark building stale, and log a failed ScrapeRun

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix Available Now filter and unify runner failure handler** - `72bc07f` (fix)
2. **Task 2: Fix existing regression test and add runner failure tests** - `ee2d562` (test)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `src/moxie/api/routers/units.py` - Replaced or_() with simple `Unit.availability_date <= available_before`
- `src/moxie/scheduler/runner.py` - Added `save_scrape_result` import; replaced manual delete block with delegation call
- `tests/api/test_units.py` - Updated `test_available_now_included_with_date_filter` to use today's date and assert on unit_number
- `tests/test_runner_failure.py` - New: 3 regression tests for runner exception handling

## Decisions Made
- `or_()` with literal "Available Now" was dead code once the normalizer was confirmed to always store dates as YYYY-MM-DD — removed entirely, no need for special-case handling
- Runner exception path now delegates to `save_scrape_result(scrape_succeeded=False)` — this makes both entry points identical by construction (the test suite for `save_scrape_result` already proves retain-and-stale behavior)
- Test inspection uses a fresh session factory (not `return_value=session`) because `runner.py` calls `db.close()` in its `finally` block, which would detach ORM objects from the shared test session

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Patch approach in test_runner_failure.py needed two iterations**
- **Found during:** Task 2 (creating test_runner_failure.py)
- **Issue 1:** Patching `importlib.import_module` globally interfered with `patch()` context manager's own module resolution (the patch system uses importlib internally). All 3 tests failed with `RuntimeError: Network timeout` during context manager setup.
- **Fix 1:** Switched to `patch("moxie.scheduler.runner.importlib.import_module")` (module-level patch) and used a nested `with` block to ensure `time` was patched first.
- **Issue 2:** After fix 1, the runner called `db.close()` in `finally`, detaching the test session's ORM objects. Tests failed with `DetachedInstanceError` and `InvalidRequestError`.
- **Fix 2:** Changed fixture from yielding a single session to yielding a `Session` factory. Used `SessionLocal` = factory (not `return_value=session`) so the runner creates/closes its own session. Post-run inspection uses a separate `Session()` call.
- **Files modified:** tests/test_runner_failure.py
- **Verification:** All 3 runner failure tests pass; 71/71 total tests pass
- **Committed in:** ee2d562 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test scaffolding approach)
**Impact on plan:** Fix was scoped entirely to test infrastructure. Production code changes were clean first try. No scope creep.

## Issues Encountered
- The two-phase fix to the test patching approach (global importlib patch → module-level patch, shared session → session factory) required careful reasoning about how `unittest.mock.patch` resolves target names and how SQLAlchemy sessions become detached after `session.close()`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both AGENT-01 and INFRA-03 bugs are fixed and regression-tested
- 71 tests pass with no regressions
- Phase 06 Plan 02 (if any) can proceed with confidence that failure handling is correct and consistent

---
*Phase: 06-fix-data-pipeline-bugs*
*Completed: 2026-02-22*
