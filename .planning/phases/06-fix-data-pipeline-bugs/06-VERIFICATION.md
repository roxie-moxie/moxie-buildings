---
phase: 06-fix-data-pipeline-bugs
verified: 2026-02-22T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 6: Fix Data Pipeline Bugs — Verification Report

**Phase Goal:** Resolve the two integration bugs found by the v1.0 audit — the "Available Now" normalizer/API filter mismatch and the dual failure-handling divergence — so the data pipeline behaves correctly and consistently regardless of entry point
**Verified:** 2026-02-22
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Units scraped as "Available Now" (stored as today's YYYY-MM-DD) are returned by the API when filtering with available_before | VERIFIED | `units.py` line 73: `query = query.filter(Unit.availability_date <= available_before)`. No `or_()` branch, no literal "Available Now" comparison. Test `test_available_now_included_with_date_filter` seeds today's date and passes (50/50 tests pass). |
| 2 | A scraper failure in the batch runner retains existing units in the DB (does not delete them) | VERIFIED | `runner.py` except block (lines 98-115) calls `save_scrape_result(..., scrape_succeeded=False)`. `base.py` failure path (lines 82-84) skips the `db.query(Unit).filter(...).delete()` call entirely. Test `test_units_retained_on_scraper_exception` passes. |
| 3 | A scraper failure in the batch runner marks the building as stale (last_scrape_status='failed') | VERIFIED | `save_scrape_result()` failure path sets `building.last_scrape_status = "failed"` and `building.last_scraped_at = now`. Test `test_building_marked_stale_on_failure` passes. |
| 4 | Both entry points (batch runner and save_scrape_result) produce identical DB state on failure: units retained, building marked failed | VERIFIED | Runner failure path now delegates to `save_scrape_result(scrape_succeeded=False)` — there is only one failure implementation. The divergence (runner clearing units vs. base retaining them) is eliminated by construction. `TestSaveFailureRetainsUnits` (8 tests) + `TestRunnerFailureHandling` (3 tests) both pass against the same code path. |

**Score:** 4/4 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/moxie/api/routers/units.py` | Corrected available_before filter using simple <= comparison | VERIFIED | Line 73: `query = query.filter(Unit.availability_date <= available_before)`. No `or_` import, no "Available Now" string comparison. File imports cleanly. |
| `src/moxie/scheduler/runner.py` | Unified failure handler delegating to save_scrape_result | VERIFIED | Line 9: `from moxie.scrapers.base import save_scrape_result`. Lines 103-113: except block calls `save_scrape_result(db, building, raw_units=[], scrape_succeeded=False, error_message=...)`. The success-path `.delete()` on line 60 is correct and intentional (inside the try block, after scrape succeeds). File imports cleanly. |
| `tests/api/test_units.py` | Corrected regression test seeding today's date instead of literal 'Available Now' | VERIFIED | Lines 167-181: `test_available_now_included_with_date_filter` uses `from datetime import date; today = date.today().strftime("%Y-%m-%d")` and seeds `availability_date=today`. Asserts `unit_number == "101"` (not availability_date string). Test passes. |
| `tests/test_runner_failure.py` | Regression tests proving runner retains units and marks building stale on failure | VERIFIED | File exists (170 lines). Contains `TestRunnerFailureHandling` class with `test_units_retained_on_scraper_exception`, `test_building_marked_stale_on_failure`, `test_scrape_run_logged_on_failure`. All 3 tests pass. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/moxie/scheduler/runner.py` | `src/moxie/scrapers/base.py` | `save_scrape_result()` call in except block | WIRED | `runner.py` line 9 imports `save_scrape_result`; lines 107-113 call it in the except block with `scrape_succeeded=False`. Verified by `grep` and test execution. |
| `src/moxie/api/routers/units.py` | normalizer date format | Filter condition matches normalizer's YYYY-MM-DD output | WIRED | `units.py` line 73 uses `<= available_before` (lexicographic string comparison for ISO dates). Normalizer stores YYYY-MM-DD. Test seeds today's date (YYYY-MM-DD) and `available_before="2026-03-01"` — filter correctly includes the unit. |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AGENT-01 | 06-01-PLAN.md | "Available Now" filter mismatch — API must return units stored as today's YYYY-MM-DD when date filter applied | SATISFIED | `units.py` simple `<=` filter verified. `test_available_now_included_with_date_filter` passes. Audit finding "normalizer stores date, API checks literal string" is resolved. |
| INFRA-03 | 06-01-PLAN.md | On scrape failure, last known unit data is retained and the building is marked as stale | SATISFIED | Runner now delegates to `save_scrape_result(scrape_succeeded=False)`. Both entry points (CLI via individual scrapers and batch runner) call the same function. Units retained, building marked `last_scrape_status='failed'`. `test_units_retained_on_scraper_exception` and `test_building_marked_stale_on_failure` pass. |

**Note on AGENT-01 naming:** REQUIREMENTS.md line 40 describes AGENT-01 as "Agent can log in with credentials created by an admin" — that aspect was satisfied in Phase 4. The v1.0 audit reused AGENT-01 to track the "Available Now" filter mismatch as an integration gap (audit document line 27: `affected_reqs: ["AGENT-01"]`). The traceability table maps AGENT-01 to Phase 6 for this fix. Both the login requirement (Phase 4) and the filter fix (Phase 6) are now satisfied.

**Orphaned requirements check:** No REQUIREMENTS.md entries are mapped to Phase 6 beyond AGENT-01 and INFRA-03. Both are claimed by 06-01-PLAN.md and verified above.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/moxie/api/routers/units.py` | 48 | Docstring still says "also includes 'Available Now' units" | Info | Stale comment — implementation is correct (simple <=), but docstring implies special handling. No functional impact. |

No blocker or warning anti-patterns found. The stale docstring comment is informational only — the implementation is correct and all tests pass.

---

## Human Verification Required

None. All truths are verifiable programmatically through static code inspection and test execution. The test suite provides direct behavioral proof for both bug fixes.

---

## Test Suite Results

Full run covering all phase 6 files plus the existing `save_scrape_result` regression suite:

```
tests/api/test_units.py             21 passed
tests/test_runner_failure.py         3 passed
tests/test_save_scrape_result.py    26 passed
                              Total: 50 passed, 0 failed (2.09s)
```

All 50 tests pass. No regressions introduced.

---

## Summary

Phase 6 fully achieves its goal. Both integration bugs identified by the v1.0 audit are resolved:

**Bug 1 (AGENT-01):** The dead `or_(Unit.availability_date == "Available Now", ...)` branch has been removed from `units.py`. The normalizer stores "Available Now" as today's YYYY-MM-DD before writing to DB, so a simple `<=` comparison correctly includes those units in date-filtered searches. The regression test is updated to seed the normalizer-aligned date format.

**Bug 2 (INFRA-03):** The batch runner's exception handler no longer reimplements DB logic inline. It delegates to `save_scrape_result(scrape_succeeded=False)`, the same function used by CLI entry points. Both entry points now produce identical DB state on failure (units retained, building marked stale, ScrapeRun logged) — the divergence is eliminated by construction, not by coordination.

---

_Verified: 2026-02-22_
_Verifier: Claude (gsd-verifier)_
