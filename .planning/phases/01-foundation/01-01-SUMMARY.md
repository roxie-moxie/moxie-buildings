---
phase: 01-foundation
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, sqlite, uv, pydantic, python]

# Dependency graph
requires: []
provides:
  - "pyproject.toml with uv project config, all runtime deps, and [project.scripts] for sheets-sync and dev"
  - "SQLAlchemy 2.0 DeclarativeBase models for Building, Unit, ScrapeRun in src/moxie/db/models.py"
  - "Alembic migration environment with render_as_batch=True and Base import from moxie.db.models"
  - "Initial schema migration (50fb02b298b3) creating buildings, units, scrape_runs tables"
  - "moxie.db SQLite database with all four tables (including alembic_version)"
  - "Session factory (SessionLocal + get_db) in src/moxie/db/session.py"
  - "Config loader in src/moxie/config.py reading DATABASE_URL, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH"
affects:
  - "02-normalizer: normalizer writes to Unit model schema defined here"
  - "03-sheets-sync: sheets sync writes to Building model schema defined here"
  - "phase-02-scrapers: all scrapers write through this schema"

# Tech tracking
tech-stack:
  added:
    - "sqlalchemy==2.0.46 — ORM with DeclarativeBase/Mapped 2.0 API"
    - "alembic==1.18.4 — database migrations with render_as_batch for SQLite/PostgreSQL portability"
    - "pydantic>=2.0 — data validation (used by normalizer in plan 02)"
    - "gspread==6.2.1 — Google Sheets API client (used by sheets sync in plan 03)"
    - "google-auth>=2.0 — service account authentication for gspread"
    - "python-dotenv>=1.0 — .env file loading"
    - "python-dateutil>=2.0 — format-agnostic date string parsing"
    - "uv==0.10.4 — Python package manager, installed via pip"
  patterns:
    - "SQLAlchemy 2.0 DeclarativeBase + Mapped[type] = mapped_column() for all models"
    - "Alembic env.py reads DATABASE_URL from env via load_dotenv() before any config"
    - "render_as_batch=True in both online and offline Alembic contexts"
    - "SQLite check_same_thread=False via connect_args for multi-threaded compatibility"
    - "Session factory pattern: SessionLocal + get_db() generator with try/finally close"

key-files:
  created:
    - "pyproject.toml — uv project config with all deps, [project.scripts], [tool.ruff]"
    - "uv.lock — dependency lockfile (37 packages)"
    - ".env.example — template with DATABASE_URL, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH"
    - "Makefile — dev, sync, test targets"
    - ".gitignore — covers .env, moxie.db, .venv, __pycache__"
    - "src/moxie/__init__.py — package marker"
    - "src/moxie/config.py — env var loader"
    - "src/moxie/db/__init__.py — package marker"
    - "src/moxie/db/models.py — Building, Unit, ScrapeRun SQLAlchemy models"
    - "src/moxie/db/session.py — engine, SessionLocal, get_db"
    - "src/moxie/sync/__init__.py — package marker for sync module"
    - "alembic.ini — Alembic config"
    - "alembic/env.py — customized with dotenv, Base import, render_as_batch=True"
    - "alembic/versions/50fb02b298b3_initial_schema.py — creates buildings, units, scrape_runs"
  modified:
    - "pyproject.toml — added description field; migrated dev-dependencies from tool.uv to dependency-groups"

key-decisions:
  - "platform field on buildings is plain String (no DB-level enum) — SQLite lacks native ENUM, values enforced at application layer"
  - "Single models.py for all three tables — at 3 tables, per-file complexity outweighs benefits; revisit at 8-10 tables"
  - "non_canonical as boolean column on units (not separate table) — non-canonical units are valid data for Phase 2 debugging; Phase 4 API filters WHERE non_canonical=false by default"
  - "Four indexes on units: bed_type, rent_cents, availability_date, building_id — matching Phase 4 API filter columns per CONTEXT.md"
  - "dependency-groups.dev instead of tool.uv.dev-dependencies — fixed deprecation warning from uv 0.10.4"

patterns-established:
  - "Pattern: All Alembic env.py files call load_dotenv() before reading DATABASE_URL"
  - "Pattern: render_as_batch=True in both online and offline Alembic context.configure() calls"
  - "Pattern: SQLite connect_args check_same_thread=False conditional on DATABASE_URL prefix"

requirements-completed: [DATA-01, DATA-02]

# Metrics
duration: 6min
completed: 2026-02-18
---

# Phase 01 Plan 01: Project Scaffold and Database Schema Summary

**SQLAlchemy 2.0 models (Building, Unit, ScrapeRun) with Alembic migration on SQLite, uv project scaffold, and 12-column units table with non_canonical flag and 4 query indexes**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-02-18T19:24:44Z
- **Completed:** 2026-02-18T19:30:26Z
- **Tasks:** 3 of 3
- **Files created:** 14

## Accomplishments

