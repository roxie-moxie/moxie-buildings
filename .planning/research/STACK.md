# Stack Research

**Domain:** Web scraping aggregator with private internal web UI
**Researched:** 2026-02-17
**Confidence:** HIGH (all core versions verified against PyPI and official release notes)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Backend runtime | LTS-adjacent, full async support, required by all scraping libs; 3.13 is available but ecosystem not fully settled on it yet |
| FastAPI | 0.129.0 | REST API + backend web framework | Native async, auto-generated OpenAPI docs, built-in dependency injection — the standard for Python API backends in 2026; Python type hints drive everything |
| SQLAlchemy | 2.0.46 | ORM and query builder | The ORM to use for Python; 2.x async-native API via `AsyncSession`; pairs perfectly with Alembic migrations |
| Alembic | 1.18.4 | Database migrations | Built by the SQLAlchemy author; autogenerate migrations from model diffs; required by SQLAlchemy 2.x projects |
| PostgreSQL | 16.x | Primary data store | Handles concurrent writes from parallel scrapers without lock contention (unlike SQLite); JSON columns useful for optional unit metadata; battle-tested for production |
| psycopg2-binary | 2.9.11 | PostgreSQL adapter for Python | Standard driver; binary wheel avoids build dependencies; works with SQLAlchemy 2.x async via `asyncpg` underneath |
| APScheduler | 3.11.2 | Job scheduler for daily scrape runs | In-process scheduler, no extra broker infrastructure (unlike Celery+Redis); cron trigger support; persists jobs to PostgreSQL so scheduled jobs survive restarts; daily scraping at this scale does not need distributed workers |
| Crawl4AI | 0.8.0 | LLM-assisted HTML extraction for custom sites | Built on Playwright; outputs clean markdown for LLM consumption; `LLMExtractionStrategy` drives structured extraction via Claude Haiku; 58k+ GitHub stars, actively maintained; the right tool for the ~50-70 long-tail custom sites |
| Playwright (Python) | 1.58.0 | Browser automation for JS-rendered sites | Used internally by Crawl4AI; also used directly for platform-specific scrapers (Entrata, RealPage, Bozzuto, Funnel) that render content dynamically; Microsoft-backed, cross-browser |
| httpx | 0.28.1 | HTTP client for REST API scrapers | Async-native; used for RentCafe/Yardi REST API calls and Entrata API calls where no browser is needed; faster than Playwright for static/API endpoints; replaces `requests` in async context |
| Next.js | 16.x | Frontend web framework | App Router with React 19.2; Turbopack stable; best-in-class for private internal tools with auth, server components, and data fetching; `create-next-app` defaults to TypeScript + Tailwind |
| TypeScript | 5.x | Frontend language | Required by Next.js 16 (min TypeScript 5.1); catches shape mismatches between API responses and UI components at compile time |
| Tailwind CSS | 4.x | Utility-first CSS | Bundled in `create-next-app` defaults; correct choice for internal tools where you need rapid iteration without custom CSS overhead |
| shadcn/ui | latest | Component library | Built on Radix UI + Tailwind; accessible by default; the standard for Next.js admin dashboards in 2025-2026; gives DataTable, Dialog, Badge, Select for filtering UIs without bloat |
| TanStack Table | 8.x | Server-side data table | Required for the agent unit search table: server-side filtering, sorting, pagination with large datasets; pairs naturally with shadcn/ui table primitives |

### Authentication

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| python-jose | 3.5.0 | JWT generation and verification on FastAPI | Standard JWT library for FastAPI; `[cryptography]` extra required for RS256/HS256 support |
| bcrypt | 5.0.0 | Password hashing | Direct bcrypt, not via passlib (see "What NOT to Use"); bcrypt 5.0 raises on truncated passwords >72 bytes, which is the correct behavior |
| python-multipart | 0.0.22 | Form parsing for FastAPI login endpoint | Required by FastAPI's `OAuth2PasswordRequestForm`; login form sends `application/x-www-form-urlencoded` |

