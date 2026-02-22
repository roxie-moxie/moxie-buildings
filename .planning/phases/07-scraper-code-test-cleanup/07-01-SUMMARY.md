---
phase: 07-scraper-code-test-cleanup
plan: 01
subsystem: testing
tags: [pytest, scraper, appfolio, llm, crawl4ai, platform_detect]

# Dependency graph
requires:
  - phase: 06-fix-data-pipeline-bugs
    provides: 71 passing tests as baseline before cleanup
provides:
  - Clean test suite: pytest tests/ runs with 0 errors, 0 failures, no --ignore flags
  - Dead tier1/rentcafe.py stub removed; tier2/securecafe.py is sole rentcafe implementation
  - KNOWN_PLATFORMS frozenset includes "sightmap" (58 buildings)
  - test_scraper_appfolio.py uses real AppFolio CSS selectors (.js-listing-item, .detail-box__value)
  - test_scraper_llm.py FakeResult mock has all attributes _probe_subpage requires
affects: [future-test-additions, scraper-validation, platform-classification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FakeResult mock must include .success, .status_code, .markdown for _probe_subpage compatibility"
    - "AppFolio test fixtures use real selectors from sedgwickproperties.appfolio.com"

key-files:
  created: []
  modified:
    - src/moxie/scrapers/platform_detect.py
    - tests/test_platform_detect.py
    - tests/test_scraper_llm.py
    - tests/test_scraper_appfolio.py
  deleted:
    - src/moxie/scrapers/tier1/rentcafe.py
    - tests/test_scraper_rentcafe.py

key-decisions:
  - "tier1/rentcafe.py deleted: registry.py maps rentcafe platform to tier2/securecafe; tier1 stub was never called"
  - "FakeResult mock needs .success=True, .status_code=200, .markdown='' to pass _probe_subpage guard in llm.py"
  - "AppFolio parser skips cards without Unit NNN in img[alt] — tests must reflect skip-not-default behavior"

patterns-established:
  - "When adding a new platform (sightmap), add to both KNOWN_PLATFORMS and add a test asserting membership"
  - "Test HTML fixtures must use real production CSS selectors, not imagined ones"

requirements-completed: [SCRAP-01]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 07 Plan 01: Scraper Code Test Cleanup Summary

**Deleted orphaned tier1/rentcafe.py stub, fixed 8 broken test items (1 collection error + 7 AttributeErrors), and added sightmap to KNOWN_PLATFORMS — pytest tests/ now passes 283 tests with zero failures and no --ignore flags**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T04:39:13Z
- **Completed:** 2026-02-22T04:41:33Z
- **Tasks:** 2
- **Files modified:** 4 (modified) + 2 (deleted)

## Accomplishments
- Deleted dead code: `src/moxie/scrapers/tier1/rentcafe.py` and its 14-test file — the registry maps `rentcafe` to tier2/securecafe, not tier1; this stub was never called
- Fixed 7 failing LLM tests by adding `result.success = True`, `result.status_code = 200`, `result.markdown = ""` to FakeResult mock — `_probe_subpage()` now checks these attributes
- Fixed 1 collection error in test_scraper_appfolio.py by updating import from `_parse_html` to `_parse_listings_html` and rewriting fixtures to use real AppFolio selectors (`.js-listing-item`, `.detail-box__value`, `.js-listing-available`, `img[alt]`)
- Added `"sightmap"` to KNOWN_PLATFORMS frozenset and added `test_known_platforms_contains_sightmap()` test
- Final state: 283 passed, 0 failed, 0 collection errors (up from 262 passing with 1 collection error + 7 failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete orphaned RentCafe stub, add sightmap to KNOWN_PLATFORMS, add test** - `e5d9f59` (chore)
2. **Task 2: Fix broken LLM and AppFolio test files** - `21f646e` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/moxie/scrapers/platform_detect.py` - Added "sightmap" to KNOWN_PLATFORMS frozenset
- `tests/test_platform_detect.py` - Added test_known_platforms_contains_sightmap()
- `tests/test_scraper_llm.py` - Added .success, .status_code, .markdown to FakeResult mock in _make_fake_crawler_ctx()
- `tests/test_scraper_appfolio.py` - Fixed import (_parse_listings_html), rewrote all HTML fixtures with real selectors, rewrote test for skipped-not-default behavior on missing unit number
- `src/moxie/scrapers/tier1/rentcafe.py` - DELETED (dead code)
- `tests/test_scraper_rentcafe.py` - DELETED (14 tests for dead code)

## Decisions Made
- Deleted tier1/rentcafe.py without hesitation: grep confirmed no production code imports it; registry.py routes `rentcafe` platform to `moxie.scrapers.tier2.securecafe`
- FakeResult mock attributes set to values that cause `_probe_subpage` to proceed to content keyword check, then return False (empty markdown), then fall through to link scoring (empty links), so `_find_availability_link` returns None and `target_url = url` — the original URL — allowing Pass 2 to proceed with `extracted_content`
- `test_parse_html_missing_unit_number_defaults_to_na` was renamed and rewritten to `test_parse_html_missing_unit_number_skipped` because `_parse_listings_html` uses `if not unit_number: continue` (skip semantics), not a default value

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None — all fixes were straightforward as described in plan research.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Test suite is clean: `pytest tests/` runs without flags, 283 passing
- SCRAP-01 formally closed: dead tier1 RentCafe stub removed
- Phase 07 plan 02 (if any) can proceed on a clean baseline

---
*Phase: 07-scraper-code-test-cleanup*
*Completed: 2026-02-22*
