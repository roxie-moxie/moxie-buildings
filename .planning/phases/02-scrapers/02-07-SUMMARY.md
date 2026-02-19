---
phase: 02-scrapers
plan: 07
subsystem: scraper
tags: [crawl4ai, beautifulsoup4, playwright, realpage, g5, groupfox, asyncwebcrawler]

# Dependency graph
requires:
  - phase: 02-01
    provides: ScraperProtocol, save_scrape_result, tier2/ package, crawl4ai installed

provides:
  - RealPage/G5 scraper (AsyncWebCrawler + BeautifulSoup) in tier2/realpage.py
  - Groupfox /floorplans scraper (AsyncWebCrawler bot-bypass) in tier2/groupfox.py
  - RealPageScraperError and GroupfoxScraperError platform-specific exceptions
  - _normalize_floorplans_url() URL normalization utility for Groupfox
  - 33 tests: 13 for realpage, 20 for groupfox

affects: [02-08, 02-09, scraper-runner]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Crawl4AI pattern: AsyncWebCrawler with CacheMode.BYPASS for fresh renders each run"
    - "Monkeypatching _fetch_rendered_html coroutine for tests — asyncio.run() not mocked directly"
    - "URL normalization pattern: strip trailing slash, check path suffix, reconstruct from scheme+netloc"

key-files:
  created:
    - src/moxie/scrapers/tier2/realpage.py
    - src/moxie/scrapers/tier2/groupfox.py
    - tests/test_scraper_realpage.py
    - tests/test_scraper_groupfox.py

key-decisions:
  - "Both scrapers monkeypatch _fetch_rendered_html (the coroutine) rather than asyncio.run — cleaner and avoids event loop issues in tests"
  - "Groupfox URL normalization strips any non-/floorplans path and constructs scheme://netloc/floorplans — not a simple append"
  - "Selector comments in both scrapers explicitly document that CSS selectors are approximate and must be verified against real URLs before production use"
  - "Groupfox _parse_html uses floor_plan_name as unit_number — Groupfox exposes floorplans not individual unit listings on the /floorplans page"

patterns-established:
  - "Tier 2 scraper pattern: _fetch_rendered_html (async, Crawl4AI) + _parse_html (sync, BeautifulSoup) + scrape() (asyncio.run bridge)"
  - "Platform error pattern: raise PlatformScraperError when Crawl4AI returns empty HTML — no silent empty list"

requirements-completed: [SCRAP-05, SCRAP-07]

# Metrics
duration: 15min
completed: 2026-02-18
---

# Phase 02 Plan 07: RealPage and Groupfox Scrapers Summary

**Tier 2 Crawl4AI scrapers for RealPage/G5 (~10-15 buildings) and Groupfox (~12 buildings) using AsyncWebCrawler + BeautifulSoup, with Groupfox /floorplans URL normalization and platform-specific error types**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-02-18T00:00:00Z
- **Completed:** 2026-02-18T00:15:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created realpage.py: AsyncWebCrawler renders JS-heavy RealPage/G5 pages, BeautifulSoup parses available-unit/floorplan-item/unit-row elements
- Created groupfox.py: AsyncWebCrawler bypasses Groupfox 403 bot detection, _normalize_floorplans_url() ensures /floorplans path always targeted
- Both scrapers raise platform-specific errors (RealPageScraperError, GroupfoxScraperError) on empty HTML — no silent failures
- 33 tests passing across both scrapers; full suite 232 tests, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: RealPage/G5 scraper (Crawl4AI + BeautifulSoup)** - `3bad144` (feat)
2. **Task 2: Groupfox /floorplans scraper (Crawl4AI bot-bypass)** - `a8a2724` (feat)

## Files Created/Modified
- `src/moxie/scrapers/tier2/realpage.py` - RealPage/G5 scraper: AsyncWebCrawler + BeautifulSoup, RealPageScraperError
- `src/moxie/scrapers/tier2/groupfox.py` - Groupfox scraper: AsyncWebCrawler + _normalize_floorplans_url + GroupfoxScraperError
- `tests/test_scraper_realpage.py` - 13 tests: parse logic (9 tests), scrape() integration (4 tests)
- `tests/test_scraper_groupfox.py` - 20 tests: URL normalization (6), parse logic (9), scrape() integration (5)

## Decisions Made
- Both scrapers monkeypatch `_fetch_rendered_html` (the coroutine) rather than `asyncio.run` — avoids event loop complications in tests and targets the correct abstraction layer.
- Groupfox URL normalization reconstructs `scheme://netloc/floorplans` from parsed components rather than appending to path — handles root, trailing slash, and other-path cases correctly.
- CSS selectors in both scrapers carry explicit `SELECTOR VERIFICATION REQUIRED` comments — selectors are informed by research but must be confirmed against live URLs before production scraping.
- Groupfox `_parse_html` uses floorplan name as `unit_number` because the /floorplans page lists floorplan types, not individual units.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Playwright browsers for Crawl4AI may need manual install: `playwright install chromium` (noted in 02-01 SUMMARY).

## Next Phase Readiness
- realpage.py and groupfox.py are importable and structurally match ScraperProtocol (scrape(building) -> list[dict])
- Both ready to be wired into the scraper runner (02-09)
- CSS selectors in both scrapers need real-URL verification before production use — this is expected and documented in the code comments

---
*Phase: 02-scrapers*
*Completed: 2026-02-18*

## Self-Check: PASSED

- `src/moxie/scrapers/tier2/realpage.py` - FOUND
- `src/moxie/scrapers/tier2/groupfox.py` - FOUND
- `tests/test_scraper_realpage.py` - FOUND
- `tests/test_scraper_groupfox.py` - FOUND
- Task commit 3bad144 - FOUND (feat(02-07): implement RealPage/G5 scraper)
- Task commit a8a2724 - FOUND (feat(02-07): implement Groupfox /floorplans scraper)
- 232 tests passing, zero failures
