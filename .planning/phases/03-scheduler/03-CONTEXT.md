# Phase 3: Scheduler - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Daily batch runner that scrapes all ~400 buildings automatically, logs results per building, and flags stale buildings. Includes a manual "run now" CLI command. The scheduler runs on a local Windows machine with APScheduler cron at 2 AM. Admin UI for viewing scrape health is Phase 5 scope.

</domain>

<decisions>
## Implementation Decisions

### Deployment target
- Runs on local Windows 11 machine that is always on at 2 AM
- Both an automated 2 AM cron schedule AND a manual `uv run scrape-all` CLI command for on-demand runs
- Single-building on-demand runs preserved (`uv run scrape --building "NAME"` continues to work)
- Batch runner reuses the same per-building scrape logic as the existing single-building commands

### Scrape pacing & concurrency
- Conservative approach: 1-2 concurrent scrapers per platform, with delays between buildings
- Crawl4AI browser scrapers: 1 browser instance at a time (sequential)
- HTTP-based scrapers (SightMap JSON API, PPM) run in parallel alongside the sequential browser scrapes
- Sheets sync runs first (pull building list), then scraping, then Sheets push (updated availability data)
- Full cycle: pull building list -> scrape all -> push results to Sheet

### Failure & data retention
- **Stale data is NOT real data** — units are cleared after failure, not preserved
- Threshold for clearing: Claude's discretion (balance transient failures vs data freshness)
- Retry logic: Claude's discretion (based on failure patterns observed in Phase 2)
- Long-term failure backoff: Claude's discretion
- Staleness threshold for flagging: Claude's discretion
- Note: This overrides INFRA-03's "retain last known data" — user explicitly wants failed buildings to show no units rather than stale listings that could mislead agents

### Run monitoring
- Google Sheet summary after each batch run:
  - **Summary row**: date, total buildings scraped, successes, failures, total units found
  - **Per-building status tab**: one row per building with latest scrape date, status (ok/failed/stale), unit count — overwritten each run (latest only, no history accumulation)
- Local log file: Claude's discretion (for debugging)
- scrape_runs DB table for programmatic access

### Claude's Discretion
- Process management approach (background service vs long-running terminal process)
- Exact concurrency limits per platform (1 vs 2)
- Retry strategy details (immediate retry with delay vs next-day only)
- Staleness threshold (after how many consecutive failures to flag)
- Data clearing threshold (after how many failures to remove units)
- Long-term failure backoff policy
- Local log file approach
- Compression/rotation of logs

</decisions>

<specifics>
## Specific Ideas

- The batch scheduler should feel like a cron job — fire and forget, check results in the morning via the Google Sheet
- Must coexist with the existing `validate-building` and `scrape` single-building commands
- Google Sheet already has ID `1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI` and an Availability tab — scheduler pushes to same sheet

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-scheduler*
*Context gathered: 2026-02-20*
