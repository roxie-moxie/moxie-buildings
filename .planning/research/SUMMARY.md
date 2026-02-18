# Project Research Summary

**Project:** Moxie Building Aggregator (MBA)
**Domain:** Scheduled web scraping aggregator with private internal search UI
**Researched:** 2026-02-17
**Confidence:** MEDIUM-HIGH

## Executive Summary

The Moxie Building Aggregator is a private internal tool that scrapes ~400 Chicago rental building websites on a daily schedule, normalizes unit availability data into a PostgreSQL database, and exposes a search/filter/export interface for real estate agents. Experts build systems like this with a tiered scraping architecture: structured API calls first (cheapest), platform-specific HTML scrapers second (medium effort), and LLM-assisted fallback last (most expensive). The technology decisions are clear and well-precedented — Python + FastAPI on the backend, Next.js + TanStack Table on the frontend, APScheduler for the daily batch, and Crawl4AI with Claude Haiku for the long-tail custom sites.

The recommended approach is to build data-first: define the canonical schema and normalization module before writing any scraper, then build scrapers tier by tier in ascending cost order, then add the API and frontend on top of real data. This ordering is non-negotiable — every subsequent phase depends on the integrity of the data that comes before it. The agent-facing UI is straightforward once real data is in the database; the filter, sort, and export features all have well-documented implementation patterns.

The dominant risks are not technical complexity but operational: Yardi/RentCafe API access requires vendor program enrollment and must be resolved before any Yardi scraper code is written; silent failures from anti-bot systems returning 200 + CAPTCHA HTML are the most dangerous data quality threat; and LLM token costs will exceed the $120/month estimate by 10-20x if HTML preprocessing is not enforced from day one. All three risks must be addressed in Phase 1 before any scraper code ships.

---

## Key Findings

### Recommended Stack

The stack is Python 3.12 + FastAPI 0.129.0 on the backend with PostgreSQL 16 as the primary store. SQLAlchemy 2.x (async) + Alembic handles the ORM and migrations. APScheduler 3.11.2 runs the daily batch in-process without requiring a message broker. Crawl4AI 0.8.0 + Playwright 1.58.0 handle LLM-assisted and browser-rendered scraping; httpx 0.28.1 handles REST API scraping. The frontend is Next.js 16 with TypeScript, Tailwind CSS, shadcn/ui components, and TanStack Table 8.x for server-side filtering and pagination.

All versions are PyPI-verified as of 2026-02-17. The key package avoidances are Scrapy (wrong abstraction for a tiered service architecture), Celery (unnecessary broker overhead for daily batch at this scale), Selenium (replaced by Playwright), passlib (unmaintained since 2020, breaks on Python 3.13), and OAuth2Client (deprecated by Google in favor of google-auth). See `STACK.md` for full version compatibility matrix.

**Core technologies:**
- Python 3.12 + FastAPI 0.129.0: async-native API backend with auto-generated OpenAPI docs and dependency injection
- PostgreSQL 16 + SQLAlchemy 2.x: handles concurrent scraper writes without lock contention; relational integrity for building→unit relationships
- APScheduler 3.11.2: in-process cron scheduler with PostgreSQL job store; avoids Celery's broker infrastructure
- Crawl4AI 0.8.0 + Claude Haiku: LLM-assisted extraction for ~50-70 long-tail custom sites; `LLMExtractionStrategy` with Pydantic schema
- Playwright 1.58.0: browser automation for JS-rendered platform scrapers (Entrata, RealPage, Bozzuto, Funnel)
- httpx 0.28.1: async HTTP client for Yardi/RentCafe and Entrata REST API calls
- Next.js 16 + TanStack Table 8.x: server-side filtering, sorting, and pagination for the agent unit search table
- shadcn/ui: accessible component library (DataTable, Badge, Dialog, Select) for the admin and agent UIs

### Expected Features

The MVP feature set is well-defined and has clear dependency ordering. Auth gates everything. The filter system (bed type, rent range, availability date, neighborhood) is the core value proposition. Data freshness badges are essential for agent trust given the daily-batch model. PDF export is the primary agent-to-client sharing mechanism. The admin scrape health dashboard with manual re-trigger is an operational necessity, not a nice-to-have.

See `FEATURES.md` for the full prioritization matrix and anti-feature analysis.

