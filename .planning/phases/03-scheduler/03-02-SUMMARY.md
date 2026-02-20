---
phase: 03-scheduler
plan: 02
subsystem: scheduler
tags: [apscheduler, cron, rotating-log, google-sheets, scrape-runs-pruning, batch]
dependency-graph:
  requires:
    - phase: 03-01
      provides: run_batch() orchestrator, batch.py, scrape-all CLI, scraper registry
  provides:
    - APScheduler BlockingScheduler with 2 AM Central cron trigger (--schedule mode)
    - Google Sheets "Scrape Status" tab pushed after each batch run (push_batch_status)
    - Rotating log file at logs/scrape_batch.log (5 MB, 7 backups)
    - scrape_runs pruning after each batch (rows older than 30 days deleted)
    - Availability tab refresh after each batch run
  affects: [scrape-all CLI, batch.py, ops monitoring]
tech-stack:
  added: [apscheduler==3.11.2, tzdata, tzlocal]
  patterns: [lazy-import scheduler (only in --schedule branch), trigger.get_next_fire_time() for pending jobs]
key-files:
  created:
    - src/moxie/scheduler/sheets_status.py
    - src/moxie/scheduler/log_config.py
  modified:
    - src/moxie/scheduler/batch.py
    - src/moxie/scrape_all.py
    - pyproject.toml
    - uv.lock
key-decisions:
  - "APScheduler imports deferred to --schedule branch — no import cost on immediate runs"
  - "Use job.trigger.get_next_fire_time() not job.next_run_time — latter is None on pending jobs before scheduler.start()"
  - "Sheets push failure does not crash batch — wrapped in try/except (monitoring, not core function)"
  - "Single ws.update() call for entire Scrape Status tab — one API request for 349+ rows"
  - "dry_run returns early before Steps 4-6 (status push, availability push, prune) — correct behavior"

requirements-completed: [INFRA-02]

duration: 4min
completed: 2026-02-20
---

# Phase 03 Plan 02: APScheduler + Sheets Status + Rotating Log Summary

**APScheduler 2 AM Central cron with Google Sheets "Scrape Status" tab, rotating log file, and scrape_runs pruning completing the fire-and-forget batch automation loop.**

## Performance

- **Duration:** ~4 minutes
- **Started:** 2026-02-20T18:55:30Z
- **Completed:** 2026-02-20T18:59:33Z
- **Tasks:** 2/2
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `scrape-all --schedule` enters APScheduler mode that fires `run_batch` at 2 AM Central daily with misfire_grace_time, coalesce, max_instances protection
- Google Sheet "Scrape Status" tab written after each batch run — summary row (date, totals) + per-building rows (name, platform, status, units, last scraped, error) in a single API call
- Rotating log file at `logs/scrape_batch.log` (5 MB max, 7 backups) captures all batch activity via `configure_logging()`
- scrape_runs older than 30 days pruned via `_prune_old_runs()` after each batch run
- Availability tab refreshed via `push_availability(db)` after each batch run

## Task Commits

Each task was committed atomically:

1. **Task 1: Google Sheets status push + scrape_runs pruning + rotating log** - `4e3aa09` (feat)
2. **Task 2: APScheduler 2 AM cron + scheduled mode CLI** - `25e556b` (feat)

## Files Created/Modified

- `src/moxie/scheduler/sheets_status.py` - `push_batch_status()`: writes Scrape Status tab with summary + per-building rows (single ws.update() call)
- `src/moxie/scheduler/log_config.py` - `configure_logging()`: sets up 5 MB rotating file handler at `logs/scrape_batch.log` (7 backups)
- `src/moxie/scheduler/batch.py` - Added `timedelta` import, `_prune_old_runs()` helper, Steps 4-6 at end of `run_batch()` (status push, availability push, prune)
- `src/moxie/scrape_all.py` - Restructured: `--schedule` flag for APScheduler mode, `--run-now`/default for immediate run, imports `configure_logging()`
- `pyproject.toml` - Added `apscheduler>=3.11.2` dependency
- `uv.lock` - Updated with apscheduler 3.11.2, tzdata, tzlocal

## Decisions Made

- APScheduler imports deferred to `--schedule` branch to avoid import cost on every `scrape-all` immediate run
- Used `job.trigger.get_next_fire_time(None, now)` instead of `job.next_run_time` — the latter is `None` on pending jobs before `scheduler.start()` is called (APScheduler 3.x behavior)
- Sheets push failure is caught and logged but does not propagate — batch status push is monitoring, not core function; a Sheets outage should not prevent scraping
- Single `ws.update()` call writes all rows at once — stays within Google Sheets API rate limits for 349+ buildings
- `dry_run` returns early before Steps 4-6 — no Sheets push or pruning during dry runs (correct; no actual scrape data produced)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed APScheduler pending job `next_run_time` AttributeError**
- **Found during:** Task 2 (APScheduler cron + scheduled mode CLI)
- **Issue:** Plan code used `scheduler.get_job("daily_scrape").next_run_time` but APScheduler 3.x raises `AttributeError` when the job is in pending state (before `scheduler.start()` is called). The attribute exists in `__slots__` but is not accessible on pending jobs.
- **Fix:** Used `job.trigger.get_next_fire_time(None, datetime.now(tz))` directly to compute next fire time before the scheduler starts.
- **Files modified:** `src/moxie/scrape_all.py`
- **Verification:** `uv run scrape-all --schedule` prints "Scheduler started. Next run at 2026-02-21 02:00:00-06:00" and blocks successfully.
- **Committed in:** `25e556b` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Single fix required to handle APScheduler 3.x pending-job behavior. No scope creep.

## Issues Encountered

None beyond the auto-fixed APScheduler attribute error above.

## Verification Results

- `uv run scrape-all --schedule` starts, prints "Scheduler started. Next run at 2026-02-21 02:00:00-06:00. Press Ctrl+C to stop." and blocks correctly
- `uv run scrape-all --run-now --skip-sync --dry-run` lists 349 buildings and exits 0
- `uv run python -c "import apscheduler; print(apscheduler.__version__)"` prints `3.11.2`
- `logs/scrape_batch.log` exists and contains timestamped batch entries
- `uv run pytest tests/ --ignore=tests/test_scraper_appfolio.py --ignore=tests/test_scraper_llm.py -x -q` — 235 passed

## Next Phase Readiness

- Phase 03 complete: daily batch automation is fully operational (`scrape-all --schedule` for daemon mode)
- Morning observability ready: check "Scrape Status" tab in Google Sheet for per-building results
- Phase 04 (UI/API) can now consume daily-refreshed unit data from the DB
- Pre-existing test failures (test_scraper_appfolio.py, test_scraper_llm.py) remain deferred — introduced in phase 02, out of scope

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| src/moxie/scheduler/sheets_status.py | FOUND |
| src/moxie/scheduler/log_config.py | FOUND |
| src/moxie/scheduler/batch.py | FOUND |
| src/moxie/scrape_all.py | FOUND |
| logs/scrape_batch.log | FOUND |
| .planning/phases/03-scheduler/03-02-SUMMARY.md | FOUND |
| Commit 4e3aa09 (Task 1) | FOUND |
| Commit 25e556b (Task 2) | FOUND |

---
*Phase: 03-scheduler*
*Completed: 2026-02-20*
