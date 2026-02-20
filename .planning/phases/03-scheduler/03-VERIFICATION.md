---
phase: 03-scheduler
verified: 2026-02-20T19:30:00Z
status: human_needed
score: 3/3 success criteria automated-verified; 1 item requires overnight human confirmation
re_verification: false
human_verification:
  - test: "Run `uv run scrape-all --schedule`, leave running until 2 AM Central, confirm batch fires"
    expected: "scrape_runs table populated with ~349 rows (one per building), logs/scrape_batch.log shows batch start/complete, Google Sheet 'Scrape Status' tab shows per-building results"
    why_human: "APScheduler cron at 2 AM can only be confirmed by an actual overnight run — no programmatic substitute for a wall-clock trigger"
---

# Phase 3: Scheduler Verification Report

**Phase Goal:** The full 400-building scrape batch runs automatically every day at 2 AM without manual intervention, failures are logged per building, and stale buildings are flagged for admin attention
**Verified:** 2026-02-20T19:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                          | Status     | Evidence                                                                                              |
|----|--------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------------------|
| 1  | APScheduler cron fires at 2 AM Central, sheets sync runs first, then parallel scrape | ✓ VERIFIED | `BlockingScheduler(timezone=ZoneInfo("America/Chicago"))`, `CronTrigger(hour=2, minute=0)`, `run_batch` registered as job; `run_batch` calls `sheets_sync` before `ThreadPoolExecutor` |
| 2  | Each building failure is isolated — one crash does not stop others             | ✓ VERIFIED | `scrape_one_building` wraps all logic in try/except; outer `as_completed` loop also catches unhandled exceptions |
| 3  | Browser-based scrapers run one at a time per platform via semaphore            | ✓ VERIFIED | `threading.Semaphore(1)` for rentcafe, groupfox, llm, entrata, mri, funnel, bozzuto, ppm in `PLATFORM_CONCURRENCY` |
| 4  | HTTP-based scrapers (sightmap, appfolio) run with concurrency of 2 per platform | ✓ VERIFIED | `threading.Semaphore(2)` for sightmap and appfolio in `PLATFORM_CONCURRENCY`                        |
| 5  | On batch failure, units for the failed building are cleared                    | ✓ VERIFIED | Failure branch in `scrape_one_building`: `db.query(Unit).filter(Unit.building_id == building.id).delete()` |
| 6  | SQLite WAL mode is enabled for safe concurrent thread access                   | ✓ VERIFIED | `@event.listens_for(engine, "connect")` sets `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000` |
| 7  | Each scraper run produces a scrape_runs row with building_id, timestamp, status, unit_count | ✓ VERIFIED | `ScrapeRun` model has all fields; `runner.py` creates rows in both success and failure paths |
| 8  | APScheduler cron actually fires at 2 AM and runs the batch unattended          | ? UNCERTAIN | Code is correct; wall-clock overnight confirmation required (see Human Verification) |
| 9  | Stale buildings (consecutive zero count >= 5) are flagged as needs_attention   | ✓ VERIFIED | `building.last_scrape_status = "needs_attention"` when `consecutive_zero_count >= 5` in `runner.py` |
| 10 | scrape_runs rows older than 30 days are pruned after each batch                | ✓ VERIFIED | `_prune_old_runs()` called at end of `run_batch()`; deletes `ScrapeRun` rows where `run_at < cutoff` |

**Score:** 9/10 truths verified (1 requires human confirmation of overnight run)

### Required Artifacts