- Complete uv project scaffold with pyproject.toml, all 7 runtime dependencies (sqlalchemy, alembic, pydantic, gspread, google-auth, python-dotenv, python-dateutil), [project.scripts] entries, and generated uv.lock with 37 packages
- SQLAlchemy 2.0 DeclarativeBase models for Building (10 columns + 2 relationships), Unit (12 columns + unique constraint + 4 indexes), and ScrapeRun (6 columns) — all using Mapped[type] syntax
- Alembic migration environment with render_as_batch=True, Base import, DATABASE_URL from env; autogenerated migration 50fb02b298b3 applied to moxie.db — all four tables verified present with correct columns

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold — pyproject.toml, .env.example, Makefile** - `eef473c` (feat)
2. **Task 2: SQLAlchemy 2.0 models — Building, Unit, ScrapeRun** - `3c8f41c` (feat)
3. **Task 3: Alembic setup and initial migration** - `6ebb2b2` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `pyproject.toml` — hatchling build backend, 7 runtime deps, [project.scripts] for sheets-sync + dev, [tool.ruff] config
- `uv.lock` — lockfile with 37 resolved packages
- `.env.example` — DATABASE_URL, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH placeholders
- `Makefile` — dev, sync, test targets mapping to uv run commands
- `.gitignore` — .env, moxie.db, .venv, __pycache__ and standard Python ignores
- `src/moxie/__init__.py` — package marker (empty)
- `src/moxie/config.py` — loads DATABASE_URL, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH from env via load_dotenv
- `src/moxie/db/__init__.py` — package marker (empty)
- `src/moxie/db/models.py` — Building, Unit, ScrapeRun with SQLAlchemy 2.0 DeclarativeBase/Mapped; Unit has non_canonical bool, UniqueConstraint, 4 indexes
- `src/moxie/db/session.py` — create_engine with SQLite check_same_thread=False, SessionLocal, get_db() generator
- `src/moxie/sync/__init__.py` — package marker for sync module
- `alembic.ini` — generated Alembic config
- `alembic/env.py` — customized: load_dotenv, Base import, DATABASE_URL from env, render_as_batch=True in both modes
- `alembic/versions/50fb02b298b3_initial_schema.py` — creates buildings (10 cols), scrape_runs (6 cols), units (12 cols + constraint + 4 indexes)

## Decisions Made

- **platform as plain String:** No DB-level enum on the buildings.platform column. SQLite lacks native ENUM; valid values ('api', 'platform', 'llm') enforced at application layer via Pydantic in plan 02.
- **Single models.py:** All three models in one file. At 3 tables, per-table files add import ordering complexity (all models must register on Base.metadata before autogenerate) with no readability benefit.
- **non_canonical as boolean column:** Non-canonical units stored in the main units table with a flag, not excluded. They're valid data for Phase 2 debugging; Phase 4 API will filter WHERE non_canonical=false.
- **Four query indexes:** ix_units_bed_type, ix_units_rent_cents, ix_units_availability_date, ix_units_building_id — matching Phase 4 API filter columns specified in CONTEXT.md.
- **dependency-groups.dev:** Migrated from deprecated tool.uv.dev-dependencies to the current dependency-groups.dev format to eliminate uv deprecation warning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed uv via pip (uv not in PATH)**
- **Found during:** Task 1 (project scaffold)
- **Issue:** `uv` was not installed or not on PATH; required to run `uv sync` per plan
- **Fix:** Installed uv 0.10.4 via `py -3.13 -m pip install uv`; used `py -3.13 -m uv` invocation pattern throughout
- **Files modified:** None (system-level install)
- **Verification:** `py -3.13 -m uv --version` returns `uv 0.10.4`
- **Committed in:** Not committed (system dependency)

**2. [Rule 1 - Bug] Fixed deprecated tool.uv.dev-dependencies field**
- **Found during:** Task 1 (uv sync output)
- **Issue:** `tool.uv.dev-dependencies` is deprecated in uv 0.10.4, will be removed in future release. Warning appeared on every uv invocation.
- **Fix:** Changed to `[dependency-groups]` with `dev = [...]` syntax per current uv spec
- **Files modified:** `pyproject.toml`
- **Verification:** `uv sync` runs without any deprecation warnings
- **Committed in:** `eef473c` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking — uv not installed; 1 bug — deprecated config field)
**Impact on plan:** Both fixes necessary for execution. No scope creep. The plan assumed uv was available; it was not installed on this system.

## Issues Encountered

- uv was not in PATH on this Windows 11 system (not installed). Installed via `py -3.13 -m pip install uv` before proceeding. All subsequent uv commands use `py -3.13 -m uv` invocation to ensure the installed version is found.

## User Setup Required

None — no external service configuration required for this plan. Google Sheets auth is required for plan 03 (sheets sync).

## Next Phase Readiness

- Schema contract is locked: building, unit, and scrape_run table structures are committed and migration-controlled
- All plan 02 files (normalizer) and plan 03 files (sheets sync) can now import from `moxie.db.models` and `moxie.db.session`
- Phase 2 scrapers can write units via the schema without further migration (unless new columns are needed)
- moxie.db exists and is at migration head — ready for seed data (plan 02 or plan 03)

## Self-Check: PASSED

All files verified present on disk. All task commits verified in git log.

| Item | Status |
|------|--------|
| pyproject.toml | FOUND |
| .env.example | FOUND |
| Makefile | FOUND |
| .gitignore | FOUND |
| uv.lock | FOUND |
| src/moxie/db/models.py | FOUND |
| src/moxie/db/session.py | FOUND |
| alembic/env.py | FOUND |
| alembic/versions/50fb02b298b3_initial_schema.py | FOUND |
| Task 1 commit eef473c | FOUND |
| Task 2 commit 3c8f41c | FOUND |
| Task 3 commit 6ebb2b2 | FOUND |

---
*Phase: 01-foundation*
*Completed: 2026-02-18*
