---
phase: 02-scrapers
plan: 04
subsystem: scrapers
tags: [rentcafe, yardi, ppm, crawl4ai, beautifulsoup, httpx, tier1, stub]

# Dependency graph
requires:
  - phase: 02-01
    provides: "save_scrape_result(), ScraperProtocol, Building model"
  - phase: 01-01
    provides: "Building model with rentcafe_property_id, rentcafe_api_token fields"
provides:
  - "src/moxie/scrapers/tier1/rentcafe.py — RentCafe/Yardi scraper stub with credential guard and Error:1020 detection"
  - "src/moxie/scrapers/tier1/ppm.py — PPM single-page scraper using Crawl4AI + BeautifulSoup"
  - "tests/test_scraper_rentcafe.py — 14 tests for stub behavior, credential validation, field mapping"
  - "tests/test_scraper_ppm.py — 17 tests for HTML parsing, name matching, unit filtering"
affects: [02-08, 02-09, phase-03-scheduler]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scraper stub pattern: NotImplementedError with clear upgrade path message"
    - "API error guard: check first item of response list for error key before processing"
    - "Dual field name fallback in mapper: raw.get('Primary') or raw.get('Fallback', default)"
    - "Single-page scraper: fetch once, filter per building via _fetch_all_ppm_units()"
    - "Case-insensitive partial contains match for building name disambiguation"
    - "monkeypatch _fetch_all_ppm_units() to test scrape() without real HTTP calls"

key-files:
  created:
    - src/moxie/scrapers/tier1/rentcafe.py
    - src/moxie/scrapers/tier1/ppm.py
    - tests/test_scraper_rentcafe.py
    - tests/test_scraper_ppm.py
  modified: []

key-decisions:
  - "RentCafe scraper is STUBBED with NotImplementedError — _fetch_units() raises until credential spike confirms API field names"
  - "RentCafeCredentialError (ValueError subclass) raised before reaching stub when property_id or api_token is missing/empty"
  - "Error:1020 guard in _check_for_api_error() prevents silent zero-unit false positives from invalid API responses"
  - "_map_unit() uses dual field name fallback (UnitNumber/ApartmentNumber, Beds/Bedrooms, Rent/MinimumRent) to handle API field name uncertainty"
  - "PPM _matches_building() uses bidirectional partial contains (unit in db OR db in unit) to handle name prefix mismatches"
  - "PPM scrape() fetches full page each call — Phase 3 scheduler should batch PPM buildings and share cached result"
  - "In-memory SQLite session used for credential tests requiring Building objects (SQLAlchemy ORM requires proper instantiation)"

patterns-established:
  - "Tier 1 scraper module pattern: RENTCAFE_API_BASE constant, typed exception classes, _fetch(), _map_unit(), scrape()"
  - "PPM single-page pattern: _fetch_ppm_html() async, _parse_ppm_html() pure, _matches_building() pure, scrape() orchestrates"

requirements-completed: [SCRAP-01, SCRAP-03]

# Metrics
duration: 25min
completed: 2026-02-18
---

# Phase 2 Plan 4: Tier 1 Scrapers (RentCafe + PPM) Summary

**RentCafe/Yardi stub with Error:1020 guard (NotImplementedError until credential spike) and PPM single-page Crawl4AI + BeautifulSoup scraper with partial case-insensitive building name matching**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-02-18T19:50:00Z
- **Completed:** 2026-02-18T20:15:00Z
- **Tasks:** 2
- **Files modified:** 4 created

## Accomplishments
- RentCafe stub scraper with explicit credential validation (RentCafeCredentialError) before hitting the unimplemented API call
- Error:1020 API response guard prevents silent zero-unit false positives from invalid RentCafe credentials
- PPM Crawl4AI scraper fetches JS-rendered page once and filters by building name using bidirectional partial contains match
- 31 total tests (14 RentCafe + 17 PPM), all passing, no real HTTP calls in test suite

## Task Commits

1. **Task 1: RentCafe/Yardi scraper stub with Error:1020 guard** - `f160ebb` (feat)
2. **Task 2: PPM single-page scraper (Crawl4AI + BeautifulSoup)** - `fb369b1` (feat, committed as part of prior session alongside appfolio.py)