| Artifact                                    | Expected                                                   | Status      | Details                                                                      |
|---------------------------------------------|------------------------------------------------------------|-------------|------------------------------------------------------------------------------|
| `src/moxie/scrapers/registry.py`            | Single source of truth for PLATFORM_SCRAPERS dict          | VERIFIED    | 11 platforms, `SKIP_PLATFORMS` set; exists, substantive, imported by both `scrape.py` and `push_availability.py` |
| `src/moxie/scheduler/runner.py`             | Per-building scrape wrapper with error isolation           | VERIFIED    | `scrape_one_building()` present; try/except isolation, clear-on-failure, ScrapeRun logging, per-thread SessionLocal |
| `src/moxie/scheduler/batch.py`              | Batch orchestrator: sheets_sync -> thread pool -> results  | VERIFIED    | `run_batch()` present; 3-step flow + Steps 4-6 (status push, availability push, prune); ThreadPoolExecutor + semaphores |
| `src/moxie/scrape_all.py`                   | CLI entrypoint with --run-now vs --schedule (APScheduler) | VERIFIED    | `main()` present; both modes implemented; `BlockingScheduler` in `--schedule` branch |
| `src/moxie/scheduler/sheets_status.py`      | Google Sheets batch status push                            | VERIFIED    | `push_batch_status()` present; summary row + per-building rows; single `ws.update()` call |
| `src/moxie/scheduler/log_config.py`         | Rotating file handler setup                                | VERIFIED    | `configure_logging()` present; `RotatingFileHandler` at `logs/scrape_batch.log`, 5 MB, 7 backups |
| `src/moxie/scheduler/__init__.py`           | Package marker                                             | VERIFIED    | File exists (empty, correct)                                                 |
| `src/moxie/db/session.py`                   | WAL mode on engine connect                                 | VERIFIED    | `@event.listens_for(engine, "connect")` sets WAL + busy_timeout              |
| `logs/scrape_batch.log`                     | Log file populated from dry-run                            | VERIFIED    | File exists; contains 349-building dry-run log entries from 2026-02-20       |

### Key Link Verification

| From                              | To                                    | Via                                              | Status  | Details                                                                           |
|-----------------------------------|---------------------------------------|--------------------------------------------------|---------|-----------------------------------------------------------------------------------|
| `batch.py`                        | `runner.py`                           | ThreadPoolExecutor submitting `_scrape_with_semaphore` -> `scrape_one_building` | WIRED | `pool.submit(_scrape_with_semaphore, ...)` at line 145; `_scrape_with_semaphore` calls `scrape_one_building` |
| `runner.py`                       | `registry.py`                         | `importlib.import_module` using `PLATFORM_SCRAPERS` | WIRED | `from moxie.scrapers.registry import PLATFORM_SCRAPERS` at line 9; used at line 55 |
| `scrape_all.py`                   | `batch.py`                            | CLI calls `run_batch()` (both modes)             | WIRED   | Import at line 17; called at line 63 (immediate) and line 89 (scheduler job)      |
| `scrape_all.py`                   | `batch.py` (via APScheduler)          | `scheduler.add_job(run_batch, CronTrigger(hour=2, minute=0))` | WIRED | Lines 88-90 in `--schedule` branch; `run_batch` is the registered job function   |
| `batch.py`                        | `sheets_status.py`                    | `push_batch_status(results)` at end of `run_batch` | WIRED | Lazy import + call at lines 179-180 (Step 4)                                     |
| `batch.py`                        | `scrape_runs` table (pruning)         | `_prune_old_runs()` deletes rows older than 30 days | WIRED | `_prune_old_runs()` at line 195 (Step 6); function defined at lines 39-53        |
| `scrape.py`                       | `registry.py`                         | Import replacing inline dict                     | WIRED   | `from moxie.scrapers.registry import PLATFORM_SCRAPERS` at line 24               |
| `push_availability.py`            | `registry.py`                         | Import replacing inline dict                     | WIRED   | `from moxie.scrapers.registry import PLATFORM_SCRAPERS` at line 24               |

### Requirements Coverage

