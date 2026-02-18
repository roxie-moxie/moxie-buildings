---
phase: 01-foundation
plan: 02
subsystem: testing
tags: [pydantic, python-dateutil, normalizer, tdd, pytest]

# Dependency graph
requires:
  - phase: 01-foundation plan 01
    provides: pyproject.toml with all dependencies installed; src/moxie package structure; SQLAlchemy models defining the units table column types
provides:
  - src/moxie/normalizer.py: UnitInput Pydantic model + normalize() pure function
  - CANONICAL_BED_TYPES frozenset with 6 canonical values
  - BED_TYPE_ALIASES dict with 30 known scraper aliases
  - tests/test_normalizer.py: 45 test cases covering all normalizer behavior
  - tests/__init__.py: test package init
affects: [02-scrapers, 03-sheets-sync, all phases that write unit data to the DB]

# Tech tracking
tech-stack:
  added: []  # all deps were already in pyproject.toml from plan 01
  patterns:
    - "Pydantic v2 UnitInput model with @field_validator(mode='before') for pre-validation coercions"
    - "frozenset for O(1) canonical type lookup"
    - "BED_TYPE_ALIASES dict keyed by lowercased+stripped raw values"
    - "normalize() pure function wrapping UnitInput instantiation"
    - "non_canonical computed in normalize() after validation: bed_type not in CANONICAL_BED_TYPES"

key-files:
  created:
    - src/moxie/normalizer.py
    - tests/test_normalizer.py
    - tests/__init__.py
  modified: []

key-decisions:
  - "Unknown bed type aliases stored as-is with non_canonical=True (original casing preserved, not lowercased)"
  - "4BR+ maps to 3BR+ per spec — 4br is in BED_TYPE_ALIASES"
  - "Rent validator uses float()*100 then round() then int() to handle decimal cents correctly"
  - "scrape_run_at uses datetime.now(timezone.utc) instead of deprecated datetime.utcnow()"
  - "dateutil.parser.parse() for format-agnostic date parsing — no strptime format strings"
  - "baths always stored as str (even if input is int); sqft always stored as int (even if input is str)"

patterns-established:
  - "All scrapers call normalize(raw, building_id) before any DB write — never write raw values directly"
  - "ValidationError on missing required fields is the enforcement mechanism for DATA-03"
  - "Optional output keys are always present in the returned dict (None, not missing)"

requirements-completed: [DATA-03]

# Metrics
duration: 22min
completed: 2026-02-18
---

# Phase 1 Plan 02: Unit Normalizer Summary

**Pydantic v2 UnitInput model with field_validator(mode='before') normalizing bed type aliases (30 aliases to 6 canonical values), rent to integer cents, and date strings to YYYY-MM-DD — 45 tests, RED/GREEN/REFACTOR TDD cycle**

## Performance

- **Duration:** 22 min
- **Started:** 2026-02-18T19:08:00Z
- **Completed:** 2026-02-18T19:30:00Z
- **Tasks:** 1 (TDD: 3 commits — RED, GREEN, REFACTOR)
- **Files created:** 3

## Accomplishments

- 45 test cases written first (RED), covering all bed type aliases, rent formats, date formats, optional fields, and ValidationError enforcement
- Normalizer implementation passes all 45 tests in first attempt (GREEN)
- Refactored `datetime.utcnow()` to `datetime.now(timezone.utc)` eliminating Python 3.12+ deprecation warnings (REFACTOR)
- `non_canonical` flag correctly computed for all known aliases (False) and unknown values (True, original casing preserved)

## Task Commits

TDD cycle — three atomic commits:

1. **RED — Failing tests** - `7fc415c` (test)
   - 45 test cases covering all normalizer behavior
   - Tests fail with `ModuleNotFoundError: No module named 'moxie.normalizer'`
2. **GREEN — Implementation** - `4514ada` (feat)
   - `src/moxie/normalizer.py` with UnitInput model and normalize() function
   - All 45 tests pass
3. **REFACTOR — Cleanup** - `c421607` (refactor)
   - Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
   - Remove unused `re` import
   - All 45 tests still pass, no warnings

**Plan metadata:** _(see final docs commit)_

## Files Created