### Google Sheets Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| gspread | 6.2.1 | Google Sheets API client | The standard Python library for Sheets access; uses `google-auth` (not deprecated `oauth2client`); service account authentication via JSON key |
| google-auth | latest | Google credential management | Required by gspread 6.x; handles service account JWT signing automatically |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| beautifulsoup4 | 4.12.x | HTML parsing | Use after httpx or Playwright fetches raw HTML for static-content platform scrapers (PPM, AppFolio) where structure is predictable |
| lxml | 5.x | Fast XML/HTML parser backend for BS4 | Always pass `"lxml"` as the BS4 parser — 3-5x faster than the default html.parser |
| anthropic | 0.49.x | Claude Haiku API client | Used by Crawl4AI's `LLMExtractionStrategy` when configured to call Claude Haiku; may also be used directly for custom LLM extraction steps |
| pydantic | 2.x | Data validation and serialization | Included with FastAPI 0.129.x; define `BaseModel` schemas for scraper output, API responses, and unit data normalization |
| python-dotenv | 1.x | Environment variable loading | Dev-time `.env` file loading for API keys, DB credentials, Google service account path |
| openpyxl | 3.x | Excel/XLSX export | Agent export to .xlsx for sharing filtered unit lists with clients |
| reportlab or weasyprint | latest | PDF export | Agent export to PDF; weasyprint preferred if HTML-to-PDF is simpler than programmatic PDF |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package manager and virtualenv | Replaces pip+venv; dramatically faster; use `uv sync` to install from `pyproject.toml` |
| Ruff | Python linter and formatter | Replaces Black + Flake8; 100x faster; zero config defaults are correct for this project |
| pyproject.toml | Dependency manifest | Use instead of `requirements.txt`; uv reads it natively |
| Docker + docker-compose | Local dev environment | FastAPI + PostgreSQL + scheduler as separate services; ensures parity with any future deployment target |
| pytest + pytest-asyncio | Backend testing | Required for testing async FastAPI routes and async scraper functions |
| Playwright's codegen | Browser script recording | `playwright codegen <url>` records selector paths for building platform-specific scrapers; cuts scraper authoring time |

---

## Installation