**Must have (table stakes):**
- Auth / login — all routes require authenticated session; username + password for v1
- Filter panel: bed type (multi-select), rent range (min/max), availability date, neighborhood (multi-select)
- Sortable results table — beds, rent, available date, building, last updated
- Data freshness badge per building — green (<24h), yellow (24-48h), red (>48h)
- CSV and PDF export of current filtered view — CSV for spreadsheet users, PDF for client deliverables
- URL-serialized filter state — enables bookmarking as the soft alternative to saved searches
- Admin: scrape health dashboard, manual re-trigger per building, agent account management

**Should have (differentiators):**
- Building detail page — all units for one building; validate demand before building
- Result count display ("47 units across 12 buildings") — quality-of-life for filter iteration
- "Available within N days" quick-select toggle — simplifies most common date filter pattern
- Scrape health email alerts — reduces time-to-notice for failures

**Defer (v2+):**
- Saved searches / per-agent filter presets — validate whether URL bookmarks are sufficient first
- Historical availability and rent trend data — requires schema redesign; meaningful only after 3-6 months of data
- Natural language search — well-designed structured filters are the right v1 answer
- Map view — neighborhood filter is the correct geographic proxy at this scope

### Architecture Approach

The system is a 5-layer pipeline: Google Sheets sync populates buildings → tiered scraper engine (API adapters, platform scrapers, LLM fallback) extracts units → normalizer converts everything to canonical UnitRecord schema → PostgreSQL stores current units + scrape run log → FastAPI serves filtered reads and admin actions → Next.js frontend renders agent search and admin health dashboard. APScheduler orchestrates the daily batch as a cron job embedded in the FastAPI process.

The foundational architectural pattern is the tiered scraper with a shared `BaseScraper` interface: every scraper, regardless of tier, receives a building record and returns raw unit dicts. `scraper_type` is stored per building in the database (set during initial data entry, not detected at runtime). The normalizer is a pure function called by all tiers — the single source of field mapping logic. Units are write-on-replace per successful run; failed runs preserve existing rows and set `is_stale=True`. See `ARCHITECTURE.md` for component diagram, data flow, and full build order.

**Major components:**
1. Google Sheets Sync — pulls building list from Sheets; upserts buildings table; runs before each scrape batch
2. Tiered Scraper Engine — Tier 1 (httpx REST API), Tier 2 (Playwright + BeautifulSoup per platform), Tier 3 (Crawl4AI + Claude Haiku LLM fallback)
3. Normalizer — pure function converting heterogeneous scraper output to canonical UnitRecord; shared by all tiers
4. PostgreSQL Data Store — buildings, units, scrape_runs tables; source of truth for all reads
5. APScheduler — cron job runs at 2 AM daily; orchestrates Sheets sync then parallel scraping with per-platform concurrency limits
6. FastAPI API Layer — /units (filter/search/export), /buildings, /health, /admin, /auth
7. Next.js Frontend — Agent search/filter/export UI; Admin scrape health dashboard + account management

### Critical Pitfalls

1. **Yardi API access is not self-service** — The RentCafe API requires formal Yardi Interfaces Program enrollment. Do not write any Yardi scraper code until access method is confirmed (vendor program vs. HTML scraping). Resolve this as a procurement action in Phase 1.

2. **Silent failures from anti-bot 200 responses** — Cloudflare Turnstile and similar systems return HTTP 200 with CAPTCHA HTML, not the actual page. Zero units extracted = scraper "succeeds" with no stale flag triggered. Fix: validate that expected DOM elements are present; require `unit_count > 0` or an explicit "building has no available units" signal; add a zero-unit alert rule for buildings that previously had listings.

3. **LLM token cost explosion from raw HTML** — Full apartment site HTML averages 200-500KB; actual unit content is 2-5KB. Sending raw HTML to Haiku will cost 10-20x the $120/month estimate. Fix: always use Crawl4AI's `result.markdown` (not `result.html`); apply CSS-selector targeting to extract only the unit listing section; enforce a token budget guard (8,000 token cap) before any volume run.

4. **Inconsistent data normalization across tiers** — Yardi returns beds as integer 0, Entrata may return "Studio" or "0BR", LLM extraction returns whatever the page says. If normalization is done per-scraper, enums diverge and search filters break silently. Fix: define canonical UnitRecord schema first; build shared normalizer before any scraper; validate all output against Pydantic model before DB write.

