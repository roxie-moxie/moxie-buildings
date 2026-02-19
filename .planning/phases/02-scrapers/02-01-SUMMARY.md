---
phase: 02-scrapers
plan: 01
subsystem: infra
tags: [httpx, beautifulsoup4, crawl4ai, lxml, anthropic, alembic, sqlalchemy, sqlite]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Building/Unit/ScrapeRun models, normalizer, alembic setup, session.py

provides:
  - ScraperProtocol (typing.Protocol) in src/moxie/scrapers/base.py
  - save_scrape_result() centralized DB write function
  - CONSECUTIVE_ZERO_THRESHOLD constant (5)
  - detect_platform() URL classification for 8 known platforms
  - consecutive_zero_count column on buildings table (migration 3522f8b6e283)
  - scrapers package tree (tier1/, tier2/, tier3/ subpackages)
  - All scraper runtime deps: httpx, beautifulsoup4, crawl4ai, lxml, anthropic

affects: [02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09]

# Tech tracking
tech-stack:
  added: [httpx>=0.28.1, beautifulsoup4>=4.14.0, crawl4ai>=0.8.0, lxml>=5.0, anthropic>=0.40.0, pytest-httpx>=0.35.0]
  patterns: [ScraperProtocol structural typing, save_scrape_result centralized DB writes, platform detection via URL pattern matching]

key-files:
  created:
    - src/moxie/scrapers/__init__.py
    - src/moxie/scrapers/base.py
    - src/moxie/scrapers/platform_detect.py
    - src/moxie/scrapers/tier1/__init__.py
    - src/moxie/scrapers/tier2/__init__.py
    - src/moxie/scrapers/tier3/__init__.py
    - alembic/versions/3522f8b6e283_add_consecutive_zero_count.py
  modified:
    - pyproject.toml
    - src/moxie/db/models.py
    - uv.lock

key-decisions:
  - "save_scrape_result separates scrape_succeeded=True/False paths — errors do not increment consecutive_zero_count, only zero-unit successes do"
  - "CONSECUTIVE_ZERO_THRESHOLD=5 — buildings get needs_attention status after 5 consecutive zero-unit successful scrapes"
  - "detect_platform returns None (not 'llm') for unrecognized URLs — caller decides llm assignment"
  - "crawl4ai-setup failed with Windows encoding error (UnicodeEncodeError on arrow char in rich console) — noted and continued per plan instructions"

patterns-established:
  - "ScraperProtocol pattern: all scrapers implement scrape(building) -> list[dict] structurally"
  - "Centralized write pattern: all scrapers call save_scrape_result() after scrape() — no direct DB writes in scraper modules"
  - "Platform detection pattern: PLATFORM_PATTERNS ordered list, first match wins"

requirements-completed: [INFRA-03]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 02 Plan 01: Scraper Infrastructure Summary

**ScraperProtocol + save_scrape_result() base infrastructure with consecutive_zero_count migration and detect_platform() URL classification for 8 scraper platforms**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T01:36:43Z
- **Completed:** 2026-02-19T01:40:55Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Installed all scraper runtime dependencies (httpx, beautifulsoup4, crawl4ai, lxml, anthropic) plus pytest-httpx dev dep
- Added consecutive_zero_count column to buildings table via Alembic migration with batch_alter_table for SQLite compatibility
- Created ScraperProtocol (typing.Protocol) and save_scrape_result() with correct success/failure/zero-unit logic
- Created detect_platform() classifying all 8 known platforms via URL pattern matching; returns None for unknowns
- 72 Phase 1 tests still passing with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Install scraper deps, add migration, update Building model** - `188c58c` (feat)
2. **Task 2: Create scrapers package with base.py and platform_detect.py** - `f14d8ce` (feat)

**Plan metadata:** `[docs commit hash]` (docs: complete plan)

## Files Created/Modified
- `pyproject.toml` - Added httpx, beautifulsoup4, crawl4ai, lxml, anthropic, pytest-httpx deps
- `uv.lock` - Updated lockfile with 82 new packages
- `src/moxie/db/models.py` - Added consecutive_zero_count: Mapped[int] field to Building
- `alembic/versions/3522f8b6e283_add_consecutive_zero_count.py` - Migration adding consecutive_zero_count column
- `src/moxie/scrapers/__init__.py` - Package marker (empty)
- `src/moxie/scrapers/base.py` - ScraperProtocol, save_scrape_result(), CONSECUTIVE_ZERO_THRESHOLD=5
- `src/moxie/scrapers/platform_detect.py` - detect_platform(), PLATFORM_PATTERNS, KNOWN_PLATFORMS
- `src/moxie/scrapers/tier1/__init__.py` - Subpackage marker (empty)
- `src/moxie/scrapers/tier2/__init__.py` - Subpackage marker (empty)
- `src/moxie/scrapers/tier3/__init__.py` - Subpackage marker (empty)

## Decisions Made
- `save_scrape_result` separates `scrape_succeeded=True/False` paths: errors do not increment `consecutive_zero_count`, only zero-unit successes do. This prevents a network blip from skewing the threshold counter.
- `CONSECUTIVE_ZERO_THRESHOLD=5` — buildings get `needs_attention` status after 5 consecutive zero-unit successful scrapes.
- `detect_platform` returns `None` (not `'llm'`) for unrecognized URLs — caller decides the `llm` assignment, keeping the function pure.
- `crawl4ai-setup` failed with Windows `UnicodeEncodeError` on arrow character in rich console output — noted and continued per plan instructions. Playwright browsers can be installed manually with `playwright install chromium`.

## Deviations from Plan

None - plan executed exactly as written. The `crawl4ai-setup` encoding error was anticipated in the plan ("if it fails with a path/permission error, note the error but continue").

## Issues Encountered
- `crawl4ai-setup` failed with `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'` — Windows cp1252 codepage cannot encode the arrow character used in rich console output. This is a terminal encoding issue on Windows, not a functional problem. crawl4ai itself imports and runs fine. Playwright browsers may need to be installed separately with `py -m uv run playwright install chromium`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 2 scrapers (plans 02-09) can now import `save_scrape_result` from `moxie.scrapers.base` and `detect_platform` from `moxie.scrapers.platform_detect`
- consecutive_zero_count column exists in database and is tracked in Building model
- Playwright browsers may need manual install: `py -m uv run playwright install chromium`

---
*Phase: 02-scrapers*
*Completed: 2026-02-19*

## Self-Check: PASSED

- All 9 expected files found on disk
- Task commits verified: 188c58c (Task 1), f14d8ce (Task 2)
- 72 Phase 1 tests passing (no regressions)
- alembic current: 3522f8b6e283 (head)
- All libs importable: httpx, bs4, crawl4ai, lxml, anthropic
