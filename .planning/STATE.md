# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.
**Current focus:** Phase 2 - Scrapers

## Current Position

Phase: 2 of 5 (Scrapers) — IN PROGRESS
Plan: 2 of 9 in phase — COMPLETE (02-02 done, next: 02-03)
Status: Phase 2 in progress — scraper infrastructure + behavioral tests complete
Last activity: 2026-02-18 — 02-02-PLAN completed (behavioral tests for detect_platform() and save_scrape_result())

Progress: [████░░░░░░] 22%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: ~19 min
- Total execution time: ~77 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3/3 | ~73 min | ~24 min |
| 02-scrapers | 2/9 | ~12 min | ~6 min |

**Recent Trend:**
- Last 5 plans: 01-01 (6 min), 01-02 (22 min), 01-03 (~45 min), 02-01 (4 min), 02-02 (8 min)
- Trend: Pure code plans with no human-verify complete quickly; service verification adds time

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Tiered scraping strategy (API → platform scraper → LLM fallback) — pending final rationale confirmation
- [Pre-Phase 1]: Google Sheets as ongoing building list source of truth — confirmed by plan 03
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
- [01-03]: get_all_values() over get_all_records() — real Moxie sheet has blank header columns that crash get_all_records()
- [01-03]: GOOGLE_SHEETS_TAB_NAME env var with 'Buildings' default — tab name configurable without code change
- [01-03]: Sheet columns in real data: Building Name, Website, Neighborhood, Managment (typo) — no platform/rentcafe columns in sheet
- [01-03]: Rows without Website URL skipped (not errored) and counted as 'skipped' in sync result
- [01-03]: _parse_rows() extracted as pure function for independent testability of column mapping logic
- [02-01]: save_scrape_result separates scrape_succeeded paths — errors do not increment consecutive_zero_count, only zero-unit successes do
- [02-01]: CONSECUTIVE_ZERO_THRESHOLD=5 — buildings get needs_attention status after 5 consecutive zero-unit successful scrapes
- [02-01]: detect_platform returns None (not 'llm') for unrecognized URLs — caller assigns llm platform
- [02-01]: crawl4ai-setup fails on Windows with UnicodeEncodeError (cp1252/arrow char) — Playwright browsers need manual install
- [02-02]: In-memory SQLite per test (not shared session) — each test gets a fresh DB, no state leakage between tests
- [02-02]: Class-based test grouping by behavior path mirrors 4-path behavioral spec
- [02-02]: CONSECUTIVE_ZERO_THRESHOLD imported from source in tests — any future constant change fails test_threshold_constant_is_five immediately

### Pending Todos

None.

### Blockers/Concerns

- [Phase 2]: Yardi/RentCafe API access is unconfirmed — requires vendor program enrollment before any Yardi scraper code is written. This is a procurement action, not a code task. Must be resolved before Phase 2 Tier 1 scraper.
- [Phase 2]: Entrata deprecated its legacy API gateway April 2025. Correct base URL and auth method for the modernized gateway must be verified before the Entrata scraper is built.
- [Phase 2]: LLM token cost must be benchmarked against 5 representative sites before full-volume enablement — $120/month estimate assumes preprocessing reduces pages to <4,000 tokens.
- [Phase 1 data gap]: platform, rentcafe_property_id, rentcafe_api_token fields not in Google Sheet — must be set manually or via future sheet column before Phase 2 scrapers can use them.

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 02-02-PLAN.md (behavioral tests). Next: 02-03-PLAN.md
Resume file: None