5. **Google Sheets sync as a single point of failure** — If the Sheets API is unavailable when the daily batch runs, the entire run aborts with zero buildings to process. Fix: cache the building list locally after each successful sync; fall back to cache on API failure; validate sync result row count (>200 buildings) before using it.

---

## Implications for Roadmap

Based on the combined research, the architecture file's build order is the correct phase structure. Every subsequent phase depends on data integrity established in the prior phase. The 5-phase sequence below is opinionated and matches the verified dependency graph.

### Phase 1: Data Foundation and Infrastructure Spike

**Rationale:** Schema must exist before scrapers write to it. Normalization must be defined before any scraper builds against it. Yardi access must be resolved before 220 buildings worth of scraper code is written. Sheets sync must have caching and validation before the batch scheduler uses it. All of Phase 2's critical pitfalls trace back to decisions made here.

**Delivers:** PostgreSQL schema (buildings, units, scrape_runs), Alembic migrations, Docker Compose local dev environment, Google Sheets sync with local cache and row-count validation, canonical UnitRecord Pydantic schema and shared normalizer module stub, confirmed Yardi API access method, concurrency limit and circuit breaker design baked into scheduler scaffold, scrape result contract (success vs. zero-unit vs. failure states defined).

**Features from FEATURES.md:** None user-visible, but establishes the `last_scraped_at` timestamp, `is_stale` boolean, and `scraper_type` field that all subsequent features depend on.

**Pitfalls to address:** Yardi API access (Pitfall 1), silent scrape failures / scrape result contract (Pitfall 2), data normalization inconsistency (Pitfall 4), Google Sheets sync failure (Pitfall 7), IP rate limiting architecture (Pitfall 6).

**Research flag:** Needs `/gsd:research-phase` — Yardi API access method is unconfirmed and requires a dedicated spike.

---

### Phase 2: Scraper Engine

**Rationale:** Build scrapers tier by tier in ascending cost order. API adapters (Tier 1) cover ~260 buildings at zero marginal cost and should ship first. Platform scrapers (Tier 2) for PPM, Funnel, Bozzuto, Groupfox, RealPage, AppFolio cover most of the remainder. LLM fallback (Tier 3) covers the ~50-70 long-tail sites last and is the most expensive to run, so it should be built and cost-validated before enabling at full volume.

**Delivers:** All scraper modules (one file per platform), per-tier integration tests, normalizer validation against real data from each platform, LLM token cost benchmarks for 5 representative sites, confirmed monthly cost projection within 20% of $120 target.

**Stack from STACK.md:** httpx 0.28.1 (Tier 1), Playwright + BeautifulSoup + lxml (Tier 2), Crawl4AI 0.8.0 + anthropic (Tier 3).

**Architecture component:** Tiered Scraper Engine with BaseScraper interface and SCRAPER_REGISTRY.

**Pitfalls to address:** LLM token cost (Pitfall 3) — enforce preprocessing before any volume testing; schema drift (Pitfall 5) — required-field assertions in each scraper; normalization coverage — run post-scrape audit query after each tier ships.

**Research flag:** Tier 2 platform scrapers are well-documented patterns (skip research phase). Tier 3 Crawl4AI integration has official docs — standard patterns. No research phase needed.

---

### Phase 3: Scheduler and Failure Handling

**Rationale:** The scheduler is only meaningful once scrapers work. Building the scheduler after the scraper engine means it can be tested immediately against real data. Failure handling (stale flags, scrape_run log writes, circuit breakers, per-platform concurrency limits) belongs in this phase, not bolted on later.

**Delivers:** APScheduler daily batch runner (cron 2 AM), per-building error capture with scrape_runs log, stale flag logic on buildings table, per-platform circuit breakers (pause tier after 3 consecutive failures), manual re-trigger capability (CLI script for pre-API testing), Google Sheets sync wired into batch run.

**Stack from STACK.md:** APScheduler 3.11.2 with SQLAlchemyJobStore; PostgreSQL job persistence.

**Architecture component:** Scheduler (cross-cutting) + Failure Handler.

