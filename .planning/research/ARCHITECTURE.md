# Architecture Research

**Domain:** Scheduled web scraping aggregator with normalized database and private search UI
**Researched:** 2026-02-17
**Confidence:** MEDIUM-HIGH (patterns well-established; specific technology choices verified against official sources and multiple credible sources)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SOURCES                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Google Sheets│  │  Yardi/Entrata│  │  Building Websites (HTML)│   │
│  │  (Sync list) │  │   REST APIs   │  │  PPM / Funnel / Bozzuto  │   │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘   │
└─────────┼─────────────────┼──────────────────────┼──────────────────┘
          │                 │                       │
┌─────────▼─────────────────▼──────────────────────▼──────────────────┐
│                        SCRAPER ENGINE                                │
│                                                                      │
│  ┌─────────────┐  ┌────────────────┐  ┌──────────────────────────┐  │
│  │  API Adapter│  │ Platform Scraper│  │  LLM Fallback            │  │
│  │  (Tier 1)   │  │    (Tier 2)    │  │  Crawl4AI + Claude Haiku │  │
│  │ Yardi/Entrata│  │ PPM/Funnel/    │  │  (~50-70 custom sites)   │  │
│  └──────┬──────┘  │ Bozzuto/etc.   │  │  (Tier 3)                │  │
│         │         └───────┬────────┘  └────────────┬─────────────┘  │
│         └─────────────────┴───────────────────────┘                 │
│                           │                                          │
│                  ┌─────────▼──────────┐                              │
│                  │   Normalizer       │                              │
│                  │ raw → unit schema  │                              │
│                  └─────────┬──────────┘                              │
└────────────────────────────┼─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                         DATA STORE                                   │
│  ┌─────────────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│  │ buildings table │  │  units table  │  │  scrape_runs table   │   │
│  │ (sync from GS)  │  │ (normalized)  │  │ (health / stale flag)│   │
│  └─────────────────┘  └───────────────┘  └──────────────────────┘   │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                           API LAYER                                  │
│              FastAPI — serves both agent UI and admin UI             │
│    /units (search/filter)  /buildings  /health  /admin  /auth        │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                         FRONTEND                                     │
│  ┌─────────────────────────────────┐  ┌──────────────────────────┐   │
│  │     Agent UI                    │  │     Admin UI             │   │
│  │  Search / Filter / Export       │  │  Scrape health dashboard │   │
│  └─────────────────────────────────┘  │  Manual re-trigger       │   │
│                                       │  Account management       │   │
│                                       └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                   SCHEDULER (cross-cutting)                          │
│         APScheduler (cron) — runs daily scrape batch                 │
│         Lives in the API process or as a separate worker             │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Scheduler** | Triggers the daily batch; owns retry logic; alerts on persistent failure | APScheduler with CronTrigger embedded in the FastAPI process (simple) or a standalone worker (if parallelism needed) |
| **Building Sync** | Pulls building list from Google Sheets; adds/updates buildings table; does not delete (soft-mark removed) | Google Sheets API client, runs before each scrape batch |
| **Scraper Engine — Tier 1 (API)** | Calls Yardi/RentCafe and Entrata REST APIs; structured response, no parsing needed | `httpx` async HTTP client; one adapter class per platform |
| **Scraper Engine — Tier 2 (Platform Scraper)** | Fetches HTML from known platform patterns (PPM, Funnel/Nestio, Bozzuto, Groupfox, RealPage, AppFolio); CSS/XPath selectors | `httpx` + `BeautifulSoup` or `selectolax`; one scraper module per platform |
| **Scraper Engine — Tier 3 (LLM Fallback)** | Hands unrecognized/custom sites to Crawl4AI; Pydantic schema instructs Claude Haiku to extract unit fields | `crawl4ai` with `LLMExtractionStrategy` + Pydantic model |
| **Normalizer** | Converts raw output from any tier into the canonical unit record schema | Pure function: `normalize(raw, building_id) -> list[UnitRecord]`; sits between scraper output and DB write |
| **Data Store** | Persists buildings, units, scrape run logs; source of truth for all reads | PostgreSQL via SQLAlchemy ORM (or raw psycopg2 for bulk inserts) |
| **Failure Handler** | On scrape error: writes failed run log, sets `is_stale=True` on building, preserves existing unit rows | Part of the scraper engine runner; wraps each per-building execution in try/except |
| **API Layer** | Exposes JSON endpoints for search, filter, export, admin actions, health data, auth | FastAPI; handles auth (JWT sessions), query params for filters, CSV/JSON export endpoint |
| **Frontend** | Agent search/filter/export UI; Admin health dashboard with re-trigger button | React (or Next.js) SPA consuming the API; no server-side rendering needed |
| **Auth** | Admin creates agent accounts; agents log in with username+password | FastAPI JWT sessions; single admin role, single agent role |

