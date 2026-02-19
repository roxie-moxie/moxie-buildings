---
phase: 02-scrapers
plan: 05
subsystem: scrapers
tags: [httpx, beautifulsoup4, html-scraping, funnel, nestio, appfolio, pytest-httpx]

# Dependency graph
requires:
  - phase: 02-01
    provides: tier2/ subpackage skeleton, httpx + beautifulsoup4 installed, Building model, ScraperProtocol

provides:
  - Funnel/Nestio HTML scraper (tier2/funnel.py) with scrape(building) -> list[dict]
  - AppFolio HTML scraper (tier2/appfolio.py) with scrape(building) -> list[dict]
  - FunnelScraperError raised on non-2xx HTTP responses
  - AppFolioScraperError raised on non-2xx HTTP responses
  - 26 tests covering both scrapers (parse + HTTP mock)

affects: [02-09, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tier 2 HTML pattern: _fetch_html() + _parse_html() + scrape() function trio for each platform"
    - "Static HTML fixture pattern: SAMPLE_HTML string in test file for parse tests (no network)"
    - "pytest-httpx mock pattern: httpx_mock.add_response() for HTTP layer tests"
    - "Selector documentation pattern: SELECTOR VERIFICATION REQUIRED comment block in _parse_html()"

key-files:
  created:
    - src/moxie/scrapers/tier2/funnel.py
    - src/moxie/scrapers/tier2/appfolio.py
    - tests/test_scraper_funnel.py
    - tests/test_scraper_appfolio.py
  modified: []

key-decisions:
  - "Heuristic CSS selectors documented with SELECTOR VERIFICATION REQUIRED comment — real page inspection needed before relying on output"
  - "Both scrapers raise platform-specific exceptions (FunnelScraperError, AppFolioScraperError) on non-2xx HTTP — not silent empty lists"
  - "Missing availability_date defaults to 'Available Now'; missing unit_number defaults to 'N/A'"
  - "BeautifulSoup with html.parser (not lxml) for both scrapers — consistent with project approach, no extra binary dependency"

patterns-established:
  - "Tier 2 scraper trio: _fetch_html(url) + _parse_html(html) + scrape(building) — matches Tier 2 pattern established by realpage.py and bozzuto.py"
  - "Test file structure: TestParseHtml class (static fixtures) + TestFetchHtml class (httpx_mock)"

requirements-completed: [SCRAP-04, SCRAP-08]

# Metrics
duration: 12min
completed: 2026-02-19
---

# Phase 02 Plan 05: Tier 2 HTML Scrapers (Funnel + AppFolio) Summary

**Funnel/Nestio and AppFolio public listing page scrapers using httpx + BeautifulSoup with heuristic CSS selectors documented for mandatory real-URL verification**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-19T01:55:53Z
- **Completed:** 2026-02-19T02:08:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created tier2/funnel.py with _fetch_html(), _parse_html(), and scrape() — covers ~15-20 Funnel/Nestio buildings
- Created tier2/appfolio.py with _fetch_html(), _parse_html(), and scrape() — covers ~5-10 AppFolio buildings
- Both scrapers raise platform-specific errors on non-2xx HTTP (caller passes scrape_succeeded=False to save_scrape_result)
- 26 tests (13 per scraper) covering parse with static HTML fixtures and HTTP layer with pytest-httpx mocks
- Full suite: 212 tests passing (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Funnel/Nestio HTML scraper** - `76e6f33` (feat)
2. **Task 2: AppFolio public listing scraper** - `fb369b1` (feat)

**Plan metadata:** `[docs commit hash]` (docs: complete plan)

## Files Created/Modified
- `src/moxie/scrapers/tier2/funnel.py` - Funnel/Nestio HTML scraper with BeautifulSoup CSS selectors
- `src/moxie/scrapers/tier2/appfolio.py` - AppFolio listing page scraper with BeautifulSoup CSS selectors
- `tests/test_scraper_funnel.py` - 13 tests: parse (9) + HTTP mock (4)
- `tests/test_scraper_appfolio.py` - 13 tests: parse (9) + HTTP mock (4)

## Decisions Made
- Heuristic CSS selectors with explicit `SELECTOR VERIFICATION REQUIRED` comment block — implementation acknowledges low-confidence HTML structure from research phase and requires a manual spike against real building URLs before trusting output.
- Both scrapers raise platform-specific RuntimeError subclasses (FunnelScraperError, AppFolioScraperError) on any non-2xx HTTP response — not silent empty list returns that would be mistaken for zero-unit success.
- Missing `availability_date` defaults to `"Available Now"` and missing `unit_number` defaults to `"N/A"` — consistent with other tier2 scrapers in the project.
- Used `html.parser` (stdlib) not `lxml` — lxml requires compiled C extension, html.parser is sufficient for static HTML.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both scrapers importable from `moxie.scrapers.tier2.funnel` and `moxie.scrapers.tier2.appfolio`
- Both satisfy `ScraperProtocol` structurally (scrape(building) -> list[dict])
- **Action required before production use:** Run each scraper against a real Funnel/Nestio URL (nestiolistings.com or funnelleasing.com) and real AppFolio URL ({subdomain}.appfolio.com/listings) to verify CSS selectors produce correct output. Adjust selectors in _parse_html() as needed.
- 212 tests passing with no regressions across all Phase 1 and Phase 2 plans completed so far

---
*Phase: 02-scrapers*
*Completed: 2026-02-19*

## Self-Check: PASSED

- funnel.py: FOUND on disk
- appfolio.py: FOUND on disk
- test_scraper_funnel.py: FOUND on disk
- test_scraper_appfolio.py: FOUND on disk
- 02-05-SUMMARY.md: FOUND on disk
- Task 1 commit 76e6f33: VERIFIED in git log
- Task 2 commit fb369b1: VERIFIED in git log
- 212 tests passing: VERIFIED
