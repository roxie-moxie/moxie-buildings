# Roadmap: Moxie Building Aggregator (MBA)

## Overview

The MBA is built data-first, in strict dependency order. The schema and normalization layer must exist before any scraper writes to it; scrapers must work before the scheduler orchestrates them; the scheduler must have produced real data before the API can be meaningfully tested; and the API contract must be settled before the frontend is typed against it. Five phases, each delivering a coherent and independently verifiable capability, from infrastructure through to the agent-facing search UI.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Schema, normalization, Sheets sync, and dev environment — the layer every scraper depends on
- [ ] **Phase 2: Scrapers** - All scraper modules across three tiers covering ~400 buildings
- [ ] **Phase 3: Scheduler** - Daily batch runner with failure handling and stale flagging
- [ ] **Phase 4: API Layer** - FastAPI auth, filter/search endpoints, and admin endpoints
- [ ] **Phase 5: Frontend** - Agent search UI and admin dashboard wired to the live API

## Phase Details

### Phase 1: Foundation
**Goal**: The database schema, normalization module, and Google Sheets sync are in place — every scraper can write to a defined schema and every subsequent phase can depend on the data contract being settled
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, DATA-01, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. Running `sheets-sync` pulls the full building list from Google Sheets and upserts all records (name, URL, neighborhood, management company) into the local database — observable by querying the buildings table
  2. The canonical UnitRecord Pydantic schema rejects any scraper output that is missing a required field (Unit #, Beds, Base rent, Availability date, Neighborhood, Building name, URL, Last scrape date) at write time
  3. Optional fields (floor plan, baths, sqft) are stored when provided and silently absent when not — no null errors, no required-field violations
  4. All scraper output passes through a single shared normalizer before reaching the database — no platform-specific raw values (e.g., integer 0 for Studio, raw "0BR" strings) survive into stored unit records
  5. The local dev environment starts with a single command and includes a populated database with at least one building and one unit from a manual seed fixture
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold, SQLAlchemy models, and Alembic initial migration
- [x] 01-02-PLAN.md — Normalizer (TDD): UnitInput Pydantic model, normalize() function, full test suite
- [x] 01-03-PLAN.md — Google Sheets sync, seed script, and dev bootstrap command

### Phase 2: Scrapers
**Goal**: All ~400 buildings are covered by working scraper modules across three tiers — Tier 1 REST APIs, Tier 2 platform HTML scrapers, and Tier 3 LLM fallback — with each module validated against real data and normalized output confirmed
**Depends on**: Phase 1
**Requirements**: INFRA-03, SCRAP-01, SCRAP-02, SCRAP-03, SCRAP-04, SCRAP-05, SCRAP-06, SCRAP-07, SCRAP-08, SCRAP-09
**Success Criteria** (what must be TRUE):
  1. Running any individual scraper module against its target buildings produces normalized unit records in the database — verifiable by querying units for those buildings after a single-scraper dry run
  2. A building whose scrape returns zero units (or an HTTP error) is marked stale in the database and retains its previous unit records — the existing data is not deleted on failure
  3. The Yardi/RentCafe scraper has a confirmed access method documented before any Yardi scraper code is merged — not assumed, confirmed
  4. The LLM fallback scraper (Crawl4AI + Claude Haiku) has been benchmarked against at least 5 representative long-tail sites and the per-site token cost confirms the monthly projection is within 20% of $120 before full-volume enablement
  5. A post-scrape audit query run after each tier's scrapers confirms zero units in the database carry non-canonical bed type values (e.g., raw integers or unstandardized strings)
**Plans**: 9 plans

Plans:
- [x] 02-01-PLAN.md — Schema migration (consecutive_zero_count), scraper deps, scrapers/base.py + platform_detect.py
- [x] 02-02-PLAN.md — TDD: detect_platform() and save_scrape_result() behavioral tests
- [x] 02-03-PLAN.md — Extend sheets_sync() with platform detection integration
- [x] 02-04-PLAN.md — Tier 1: RentCafe/Yardi scraper (stub) + PPM single-page scraper
- [x] 02-05-PLAN.md — Tier 2: Funnel/Nestio + AppFolio HTML scrapers
- [ ] 02-06-PLAN.md — Tier 2: Bozzuto HTML scraper with Crawl4AI upgrade path
- [x] 02-07-PLAN.md — Tier 2: RealPage/G5 + Groupfox Crawl4AI scrapers
- [x] 02-08-PLAN.md — Tier 3: LLM fallback scraper (Crawl4AI + Claude Haiku)
- [ ] 02-09-PLAN.md — LLM benchmark: 5 real sites, cost projection, human-verify checkpoint

### Phase 3: Scheduler
**Goal**: The full 400-building scrape batch runs automatically every day at 2 AM without manual intervention, failures are logged per building, and stale buildings are flagged for admin attention
**Depends on**: Phase 2
**Requirements**: INFRA-02
**Success Criteria** (what must be TRUE):
  1. The APScheduler cron job fires at 2 AM daily, runs the Google Sheets sync first, then runs all scrapers in parallel with per-platform concurrency limits — verifiable by inspecting the scrape_runs log after an overnight run
  2. Each scraper run produces a scrape_runs row with building ID, run timestamp, success/failure status, and unit count — observable by querying the scrape_runs table
  3. A simulated full 400-building dry run completes without hitting platform rate limits — confirmed by zero 429 responses and no IP blocks during the dry run
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: API Layer
**Goal**: Authenticated FastAPI endpoints expose unit search with all filter parameters, admin account management, and admin scrape controls — fully testable against real database data from Phase 3 batch runs
**Depends on**: Phase 3
**Requirements**: AGENT-01, ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04
**Success Criteria** (what must be TRUE):
  1. An agent can authenticate with email and password and receive a JWT that grants access to unit search endpoints — unauthenticated requests to protected routes return 401
  2. An admin can create a new agent account, and that agent can immediately log in with the credentials the admin set — verifiable end-to-end via API calls
  3. An admin can disable an agent account and the agent's JWT is no longer accepted by protected endpoints after the account is deactivated
  4. An admin can view the full building list as synced from Google Sheets via the /buildings endpoint (name, URL, neighborhood, management company, scraper type)
  5. An admin can trigger a re-scrape for a specific building via the /admin/rescrape endpoint and poll for completion — the scrape_runs table reflects the new run when done
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Frontend
**Goal**: Agents can log in, search and filter all available units, see data freshness per building, and the admin can manage agent accounts and monitor scrape health — all from the browser with no manual API calls required
**Depends on**: Phase 4
**Requirements**: AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, AGENT-07
**Success Criteria** (what must be TRUE):
  1. An agent can filter the unit results table by any combination of bed type (multi-select), rent range (min/max), availability date (on or before), and neighborhood (multi-select) — results update without a full page reload
  2. An agent can sort the results table by rent, availability date, building name, or neighborhood by clicking column headers
  3. Each row (or building section) in the results table shows a data freshness indicator — green for scraped within 24h, yellow for 24-48h, red for older — so agents know whether to trust the data
  4. An admin can view the scrape health dashboard showing last run time, success/failure status, and stale flag for every building, and can click a re-trigger button to kick off a re-scrape for any individual building
  5. Filter state is reflected in the URL query string — an agent can copy the URL, share it, and a colleague who opens it sees the same filtered results without re-entering any criteria
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-02-18 |
| 2. Scrapers | 5/9 | In Progress|  |
| 3. Scheduler | 0/TBD | Not started | - |
| 4. API Layer | 0/TBD | Not started | - |
| 5. Frontend | 0/TBD | Not started | - |
