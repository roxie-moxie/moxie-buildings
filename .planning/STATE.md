# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Agents can instantly find available units matching any client's criteria across the entire downtown Chicago rental market, with data refreshed daily.
**Current focus:** Phase 3 - Orchestrator (Phase 2 complete)

## Current Position

Phase: 2 of 5 (Scrapers) — COMPLETE
Plan: 9 of 9 in phase — COMPLETE (all Phase 2 plans done)
Status: Phase 2 complete — all scrapers built, LLM benchmark passed ($8.51/month), ready for Phase 3
Last activity: 2026-02-18 — 02-09-PLAN completed (LLM benchmark: $8.51/month, PASS)

Progress: [████████░░] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 12 (3 foundation + 9 scrapers)
- Average duration: ~14 min
- Total execution time: ~165 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3/3 | ~73 min | ~24 min |
| 02-scrapers | 9/9 | ~92 min | ~10 min |

**Recent Trend:**
- Last 5 plans: 02-05 (~10 min), 02-06 (~12 min), 02-07 (~15 min), 02-08 (~18 min), 02-09 (~20 min)
- Trend: 02-09 included human-verify checkpoint (LLM benchmark run by user) — longer than pure code plans

*Updated after each plan completion*
| Phase 02-scrapers P05 | 12 | 2 tasks | 4 files |
| Phase 02-scrapers P09 | 20 | 2 tasks | 2 files |

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
- [02-03]: db.flush() required before detection query in sheets_sync() — autoflush=False sessions don't flush newly-added objects before filter() queries
- [02-03]: Detection pass queries all null-platform buildings (not just newly upserted) — catches buildings from prior sync passes that were missed
- [02-03]: detect_platform() returns None; sheets_sync() assigns 'llm' — fills blanks only, existing non-null platform values never overwritten
- [02-04]: RentCafe scraper STUBBED with NotImplementedError — _fetch_units() raises until credential spike confirms API field names
- [02-04]: RentCafeCredentialError raised before stub when property_id or api_token is missing/empty — prevents silent failure
- [02-04]: Error:1020 guard in _check_for_api_error() prevents silent zero-unit false positives from invalid RentCafe credentials
- [02-04]: _map_unit() uses dual field name fallback (UnitNumber/ApartmentNumber, Beds/Bedrooms) to handle API field name uncertainty
- [02-04]: PPM _matches_building() uses bidirectional partial contains for building name prefix mismatch handling
- [02-07]: Both Crawl4AI scrapers monkeypatch _fetch_rendered_html coroutine directly — cleaner than mocking asyncio.run, avoids event loop complications
- [02-07]: Groupfox URL normalization reconstructs scheme://netloc/floorplans from parsed components — handles root/trailing-slash/other-path cases
- [02-07]: Groupfox _parse_html uses floorplan name as unit_number — /floorplans page lists floorplan types, not individual units
- [02-07]: Both scrapers have SELECTOR VERIFICATION REQUIRED comments — CSS selectors are research-informed approximations, must be confirmed against live URLs
- [Phase 02-scrapers]: Heuristic CSS selectors with SELECTOR VERIFICATION REQUIRED comment — real page inspection needed before trusting scraper output for Funnel and AppFolio
- [Phase 02-scrapers]: FunnelScraperError and AppFolioScraperError raised on non-2xx HTTP — not silent empty lists, preserves save_scrape_result scrape_succeeded=False path
- [02-06]: BozzutoScraperError raised on 403/429/503 with explicit bot detection message and Crawl4AI upgrade recommendation — distinguishes bot detection from generic HTTP errors
- [02-06]: Multi-selector fallback in _parse_html() (available-apartment, fp-apartment, unit-card, apartment-item) — handles Bozzuto page structure variants across ~13 buildings
- [02-06]: Crawl4AI upgrade path left as inline commented block in _fetch_html() — single-file activation, no architectural changes needed
- [02-08]: AsyncWebCrawler tests require context manager mocking (__aenter__/__aexit__/arun) — patching arun alone fails because __aenter__ launches Playwright browsers before arun is reached
- [02-08]: LLM scraper filtering (unit_number/bed_type/rent required) in _scrape_with_llm, not in scrape() -- tests call _scrape_with_llm directly with mocked crawler for filtering coverage
- [02-08]: ANTHROPIC_API_KEY checked at call time in _scrape_with_llm -- import never fails; only scrape() raises EnvironmentError when key absent
- [Phase 02-scrapers]: LLM tier cost benchmarked at $8.51/month — PASS, full-volume enablement approved
- [Phase 02-scrapers]: Token counts for LLM benchmark estimated from output JSON length — not instrumented against Anthropic API, sufficient for gate decision

### Pending Todos

None.

### Blockers/Concerns

- [Phase 2]: Yardi/RentCafe API access is unconfirmed — requires vendor program enrollment before any Yardi scraper code is written. This is a procurement action, not a code task. Must be resolved before Phase 2 Tier 1 scraper.
- [Phase 2]: Entrata deprecated its legacy API gateway April 2025. Correct base URL and auth method for the modernized gateway must be verified before the Entrata scraper is built.
- [Phase 2 — RESOLVED]: LLM token cost benchmarked: $8.51/month (PASS — 93% below $120 target). Full-volume enablement approved.
- [Phase 1 data gap]: platform, rentcafe_property_id, rentcafe_api_token fields not in Google Sheet — must be set manually or via future sheet column before Phase 2 scrapers can use them.

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 02-09-PLAN.md — Phase 2 scrapers complete (all 9/9 plans done). Ready for Phase 3 orchestrator.
Resume file: None
