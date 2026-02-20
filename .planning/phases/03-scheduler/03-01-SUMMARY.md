---
phase: 03-scheduler
plan: 01
subsystem: batch-infrastructure
tags: [scheduler, batch, concurrency, sqlite, wal, registry, cli]
dependency-graph:
  requires: []
  provides: [scrape-all CLI, batch orchestrator, scraper registry, WAL mode]
  affects: [scrape.py, push_availability.py, db/session.py]
tech-stack:
  added: [ThreadPoolExecutor, threading.Semaphore]
  patterns: [registry pattern, per-platform semaphore concurrency, clear-on-failure, WAL mode]
key-files:
  created:
    - src/moxie/scrapers/registry.py
    - src/moxie/scheduler/__init__.py
    - src/moxie/scheduler/runner.py
    - src/moxie/scheduler/batch.py
    - src/moxie/scrape_all.py
  modified:
    - src/moxie/scrape.py
    - src/moxie/sync/push_availability.py
    - src/moxie/db/session.py
    - pyproject.toml
decisions:
  - "PLATFORM_SCRAPERS centralized in registry.py as single source of truth — eliminates drift between scrape.py and push_availability.py"
  - "SQLite WAL mode + 30s busy_timeout enables safe concurrent thread writes during batch runs"
  - "Clear-on-failure semantics: units deleted on scraper error (stale data is not real data)"
  - "Per-platform semaphores: browser platforms (Crawl4AI/Playwright) concurrency=1, HTTP platforms concurrency=2"
  - "db.get(Building, id) over deprecated db.query(Building).get(id) — SQLAlchemy 2.0 style"
metrics:
  duration: "4 minutes"
  completed: "2026-02-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 4
  commits: 2
---

# Phase 03 Plan 01: Batch Scraping Infrastructure Summary

**One-liner:** Thread pool batch scraper with per-platform semaphores, clear-on-failure semantics, and `scrape-all` CLI using centralized registry and SQLite WAL mode.

## What Was Built

### Task 1: Centralized Scraper Registry + SQLite WAL Mode (commit: 88c52a5)

**`src/moxie/scrapers/registry.py`** — New single source of truth for `PLATFORM_SCRAPERS` dict (11 platforms) and `SKIP_PLATFORMS` set. Eliminates the duplicated dict that previously lived in both `scrape.py` and `push_availability.py` with a "keep in sync" comment.

**`src/moxie/db/session.py`** — Added `@event.listens_for(engine, "connect")` listener that sets `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000` on every SQLite connection. Confirmed active: `engine.raw_connection().execute('PRAGMA journal_mode').fetchone()` returns `('wal',)`.

**`src/moxie/scrape.py`** and **`src/moxie/sync/push_availability.py`** — Removed inline `PLATFORM_SCRAPERS` dicts; both now import from `moxie.scrapers.registry`.

### Task 2: Per-Building Runner + Batch Orchestrator + CLI (commit: 3cb1a26)

**`src/moxie/scheduler/runner.py`** — `scrape_one_building(building_id, name, url, platform)` runs in a thread pool thread. Each invocation creates its own `SessionLocal()`, imports the scraper via `importlib`, normalizes results, and commits. On failure: rolls back, clears all units for that building, records ScrapeRun with status="failed". Inter-scrape delay: 1.0s for browser platforms, 0.2s for HTTP platforms.

**`src/moxie/scheduler/batch.py`** — `run_batch()` orchestrates the full cycle: optional `sheets_sync()` call, load all scrapeable buildings from DB (excluding `SKIP_PLATFORMS`), fan out to `ThreadPoolExecutor(max_workers=8)` with per-platform `threading.Semaphore`. Browser platforms (rentcafe, groupfox, llm, entrata, mri, funnel, bozzuto, ppm) get semaphore(1); HTTP platforms (sightmap, appfolio) get semaphore(2). Supports `dry_run` and `skip_sheets_sync` flags.

**`src/moxie/scrape_all.py`** + `pyproject.toml` — CLI registered as `scrape-all`. Supports `--dry-run`, `--skip-sync`, `--run-now` flags.

## Verification Results

- `uv run python -c "from moxie.scrapers.registry import PLATFORM_SCRAPERS; print(len(PLATFORM_SCRAPERS))"` → `11`
- `uv run scrape-all --dry-run --skip-sync` → lists 349 buildings across all platforms, exits 0
- `uv run pytest tests/ --ignore=tests/test_scraper_appfolio.py --ignore=tests/test_scraper_llm.py -q` → `235 passed`
- WAL mode: `('wal',)` confirmed

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written. Minor adjustment: used `db.get(Building, building_id)` instead of `db.query(Building).get(building_id)` in runner.py — the latter is deprecated in SQLAlchemy 2.0 and the plan used the deprecated form. Used the correct 2.0 API.

### Out-of-Scope Discoveries (Deferred)

Two pre-existing test failures were discovered (both introduced in phase 02 when scrapers were rewritten without updating tests):

1. `tests/test_scraper_appfolio.py` — imports `_parse_html` (renamed to `_parse_listings_html` in phase 02 rewrite)
2. `tests/test_scraper_llm.py::test_scrape_with_llm_returns_empty_on_malformed_json` — `FakeResult` mock missing `success` attribute (added to production code in phase 02)

Both documented in `deferred-items.md`. Not fixed (out of scope per deviation rules — pre-existing failures in unrelated files).

## Self-Check: PASSED

All created files exist on disk. Both task commits verified in git log.

| Check | Result |
|-------|--------|
| src/moxie/scrapers/registry.py | FOUND |
| src/moxie/scheduler/__init__.py | FOUND |
| src/moxie/scheduler/runner.py | FOUND |
| src/moxie/scheduler/batch.py | FOUND |
| src/moxie/scrape_all.py | FOUND |
| Commit 88c52a5 (Task 1) | FOUND |
| Commit 3cb1a26 (Task 2) | FOUND |