| Requirement | Source Plan     | Description                                                    | Status      | Evidence                                                                    |
|-------------|-----------------|----------------------------------------------------------------|-------------|-----------------------------------------------------------------------------|
| INFRA-02    | 03-01, 03-02    | All scrapes run automatically on a daily scheduled basis without manual intervention | SATISFIED | APScheduler `BlockingScheduler` with 2 AM `CronTrigger`; `run_batch` orchestrates full cycle; `scrape-all --schedule` is the daemon entrypoint; `pyproject.toml` registers the CLI |

**Note on INFRA-03 conflict:** INFRA-03 ("retain last known unit data on failure") was explicitly overridden by user decision documented in `03-CONTEXT.md`: "Stale data is NOT real data — units are cleared after failure, not preserved." The clear-on-failure behavior in `runner.py` is intentional and correct per this decision. INFRA-03 is assigned to Phase 2 (which implemented `save_scrape_result` with retention), but Phase 3 deliberately overrides the retention behavior for batch runs. This design decision is documented and intentional.

**Note on "400-building" criterion:** The phase goal says "full 400-building scrape" but the verified dry run shows 349 buildings. The difference is 58 buildings classified as `dead` or `needs_classification` (SKIP_PLATFORMS), which correctly have no working scraper. 349 is the actual working scrapeable population. The criterion language was aspirational — the implementation correctly excludes unscrapeable buildings rather than attempting and failing on them.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No placeholder, stub, or TODO anti-patterns found in any phase 3 files |

Pre-existing test failures (deferred from phase 02):
- `tests/test_scraper_appfolio.py` — stale import (`_parse_html` vs `_parse_listings_html`)
- `tests/test_scraper_llm.py` — `FakeResult` mock missing `success` attribute

Both documented in `deferred-items.md`. Not introduced by phase 3. Phase 3 test suite runs cleanly with `--ignore` flags: 235 passed.

### Human Verification Required

#### 1. Overnight 2 AM Cron Confirmation

**Test:** Run `uv run scrape-all --schedule` before 2 AM Central (or adjust system clock). Leave running until after 2 AM. Check results in the morning.

**Expected:**
- `logs/scrape_batch.log` shows "=== Batch scrape starting ===" at approximately 02:00 Central
- Sheets sync log entry ("Step 1: Syncing building list from Google Sheets...")
- ~349 per-building lines ("OK building_name: N units (platform)" or "FAIL ...")
- "=== Batch complete: X ok, Y failed..." at end
- Google Sheet "Scrape Status" tab overwritten with summary row + 349 per-building rows
- Google Sheet "Availability" tab refreshed with latest unit data
- `scrape_runs` table contains new rows with today's `run_at` timestamp

**Why human:** The APScheduler `CronTrigger(hour=2, minute=0)` can only be confirmed by an actual wall-clock overnight run. Code inspection confirms the trigger is correctly configured and wired to `run_batch`, but the firing itself cannot be simulated programmatically.

### Gaps Summary

No gaps found. All code artifacts exist, are substantive, and are correctly wired. The single outstanding item is the wall-clock confirmation of the 2 AM cron trigger, which is inherently human-verifiable after the first overnight run.

**ROADMAP.md minor doc issue:** Line 75 of ROADMAP.md still shows `03-02-PLAN.md` as `[ ]` (unchecked) despite plan completion. This is a documentation artifact, not a code gap — the code is fully implemented. The table at the bottom of ROADMAP.md correctly shows Phase 3 as "Complete (2026-02-20)".

---

## Commit Verification

All four phase commits verified in git log:

| Commit  | Task                                          | Status  |
|---------|-----------------------------------------------|---------|
| 88c52a5 | 03-01 Task 1: Scraper registry + WAL mode     | FOUND   |
| 3cb1a26 | 03-01 Task 2: Batch infrastructure + CLI      | FOUND   |
| 4e3aa09 | 03-02 Task 1: Sheets status + log + pruning   | FOUND   |
| 25e556b | 03-02 Task 2: APScheduler 2 AM cron + CLI     | FOUND   |

---

_Verified: 2026-02-20T19:30:00Z_
_Verifier: Claude (gsd-verifier)_