**Pitfalls to address:** Rate limiting enforcement — test full 400-building dry run before enabling production schedule; circuit breakers verified under simulated platform failure.

**Research flag:** Standard patterns — APScheduler documentation is comprehensive and well-established. No research phase needed.

---

### Phase 4: API Layer

**Rationale:** The API layer needs real, normalized data in the database to be meaningfully testable. Building it after Phase 3 means it can be developed and tested against a fully populated database from a real batch run.

**Delivers:** FastAPI app scaffold, JWT auth (login, agent/admin roles), /units endpoint with all filter parameters (beds, rent range, availability date, neighborhood), /units?format=csv export endpoint, /buildings list endpoint, /health scrape run log endpoints, /admin re-trigger and account management endpoints.

**Stack from STACK.md:** FastAPI 0.129.0, python-jose 3.5.0, bcrypt 5.0.0, python-multipart 0.0.22, SQLAlchemy 2.x async sessions via FastAPI dependency injection.

**Architecture component:** API Layer.

**Features from FEATURES.md:** All P1 auth and filter features; CSV export (low-complexity, ships in this phase); admin re-trigger and account management endpoints.

**Research flag:** Standard patterns — FastAPI auth and filter endpoint patterns are thoroughly documented. No research phase needed.

---

### Phase 5: Frontend

**Rationale:** Frontend requires API endpoints to develop against. Building last means the frontend is never blocked by backend gaps, and the API contract is settled before the frontend client is typed.

**Delivers:** Login page, agent search UI (filter panel + sortable TanStack Table results), data freshness badges, CSV download, PDF export of filtered results, admin scrape health dashboard (per-building status, stale flag, last run time, re-trigger button), agent account management UI, URL-serialized filter state.

**Stack from STACK.md:** Next.js 16, TypeScript 5.x, Tailwind CSS 4.x, shadcn/ui, TanStack Table 8.x, openpyxl / weasyprint for PDF generation on the backend.

**Architecture component:** Frontend (Agent UI + Admin UI).

**Features from FEATURES.md:** All P1 agent-facing features (filter panel, sortable table, freshness badge, CSV/PDF export, URL filters), all P1 admin features (health dashboard, re-trigger, account management).

**Pitfalls to address:** UX pitfalls from PITFALLS.md — zero-unit buildings flagged with "data may be incomplete" warning; scrape errors surfaced only in admin view (agents see "data temporarily unavailable"); staleness badge shows contextual state, not raw timestamp.

**Research flag:** PDF export implementation needs a library decision (weasyprint vs. reportlab); standard patterns exist for both. No research phase needed unless PDF layout requirements are complex.

---

### Phase Ordering Rationale

- Schema before scrapers: scrapers cannot write to tables that do not exist; normalization logic must be settled before any scraper implements it
- Scrapers before scheduler: the scheduler is a runner that calls scrapers; testing it without working scrapers produces no useful signal
- Scheduler before API: the API's /health endpoint and data freshness features require scrape_runs data; this only exists after real batch runs
- API before frontend: the frontend's typed API client and filter logic cannot be developed against a moving target; settle the API contract first
- Yardi spike in Phase 1: affects 55% of buildings (220/400); the wrong access assumption propagates into every subsequent phase

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Yardi API spike):** Yardi API access method is unconfirmed — this is a procurement/legal question, not a technical one. Requires direct investigation with Yardi or client contacts before any pipeline code is written.
- **Phase 2 (Entrata API):** Entrata deprecated its legacy gateway in April 2025; the correct base URL and auth method for the modernized gateway need verification against actual Entrata API documentation before the scraper is built.