**Plan metadata:** (created in this commit)

## Files Created/Modified
- `src/moxie/scrapers/tier1/rentcafe.py` - RentCafe stub with RentCafeCredentialError, RentCafeAPIError, _check_for_api_error(), _map_unit(), scrape()
- `src/moxie/scrapers/tier1/ppm.py` - PPM scraper with AsyncWebCrawler, _parse_ppm_html(), _matches_building(), scrape()
- `tests/test_scraper_rentcafe.py` - 14 tests: credential validation, Error:1020 guard, _map_unit() field mapping, stub NotImplementedError
- `tests/test_scraper_ppm.py` - 17 tests: HTML parsing (7), building name matching (6), scrape() integration (4)

## Decisions Made
- RentCafe scraper is a clean stub: the structure is complete (credential check, error guard, field mapper) but `_fetch_units()` raises NotImplementedError with a clear message pointing to the credential spike task
- Error:1020 guard uses first-item check on response list — RentCafe API returns `[{"Error": "1020"}]` for invalid credentials, not an HTTP error
- `_map_unit()` maps both primary and fallback field names (e.g., `Beds` vs `Bedrooms`) since the exact `apartmentavailability` endpoint field names are unconfirmed until the spike
- PPM building name matching uses bidirectional contains: `unit_lower in db_lower or db_lower in unit_lower` to handle cases where PPM uses short names but DB has prefixed names like "PPM - Streeterville Tower"
- In-memory SQLite session used for tests requiring Building objects — `Building.__new__()` approach fails because SQLAlchemy instrumented attributes require proper ORM initialization

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLAlchemy Building instantiation via __new__ fails**
- **Found during:** Task 1 (RentCafe test writing)
- **Issue:** Plan specified "Use in-memory Building objects (not DB-backed)" — `Building.__new__(Building)` + `setattr()` fails with `AttributeError: 'NoneType' object has no attribute 'set'` because SQLAlchemy instrumented attributes require proper ORM state initialization
- **Fix:** Used in-memory SQLite session (same as other test files) to insert and retrieve Building objects, giving proper ORM-backed instances
- **Files modified:** tests/test_scraper_rentcafe.py
- **Verification:** All 14 credential tests pass with DB-backed Building objects
- **Committed in:** f160ebb (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The fix is necessary for correctness. In-memory SQLite is fast (< 1ms per test), matches existing test patterns, and adds no complexity.

## Issues Encountered
- PPM files (`ppm.py`, `test_scraper_ppm.py`) were already committed in a prior session (commit fb369b1) alongside appfolio.py under a mis-labeled commit message. Files were correct and tests pass — no re-commit was needed.
- `test_scraper_llm.py` has 7 pre-existing failures unrelated to this plan (LLM scraper field filtering logic and Playwright browser not installed). These are out of scope for 02-04.

## User Setup Required
None — RentCafe scraper is fully stubbed. No API credentials needed until the credential spike is completed.

## Next Phase Readiness
- `from moxie.scrapers.tier1.rentcafe import scrape` — callable by Phase 3 dispatcher; raises NotImplementedError until credential spike replaces _fetch_units()
- `from moxie.scrapers.tier1.ppm import scrape` — functional, requires Playwright browsers installed (`playwright install`) for real execution
- Phase 3 scheduler should batch all PPM buildings and call ppm.scrape() once per building (page is fetched per call — caching optimization is a Phase 3 concern)
- RentCafe credential spike (see RESEARCH.md Open Question 1) must complete before Phase 3 can use rentcafe.scrape() against real buildings

---
*Phase: 02-scrapers*
*Completed: 2026-02-18*

## Self-Check: PASSED

- FOUND: src/moxie/scrapers/tier1/rentcafe.py
- FOUND: src/moxie/scrapers/tier1/ppm.py
- FOUND: tests/test_scraper_rentcafe.py
- FOUND: tests/test_scraper_ppm.py
- FOUND: .planning/phases/02-scrapers/02-04-SUMMARY.md
- FOUND commit: f160ebb (Task 1 — RentCafe scraper)
- FOUND commit: fb369b1 (Task 2 — PPM scraper, committed in prior session)
