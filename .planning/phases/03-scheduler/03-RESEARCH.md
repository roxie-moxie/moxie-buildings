# Phase 3: Scheduler - Research

**Researched:** 2026-02-20
**Domain:** Python APScheduler, asyncio concurrency, per-platform batch scraping, SQLite concurrency, Google Sheets rate limits
**Confidence:** HIGH (APScheduler API verified from official docs; scraper architecture from live codebase inspection; concurrency patterns from official Python docs and verified sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Deployment target**: Runs on local Windows 11 machine that is always on at 2 AM
- **Both automated 2 AM cron AND manual `uv run scrape-all` CLI** command for on-demand runs
- **Single-building on-demand runs preserved** — `uv run scrape --building "NAME"` continues to work unchanged
- **Batch runner reuses same per-building scrape logic** as existing single-building commands
- **Scrape pacing & concurrency**:
  - Conservative: 1-2 concurrent scrapers per platform, with delays between buildings
  - Crawl4AI browser scrapers: 1 browser instance at a time (sequential)
  - HTTP-based scrapers (SightMap JSON API, PPM): run in parallel alongside sequential browser scrapes
- **Full cycle**: pull building list from Sheets -> scrape all -> push results to Sheet
- **Sheets sync runs first**, then scraping, then Sheets push
- **Failure & data retention**:
  - Stale data is NOT real data — units are cleared after failure (overrides INFRA-03 retain behavior)
  - This means: on failure, delete existing units for that building, write scrape_runs row with status=failed
  - Threshold for clearing and retry logic: Claude's discretion
- **Google Sheet summary after each batch run**:
  - Summary row: date, total buildings scraped, successes, failures, total units found
  - Per-building status tab: one row per building, latest scrape date, status (ok/failed/stale), unit count — overwritten each run (not accumulated)
- **scrape_runs DB table** for programmatic access (already exists in schema)

### Claude's Discretion

- Process management approach (background service vs long-running terminal process)
- Exact concurrency limits per platform (1 vs 2)
- Retry strategy details (immediate retry with delay vs next-day only)
- Staleness threshold (after how many consecutive failures to flag)
- Data clearing threshold (after how many failures to remove units)
- Long-term failure backoff policy
- Local log file approach
- Compression/rotation of logs

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-02 | All scrapes run automatically on a daily scheduled basis without manual intervention | APScheduler 3.x BlockingScheduler with cron trigger at 2 AM; Windows process management via NSSM or long-running terminal; `scrape-all` CLI also satisfies manual run requirement |

</phase_requirements>

---

## Summary

The scheduler phase adds a batch orchestration layer on top of the already-working per-building scraper modules. The core problem is coordinating ~400 buildings across platforms with different concurrency constraints: Crawl4AI browser scrapers (SecureCafe, Groupfox, PPM, LLM) must run sequentially due to Playwright's single-browser-instance constraint, while HTTP-based scrapers (SightMap, AppFolio, PPM API) can run concurrently. APScheduler 3.x (currently at 3.11.2) is the proven standard for this job — a `BlockingScheduler` with a 2 AM cron trigger is all that's needed since the machine is always on. The scrapers already use `asyncio.run()` internally, so the batch runner can call each `scrape()` function synchronously in a thread pool, using per-platform semaphores to enforce concurrency limits.

The biggest implementation subtlety is the mix of sync and async scrapers in the existing codebase. SightMap and PPM scrapers are sync (using `httpx.Client`); SecureCafe, Groupfox, and LLM scrapers are sync wrappers that internally call `asyncio.run()`. Calling `asyncio.run()` from inside a thread pool (via `run_in_executor`) fails if there is already a running event loop in that thread. The safe approach is: run each building's `scrape()` call in a `ThreadPoolExecutor` thread, where each thread owns its own event loop. This avoids all nested event loop problems and keeps the batch runner simple.

Google Sheets update at the end of the run must be a single batch write (one `ws.update()` call for the entire per-building status tab), not one API call per building — the Sheets API is limited to 300 requests/minute per project and 60/minute per user. The scrape_runs table already exists in the schema and will capture per-run data.

**Primary recommendation:** Use APScheduler 3.x `BlockingScheduler` + `ThreadPoolExecutor` with per-platform semaphores. Run `scrape-all` as a long-lived process managed by NSSM (auto-restart on crash) or started manually in a terminal — keep it simple, avoid daemon complexity.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 (3.x) | Cron scheduling, job management | Mature, stable, in-process, cross-platform — does not require a running daemon or server |
| Python standard `concurrent.futures.ThreadPoolExecutor` | stdlib | Thread pool for parallel building scrapes | No extra dependency; works correctly with asyncio.run() isolation per thread |
| Python standard `asyncio.Semaphore` | stdlib | Per-platform concurrency limits | Lightweight, built-in, avoids external rate-limit libraries |
| Python standard `logging` + `RotatingFileHandler` | stdlib | Local log file with size rotation | No extra dependency; battle-tested |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytz or `zoneinfo` (stdlib, Python 3.9+) | stdlib | Timezone for APScheduler cron trigger | APScheduler 3.x requires timezone to be specified for cron triggers |
| gspread | 6.2.1 (already in project) | Google Sheets batch status write | Already installed; batch_update() for single-call status tab write |
| NSSM | latest | Windows service wrapper — keeps process alive | Only needed for unattended overnight operation; optional if running in a terminal |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler BlockingScheduler | Windows Task Scheduler | WTS is simpler but requires a short-lived script (no long-running process); APScheduler keeps job state in-process |
| APScheduler BlockingScheduler | APScheduler AsyncIOScheduler | AsyncIOScheduler is slightly cleaner for async code, but our scraper functions wrap asyncio internally — blocking + thread pool avoids nested event loop issues entirely |
| ThreadPoolExecutor | asyncio.gather with run_in_executor | Same underlying mechanism; `ThreadPoolExecutor.map/submit` is simpler to reason about for this batch use case |
| RotatingFileHandler | JSON structured logging | JSON logs are better for parsing by tools; plain text is sufficient for this use case (debug in morning, check sheet for summary) |

**Installation:**
```bash
uv add apscheduler
# pytz not needed if using Python 3.9+ zoneinfo; otherwise: uv add pytz
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/moxie/
├── scheduler/
│   ├── __init__.py
│   ├── batch.py          # run_batch(): orchestrates full scrape cycle
│   └── runner.py         # scrape_one_building(): wraps scrape() + save_scrape_result()
├── scraper_all.py        # CLI entrypoint: `scrape-all` (both scheduled and manual)
```

The scheduler module is thin: `batch.py` calls sheets_sync, then fans out building scrapes using a thread pool with per-platform semaphores, then writes the summary to Google Sheets. `runner.py` is the per-building wrapper (scrape + save + error isolation). `scraper_all.py` is registered in `pyproject.toml` as the `scrape-all` CLI entry point, and also wires up APScheduler for the 2 AM cron.

### Pattern 1: APScheduler 3.x BlockingScheduler with 2 AM Cron

**What:** A long-running Python process that sleeps until 2 AM, then triggers the full batch. The `scrape-all` CLI can also be called directly to trigger an immediate run without scheduling.

**When to use:** Always — this is the locked decision for this phase.

```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-now", action="store_true", help="Run immediately, then exit")
    args = parser.parse_args()

    if args.run_now:
        run_batch()  # Manual on-demand run
        return

    # Scheduled mode: fire at 2 AM Chicago time daily
    scheduler = BlockingScheduler(timezone=ZoneInfo("America/Chicago"))
    scheduler.add_job(
        run_batch,
        CronTrigger(hour=2, minute=0),
        id="daily_scrape",
        name="Daily full-building scrape",
        misfire_grace_time=3600,   # Run within 1h of missed trigger (e.g. after restart)
        coalesce=True,              # Only run once if multiple firings were missed
        max_instances=1,            # Never run two batch jobs concurrently
    )
    print("Scheduler started. Next run at 2 AM. Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
```

### Pattern 2: Per-Building Thread Pool with Per-Platform Semaphores

**What:** Fan out building scrapes across threads. Each platform gets a semaphore capping concurrent runs. Browser-based scrapers (SecureCafe, Groupfox, LLM) get a semaphore of 1; HTTP scrapers (SightMap, PPM) get 2.

**Critical insight:** The existing scrapers use `asyncio.run()` internally (SecureCafe, PPM, LLM all call `asyncio.run()`). Calling `asyncio.run()` from a thread that is already running an event loop causes `RuntimeError: This event loop is already running`. The fix: run each `scrape()` call in a fresh `ThreadPoolExecutor` thread. Each thread has no running event loop, so `asyncio.run()` inside the scraper works correctly.

```python
# Pattern: per-platform semaphore + thread pool, isolation per building
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Semaphores keyed by platform — created once, shared across threads via threading.Semaphore
_PLATFORM_SEMAPHORES: dict[str, threading.Semaphore] = {
    # Browser-based: 1 at a time (Playwright is not thread-safe across sessions)
    "rentcafe": threading.Semaphore(1),
    "groupfox":  threading.Semaphore(1),
    "llm":       threading.Semaphore(1),
    "entrata":   threading.Semaphore(1),
    "mri":       threading.Semaphore(1),
    "funnel":    threading.Semaphore(1),
    "bozzuto":   threading.Semaphore(1),
    # HTTP-based: allow 2 concurrent
    "sightmap":  threading.Semaphore(2),
    "appfolio":  threading.Semaphore(2),
    "ppm":       threading.Semaphore(1),   # PPM: 1 shared page, serialize to avoid dup fetches
    "realpage":  threading.Semaphore(1),
}

def scrape_one_building(building) -> dict:
    """Run one building's scraper, return result dict. Called in a thread."""
    platform = building.platform or "llm"
    sem = _PLATFORM_SEMAPHORES.get(platform, threading.Semaphore(1))
    with sem:  # Blocks until slot available for this platform
        try:
            mod = importlib.import_module(PLATFORM_SCRAPERS[platform])
            raw_units = mod.scrape(building)
            # Save result to DB
            db = SessionLocal()
            try:
                save_scrape_result(db, building, raw_units, scrape_succeeded=True)
                db.commit()
            finally:
                db.close()
            return {"building_id": building.id, "status": "success", "unit_count": len(raw_units)}
        except Exception as e:
            # Isolate: one building failure does not affect others
            db = SessionLocal()
            try:
                # On failure: clear units (user decision: stale data = no data)
                db.query(Unit).filter(Unit.building_id == building.id).delete()
                save_scrape_result(db, building, [], scrape_succeeded=False, error_message=str(e))
                db.commit()
            finally:
                db.close()
            return {"building_id": building.id, "status": "failed", "error": str(e)}

def run_batch():
    db = SessionLocal()
    try:
        buildings = db.query(Building).filter(Building.platform != "dead").all()
    finally:
        db.close()

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(scrape_one_building, b): b for b in buildings}
        for future in as_completed(futures):
            results.append(future.result())

    # Post-batch: write summary to Google Sheets
    _push_batch_summary(results)
```

**Why `threading.Semaphore` not `asyncio.Semaphore`:** The batch loop runs in the main thread (synchronously); threads use `threading.Semaphore` which is thread-safe without an event loop.

### Pattern 3: Failure Isolation — One Building Cannot Kill the Batch

**What:** Each building's scrape runs inside a try/except. Exceptions are caught per-building. The `as_completed()` loop processes results without propagating exceptions to the pool.

**On failure behavior (user decision):** Clear existing units for the failed building. This differs from the current `save_scrape_result()` failure path which retains units. The batch runner must explicitly delete units before calling `save_scrape_result()` on failure — or `save_scrape_result()` needs a new `clear_on_failure=True` flag.

**Current `save_scrape_result()` failure path (from base.py):**
```python
# On failure: retains existing units, sets last_scrape_status='failed'
else:
    building.last_scrape_status = "failed"
    building.last_scraped_at = now
```

**Required change for Phase 3:** The batch runner should delete units on failure before calling save_scrape_result, OR add a parameter to base.py. The `clear_on_failure` behavior is new for the batch runner — single-building `scrape` and `validate-building` commands should retain their current behavior (to preserve Phase 2 validation workflow).

### Pattern 4: Google Sheets Batch Status Write

**What:** After the full batch run, write one row per building to a "Scrape Status" tab. Use a single `ws.update()` call (not per-building API calls) to stay within the 60 requests/minute per-user limit.

```python
# Single batch write — counts as ONE API request regardless of row count
status_rows = [["Building", "Status", "Units", "Last Scraped", "Error"]]
for r in results:
    status_rows.append([r["building_name"], r["status"], r.get("unit_count", 0),
                        r["scraped_at"], r.get("error", "")])
ws.update(status_rows, value_input_option="RAW")  # One call for all 400 rows
```

**Rate limit context:** 300 write requests per 60 seconds per project, 60 per user. The batch run writes to TWO tabs (Availability + Scrape Status) — that's 2 API calls. No rate limit concern.

### Anti-Patterns to Avoid

- **Calling `asyncio.run()` in a thread that already has a running event loop:** The batch runner must not be inside an `asyncio` event loop itself. Use `BlockingScheduler` (not `AsyncIOScheduler`) to keep the top-level context synchronous.
- **One DB session shared across threads:** SQLAlchemy sessions are not thread-safe. Each thread must create its own `SessionLocal()` and close it when done.
- **One Google Sheets API call per building for the status tab:** This would exhaust the 60/minute per-user quota. Always batch into a single `ws.update()`.
- **Ignoring the PPM special case:** PPM has 19 buildings on one shared page. The batch runner should call PPM's scraper once per unique PPM page, then distribute units to buildings — or accept the per-building call (PPM scraper fetches the page each time). At 19 buildings, the extra fetches are acceptable; no change needed unless it's explicitly an issue.
- **Running the LLM scraper concurrently with other LLM scrapes:** The LLM scraper calls the Anthropic API which has its own rate limits. Keep `llm` semaphore at 1 and add an inter-scrape delay.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cron scheduling | Custom sleep loop with time checks | APScheduler 3.x CronTrigger | Handles DST, misfire_grace_time, coalesce on restart — all edge cases |
| Thread pool management | Manual thread creation + join | `concurrent.futures.ThreadPoolExecutor` | stdlib; handles exceptions, `as_completed()`, proper shutdown |
| Per-platform concurrency | Custom counter with locks | `threading.Semaphore` | stdlib; atomic, correct, no overhead |
| Log rotation | Custom file truncation | `logging.handlers.RotatingFileHandler` | stdlib; handles size limits, backup file count |
| Windows auto-start after crash | Manual restart script | NSSM | Tested production solution; handles stdout/stderr capture, auto-restart |

**Key insight:** Every problem in this phase has a stdlib or well-maintained ecosystem solution. Custom implementations of scheduling, thread pooling, and log rotation introduce correctness bugs that are hard to detect until 3 AM.

---

## Common Pitfalls

### Pitfall 1: Nested Event Loop Crash (`asyncio.run()` inside a thread with a running loop)

**What goes wrong:** If the batch runner uses `AsyncIOScheduler` or `asyncio.gather()` at the top level, and then calls a scraper that also calls `asyncio.run()` (SecureCafe does this: `asyncio.run(_fetch_rendered_html(...))`), Python raises `RuntimeError: This event loop is already running`.

**Why it happens:** `asyncio.run()` creates and runs a new event loop in the current thread. If a loop is already running (because the caller is inside an async context), this fails.

**How to avoid:** Keep the batch runner top-level synchronous. Use `BlockingScheduler` (not `AsyncIOScheduler`). Let each scraper thread call `asyncio.run()` in its own clean thread. `ThreadPoolExecutor` threads start with no running event loop.

**Warning signs:** `RuntimeError: This event loop is already running` in logs.

### Pitfall 2: Shared SQLAlchemy Session Across Threads

**What goes wrong:** Session state corruption, `DetachedInstanceError`, or SQLite `database is locked` errors when multiple threads write through the same session.

**Why it happens:** SQLAlchemy sessions are not thread-safe. SQLite's default locking mode allows only one writer at a time; concurrent writes from multiple sessions cause `OperationalError: database is locked`.

**How to avoid:** Each thread creates its own session (`db = SessionLocal()`), uses it, commits, and closes it. Never share a session across threads. The existing `check_same_thread=False` in session.py is necessary for SQLite but is not sufficient to make shared sessions safe.

**SQLite WAL mode:** Enabling WAL mode (`PRAGMA journal_mode=WAL`) allows concurrent reads alongside a writer and significantly reduces write-lock contention. Add this as a connection event at app startup. With per-thread sessions and WAL, the ~400-building batch won't deadlock (writes are short, serialized by SQLite, threads wait up to `timeout` seconds).

**How to enable WAL in SQLAlchemy:**
```python
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=30000")  # Wait up to 30s for locks
```

**Warning signs:** `OperationalError: database is locked` in batch logs.

### Pitfall 3: `scrape_runs` Table Growth Without Pruning

**What goes wrong:** Running 400 buildings daily creates 400 rows/day = 146,000 rows/year. Queries slow down; DB size grows.

**Why it happens:** `scrape_runs` accumulates indefinitely; there is no purge job.

**How to avoid:** Add a cleanup step at the end of each batch: delete `scrape_runs` rows older than N days (e.g., 30 days). One SQL `DELETE` statement; takes milliseconds.

**Warning signs:** `scrape_runs` query latency increases over weeks; DB file grows beyond expected size.

### Pitfall 4: Google Sheets Rate Limit from Multiple Tab Writes

**What goes wrong:** Writing to both "Availability" and "Scrape Status" tabs plus a summary row as separate API calls hits the 60/minute per-user limit if done naively in a loop.

**Why it happens:** Per-building sheet updates (one call per building) = 400 API calls. Rate limit is 60/minute per user.

**How to avoid:** Build the complete status table in memory first, then write it all at once with a single `ws.update()` call. The existing `push_availability()` already does this correctly — follow the same pattern for the status tab.

**Warning signs:** `gspread.exceptions.APIError: {'code': 429, 'message': 'Quota exceeded...'}` in logs.

### Pitfall 5: Windows ProactorEventLoop Requirement for Playwright/Crawl4AI

**What goes wrong:** Crawl4AI uses Playwright which requires `ProactorEventLoop` on Windows. If the batch process changes the event loop policy, Crawl4AI may fail with `NotImplementedError`.

**Why it happens:** Python 3.8+ defaults to `ProactorEventLoop` on Windows, but some code explicitly sets `SelectorEventLoop` which doesn't support async subprocesses.

**How to avoid:** Don't set any custom event loop policy. Python's default on Windows 11 with Python 3.12 is already `ProactorEventLoop`. Never add `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`.

**Warning signs:** Playwright hanging or `NotImplementedError` on asyncio subprocess calls.

---

## Code Examples

Verified patterns from official sources and codebase inspection:

### APScheduler 3.x: 2 AM Cron Job Setup

```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BlockingScheduler(timezone=ZoneInfo("America/Chicago"))
scheduler.add_job(
    run_batch,
    CronTrigger(hour=2, minute=0),
    id="daily_scrape",
    misfire_grace_time=3600,  # Run if missed by up to 1 hour (e.g. machine woke late)
    coalesce=True,             # Don't double-run if multiple fires were missed
    max_instances=1,           # Never run two batches at once
)
scheduler.start()             # Blocks until KeyboardInterrupt or SystemExit
```

### ThreadPoolExecutor: Parallel Building Scrapes

```python
# Source: Python stdlib docs + pattern from APScheduler job handler
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_batch():
    buildings = get_all_scrapeable_buildings()
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_to_building = {pool.submit(scrape_one_building, b): b for b in buildings}
        for future in as_completed(future_to_building):
            building = future_to_building[future]
            try:
                result = future.result()
            except Exception as e:
                # Shouldn't reach here if scrape_one_building handles exceptions internally
                result = {"building_id": building.id, "status": "error", "error": str(e)}
            results.append(result)
    return results
```

### Per-Platform Semaphore: Thread-Safe Concurrency Limits

```python
# Source: Python stdlib threading docs
import threading

PLATFORM_CONCURRENCY = {
    "rentcafe": 1,   # Crawl4AI/Playwright: 1 at a time
    "groupfox": 1,
    "llm": 1,
    "entrata": 1,
    "mri": 1,
    "sightmap": 2,   # HTTP only: allow 2 parallel
    "appfolio": 2,
    "ppm": 1,        # Shared page — serialize to avoid duplicate fetches
    "funnel": 1,
    "bozzuto": 1,
    "realpage": 1,
}

_semaphores = {p: threading.Semaphore(n) for p, n in PLATFORM_CONCURRENCY.items()}
_default_sem = threading.Semaphore(1)

def scrape_one_building(building) -> dict:
    platform = building.platform or "llm"
    sem = _semaphores.get(platform, _default_sem)
    with sem:
        # scrape, save, return result
        ...
```

### WAL Mode for SQLite Concurrent Writes

```python
# Source: SQLite docs + SQLAlchemy event API
from sqlalchemy import event
from moxie.db.session import engine

@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=30000")
```

### Rotating Log File

```python
# Source: Python stdlib logging docs
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "logs/scrape_batch.log",
    maxBytes=5 * 1024 * 1024,   # 5 MB per file
    backupCount=7,                # Keep 7 rotations (~35 MB total)
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.getLogger("moxie").addHandler(handler)
logging.getLogger("moxie").setLevel(logging.INFO)
```

### Google Sheets: Single-Call Status Tab Write

```python
# Source: gspread docs https://docs.gspread.org/en/latest/user-guide.html
# Counts as ONE API request regardless of row count
header = ["Building", "Platform", "Status", "Units", "Last Scraped", "Error"]
rows = [header]
for r in batch_results:
    rows.append([
        r["building_name"], r["platform"], r["status"],
        r.get("unit_count", 0), r["scraped_at"], r.get("error", "")[:200],
    ])
ws.clear()
ws.update(rows, value_input_option="RAW")  # Single API call
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Celery + Redis for task queuing | APScheduler 3.x in-process scheduler | N/A (project choice) | No Redis dep, no worker process, simpler ops |
| `asyncio.gather` for parallel scrapers | `ThreadPoolExecutor` for parallel scrapers | N/A | Avoids nested event loop issues with existing sync wrappers |
| crontab (Linux/Mac) | APScheduler cron trigger (cross-platform) | N/A (Windows target) | Works on Windows without WSL |

**Deprecated/outdated:**
- APScheduler 4.x (stable docs show `0.0.post50`) — despite being newer, 4.x has a completely redesigned API incompatible with 3.x patterns, and the `0.0.post50` stable version label suggests it is still pre-1.0. Use 3.11.2 (3.x), which is the mature production-ready release.

---

## Existing Codebase Facts (Critical for Planning)

These are facts from inspecting the live codebase that directly constrain the implementation plan:

1. **Scrapers are synchronous wrappers**: All `scrape(building)` functions have a sync signature. SecureCafe, PPM, Groupfox, and LLM scrapers internally call `asyncio.run()`. SightMap and AppFolio use `httpx` (sync). The batch runner can call all of them uniformly via `mod.scrape(building)`.

2. **`save_scrape_result()` on failure retains units** (base.py line 83-84): The current failure path does NOT delete units. The batch runner's "clear on failure" behavior requires either: (a) a new `clear_on_failure=True` kwarg on `save_scrape_result()`, or (b) the batch runner explicitly deletes units before calling `save_scrape_result()` on failure.

3. **`PLATFORM_SCRAPERS` dict is duplicated** in `scrape.py` and `push_availability.py` with a comment "keep in sync". The batch runner will need this dict too — this should be centralized into a shared module (e.g., `moxie.scrapers.registry`) as part of Phase 3.

4. **`scrape_runs` table already exists**: Building ID, run_at, status, unit_count, error_message. No schema migration needed for logging batch runs.

5. **`buildings.last_scrape_status`** field exists with values: `"never"`, `"success"`, `"failed"`, `"needs_attention"`. The per-building status tab in Google Sheets can map directly to this field.

6. **`consecutive_zero_count` on Building model** already tracks consecutive zero-unit successes. The staleness flag (`needs_attention`) is already triggered at `CONSECUTIVE_ZERO_THRESHOLD = 5`. This mechanism can be reused for the batch runner without changes.

7. **`sheets_sync(db)` function** in `moxie.sync.sheets` is already callable programmatically — the batch runner can import and call it directly without subprocess overhead.

8. **PPM scraper special case**: PPM fetches the same page for all 19 buildings. When 19 PPM buildings scrape concurrently (even with sem=1 per building), they still hit the page 19x. Options: (a) accept it (19 fetches, PPM page is fast), (b) pre-scrape PPM once and pass units to all 19 buildings. Option (a) is fine for now given sem=1.

---

## Open Questions

1. **`max_workers` for ThreadPoolExecutor**
   - What we know: 400 buildings; browser scrapers serialize via semaphore(1); HTTP scrapers can run 2x
   - What's unclear: Optimal pool size — too large wastes OS threads; too small adds latency
   - Recommendation: Start with `max_workers=8`. Most threads block on I/O or wait for their semaphore; 8 active threads cover multiple platforms simultaneously without overwhelming the machine.

2. **Inter-building delay for same platform**
   - What we know: User wants "delays between buildings" but exact values are Claude's discretion
   - What's unclear: How much delay is enough to avoid 429s on SecureCafe/SightMap
   - Recommendation: Start with 0.5s delay after releasing semaphore for browser platforms, 0s for HTTP. Add a configurable `INTER_SCRAPE_DELAY_SECS` env var so it can be tuned without code changes.

3. **Dry run mode for rate-limit testing**
   - Success criterion 3 requires a "simulated full 400-building dry run with zero 429 responses"
   - What we know: Dry run = call `scrape()` but skip `save_scrape_result()` — or mock scrape functions
   - Recommendation: Add `--dry-run` flag to `scrape-all` that calls scrapers but skips DB writes. Log which buildings would be scraped. Count 429 responses by checking for HTTP 429 in exception messages.

4. **When to clear units on failure (threshold)**
   - What we know: "Stale data is NOT real data" — clear after failure
   - What's unclear: Should clearing be immediate (after first failure) or after N failures?
   - Recommendation: Clear immediately on failure. The user was explicit: stale listings can mislead agents. If the scraper succeeds on next run, units are restored. One failed night is acceptable data loss; stale listings persisting for days is not.

---

## Sources

### Primary (HIGH confidence)
- https://apscheduler.readthedocs.io/en/3.x/userguide.html — BlockingScheduler, CronTrigger, misfire_grace_time, coalesce, max_instances, timezone
- https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html — CronTrigger parameter reference (hour, minute, timezone, jitter)
- https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html — SQLAlchemyJobStore API
- https://developers.google.com/workspace/sheets/api/limits — 300 req/min per project, 60/min per user, no daily limit
- https://docs.python.org/3/library/concurrent.futures.html — ThreadPoolExecutor, as_completed
- https://docs.python.org/3/library/logging.handlers.html — RotatingFileHandler
- Live codebase inspection: `src/moxie/scrapers/base.py`, `src/moxie/db/models.py`, `src/moxie/db/session.py`, `src/moxie/scrape.py`, `src/moxie/sync/push_availability.py`, `src/moxie/sync/sheets.py`, all scraper modules

### Secondary (MEDIUM confidence)
- https://pypi.org/project/APScheduler/ — APScheduler 3.11.2 is current stable (Dec 22 2025 release)
- https://sqlite.org/threadsafe.html + community sources — WAL mode for concurrent writers, busy_timeout
- https://docs.crawl4ai.com/complete-sdk-reference/ — AsyncWebCrawler arun_many(), session reuse
- https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm/ — NSSM Windows service wrapper
- https://oxylabs.io/blog/python-script-service-guide — NSSM for long-running Python process on Windows

### Tertiary (LOW confidence)
- Community reports of APScheduler AsyncIOScheduler crashing on Windows 11 — GitHub issue #952 (2024); specific to AsyncIOScheduler not BlockingScheduler. Using BlockingScheduler avoids this.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — APScheduler 3.11.2 verified on PyPI; stdlib tools verified in Python docs
- Architecture: HIGH — Patterns derived from codebase inspection and verified library APIs
- Pitfalls: HIGH — Nested event loop, thread-safety, and rate limit risks are documented facts verified with official sources

**Research date:** 2026-02-20
**Valid until:** 2026-08-20 (APScheduler 3.x is mature/stable; Python stdlib APIs are stable; Google Sheets quotas change rarely)