Phases with standard patterns (skip research phase):
- **Phase 1 (schema, Alembic, Docker):** PostgreSQL + SQLAlchemy 2.x + Alembic patterns are thoroughly documented; no ambiguity.
- **Phase 2 (Tier 2 platform scrapers):** Playwright + BeautifulSoup patterns are well-established; one scraper per platform is mechanical work.
- **Phase 2 (Crawl4AI):** Official Crawl4AI docs are comprehensive; LLMExtractionStrategy with Pydantic is the documented pattern.
- **Phase 3 (APScheduler):** Well-documented; SQLAlchemyJobStore setup is a known pattern.
- **Phase 4 (FastAPI auth/filters):** Standard FastAPI patterns; no ambiguity.
- **Phase 5 (Next.js/TanStack):** TanStack Table server-side pattern is documented; shadcn/ui integration is standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified against PyPI with release dates; alternatives analysis is thorough; version compatibility matrix is explicit |
| Features | MEDIUM | Core filter/search/export patterns verified across consumer and professional real estate platforms; some UX specifics are synthesis from evidence rather than MBA-specific research |
| Architecture | MEDIUM-HIGH | Patterns well-established across multiple credible scraping architecture sources; specific choices (APScheduler vs. Celery, tiered scraper) verified; component boundary design is well-reasoned |
| Pitfalls | MEDIUM | Core pitfalls verified across multiple sources; Yardi access risk is confirmed by official ToU but exact access path for this project requires direct investigation; platform-specific HTML scraper fragility is verified by pattern, not by testing against actual sites |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Yardi API access method (Critical):** Must be confirmed before Phase 2 begins. Three possible paths: (a) client buildings grant authorized vendor access, (b) enroll in Yardi Interfaces Program, (c) fall back to HTML scraping of RentCafe property pages. This decision changes the scraper architecture for 220 buildings.

- **Entrata legacy API gateway deprecation (Moderate):** Entrata deprecated its legacy gateway April 15, 2025. The correct base URL and auth method for the modernized gateway should be verified against Entrata's current API documentation before the Entrata scraper is written.

- **Platform scraper selector stability (Moderate):** Actual CSS selectors for PPM, Funnel, Bozzuto, Groupfox, RealPage, and AppFolio have not been researched — the architecture correctly defers this to implementation. Use `playwright codegen <url>` during Phase 2 to record selectors for each platform.

- **LLM cost at production volume (Moderate):** The $120/month estimate assumes preprocessing reduces each page to <4,000 tokens. This must be validated against 5 representative long-tail sites before enabling the full 50-70 building LLM tier. Do not assume the estimate is correct until token benchmarks are run.

- **AppFolio subdomain pattern (Minor):** AppFolio uses tenant-specific subdomains (`{property}.appfolio.com`). The scraper must use the full URL stored in Google Sheets, not derive it from the building name. Confirm that all AppFolio buildings have complete URLs in the current Sheets data.

---

## Sources

### Primary (HIGH confidence)
- FastAPI PyPI v0.129.0 (2026-02-12), official docs — API framework, auth patterns, background tasks
- SQLAlchemy PyPI v2.0.46 (2026-01-21), Alembic PyPI v1.18.4 (2026-02-10) — ORM and migrations
- APScheduler PyPI v3.11.2 (2025-12-22) — scheduling patterns
- Crawl4AI PyPI v0.8.0 (2026-01-16) + official docs — LLM extraction strategy, async architecture
- Playwright Python PyPI v1.58.0 (2026-01-30) — browser automation
- Next.js 16 release notes (2025-10-21) — frontend framework requirements
- Yardi RC API Terms of Use — confirms API access is licensed, not public
- Google Sheets API official docs — rate limits (300 req/60s)
- bcrypt PyPI v5.0.0 (2025-09-25), python-jose PyPI v3.5.0 (2025-05-28) — auth libraries
- gspread PyPI v6.2.1 (2025-05-14) + auth docs — Google Sheets integration

### Secondary (MEDIUM confidence)
- Crawl4AI hands-on guide (ScrapingBee) — production integration patterns
- Scalable web scraping architecture (promptcloud.com) — component separation, parallelization
- Web scraping without getting blocked (ScrapingBee 2026) — anti-bot patterns
- ZenRows: Bypass Rate Limit — rate limiting mechanics
- LLM cost optimization for scraping (webscraping.ai) — preprocessing strategies
- Entrata Enhanced API Program announcement (PR Newswire, 2024) — legacy gateway deprecation
- Scraper monitoring dashboard features (ScrapeOps) — admin health dashboard patterns
- Filter UI best practices (Eleken, Insaim Design) — agent search UI patterns
- Table UX best practices (Tenscope) — results table design
- APScheduler vs Celery architectural comparison (leapcell.io)

### Tertiary (LOW confidence)
- Yardi RentCafe API Reference (unitmap.com — third-party docs) — API shape, not access method

---
*Research completed: 2026-02-17*
*Ready for roadmap: yes*