- `src/moxie/normalizer.py` — UnitInput Pydantic model with field validators for bed_type, rent, and availability_date; CANONICAL_BED_TYPES frozenset; BED_TYPE_ALIASES dict; normalize() public function
- `tests/test_normalizer.py` — 45 test cases in 5 test classes: TestBedTypeNormalization (21), TestRentNormalization (7), TestDateNormalization (6), TestOptionalFields (4), TestOutputStructure (3), TestRequiredFieldEnforcement (4)
- `tests/__init__.py` — empty package init

## Test Coverage

| Category | Tests | What is Covered |
|----------|-------|-----------------|
| Bed type normalization | 21 | All 19 canonical aliases + 2 non-canonical (PENTHOUSE, 5BR) |
| Rent normalization | 7 | Dollar sign, comma, /mo suffix, integer input, type enforcement |
| Date normalization | 6 | Available Now, now, ISO passthrough, long format, slash format, 2-digit year |
| Optional fields | 4 | Present/None when provided/absent; baths as str; sqft as int |
| Output structure | 3 | building_id propagation, all required keys, scrape_run_at is datetime |
| Required fields | 4 | ValidationError for each missing required field |
| **Total** | **45** | **All behavior categories from spec** |

## Decisions Made

- **Unknown bed type aliases stored as-is with original casing.** The spec says `"PENTHOUSE"` → `"PENTHOUSE"` (not `"penthouse"`). The validator strips+lowercases for lookup only; if no alias match, returns original stripped value.
- **4br maps to 3BR+ per spec.** Verified: `"4br"` is in BED_TYPE_ALIASES mapping to `"3BR+"`. 5-bedroom and above are non-canonical.
- **Rent uses `round(float(s) * 100)` then `int()`.** Using `float()` handles edge cases like `"995.50"` (half-cent rents) correctly without floating-point accumulation; `round()` prevents `int(99500.0000000001)` = 99500 bugs.
- **`scrape_run_at` uses `datetime.now(timezone.utc)`.** Python 3.12+ deprecates `datetime.utcnow()`. The timezone-aware form is required going forward.
- **`dateutil.parser.parse()` for all non-"available now" dates.** Format-agnostic parsing handles the variety of date formats scrapers return without maintaining a list of strptime format strings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Project scaffold required before TDD could begin**
- **Found during:** Pre-execution check
- **Issue:** Plan 01 (scaffold, models, Alembic) had commits in the repo (`feat(01-01)` × 3) but Plan 02 listed `depends_on: []`. The `tests/` and `src/moxie/sync/__init__.py` directories needed to exist for the RED commit.
- **Fix:** Created `tests/__init__.py`, `src/moxie/__init__.py`, and `src/moxie/sync/__init__.py` as empty package inits (per plan spec). These were included in the RED commit.
- **Files modified:** `tests/__init__.py`, `src/moxie/__init__.py`, `src/moxie/sync/__init__.py`
- **Verification:** pytest collected tests successfully after these files existed
- **Committed in:** `7fc415c` (RED test commit)

**2. [Rule 1 - Bug] Removed unused `re` import from normalizer**
- **Found during:** REFACTOR cycle
- **Issue:** The `import re` statement was present in the GREEN implementation but the rent validator used `float()` directly — no regex was needed.
- **Fix:** Removed unused import in REFACTOR commit.
- **Files modified:** `src/moxie/normalizer.py`
- **Verification:** All 45 tests pass, no import warnings
- **Committed in:** `c421607` (REFACTOR commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None — implementation worked on first attempt. All 45 tests went GREEN immediately after writing normalizer.py.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Normalizer is complete and fully tested. Phase 2 scrapers can call `from moxie.normalizer import normalize` to convert raw output before DB write.
- `ValidationError` on missing required fields is the enforcement mechanism — scrapers that omit `unit_number`, `bed_type`, `rent`, or `availability_date` will fail at normalize() time, not silently at DB write time.
- BED_TYPE_ALIASES should be extended as new scrapers return new alias formats in Phase 2.
- Plan 03 (Google Sheets sync) can proceed — it uses `normalize()` only for the initial dev bootstrap seed, not for building syncs.

---
*Phase: 01-foundation*
*Completed: 2026-02-18*