```bash
# Backend (Python)
uv init mba-backend
uv add fastapi==0.129.0 sqlalchemy==2.0.46 alembic==1.18.4 psycopg2-binary==2.9.11
uv add apscheduler==3.11.2 crawl4ai==0.8.0 playwright==1.58.0
uv add httpx==0.28.1 beautifulsoup4 lxml
uv add gspread==6.2.1 google-auth
uv add python-jose[cryptography]==3.5.0 bcrypt==5.0.0 python-multipart==0.0.22
uv add pydantic python-dotenv anthropic openpyxl
uv add --dev ruff pytest pytest-asyncio

# Install Playwright browsers after install
playwright install chromium

# Frontend (Next.js)
npx create-next-app@latest mba-frontend --typescript --tailwind --eslint --app
npx shadcn@latest init
npm install @tanstack/react-table
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Job scheduler | APScheduler | Celery + Redis | Celery requires a message broker (Redis/RabbitMQ), adding infra complexity. For daily batch scraping on a single server, Celery's distributed worker model is architectural overkill. APScheduler runs in-process and persists to PostgreSQL. |
| Job scheduler | APScheduler | cron (OS-level) | OS cron can't dynamically enable/disable per-building scrapes, report job status back to the database, or be managed via admin UI. APScheduler can do all three. |
| HTTP client | httpx | aiohttp | aiohttp is marginally faster but has a more complex API and session management. httpx's Requests-compatible API reduces cognitive overhead; the performance difference is irrelevant at 400 sites/day. |
| HTTP client | httpx | requests | requests is synchronous; using it inside async FastAPI routes blocks the event loop. httpx drops in as a near-identical async replacement. |
| LLM scraping | Crawl4AI | Firecrawl (SaaS) | Firecrawl is a managed cloud service — costs scale with usage and sends your content to a third party. Crawl4AI is self-hosted, open-source, and the team already confirmed the ~$120/month LLM cost is for the Claude API only, not a scraping SaaS. |
| LLM scraping | Crawl4AI | ScrapeGraphAI | Less active community, fewer extraction strategy options. Crawl4AI's `JsonCssExtractionStrategy` + `LLMExtractionStrategy` tiering is a better fit for this project's hybrid needs. |
| ORM | SQLAlchemy | Tortoise-ORM | Tortoise is async-first but has a smaller ecosystem and less mature migration tooling. SQLAlchemy 2.x async is now production-grade and has Alembic. |
| ORM | SQLAlchemy | Prisma (Python client) | Prisma's Python client is beta-quality; the JS/TS version is excellent but this is a Python backend. |
| Frontend | Next.js 16 | plain React + Vite | Next.js provides file-based routing, built-in auth patterns, and server actions that reduce boilerplate for an internal tool. Vite SPA would need a separate router, server, and more plumbing. |
| Frontend | Next.js 16 | Django + Jinja templates | Django templates have no component model; building a filterable data table and real-time scrape health dashboard in Jinja would be significantly more work than React with TanStack Table. |
| Database | PostgreSQL | SQLite | SQLite has write lock contention when multiple async scraper workers write simultaneously. PostgreSQL handles this correctly and is required for production reliability. |
| Password hashing | bcrypt (direct) | passlib | passlib's last release was 2020; it emits deprecation warnings on Python 3.12+ and breaks on 3.13 due to the removal of `crypt`. Use `bcrypt` directly. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Scrapy | Framework-level opinions conflict with the tiered scraper architecture. Scrapy assumes you're building a spider, not a service with per-building strategy routing. FastAPI + Playwright + httpx gives full control. | httpx + BeautifulSoup + Playwright (per-strategy) |
| Selenium | Slower than Playwright, older API, more flaky. Playwright replaced it as the standard browser automation tool. | Playwright 1.58 |
| celery | Unnecessary infra (broker + workers) for a daily batch job that runs on one server. | APScheduler with PostgreSQL job store |
| requests library | Synchronous; blocks FastAPI's async event loop. Not safe to use inside `async def` route handlers. | httpx with `AsyncClient` |
| passlib | Unmaintained since 2020; breaks on Python 3.13 due to stdlib `crypt` removal. | bcrypt 5.0 directly |
| oauth2client | Deprecated by Google. gspread 6.x uses `google-auth` natively. | google-auth |
| PyMongo / MongoDB | No relational integrity for building→unit relationships; harder to query "all units for buildings in neighborhood X." PostgreSQL relational model is the right fit. | PostgreSQL |
| Selenium Wire / mitmproxy for API interception | Overly complex; use direct API calls (httpx) where APIs exist, Playwright for JS-rendered HTML, and Crawl4AI+LLM only for unstructured fallback. | Tiered approach per PROJECT.md |

---

## Stack Patterns by Variant

**For scraping RentCafe/Yardi REST API buildings (~220 buildings):**
- Use `httpx.AsyncClient` with async context manager
- Parse JSON response directly into Pydantic models
- No browser needed — pure HTTP

**For scraping Entrata / RealPage / Funnel API-adjacent buildings:**
- Use `httpx.AsyncClient` first; if response is HTML or requires auth flow, fall back to Playwright
- Inspect network tab during development with `playwright codegen` to identify actual data endpoints

**For scraping PPM, Groupfox, AppFolio, Bozzuto (known platform HTML scrapers):**
- Use Playwright to render the page, then BeautifulSoup + lxml to parse the resulting HTML
- Write one scraper class per platform; all buildings on that platform share the scraper

**For scraping long-tail custom WordPress/Squarespace sites (~50-70 buildings):**
- Use Crawl4AI with `LLMExtractionStrategy` pointed at Claude Haiku
- Define a Pydantic extraction schema matching the unit data model
- Keep Crawl4AI as the last tier — only invoke it when no platform-specific scraper matches

**For the admin scrape health dashboard:**
- Write scrape run results to a `scrape_log` table in PostgreSQL (building_id, run_at, status, units_found, error_message)
- Query via FastAPI endpoint; display with TanStack Table in Next.js
- Polling is fine at daily cadence — no websockets needed

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI 0.129.0 | Pydantic 2.x, Python 3.10+ | FastAPI dropped Pydantic v1 support in 0.100.x; use Pydantic v2 only |
| Crawl4AI 0.8.0 | Python >=3.10, Playwright 1.x | Crawl4AI installs its own Playwright; verify versions don't conflict if installing both independently |
| Alembic 1.18.4 | Python >=3.10, SQLAlchemy 1.4+ and 2.x | Fully compatible with SQLAlchemy 2.0.x |
| APScheduler 3.11.2 | Python 3.x, SQLAlchemy 1.4+/2.x for job store | Use `SQLAlchemyJobStore` with the same PostgreSQL connection; APScheduler 4.x (beta) has a breaking API — stay on 3.x |
| gspread 6.2.1 | google-auth 2.x | Do NOT install oauth2client alongside google-auth; they conflict |
| bcrypt 5.0.0 | Python 3.9+ | python-jose requires bcrypt as its cryptography backend when using `[cryptography]` extra |
| Next.js 16 | Node.js >=20.9.0, TypeScript >=5.1 | Node.js 18 dropped; ensure CI/deployment uses Node 20+ |

---

## Sources

- [Crawl4AI PyPI page](https://pypi.org/project/Crawl4AI/) — v0.8.0, released 2026-01-16, Python >=3.10 (VERIFIED)
- [Crawl4AI docs v0.8.x](https://docs.crawl4ai.com/) — extraction strategies, LLM integration (VERIFIED)
- [FastAPI PyPI page](https://pypi.org/project/fastapi/) — v0.129.0, released 2026-02-12 (VERIFIED)
- [APScheduler PyPI page](https://pypi.org/project/APScheduler/) — v3.11.2, released 2025-12-22 (VERIFIED)
- [Playwright Python PyPI](https://pypi.org/project/playwright/) — v1.58.0, released 2026-01-30 (VERIFIED)
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — v2.0.46, released 2026-01-21 (VERIFIED)
- [Alembic PyPI](https://pypi.org/project/alembic/) — v1.18.4, released 2026-02-10, Python >=3.10 (VERIFIED)
- [psycopg2-binary PyPI](https://pypi.org/project/psycopg2-binary/) — v2.9.11, released 2025-10-10 (VERIFIED)
- [httpx PyPI](https://pypi.org/project/httpx/) — v0.28.1, released 2024-12-06 (VERIFIED)
- [python-jose PyPI](https://pypi.org/project/python-jose/) — v3.5.0, released 2025-05-28 (VERIFIED)
- [bcrypt PyPI](https://pypi.org/project/bcrypt/) — v5.0.0, released 2025-09-25 (VERIFIED)
- [gspread PyPI](https://pypi.org/project/gspread/) — v6.2.1, released 2025-05-14 (VERIFIED)
- [python-multipart PyPI](https://pypi.org/project/python-multipart/) — v0.0.22, released 2026-01-25 (VERIFIED)
- [Next.js 16 release notes](https://nextjs.org/blog/next-16) — Turbopack stable, React 19.2, Node 20.9+ required (VERIFIED, published 2025-10-21)
- [APScheduler vs Celery comparison](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat) — architectural tradeoffs (MEDIUM confidence, WebSearch verified)
- [passlib PyPI](https://pypi.org/project/passlib/) — last release 2020; breakage on Python 3.13 (VERIFIED)
- [pypi/warehouse issue #15454](https://github.com/pypi/warehouse/issues/15454) — passlib future/deprecation discussion (MEDIUM confidence)
- [gspread auth docs v6.2.1](https://docs.gspread.org/en/v6.2.1/oauth2.html) — oauth2client deprecated, use google-auth (VERIFIED)

---

*Stack research for: Moxie Building Aggregator (MBA) — web scraping aggregator with private agent/admin web UI*
*Researched: 2026-02-17*
