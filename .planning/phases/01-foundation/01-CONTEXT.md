# Phase 1: Foundation - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

The database schema, normalization module, Google Sheets sync, and dev environment. This phase establishes the data contract that every scraper in Phase 2 depends on. It delivers: a running local environment (single command), a populated schema with seed data, a working `sheets-sync` command, and a shared normalizer that rejects or flags invalid scraper output at write time.

Creating scraper modules, scheduling, and any frontend are explicitly out of scope.

</domain>

<decisions>
## Implementation Decisions

### Database & stack
- **Local dev:** SQLite (zero-config, file-based)
- **Production target:** PostgreSQL (SQLite for dev, swap at deploy via SQLAlchemy abstraction)
- **ORM:** SQLAlchemy (enables SQLite↔PostgreSQL portability)
- **Migrations:** Alembic
- **Python tooling:** uv (replaces pip + venv — `uv sync` for install)

### Dev environment
- **Startup command:** `uv run dev` or `make dev` (pure Python, no Docker)
- **What it does:** creates venv, installs deps, runs migrations, seeds DB
- **Config:** `.env` for secrets (gitignored), `.env.example` committed with all required var names and placeholder values
- **DB inspection:** CLI only (`sqlite3` + custom query scripts) — no Datasette or GUI tools in Phase 1
- **Seed data:** 3–5 buildings + 5–10 units (representative enough to test queries and filters during Phase 2+ development)

### Schema — buildings table
Columns synced from Google Sheets:
- `id` (auto-increment PK)
- `name`
- `url` (unique — primary upsert key)
- `neighborhood`
- `management_company`
- `platform` (which scraper tier: 'api' / 'platform' / 'llm')
- `rentcafe_property_id` (nullable — RentCafe API buildings only)
- `rentcafe_api_token` (nullable — RentCafe API buildings only)
- `last_scrape_status` ('never' / 'success' / 'failed')
- `last_scraped_at` (timestamp of last successful scrape run)

Amenity columns (washer/dryer, parking, etc.) deferred to a future migration when that data is available.

### Schema — units table
- `id` (auto-increment PK)
- `building_id` (FK → buildings)
- `unit_number` (any non-empty string — no format constraint)
- `bed_type` (canonical string from normalizer)
- `rent_cents` (integer — e.g., 150000 = $1,500.00)
- `availability_date` (TEXT, ISO format: YYYY-MM-DD)
- `floor_plan_name` (nullable TEXT)
- `floor_plan_url` (nullable TEXT)
- `baths` (nullable)
- `sqft` (nullable)
- `scrape_run_at` (timestamp set at insert time)
- Unique constraint on `(building_id, unit_number)` for upsert identity

**On re-scrape:** delete all units for the building, then insert fresh. No unit history retained — freshness tracked at the building level via `last_scraped_at`.

### Schema — scrape_runs table
Defined in Phase 1 (Phase 2 scrapers write to it):
- `id` (auto-increment PK)
- `building_id` (FK → buildings)
- `run_at` (timestamp)
- `status` ('success' / 'failed')
- `unit_count` (integer — units returned by scraper)
- `error_message` (nullable TEXT — populated on failure)

### Schema — indexes
Claude's discretion: index filter columns that Phase 4 API will query against (`bed_type`, `rent_cents`, `availability_date`, `building_id`). No instruction to under- or over-index.

### Normalizer — canonical bed types
Exact canonical values the normalizer must output:
- `Studio`
- `Convertible`
- `1BR`
- `1BR+Den`
- `2BR`
- `3BR+`

Any scraper output not matching one of these values is stored as-is with a `non_canonical` flag for manual review (not rejected outright).

### Normalizer — rent
- Stored as integer cents (e.g., $1,500.00 → 150000)
- Normalizer strips `$`, commas, and `.00` suffix; converts to integer

### Normalizer — dates
- Stored as ISO date string: `YYYY-MM-DD`
- Normalizer parses whatever the scraper provides and converts to this format

### Normalizer — neighborhood
- NOT scraped — neighborhood is a building-level attribute from Google Sheets
- Set at sync time, not touched by the normalizer

### Normalizer — last scrape tracking
- `scrape_run_at` on each unit row records when that unit was written
- Building-level freshness tracked via `last_scraped_at` on buildings table

### Google Sheets sync
- **Auth:** Service account `roxie-sheets@moxie-roxie.iam.gserviceaccount.com` (JSON key file path in `.env`)
- **Sheet ID:** Stored in `.env` as `GOOGLE_SHEETS_ID`
- **Tab:** Named tab `Buildings`
- **Upsert key:** `url` — building records matched by URL, not name
- **On building deleted from Sheet:** Hard delete from DB (and cascade delete its units)
- **Output:** Summary after each run — `Added: X, Updated: Y, Deleted: Z`

### Claude's Discretion
- Exact Alembic migration file structure and naming
- SQLAlchemy model organization (single models.py vs per-table files)
- Index definitions beyond primary keys and FKs
- Whether `platform` field on buildings has a DB-level enum constraint or is a plain string
- `scraper_type` field: "platform" column on buildings table (from Sheet) — Claude picks whether to enforce as enum

</decisions>

<specifics>
## Specific Ideas

- The service account email is already provisioned: `roxie-sheets@moxie-roxie.iam.gserviceaccount.com` — no new GCP setup needed, just configure the key file path in `.env`
- Seed data should be representative enough for Phase 2 development (3–5 buildings, 5–10 units) — not just the minimum 1+1 the success criterion requires
- Building-level amenity columns (washer/dryer, parking, etc.) intentionally deferred — the Sheet doesn't have this data yet; add via Alembic migration when ready
- The `rentcafe_property_id` and `rentcafe_api_token` columns exist on buildings because different RentCafe buildings may have different API credentials

</specifics>

<deferred>
## Deferred Ideas

- Building amenity columns (washer/dryer in unit vs building, parking, pets, etc.) — add via Alembic migration in a future phase when Sheet data is available
- Agent toggle/hide UI for filtering buildings by amenity criteria — Phase 5 frontend
- Datasette or any admin DB inspection UI — Phase 5

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-17*
