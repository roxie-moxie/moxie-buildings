---
phase: 02-scrapers
plan: 08
subsystem: scraper
tags: [crawl4ai, claude-haiku, llm, anthropic, playwright, pydantic, asyncio]

requires:
  - phase: 02-01
    provides: save_scrape_result, ScraperProtocol, Building model

provides:
  - src/moxie/scrapers/tier3/llm.py -- Tier 3 LLM fallback scraper using Crawl4AI + Claude Haiku
  - tests/test_scraper_llm.py -- 12 tests for JSON parsing, filtering, and error handling
  - ANTHROPIC_API_KEY documented in .env.example

affects: [02-09, scraper-runner, orchestrator]

tech-stack:
  added: []
  patterns:
    - "AsyncWebCrawler mock pattern: mock __aenter__/__aexit__/arun with AsyncMock to avoid Playwright browser launch in tests"
    - "Module-level async function (_scrape_with_llm) as monkeypatch seam for scrape() integration tests"
    - "LLMExtractionStrategy + Pydantic schema for structured JSON extraction from arbitrary HTML"

key-files:
  created:
    - src/moxie/scrapers/tier3/llm.py
    - tests/test_scraper_llm.py
  modified:
    - .env.example

key-decisions:
  - "Tests mock AsyncWebCrawler context manager (not arun) -- patching arun alone fails because __aenter__ tries to launch Playwright browsers before arun is reached"
  - "Filtering logic (unit_number/bed_type/rent required) lives in _scrape_with_llm, tested via direct async call with mocked crawler -- not via scrape() passthrough"
  - "scrape() tests use _scrape_with_llm as monkeypatch seam for passthrough behavior tests, avoiding asyncio.run complexity"
  - "ANTHROPIC_API_KEY checked at call time (not import time) so import never fails -- only scrape() raises EnvironmentError"

patterns-established:
  - "AsyncWebCrawler mock: MagicMock with AsyncMock __aenter__/__aexit__ + AsyncMock arun -- prevents Playwright from being invoked during tests"

requirements-completed: [SCRAP-02, SCRAP-09]

duration: 18min
completed: 2026-02-18
---

# Phase 2 Plan 8: LLM Fallback Scraper Summary

**Crawl4AI + Claude Haiku Tier 3 scraper using LLMExtractionStrategy with Pydantic schema extraction for custom sites and Entrata buildings, with 12 unit tests using AsyncWebCrawler mocking to avoid Playwright browser dependency**

## Performance

- **Duration:** 18 min
- **Started:** 2026-02-18T00:00:00Z
- **Completed:** 2026-02-18T00:18:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- LLM fallback scraper using Crawl4AI LLMExtractionStrategy with Claude Haiku 3 (`anthropic/claude-3-haiku-20240307`)
- Pydantic schema-based extraction covering all UnitInput fields (unit_number, bed_type, rent, availability_date + 3 optionals)
- Robust error handling: malformed JSON, null content, non-list JSON all return empty list (no crash)
- EnvironmentError raised with clear message when ANTHROPIC_API_KEY is absent
- 12 tests passing with no real network/API/Playwright calls -- AsyncWebCrawler fully mocked
- ANTHROPIC_API_KEY added to .env.example

## Task Commits

Each task was committed atomically:

1. **Task 1: LLM fallback scraper (Crawl4AI + Claude Haiku)** - `6ab708a` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/moxie/scrapers/tier3/llm.py` - Tier 3 LLM fallback scraper: _UnitRecord Pydantic schema, _EXTRACTION_INSTRUCTION, _scrape_with_llm() async function, scrape() synchronous entrypoint
- `tests/test_scraper_llm.py` - 12 tests covering EnvironmentError guard, malformed/null/non-list JSON recovery, required field filtering (unit_number, bed_type, rent), and valid record passthrough
- `.env.example` - Added ANTHROPIC_API_KEY=your_key_here

## Decisions Made
- Tests mock AsyncWebCrawler at the context manager level (`__aenter__`, `__aexit__`, `arun`) rather than patching `arun` alone -- this is necessary because `__aenter__` tries to launch Playwright browsers before `arun` is called, and Playwright chromium is not installed in this environment.
- Filtering logic (unit_number/bed_type/rent required) lives in `_scrape_with_llm`, so filtering tests call `_scrape_with_llm` directly via `asyncio.run()` with the crawler mocked, rather than going through `scrape()`.
- `scrape()` integration tests use `_scrape_with_llm` as a monkeypatch seam -- replacing the async function directly sidesteps asyncio complexity while verifying the synchronous wrapper behavior.
- ANTHROPIC_API_KEY is checked at call time inside `_scrape_with_llm`, not at import time -- this preserves importability without credentials set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test strategy: AsyncWebCrawler requires context manager mocking, not arun patching**
- **Found during:** Task 1 (test execution)
- **Issue:** Initial test implementation patched `crawl4ai.AsyncWebCrawler.arun` but Playwright's `__aenter__` runs before `arun` and tries to launch Chromium browsers, causing `BrowserType.launch: Executable doesn't exist` errors. Also, `_patch_scrape` tests passed `_scrape_with_llm` a pre-filtered list, but filtering only happens inside `_scrape_with_llm`, so filtering tests were not actually testing filtering.
- **Fix:** (a) Rewrote crawler-level tests to patch AsyncWebCrawler at the context manager level using MagicMock + AsyncMock. (b) Moved filtering tests to call `_scrape_with_llm` directly with mocked crawler. (c) Renamed `scrape()` passthrough tests to properly reflect they test passthrough (not filtering).
- **Files modified:** tests/test_scraper_llm.py
- **Verification:** All 12 tests pass, 244 total suite passes
- **Committed in:** 6ab708a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in initial test strategy)
**Impact on plan:** Fix was necessary for tests to actually test the documented behavior. No scope creep.

## Issues Encountered
- Playwright Chromium not installed on this Windows dev machine -- the STATE.md blocker `crawl4ai-setup fails on Windows with UnicodeEncodeError (cp1252/arrow char)` was already noted. Test mocking strategy completely avoids Playwright at test time.

## User Setup Required
**External services require manual configuration:**
- `ANTHROPIC_API_KEY` -- Required to run the LLM scraper. Get from: Anthropic Console (console.anthropic.com) -> API Keys -> Create new key. Add to `.env` file.

## Next Phase Readiness
- Tier 3 LLM scraper is complete and importable
- All 244 tests pass; no regressions
- Ready for Phase 2 Plan 9 (scraper runner / orchestrator that dispatches to tier1/tier2/tier3 based on platform field)

---
*Phase: 02-scrapers*
*Completed: 2026-02-18*