---

## Recommended Project Structure

```
moxie-buildings/
├── backend/
│   ├── scrapers/               # One module per platform
│   │   ├── base.py             # Abstract BaseScraper interface
│   │   ├── yardi.py            # Tier 1: Yardi/RentCafe API adapter
│   │   ├── entrata.py          # Tier 1: Entrata API adapter
│   │   ├── ppm.py              # Tier 2: PPM availability page
│   │   ├── funnel.py           # Tier 2: Funnel/Nestio platform
│   │   ├── bozzuto.py          # Tier 2: Bozzuto platform
│   │   ├── groupfox.py         # Tier 2: Groupfox/RentCafe variant
│   │   ├── realpage.py         # Tier 2: RealPage/G5
│   │   ├── appfolio.py         # Tier 2: AppFolio
│   │   └── llm_fallback.py     # Tier 3: Crawl4AI + Claude Haiku
│   ├── normalizer.py           # raw → UnitRecord canonical schema
│   ├── sync/
│   │   └── google_sheets.py    # Building list sync from Google Sheets
│   ├── scheduler/
│   │   └── daily_batch.py      # APScheduler cron job; orchestrates full run
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models (buildings, units, scrape_runs)
│   │   ├── session.py          # DB connection / session factory
│   │   └── migrations/         # Alembic migration files
│   ├── api/
│   │   ├── main.py             # FastAPI app + lifespan (scheduler startup)
│   │   ├── auth.py             # JWT login/logout, account management
│   │   ├── units.py            # /units search/filter/export endpoints
│   │   ├── buildings.py        # /buildings list and detail endpoints
│   │   ├── health.py           # /health scrape run logs, stale flags
│   │   └── admin.py            # /admin re-trigger, account CRUD
│   └── config.py               # Settings (env vars: DB_URL, GS_KEY, etc.)
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Search.tsx       # Agent: search + filter + export
│   │   │   ├── Health.tsx       # Admin: scrape health dashboard
│   │   │   └── Admin.tsx        # Admin: account management
│   │   ├── components/          # Shared UI components
│   │   └── api/                 # Typed API client functions
│   └── ...
├── .env                         # Secrets (never committed)
└── docker-compose.yml           # Local dev: postgres + backend + frontend
```

### Structure Rationale

