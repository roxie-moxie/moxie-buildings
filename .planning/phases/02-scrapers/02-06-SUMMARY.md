---
phase: 02-scrapers
plan: 06
subsystem: scrapers
tags: [httpx, beautifulsoup4, html-scraping, bozzuto, bot-detection, crawl4ai, pytest-httpx]

# Dependency graph
requires:
  - phase: 02-01
    provides: tier2/ subpackage skeleton, httpx + beautifulsoup4 installed, Building model, ScraperProtocol

provides:
  - Bozzuto HTML scraper (tier2/bozzuto.py) with scrape(building) -> list[dict]
  - BozzutoScraperError raised on 403/429/503 (bot detection) with Crawl4AI upgrade recommendation
  - Multi-selector fallback strategy in _parse_html() for varying Bozzuto page structures
  - Crawl4AI upgrade path documented inline for easy activation
  - 21 tests covering parse logic, HTTP error handling, and scrape() integration

affects: [02-09, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bot-detection guard pattern: _BOT_DETECTION_STATUSES set {403, 429, 503} raises platform-specific error with Crawl4AI upgrade message"
    - "Multi-selector fallback: try selectors in order, break on first match — handles Bozzuto page structure variants"
    - "Inline upgrade path: Crawl4AI block commented inline in _fetch_html() for single-file activation"

key-files:
  created:
    - src/moxie/scrapers/tier2/bozzuto.py
    - tests/test_scraper_bozzuto.py
  modified: []

key-decisions:
  - "BozzutoScraperError raised on 403/429/503 specifically — these codes indicate bot detection, not generic HTTP error; message explicitly recommends Crawl4AI upgrade"
  - "Multi-selector fallback in _parse_html(): available-apartment, fp-apartment, unit-card, apartment-item — first match wins, handles Bozzuto page structure variants across ~13 buildings"
  - "Crawl4AI upgrade path left as inline comment block in _fetch_html() — operator can activate by uncommenting one block and removing httpx block, no structural changes required"
  - "SELECTOR VERIFICATION REQUIRED comment in _parse_html() — Bozzuto HTML was not directly inspectable during research; selectors are heuristic and must be confirmed against real URLs"

patterns-established:
  - "Tier 2 HTTP scraper pattern: _fetch_html(url) + _parse_html(html) + scrape(building) function trio — consistent with appfolio.py and funnel.py"
  - "Bot-detection status separation: _BOT_DETECTION_STATUSES distinguishes bot detection from generic errors in the error message"

requirements-completed: [SCRAP-06]

# Metrics
duration: 8min
completed: 2026-02-18
---

# Phase 02 Plan 06: Bozzuto HTML Scraper Summary

**Bozzuto HTML scraper using httpx + BeautifulSoup with bot-detection guard (403/429/503 raises BozzutoScraperError with Crawl4AI upgrade path) and multi-selector fallback for ~13 buildings**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-02-18T19:55:27Z
- **Completed:** 2026-02-18T20:03:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Created tier2/bozzuto.py with _fetch_html(), _parse_html(), and scrape() — covers ~13 Bozzuto-managed buildings
- BozzutoScraperError raised on bot-detection status codes (403, 429, 503) with explicit message recommending Crawl4AI upgrade path
- Multi-selector fallback in _parse_html(): tries available-apartment, fp-apartment, unit-card, apartment-item selectors in order, uses first matching set
- Crawl4AI upgrade path documented inline in _fetch_html() — single comment block to uncomment for activation
- 21 tests covering parse logic (10 tests), HTTP error/success layer (7 tests), and scrape() integration (4 tests)
- 244 total tests passing, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Bozzuto HTML scraper with bot-detection upgrade path** - `4f61256` (feat)

## Files Created/Modified
- `src/moxie/scrapers/tier2/bozzuto.py` - Bozzuto scraper: _fetch_html + _parse_html + scrape, BozzutoScraperError, multi-selector fallback, Crawl4AI upgrade comment
- `tests/test_scraper_bozzuto.py` - 21 tests: TestParseHtml (10), TestFetchHtml (7), TestScrape (4)

## Decisions Made
- BozzutoScraperError raised specifically on 403/429/503 with "bot detection" in message and "Crawl4AI" upgrade recommendation — distinguishes bot detection from generic HTTP errors for operator clarity.
- Multi-selector fallback: four selectors tried in order, first match wins — handles Bozzuto page structure variants without requiring per-building configuration for ~13 buildings.
- Crawl4AI upgrade left as inline commented block in `_fetch_html()` — activating the upgrade is a single-file edit (uncomment one block, remove httpx block), no architectural changes required.
- `SELECTOR VERIFICATION REQUIRED` comment added to `_parse_html()` — Bozzuto HTML structure was not directly inspectable during research, so selectors are heuristic and must be confirmed against real bozzuto.com property URLs before trusting output.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- bozzuto.py is importable from `moxie.scrapers.tier2.bozzuto` and structurally matches ScraperProtocol (scrape(building) -> list[dict])
- Ready to be wired into the scraper runner (02-09)
- **Action required before production use:** Run scraper against a real bozzuto.com property URL (e.g., community.bozzuto.com/apartments/) and verify CSS selectors produce correct output. Adjust selectors in _parse_html() as needed. If 403/429/503 returned, activate the Crawl4AI upgrade path in _fetch_html().
- 244 tests passing with no regressions

---
*Phase: 02-scrapers*
*Completed: 2026-02-18*

## Self-Check: PASSED

- `src/moxie/scrapers/tier2/bozzuto.py` - FOUND on disk
- `tests/test_scraper_bozzuto.py` - FOUND on disk
- Task commit 4f61256 - FOUND (feat(02-06): implement Bozzuto HTML scraper)
- 244 tests passing, zero failures - VERIFIED
