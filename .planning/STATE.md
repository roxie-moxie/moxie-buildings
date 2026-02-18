# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.
**Current focus:** Phase 1 - Foundation

## Current Position

Phase: 1 of 5 (Foundation)
Plan: 2 of 3 in current phase
Status: In progress
Last activity: 2026-02-18 — 01-02-PLAN completed

Progress: [██░░░░░░░░] 13%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 14 min
- Total execution time: 0.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 2/3 | 28 min | 14 min |

**Recent Trend:**
- Last 5 plans: 01-01 (6 min), 01-02 (22 min)
- Trend: TDD plans take longer; baseline for feature plans is ~6 min

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Tiered scraping strategy (API → platform scraper → LLM fallback) — pending final rationale confirmation
- [Pre-Phase 1]: Google Sheets as ongoing building list source of truth — pending
- [Pre-Phase 1]: LLM fallback (Crawl4AI + Claude Haiku) for custom sites — pending
- [Pre-Phase 1]: Daily scrape cadence at 2 AM — pending
- [01-01]: platform field on buildings is plain String (no DB-level enum) — SQLite lacks native ENUM, enforced at app layer
- [01-01]: Single models.py for all three tables — at 3 tables, per-file complexity outweighs benefits
- [01-01]: non_canonical as boolean column on units (not separate table) — valid data for Phase 2 debugging, Phase 4 API filters WHERE non_canonical=false
- [01-01]: Four indexes on units (bed_type, rent_cents, availability_date, building_id) — matching Phase 4 API filter columns
- [01-02]: Unknown bed type aliases stored as-is with original casing preserved (non_canonical=True) — not lowercased, not rejected
- [01-02]: 4BR+ maps to 3BR+ per spec — 4br is in BED_TYPE_ALIASES
- [01-02]: scrape_run_at uses datetime.now(timezone.utc) — datetime.utcnow() deprecated in Python 3.12+
- [01-02]: dateutil.parser.parse() for all non-"available now" dates — format-agnostic, no strptime format strings needed

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Yardi/RentCafe API access is unconfirmed — requires vendor program enrollment before any Yardi scraper code is written. This is a procurement action, not a code task. Must be resolved before Phase 2.
- [Phase 2]: Entrata deprecated its legacy API gateway April 2025. Correct base URL and auth method for the modernized gateway must be verified before the Entrata scraper is built.
- [Phase 2]: LLM token cost must be benchmarked against 5 representative sites before full-volume enablement — $120/month estimate assumes preprocessing reduces pages to <4,000 tokens.

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 01-02-PLAN.md (unit normalizer — TDD: 45 tests, RED/GREEN/REFACTOR)
Resume file: None