- **scrapers/**: One file per platform makes adding/removing platforms surgical. New platform = new file, no changes to other scrapers.
- **normalizer.py**: A single function that all tiers call after extraction ensures the database always receives the same shape. The only place where field mapping logic lives.
- **scheduler/**: Kept separate from `api/` so the batch runner can be tested in isolation without starting the HTTP server.
- **db/models.py**: All table definitions in one file; Alembic handles schema evolution without downtime.
- **api/**: Endpoint modules split by concern (units, buildings, health, admin) — each file stays small and focused.

---

## Architectural Patterns

### Pattern 1: Tiered Scraper with Shared Interface

**What:** Every scraper — regardless of tier — implements the same interface: it receives a building record and returns a list of raw unit dicts (or raises an exception). The caller (daily batch runner) does not know which tier ran.

**When to use:** Always. This is the foundational pattern that makes adding new platforms safe and allows the normalizer to be platform-agnostic.

**Trade-offs:** Small overhead of defining a base class; massive payoff in testability (each scraper tested in isolation) and interchangeability.

**Example:**
```python
from abc import ABC, abstractmethod
from typing import list

class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, building: Building) -> list[dict]:
        """Return raw unit dicts or raise ScraperError."""
        ...

class YardiScraper(BaseScraper):
    async def scrape(self, building: Building) -> list[dict]:
        # Call Yardi API, return raw response units
        ...

class LLMFallbackScraper(BaseScraper):
    async def scrape(self, building: Building) -> list[dict]:
        # Run Crawl4AI with Haiku, return extracted units
        ...
```

---

### Pattern 2: Strategy Selection at Build Time, Not Runtime

**What:** Each building row in the database has a `scraper_type` field (e.g., `"yardi"`, `"ppm"`, `"llm_fallback"`). The batch runner reads this and instantiates the correct scraper class. There is no runtime detection or guessing.

**When to use:** Always. Platform research is already complete; the mapping from building to scraper type is a data problem (stored in the buildings table, synced from Google Sheets), not a code problem.

**Trade-offs:** Requires the `scraper_type` column to be populated accurately. Manual correction via the admin UI is the escape hatch when a building changes platforms.

**Example:**
```python
SCRAPER_REGISTRY = {
    "yardi": YardiScraper(),
    "entrata": EntrataScaper(),
    "ppm": PPMScraper(),
    "llm_fallback": LLMFallbackScraper(),
    # ...
}

scraper = SCRAPER_REGISTRY[building.scraper_type]
raw_units = await scraper.scrape(building)
```

---

### Pattern 3: Write-on-Replace Unit Records Per Run

**What:** Each daily run deletes the existing unit rows for a building and inserts the freshly scraped ones. Units are not updated in place; they are replaced. The `scrape_runs` log is append-only.

**When to use:** Always, for this project. Unit-level pricing and availability change daily; stale unit rows from prior runs are not useful and create confusion. The unit table reflects "what is available right now."

**Trade-offs:** History of individual unit pricing is lost (not a requirement). On a failed scrape, the delete-and-replace does NOT run — old rows remain intact (this is the "retain last known data" behavior).

**Example:**
```python
async def write_units(building_id: int, units: list[UnitRecord], db: Session):
    # Only runs on success — failure path skips this entirely
    db.query(Unit).filter(Unit.building_id == building_id).delete()
    db.bulk_insert_mappings(Unit, [u.dict() for u in units])
    db.commit()
```

---

### Pattern 4: Append-Only Scrape Run Log

**What:** Every scrape attempt (per building, per day) writes a row to `scrape_runs`: timestamp, building_id, status (success/failure), error message, unit count. The `buildings` table has a `is_stale` boolean and `last_scraped_at` timestamp that are updated after each run.

**When to use:** Always. This is the data the admin health dashboard reads. Without it, there is no visibility into which buildings are broken.

**Trade-offs:** Table grows by ~400 rows/day (~150K rows/year). This is trivial for PostgreSQL; no archival strategy needed for years.

**Example schema:**
```sql
CREATE TABLE scrape_runs (
    id          SERIAL PRIMARY KEY,
    building_id INTEGER NOT NULL REFERENCES buildings(id),
    run_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status      TEXT NOT NULL,         -- 'success' | 'failure'
    error_msg   TEXT,
    unit_count  INTEGER,
    tier_used   TEXT                   -- 'api' | 'platform' | 'llm'
);

CREATE TABLE buildings (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL,
    neighborhood    TEXT,
    scraper_type    TEXT NOT NULL,
    is_stale        BOOLEAN NOT NULL DEFAULT FALSE,
    last_scraped_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ
);
```

---

## Data Flow

### Daily Batch Flow (the primary path)

```
Scheduler (cron: daily 2 AM)
    │
    ▼
Google Sheets Sync
    │  Upsert buildings table (add new, update existing, mark removed)
    │
    ▼
For each active building (in parallel, N workers):
    │
    ├── Read building.scraper_type
    ├── Instantiate correct scraper
    ├── scraper.scrape(building) ──► [SUCCESS] ──► normalizer(raw) ──► write_units()
    │                                                                     │
    │                                                              update buildings:
    │                                                              is_stale=False
    │                                                              last_scraped_at=now
    │                                                              last_success_at=now
    │
    └──────────────────────────────► [FAILURE] ──► log error to scrape_runs
                                                   set buildings.is_stale=True
                                                   preserve existing unit rows (no delete)
                                                   (alert if consecutive failures > N)
```

### Search Request Flow (agent reads)

```
Agent browser
    │
    ▼
GET /units?beds=1BR&min_rent=1500&max_rent=2500&neighborhood=River North&available_before=2026-03-01
    │
    ▼
FastAPI /units endpoint
    │  Auth check (JWT)
    │  Build SQL query with filters
    │  JOIN units + buildings
    │
    ▼
PostgreSQL
    │  Returns filtered unit rows with building metadata
    │
    ▼
JSON response ──► React frontend renders results table
                  (Export button ──► GET /units?...&format=csv ──► file download)
```

### Admin Re-Trigger Flow

```
Admin clicks "Re-scrape" for a stale building
    │
    ▼
POST /admin/buildings/{id}/scrape
    │
    ▼
FastAPI enqueues single-building scrape (background task)
    │
    ▼
Same scraper pipeline as daily batch (single building)
    │
    ▼
Result written to DB + scrape_runs log
Admin dashboard refreshes stale status
```

---

## Build Order

The components have strict dependencies that determine build order. Each phase should be independently testable before the next begins.

```
Phase 1: Data Foundation
    ├── Database schema (buildings, units, scrape_runs tables)
    ├── Alembic migrations
    └── Google Sheets sync (buildings table populated)
    [Can verify: DB has real building data]

Phase 2: Scraper Engine
    ├── BaseScraper interface + normalizer
    ├── Tier 1: API scrapers (Yardi, Entrata) — highest coverage, lowest risk
    ├── Tier 2: Platform scrapers (PPM first — single page covers 18 buildings)
    ├── Tier 2: Remaining platform scrapers (Funnel, Bozzuto, Groupfox, RealPage, AppFolio)
    └── Tier 3: LLM fallback (Crawl4AI + Haiku)
    [Can verify: run scrapers manually, inspect normalized output in DB]

Phase 3: Scheduler + Failure Handling
    ├── APScheduler daily batch runner
    ├── Per-building error capture + scrape_runs log writes
    ├── Stale flag logic on buildings table
    └── Manual re-trigger capability (CLI or simple script)
    [Can verify: run a full batch, check scrape_runs, confirm stale flags set on failures]

Phase 4: API Layer
    ├── FastAPI app scaffold + config
    ├── Auth (JWT login, agent/admin roles)
    ├── /units search/filter endpoints
    ├── /buildings list endpoint
    ├── /health scrape run log endpoints
    └── /admin re-trigger + account management endpoints
    [Can verify: curl/Postman tests against real data]

Phase 5: Frontend
    ├── Auth flow (login page)
    ├── Agent search UI (filter panel + results table)
    ├── Export (CSV download)
    └── Admin health dashboard (stale buildings list, re-trigger button, account management)
    [Can verify: end-to-end user workflow]
```

**Why this order:**
- The database schema must exist before any scraper can write to it.
- Scrapers must work before the scheduler is meaningful (scheduler is just a runner that calls scrapers).
- The API layer needs real data in the DB to be testable.
- The frontend needs the API to be functional to develop against.
- This order means every phase produces something independently verifiable — you are not blocked waiting for the full system.

---

## Anti-Patterns

### Anti-Pattern 1: Runtime Platform Detection

**What people do:** Write the scraper to fetch the page, then inspect the HTML to detect which platform it is and dispatch accordingly.

**Why it's wrong:** Platform detection from HTML is brittle. Sites change templates, A/B test layouts, and CDNs serve cached versions. Detection logic becomes a maintenance burden and a source of silent misclassifications.

**Do this instead:** Store `scraper_type` per building in the database (from the pre-existing platform research). Detection is a one-time human judgment recorded as data, not repeated algorithmic guessing.

---

### Anti-Pattern 2: Deleting Units on Failure

**What people do:** Delete old unit rows before starting the scrape, then insert new ones. If the scrape fails mid-run, the building has no units in the database.

**Why it's wrong:** Agents see zero results for a building that actually has available units. Data disappears on every failure — the opposite of "retain last known data."

**Do this instead:** Only delete-and-replace units after a successful scrape completion. On failure, leave existing rows intact, set `is_stale=True`, and log the error.

---

### Anti-Pattern 3: Scraping All Buildings Sequentially

**What people do:** Loop through 400 buildings one at a time, scraping each before moving to the next.

**Why it's wrong:** Sequential scraping of 400 buildings will take many hours and will not complete within the daily window. Some sites are slow (2-5s per request).

**Do this instead:** Parallelize with a bounded worker pool (e.g., `asyncio.Semaphore(20)` — 20 concurrent scrapes). Rate-limit per domain (not globally) to avoid hammering individual sites.

---

### Anti-Pattern 4: LLM for All Buildings

**What people do:** Route all buildings through the LLM fallback because it's simpler than maintaining platform-specific scrapers.

**Why it's wrong:** At ~$120/month for 50-70 buildings, extending LLM scraping to 400 buildings would cost ~$700-900/month. API scrapers and platform scrapers are free (after development). The tiered strategy exists precisely to minimize LLM cost.

**Do this instead:** LLM fallback is the last resort. API scrapers for Yardi/Entrata cover ~260 buildings at zero marginal cost. Build the tiers in cost-ascending order.

---

### Anti-Pattern 5: Monolithic Scraper Module

**What people do:** Put all scraping logic in one file with if/else branching per platform.

**Why it's wrong:** With 8+ platforms, this file becomes hundreds of lines that cannot be individually tested. One platform's change breaks the whole module. New contributors cannot find where a specific platform lives.

**Do this instead:** One file per platform in `scrapers/`. Each file is independently testable, discoverable, and changeable.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current (~400 buildings, <10 agents) | Single server, APScheduler embedded in FastAPI process, PostgreSQL on same host or managed service (Render, Railway). No queue needed. |
| 1K buildings, 50 agents | Same architecture; add DB indexes on `units(beds, rent, available_date, building_id)` if query times degrade. Extract scheduler to separate process if memory is a concern. |
| 5K+ buildings | Move scraper workers to a task queue (Celery + Redis) to parallelize across machines. The scraper interface is already queue-friendly — this is an infrastructure change, not a code rewrite. |

**First bottleneck for this project:** LLM cost, not compute. The ~$120/month budget constrains how many buildings use the LLM tier. Everything else (DB queries, API responses) is trivial at this scale.

**Second bottleneck:** IP rate limiting from target sites, not server capacity. Mitigation: per-domain rate limiting and polite delays, not proxy rotation (overkill for internal tooling).

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google Sheets API | OAuth2 service account; read-only; pull full building list on each batch run | Building list is the source of truth — MBA syncs but does not write back |
| Yardi/RentCafe API | REST API with auth (credentials TBD — requires investigation); HTTP client with retry | Access method unconfirmed; fallback to platform scraper if API is unavailable |
| Entrata API | REST API; per-building endpoint pattern | More consistent than Yardi; endpoints are publicly documented |
| Claude Haiku (Anthropic API) | Called via Crawl4AI's `LLMExtractionStrategy`; Pydantic schema passed as extraction target | Cost-sensitive: batch async calls; Crawl4AI handles chunking and prompt construction |
| Crawl4AI | Python library (async); wraps Playwright for JS-rendered pages; invoked per-building in the LLM tier | Use `AsyncWebCrawler` with `LLMExtractionStrategy`; Pydantic model defines unit schema |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scheduler ↔ Scraper Engine | Direct Python function call (same process, or Celery task if extracted) | Scheduler does not import scraper internals — calls `run_batch()` only |
| Scraper Engine ↔ Normalizer | Function call: `normalize(raw_dict, building) -> UnitRecord` | Normalizer is pure (no DB access, no I/O) — easy to unit test |
| Normalizer ↔ Data Store | SQLAlchemy session passed from caller; normalizer returns records, caller writes | Keeps normalizer dependency-free |
| API Layer ↔ Data Store | SQLAlchemy session via FastAPI dependency injection (`Depends(get_db)`) | Standard FastAPI pattern; no ORM queries in endpoint handlers — use service functions |
| API Layer ↔ Scheduler | Scheduler registered on FastAPI `lifespan` startup; admin re-trigger adds a one-shot job | If scheduler extracted to separate process, admin re-trigger becomes an HTTP call or queue message |
| Frontend ↔ API Layer | JSON REST (no GraphQL needed at this scale); typed API client in frontend | CORS configured; auth via JWT in Authorization header |

---

## Sources

- groupbwt.com — Web Scraping Infrastructure That Doesn't Break Under Pressure (architecture layers, independent failure): https://groupbwt.com/blog/infrastructure-of-web-scraping/
- mobigesture.com — Reliable Web Scraping Robot (scheduler, message broker decoupling, failure tiers): https://mobigesture.com/reliable-webscraping-robot.html
- Crawl4AI official docs (LLMExtractionStrategy, async architecture, Pydantic schema integration): https://docs.crawl4ai.com/
- FastAPI official docs (background tasks, APScheduler integration, lifespan): https://fastapi.tiangolo.com/reference/background/
- promptcloud.com — Scalable Web Scraping Architecture (component separation, parallelization): https://www.promptcloud.com/blog/scalable-web-scraping-architecture/
- shoppingscraper.com — Data Freshness in Web Scraping (timestamp patterns, stale flagging): https://shoppingscraper.com/blog/how-to-ensure-data-freshness-in-web-scraping
- scrapingbee.com — Crawl4AI hands-on guide (production integration, Pydantic extraction): https://www.scrapingbee.com/blog/crawl4ai/

---
*Architecture research for: Moxie Building Aggregator (MBA) — scheduled web scraping aggregator*
*Researched: 2026-02-17*
