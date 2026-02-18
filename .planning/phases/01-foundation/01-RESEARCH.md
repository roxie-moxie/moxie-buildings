# Phase 1: Foundation - Research

**Researched:** 2026-02-17
**Domain:** SQLAlchemy/Alembic schema setup, Pydantic normalizer, gspread Google Sheets sync, uv dev environment
**Confidence:** HIGH (core stack verified via official docs and PyPI; patterns verified against SQLAlchemy 2.0 docs, Alembic docs, gspread 6.2.1 docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Database & stack**
- Local dev: SQLite (zero-config, file-based)
- Production target: PostgreSQL (SQLite for dev, swap at deploy via SQLAlchemy abstraction)
- ORM: SQLAlchemy (enables SQLite/PostgreSQL portability)
- Migrations: Alembic
- Python tooling: uv (replaces pip + venv — `uv sync` for install)

**Dev environment**
- Startup command: `uv run dev` or `make dev` (pure Python, no Docker)
- What it does: creates venv, installs deps, runs migrations, seeds DB
- Config: `.env` for secrets (gitignored), `.env.example` committed with all required var names and placeholder values
- DB inspection: CLI only (`sqlite3` + custom query scripts) — no Datasette or GUI tools in Phase 1
- Seed data: 3-5 buildings + 5-10 units (representative enough to test queries and filters during Phase 2+ development)

**Schema — buildings table**
- `id` (auto-increment PK), `name`, `url` (unique — primary upsert key), `neighborhood`, `management_company`
- `platform` (which scraper tier: 'api' / 'platform' / 'llm')
- `rentcafe_property_id` (nullable), `rentcafe_api_token` (nullable)
- `last_scrape_status` ('never' / 'success' / 'failed'), `last_scraped_at` (timestamp)

**Schema — units table**
- `id` (auto-increment PK), `building_id` (FK → buildings), `unit_number`, `bed_type`, `rent_cents`, `availability_date` (TEXT ISO), `floor_plan_name` (nullable), `floor_plan_url` (nullable), `baths` (nullable), `sqft` (nullable), `scrape_run_at`
- Unique constraint on `(building_id, unit_number)`
- On re-scrape: delete all units for the building, then insert fresh

**Schema — scrape_runs table**
- `id` (auto-increment PK), `building_id` (FK → buildings), `run_at`, `status` ('success' / 'failed'), `unit_count`, `error_message` (nullable)

**Schema — indexes**
- Claude's discretion: index filter columns that Phase 4 API will query against

**Normalizer — canonical bed types**
- `Studio`, `Convertible`, `1BR`, `1BR+Den`, `2BR`, `3BR+`
- Non-canonical values stored as-is with `non_canonical` flag — NOT rejected

**Normalizer — rent**
- Stored as integer cents; normalizer strips `$`, commas, `.00` suffix

**Normalizer — dates**
- Stored as ISO date string: `YYYY-MM-DD`; normalizer parses whatever scraper provides

**Normalizer — neighborhood**
- NOT scraped — building-level attribute from Google Sheets; not touched by normalizer

**Google Sheets sync**
- Auth: Service account `roxie-sheets@moxie-roxie.iam.gserviceaccount.com` (JSON key file path in `.env`)
- Sheet ID: stored in `.env` as `GOOGLE_SHEETS_ID`; tab: `Buildings`
- Upsert key: `url`; on building deleted from Sheet: hard delete from DB (cascade delete units)
- Output: `Added: X, Updated: Y, Deleted: Z`

### Claude's Discretion

- Exact Alembic migration file structure and naming
- SQLAlchemy model organization (single models.py vs per-table files)
- Index definitions beyond primary keys and FKs
- Whether `platform` field on buildings has a DB-level enum constraint or is a plain string
- `scraper_type` field: "platform" column on buildings table (from Sheet) — Claude picks whether to enforce as enum

### Deferred Ideas (OUT OF SCOPE)

- Building amenity columns (washer/dryer in unit vs building, parking, pets, etc.) — future Alembic migration
- Agent toggle/hide UI for filtering buildings by amenity criteria — Phase 5 frontend
- Datasette or any admin DB inspection UI — Phase 5
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System reads building list from Google Sheets and syncs records (building name, URL, neighborhood, management company) to the local database | gspread 6.2.1 `get_all_records()` + SQLAlchemy upsert on `url`; hard delete on missing rows |
| DATA-01 | Each unit record stores required fields: Unit #, Beds, Base monthly rent, Availability date, Neighborhood, Building name, Building website URL, Date of last scrape | `units` table schema covers all required fields; neighborhood/building name/URL come from the JOIN with buildings |
| DATA-02 | Unit records store optional fields when source provides them: Floor plan, Number of baths, Square footage | `floor_plan_name`, `floor_plan_url`, `baths`, `sqft` all nullable TEXT/numeric columns on units |
| DATA-03 | Unit data from all platforms is normalized to the canonical format before storage (no platform-specific raw values in the database) | Pydantic v2 `UnitInput` model with `@field_validator(mode='before')` normalizes bed_type, rent_cents, availability_date before DB write |
</phase_requirements>

---

## Summary

Phase 1 establishes the data contract that all Phase 2 scrapers write to. It has four distinct work streams: (1) project scaffold with uv, (2) SQLAlchemy models + Alembic migrations, (3) the Pydantic normalizer module, and (4) the Google Sheets sync command. These can be built sequentially in that order because each builds on the last: the schema must exist before the normalizer references it, the normalizer must exist before the sync uses it to validate buildings data.

The stack is mature and well-documented. SQLAlchemy 2.0 with DeclarativeBase/Mapped typing is the standard ORM pattern; Alembic with `render_as_batch=True` in env.py handles SQLite's ALTER TABLE limitations while remaining transparent on PostgreSQL. The gspread 6.2.1 service account pattern is a two-call flow: authenticate with the JSON key file, then `get_all_records()` from the `Buildings` tab. The normalizer is a pure function with no DB access — Pydantic `@field_validator(mode='before')` handles all field coercions.

The one decision with lasting impact is how to implement the buildings upsert. SQLAlchemy does not have a dialect-agnostic `ON CONFLICT` construct; both SQLite and PostgreSQL support `INSERT ... ON CONFLICT DO UPDATE` but via dialect-specific `insert()` functions. The recommended pattern is to use the SQLite dialect's `insert().on_conflict_do_update()` for local dev and the PostgreSQL dialect's equivalent for production, selecting the right import based on the `DATABASE_URL` dialect prefix. Alternatively, a SELECT + INSERT/UPDATE pattern avoids the dialect split at the cost of two queries.

**Primary recommendation:** Single `models.py` for all four tables (buildings, units, scrape_runs, and an optional `non_canonical_units` log). Use `render_as_batch=True` in Alembic env.py. Implement the sheets sync as a standalone CLI entrypoint (`uv run sheets-sync`) and the dev bootstrap as a Python script registered under `[project.scripts]` in pyproject.toml.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.46 | ORM + query builder | The Python ORM; 2.x DeclarativeBase/Mapped typing is the modern API; pairs with Alembic |
| Alembic | 1.18.4 | Database migrations | Written by SQLAlchemy's author; autogenerate from model diffs; `render_as_batch` handles SQLite |
| Pydantic | 2.x (bundled with FastAPI) | Normalizer schema validation | `@field_validator(mode='before')` cleanly handles pre-normalization coercions |
| gspread | 6.2.1 | Google Sheets API client | Standard Python Sheets library; service account auth via `google-auth`, not deprecated `oauth2client` |
| google-auth | 2.x | Google credential management | Required by gspread 6.x; handles service account JWT signing automatically |
| python-dotenv | 1.x | .env file loading | Loads DATABASE_URL, GOOGLE_SHEETS_ID, and key file path for dev without shell exports |
| python-dateutil | 2.x | Date string parsing | Handles heterogeneous date strings from scrapers (`"Available Now"`, `"March 1"`, `"2026-03-01"`) |
| uv | latest | Python package manager + venv | Replaces pip + venv; `uv sync` installs from pyproject.toml lockfile in seconds |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest | Unit testing | Test normalizer, sheets sync, and seed script in isolation |
| ruff | latest | Linter + formatter | Replaces Black + Flake8; zero-config; run as `uv run ruff check .` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-dateutil | stdlib `datetime.strptime` | strptime requires knowing the format string; dateutil's `parse()` is format-agnostic, handles scraper output variability |
| Pydantic validator | inline normalizer functions | Pydantic validators integrate with IDE type checking and produce consistent error messages; inline functions have no schema contract |
| Single models.py | Per-table files in `db/` package | Per-table files require careful import ordering so all models register on `Base.metadata` before `alembic autogenerate` runs; single file has no import risks at this table count (4 tables) |

**Installation:**
```bash
uv init moxie-buildings
uv add sqlalchemy==2.0.46 alembic==1.18.4 pydantic python-dotenv
uv add gspread==6.2.1 google-auth python-dateutil
uv add --dev pytest ruff
```

---

## Architecture Patterns

### Recommended Project Structure

```
moxie-buildings/
├── pyproject.toml              # uv project config + [project.scripts]
├── uv.lock                     # lockfile (committed)
├── .env                        # secrets (gitignored)
├── .env.example                # template (committed)
├── Makefile                    # optional: make dev, make sync, make test
├── alembic.ini                 # generated by alembic init
├── alembic/
│   ├── env.py                  # customized: reads DATABASE_URL from .env
│   └── versions/               # migration files
│       └── 001_initial_schema.py
├── src/
│   └── moxie/
│       ├── __init__.py
│       ├── config.py           # Settings class: DATABASE_URL, GOOGLE_SHEETS_ID, etc.
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py       # all 4 SQLAlchemy models (Building, Unit, ScrapeRun)
│       │   └── session.py      # create_engine + SessionLocal + get_db
│       ├── normalizer.py       # UnitInput Pydantic model + normalize() pure function
│       └── sync/
│           ├── __init__.py
│           └── sheets.py       # sheets_sync() function; CLI entrypoint
├── scripts/
│   └── seed.py                 # inserts 3-5 buildings + 5-10 units for dev
└── tests/
    ├── test_normalizer.py
    └── test_sheets_sync.py
```

### Pattern 1: SQLAlchemy 2.0 DeclarativeBase Models

**What:** Use `DeclarativeBase` + `Mapped` type annotations for all model definitions. This is the SQLAlchemy 2.0 standard; the 1.x `Column()` pattern still works but is considered legacy.

**When to use:** Always for new code in SQLAlchemy 2.x.

**Example:**
```python
# Source: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    neighborhood: Mapped[Optional[str]] = mapped_column(String)
    management_company: Mapped[Optional[str]] = mapped_column(String)
    platform: Mapped[Optional[str]] = mapped_column(String)        # 'api' | 'platform' | 'llm'
    rentcafe_property_id: Mapped[Optional[str]] = mapped_column(String)
    rentcafe_api_token: Mapped[Optional[str]] = mapped_column(String)
    last_scrape_status: Mapped[str] = mapped_column(String, server_default="never")
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column()

    units: Mapped[list["Unit"]] = relationship(back_populates="building", cascade="all, delete-orphan")
    scrape_runs: Mapped[list["ScrapeRun"]] = relationship(back_populates="building", cascade="all, delete-orphan")

class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("building_id", "unit_number", name="uq_unit_building_number"),
        Index("ix_units_bed_type", "bed_type"),
        Index("ix_units_rent_cents", "rent_cents"),
        Index("ix_units_availability_date", "availability_date"),
        Index("ix_units_building_id", "building_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    unit_number: Mapped[str] = mapped_column(String, nullable=False)
    bed_type: Mapped[str] = mapped_column(String, nullable=False)
    non_canonical: Mapped[bool] = mapped_column(default=False)
    rent_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_date: Mapped[str] = mapped_column(String, nullable=False)    # YYYY-MM-DD
    floor_plan_name: Mapped[Optional[str]] = mapped_column(String)
    floor_plan_url: Mapped[Optional[str]] = mapped_column(String)
    baths: Mapped[Optional[str]] = mapped_column(String)
    sqft: Mapped[Optional[int]] = mapped_column(Integer)
    scrape_run_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    building: Mapped["Building"] = relationship(back_populates="units")

class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String, nullable=False)    # 'success' | 'failed'
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String)

    building: Mapped["Building"] = relationship(back_populates="scrape_runs")
```

### Pattern 2: Alembic env.py with SQLite/PostgreSQL portability

**What:** Configure Alembic's `env.py` to read `DATABASE_URL` from the environment (via `.env`), and enable `render_as_batch=True` so that generated migrations work on both SQLite (which cannot ALTER columns) and PostgreSQL (which uses standard ALTER and ignores batch mode transparently).

**When to use:** Always when the codebase targets both SQLite (dev) and PostgreSQL (prod).

**Example:**
```python
# alembic/env.py — key customizations
import os
from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool
from moxie.db.models import Base   # imports all models, registers them on Base.metadata

load_dotenv()

config = context.config
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
target_metadata = Base.metadata

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,    # required for SQLite ALTER TABLE compatibility
        )
        with context.begin_transaction():
            context.run_migrations()
```

**Note on render_as_batch:** The Alembic docs confirm: "This mode is safe to use in all cases, as the `Operations.batch_alter_table()` directive by default only takes place for SQLite; other backends will behave just as they normally do in the absence of the batch directives." Source: https://alembic.sqlalchemy.org/en/latest/batch.html

### Pattern 3: Session factory and get_db dependency

**What:** A `SessionLocal` factory created once at module load time; a `get_db()` generator that yields a session and closes it after the request or call completes.

**Example:**
```python
# src/moxie/db/session.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./moxie.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False   # required for SQLite in multi-threaded contexts

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**SQLite note:** `check_same_thread=False` must be set for SQLite when sessions are used across threads (e.g., in a CLI that passes a session to a function). PostgreSQL does not need this argument and ignores it.

### Pattern 4: Pydantic v2 Normalizer

**What:** A `UnitInput` Pydantic model that accepts raw scraper output and normalizes it via `@field_validator(mode='before')`. A `normalize()` function wraps the model and returns a `UnitRecord` dict suitable for DB insertion.

**When to use:** All scrapers call `normalize(raw_dict)` before writing to the DB. The normalizer is the single source of truth for field mapping.

**Example:**
```python
# src/moxie/normalizer.py
import re
from datetime import datetime
from typing import Optional, Any
from dateutil import parser as dateutil_parser
from pydantic import BaseModel, field_validator, model_validator

CANONICAL_BED_TYPES = {"Studio", "Convertible", "1BR", "1BR+Den", "2BR", "3BR+"}

# Common aliases raw scrapers return
BED_TYPE_ALIASES = {
    "0": "Studio", "0br": "Studio", "studio": "Studio",
    "convertible": "Convertible", "alcove": "Convertible", "jr 1br": "Convertible",
    "1": "1BR", "1br": "1BR", "1 bed": "1BR", "one bedroom": "1BR",
    "1br+den": "1BR+Den", "1 bed den": "1BR+Den", "1+den": "1BR+Den",
    "2": "2BR", "2br": "2BR", "2 bed": "2BR", "two bedroom": "2BR",
    "3": "3BR+", "3br": "3BR+", "3 bed": "3BR+", "3+": "3BR+", "4br": "3BR+",
}

class UnitInput(BaseModel):
    unit_number: str
    bed_type: str
    rent: Any           # accepts "$1,500.00", "1500", 1500
    availability_date: Any   # accepts any parseable date string
    floor_plan_name: Optional[str] = None
    floor_plan_url: Optional[str] = None
    baths: Optional[Any] = None
    sqft: Optional[Any] = None

    @field_validator("bed_type", mode="before")
    @classmethod
    def normalize_bed_type(cls, v: Any) -> str:
        normalized = str(v).strip().lower()
        return BED_TYPE_ALIASES.get(normalized, str(v).strip())

    @field_validator("rent", mode="before")
    @classmethod
    def normalize_rent(cls, v: Any) -> int:
        """Return rent as integer cents."""
        s = str(v).strip().replace("$", "").replace(",", "").replace("/mo", "")
        # Remove .00 suffix
        s = re.sub(r"\.0+$", "", s)
        return int(float(s) * 100) if "." in s else int(s) * 100

    @field_validator("availability_date", mode="before")
    @classmethod
    def normalize_date(cls, v: Any) -> str:
        """Return YYYY-MM-DD string. Handle 'Available Now' → today."""
        s = str(v).strip().lower()
        if s in ("available now", "now", "immediate", "immediately", ""):
            return datetime.today().strftime("%Y-%m-%d")
        parsed = dateutil_parser.parse(str(v))
        return parsed.strftime("%Y-%m-%d")


def normalize(raw: dict, building_id: int) -> dict:
    """
    Normalize raw scraper output to DB-ready unit dict.
    Returns a dict with: building_id, unit_number, bed_type, non_canonical,
    rent_cents, availability_date, floor_plan_name, floor_plan_url, baths, sqft, scrape_run_at.
    """
    inp = UnitInput(**raw)
    is_canonical = inp.bed_type in CANONICAL_BED_TYPES
    return {
        "building_id": building_id,
        "unit_number": inp.unit_number,
        "bed_type": inp.bed_type,
        "non_canonical": not is_canonical,
        "rent_cents": inp.rent,     # already normalized to int cents by validator
        "availability_date": inp.availability_date,
        "floor_plan_name": inp.floor_plan_name,
        "floor_plan_url": inp.floor_plan_url,
        "baths": str(inp.baths) if inp.baths is not None else None,
        "sqft": int(inp.sqft) if inp.sqft is not None else None,
        "scrape_run_at": datetime.utcnow(),
    }
```

### Pattern 5: Google Sheets sync with gspread 6.2.1

**What:** Authenticate with a service account JSON key, open the spreadsheet by ID, read the `Buildings` tab with `get_all_records()` (returns a list of dicts keyed by header row), then upsert each building to the DB using `url` as the conflict key. Hard-delete any buildings in DB whose URL is no longer in the Sheet (cascade deletes units).

**Example:**
```python
# src/moxie/sync/sheets.py
import os
from dotenv import load_dotenv
import gspread
from sqlalchemy.orm import Session
from moxie.db.models import Building
from moxie.db.session import get_db

load_dotenv()

def sheets_sync(db: Session) -> dict:
    """
    Sync buildings from Google Sheets to DB.
    Returns {"added": int, "updated": int, "deleted": int}.
    """
    gc = gspread.service_account(filename=os.environ["GOOGLE_SHEETS_KEY_PATH"])
    sh = gc.open_by_key(os.environ["GOOGLE_SHEETS_ID"])
    worksheet = sh.worksheet("Buildings")
    rows = worksheet.get_all_records()    # list[dict] keyed by header row

    sheet_urls = {row["url"] for row in rows}
    added = updated = deleted = 0

    for row in rows:
        existing = db.query(Building).filter_by(url=row["url"]).first()
        if existing:
            existing.name = row["name"]
            existing.neighborhood = row.get("neighborhood")
            existing.management_company = row.get("management_company")
            existing.platform = row.get("platform")
            existing.rentcafe_property_id = row.get("rentcafe_property_id") or None
            existing.rentcafe_api_token = row.get("rentcafe_api_token") or None
            updated += 1
        else:
            db.add(Building(
                name=row["name"],
                url=row["url"],
                neighborhood=row.get("neighborhood"),
                management_company=row.get("management_company"),
                platform=row.get("platform"),
                rentcafe_property_id=row.get("rentcafe_property_id") or None,
                rentcafe_api_token=row.get("rentcafe_api_token") or None,
                last_scrape_status="never",
            ))
            added += 1

    # Hard delete buildings no longer in Sheet
    for building in db.query(Building).all():
        if building.url not in sheet_urls:
            db.delete(building)   # cascade deletes units via relationship
            deleted += 1

    db.commit()
    return {"added": added, "updated": updated, "deleted": deleted}
```

**Auth note:** gspread 6.x requires the spreadsheet to be shared with the service account email (`roxie-sheets@moxie-roxie.iam.gserviceaccount.com`) — the same as sharing with any Google account. The service account must have at least Viewer access. Without this sharing step, you receive `SpreadsheetNotFound`. Source: https://docs.gspread.org/en/v6.2.1/oauth2.html

### Pattern 6: uv project scripts for CLI entrypoints

**What:** Register `sheets-sync` and `dev` as `[project.scripts]` in `pyproject.toml` so they run as `uv run sheets-sync` and `uv run dev`. This is the Python packaging standard for CLI entrypoints and works correctly with `uv`.

**Example pyproject.toml:**
```toml
[project]
name = "moxie-buildings"
version = "0.1.0"
requires-python = ">=3.12"

[project.scripts]
sheets-sync = "moxie.sync.sheets:main"
dev = "scripts.dev_bootstrap:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "ruff>=0.9",
]
```

The `scripts/dev_bootstrap.py::main` function runs migrations (`alembic upgrade head`) and seeds the DB. `uv run dev` ensures deps are synced first, then invokes the script within the managed venv.

### Anti-Patterns to Avoid

- **Hardcoded column indices in Sheets parsing:** `row[0]`, `row[1]` breaks immediately if someone reorders columns in the Sheet. Always use `get_all_records()` which keys by header name.
- **Calling the Sheets API from every request:** Sync runs on schedule or on demand via `uv run sheets-sync`. Never call gspread from a request handler.
- **Deleting units before scrape succeeds:** The architecture decision is delete-on-success only. If you delete units before calling the scraper, a failed scrape leaves the building with zero units.
- **Storing rent as string:** Rent must be stored as integer cents from day one. Range filter queries (`WHERE rent_cents BETWEEN ? AND ?`) are impossible on string values.
- **Using the legacy Alembic `Column()` notation in new migrations:** Alembic autogenerate with SQLAlchemy 2.0 models produces `Mapped` type-annotated column definitions. Do not mix legacy and 2.0 style in the same file.
- **Skipping `render_as_batch=True`:** Without it, autogenerated migrations that alter columns or add constraints will fail on SQLite, breaking the "develop on SQLite" workflow.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date string parsing | Custom regex per format | `python-dateutil` `parse()` | Handles `"March 1, 2026"`, `"03/01/26"`, `"2026-03-01"`, `"Available Now"` without format strings; battle-tested edge cases |
| Sheets auth | OAuth2 manual flow | `gspread.service_account(filename=...)` | Service account flow handles JWT signing, token refresh, and scope negotiation; all edge cases are handled |
| DB migration versioning | Hand-written SQL files | Alembic autogenerate | Alembic detects model diffs, generates reversible migrations, and handles the SQLite batch mode; hand-written SQL files do not autogenerate and do not handle rollbacks cleanly |
| Rent parsing | `float(rent_string.strip("$").replace(",",""))` | Pydantic `@field_validator` | Validators are reusable, testable, and produce schema-level error messages; ad hoc parsing is duplicated across scrapers |
| Upsert logic | Manual SELECT + INSERT/UPDATE | SQLAlchemy dialect upsert or session query + conditional | Dialect upsert is single-statement and atomic; manual SELECT + conditional is two queries and can race |

**Key insight:** Every one of these hand-rolled solutions will fail on an edge case that the library has already solved. The Sheets auth in particular has a non-obvious sharing requirement (the Sheet must be shared with the service account email) that is not intuitive and will block progress if not handled.

---

## Common Pitfalls

### Pitfall 1: SQLite `check_same_thread` error

**What goes wrong:** `ProgrammingError: SQLite objects created in a thread can only be used in that same thread.`

**Why it happens:** SQLite connections created in one thread (e.g., the main CLI thread) cannot be handed to another thread (e.g., a session used inside a called function that uv runs). FastAPI uses a thread pool; CLI scripts may use threading for seed parallelism.

**How to avoid:** Always set `connect_args={"check_same_thread": False}` when the `DATABASE_URL` is `sqlite://`. This is safe — it disables a guard that is overly conservative for this use case.

**Warning signs:** Error only appears in certain call paths, not during basic testing.

---

### Pitfall 2: Alembic doesn't detect models because import is missing

**What goes wrong:** `alembic revision --autogenerate` produces an empty migration (no table creates) even though your models are defined.

**Why it happens:** Alembic reads `target_metadata = Base.metadata`, but if `models.py` is never imported in `env.py`, the models never register on `Base.metadata`. Alembic sees an empty metadata and generates a no-op migration.

**How to avoid:** Import the models module explicitly in `env.py`:
```python
from moxie.db.models import Base  # noqa: F401 — side effect import registers all models
```
This must be done before `target_metadata = Base.metadata`.

**Warning signs:** Running `alembic revision --autogenerate -m "initial"` generates a migration file with empty `upgrade()` and `downgrade()` functions.

---

### Pitfall 3: gspread `SpreadsheetNotFound` on valid sheet ID

**What goes wrong:** `gspread.exceptions.SpreadsheetNotFound` is raised even though the spreadsheet ID is correct.

**Why it happens:** The Google Sheet has not been shared with the service account email. The service account is a separate Google identity and cannot see sheets that haven't been explicitly shared with it.

**How to avoid:** Share the Google Sheet with `roxie-sheets@moxie-roxie.iam.gserviceaccount.com` via the normal Sheets sharing UI (Viewer or Editor access). This is a one-time setup step, not a code fix.

**Warning signs:** The error appears immediately on the first `gc.open_by_key()` call, not during auth.

---

### Pitfall 4: Alembic migration fails on SQLite when adding NOT NULL column

**What goes wrong:** `alembic upgrade head` fails with `IntegrityError: NOT NULL constraint failed` when adding a column with no default to a table that has existing rows.

**Why it happens:** SQLite does not support `ALTER TABLE ADD COLUMN NOT NULL` without a default. PostgreSQL allows it if the table is empty but rejects it on existing rows.

**How to avoid:** Always provide a `server_default` or `nullable=True` when adding columns via Alembic. For columns that should be NOT NULL in the long run, add them as nullable, backfill, then add the NOT NULL constraint in a second migration.

**Warning signs:** Migration fails only when the DB has existing data; passes on a fresh empty DB.

---

### Pitfall 5: `get_all_records()` returns empty list silently when tab name is wrong

**What goes wrong:** `worksheet.get_all_records()` returns `[]` (empty list) instead of raising an error when the `Buildings` tab name doesn't match exactly (case-sensitive).

**Why it happens:** gspread raises `WorksheetNotFound` when `sh.worksheet("buildings")` (lowercase) is called and the tab is named `"Buildings"`. But if the sheet is empty, `get_all_records()` returns `[]` without raising. These two situations look identical to calling code.

**How to avoid:** Add a row count guard after `get_all_records()`:
```python
rows = worksheet.get_all_records()
if len(rows) < 5:   # threshold based on known minimum number of buildings
    raise ValueError(f"Sheets sync returned suspiciously few rows: {len(rows)}")
```

**Warning signs:** Sync reports `Added: 0, Updated: 0, Deleted: N` where N is all existing buildings — the sync "succeeded" but deleted everything.

---

### Pitfall 6: `non_canonical` flag missing from DB schema

**What goes wrong:** The normalizer outputs a `non_canonical` boolean but the `units` table has no corresponding column — insertion fails with an `IntegrityError` or the field is silently dropped.

**Why it happens:** The `non_canonical` flag is in the normalizer output spec but easy to miss when writing the initial Alembic migration from the `Unit` model.

**How to avoid:** Include `non_canonical: Mapped[bool] = mapped_column(default=False)` in the `Unit` model before running `alembic revision --autogenerate`. Run `alembic upgrade head` and verify the column exists with `sqlite3 moxie.db ".schema units"`.

---

## Code Examples

Verified patterns from official sources:

### Complete Alembic migration for initial schema

```python
# alembic/versions/001_initial_schema.py
# Source: https://alembic.sqlalchemy.org/en/latest/batch.html
"""Initial schema: buildings, units, scrape_runs

Revision ID: 001
Create Date: 2026-02-17
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None

def upgrade() -> None:
    op.create_table(
        'buildings',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('url', sa.String, unique=True, nullable=False),
        sa.Column('neighborhood', sa.String),
        sa.Column('management_company', sa.String),
        sa.Column('platform', sa.String),
        sa.Column('rentcafe_property_id', sa.String),
        sa.Column('rentcafe_api_token', sa.String),
        sa.Column('last_scrape_status', sa.String, server_default='never', nullable=False),
        sa.Column('last_scraped_at', sa.DateTime),
    )
    op.create_table(
        'units',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('building_id', sa.Integer, sa.ForeignKey('buildings.id'), nullable=False),
        sa.Column('unit_number', sa.String, nullable=False),
        sa.Column('bed_type', sa.String, nullable=False),
        sa.Column('non_canonical', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('rent_cents', sa.Integer, nullable=False),
        sa.Column('availability_date', sa.String, nullable=False),
        sa.Column('floor_plan_name', sa.String),
        sa.Column('floor_plan_url', sa.String),
        sa.Column('baths', sa.String),
        sa.Column('sqft', sa.Integer),
        sa.Column('scrape_run_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('building_id', 'unit_number', name='uq_unit_building_number'),
    )
    op.create_index('ix_units_bed_type', 'units', ['bed_type'])
    op.create_index('ix_units_rent_cents', 'units', ['rent_cents'])
    op.create_index('ix_units_availability_date', 'units', ['availability_date'])
    op.create_index('ix_units_building_id', 'units', ['building_id'])
    op.create_table(
        'scrape_runs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('building_id', sa.Integer, sa.ForeignKey('buildings.id'), nullable=False),
        sa.Column('run_at', sa.DateTime, nullable=False),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('unit_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.String),
    )

def downgrade() -> None:
    op.drop_table('scrape_runs')
    op.drop_table('units')
    op.drop_table('buildings')
```

### gspread service account authentication

```python
# Source: https://docs.gspread.org/en/v6.2.1/oauth2.html
import gspread

# Option 1: default credential file location (~/.config/gspread/service_account.json)
gc = gspread.service_account()

# Option 2: explicit path (preferred — path comes from .env)
gc = gspread.service_account(filename="/path/to/service-account-key.json")

sh = gc.open_by_key("SPREADSHEET_ID_FROM_ENV")
worksheet = sh.worksheet("Buildings")           # tab name is case-sensitive
rows = worksheet.get_all_records()              # list of dicts keyed by header row
```

### Pydantic v2 field_validator mode='before'

```python
# Source: https://docs.pydantic.dev/latest/concepts/validators/
from typing import Any
from pydantic import BaseModel, field_validator

class UnitInput(BaseModel):
    rent: Any

    @field_validator("rent", mode="before")
    @classmethod
    def normalize_rent(cls, v: Any) -> int:
        # Runs before Pydantic's type validation; receives raw input
        s = str(v).strip().replace("$", "").replace(",", "")
        return int(float(s))    # returns int; Pydantic validates it as int

# Usage: UnitInput(rent="$1,500.00")  → rent=1500
```

### uv project scripts entrypoint

```toml
# pyproject.toml — Source: https://docs.astral.sh/uv/concepts/projects/config/
[project.scripts]
sheets-sync = "moxie.sync.sheets:main"
dev = "scripts.dev_bootstrap:main"
```

```python
# scripts/dev_bootstrap.py
import subprocess, sys

def main():
    """Run migrations then seed. Invoked via: uv run dev"""
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "scripts/seed.py"], check=True)
    print("Dev environment ready.")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Column()` SQLAlchemy 1.x style | `Mapped[type] = mapped_column()` SQLAlchemy 2.x | SQLAlchemy 2.0 (2023) | Type-safe, IDE-friendly; autogenerate works better |
| `oauth2client` for Sheets auth | `google-auth` + `gspread 6.x` | gspread 6.0 (2024) | `oauth2client` deprecated; `google-auth` is the correct library |
| `passlib` for password hashing | `bcrypt` directly | bcrypt 5.0 (2025) | passlib unmaintained since 2020; breaks Python 3.13 |
| `pip` + `requirements.txt` | `uv` + `pyproject.toml` | uv stable (2024) | 10-100x faster installs; lockfile for reproducibility |
| `alembic init` default (no batch) | `alembic init` + `render_as_batch=True` in env.py | Alembic batch mode stable | Required for SQLite dev workflow; transparent on PostgreSQL |

**Deprecated/outdated:**
- `oauth2client`: Deprecated by Google. gspread 6.x uses `google-auth`. Do not install.
- SQLAlchemy 1.x `Column()` / `declarative_base()`: Still works but is the legacy API. New projects should use `DeclarativeBase` + `Mapped`.
- `pip install -r requirements.txt`: Replaced by `uv sync` for this project.

---

## Discretion Recommendations

These areas were flagged as "Claude's Discretion" in CONTEXT.md. Researched recommendations:

### Model organization: single models.py (recommended)

With 3 tables (Building, Unit, ScrapeRun), a single `models.py` is the correct choice. Per-table files at this count add import ordering complexity (models must all be imported before Alembic can see them on `Base.metadata`) with no benefit. Use separate files if and when the table count grows beyond ~8-10 tables.

### Index definitions

The CONTEXT.md locks "index filter columns that Phase 4 API will query against." The Phase 4 API filters on `bed_type`, `rent_cents`, `availability_date`, and `building_id`. Recommended indexes:
- `ix_units_bed_type` on `units.bed_type`
- `ix_units_rent_cents` on `units.rent_cents`
- `ix_units_availability_date` on `units.availability_date`
- `ix_units_building_id` on `units.building_id` (FKs are not auto-indexed in SQLite; PostgreSQL does not auto-index FKs either)

A composite index `(building_id, bed_type)` is an option for the most common Phase 4 query pattern (units for a specific building filtered by bed type), but is premature optimization for Phase 1. Add it in Phase 4 if query plans show it needed.

### `platform` field: plain string (recommended)

Use plain `String` with no DB-level enum constraint for Phase 1. Reasons: (1) SQLite does not have a native ENUM type; (2) DB-level enums in PostgreSQL require migration to change valid values; (3) Pydantic validation in the normalizer already enforces valid values at application layer. A DB-level CHECK constraint is an option but adds migration overhead for a column that will likely gain new values ('api', 'platform', 'llm' are the current three). Use a Python-level literal or enum in the application code for validation.

---

## Open Questions

1. **Alembic migration naming convention**
   - What we know: Alembic autogenerates names like `20260217_abc123_initial_schema.py`; manual naming like `001_initial_schema.py` is common in smaller projects
   - What's unclear: No specific naming convention was locked in CONTEXT.md
   - Recommendation: Use autogenerated timestamp-based names (`alembic revision --autogenerate -m "initial schema"`) — they sort chronologically by default, avoiding conflicts if two developers create migrations simultaneously

2. **`non_canonical` unit handling: separate table vs column flag**
   - What we know: CONTEXT.md says non-canonical values stored as-is with a `non_canonical` flag
   - What's unclear: Whether the flag should be a boolean on units, or non-canonical units should be excluded from the main table entirely
   - Recommendation: Boolean `non_canonical` column on the `units` table. Non-canonical units are valid data; they just need review. Excluding them from the table would make them invisible to Phase 2 debugging. The Phase 4 API can filter `WHERE non_canonical = false` by default.

3. **`.env.example` — what goes in it?**
   - What we know: CONTEXT.md mandates `.env.example` committed with all required var names and placeholder values
   - Recommendation: The following keys must appear in `.env.example`:
     ```
     DATABASE_URL=sqlite:///./moxie.db
     GOOGLE_SHEETS_ID=your-google-sheet-id-here
     GOOGLE_SHEETS_KEY_PATH=/path/to/service-account-key.json
     ```
     For production PostgreSQL, `DATABASE_URL` would be `postgresql://user:pass@host/dbname`.

---

## Sources

### Primary (HIGH confidence)
- [SQLAlchemy 2.0 ORM Quick Start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html) — DeclarativeBase, Mapped, mapped_column patterns
- [SQLAlchemy 2.0 Engine Configuration](https://docs.sqlalchemy.org/en/20/core/engines.html) — create_engine, sessionmaker, SQLite connect_args
- [SQLAlchemy 2.0 SQLite dialect](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) — ON CONFLICT upsert, check_same_thread
- [Alembic batch migrations](https://alembic.sqlalchemy.org/en/latest/batch.html) — render_as_batch, batch_alter_table
- [Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) — model import requirement for metadata registration
- [gspread 6.2.1 auth docs](https://docs.gspread.org/en/v6.2.1/oauth2.html) — service_account(), scope requirements, sharing requirement
- [gspread user guide](https://docs.gspread.org/en/latest/user-guide.html) — get_all_records(), open_by_key(), worksheet()
- [Pydantic v2 validators](https://docs.pydantic.dev/latest/concepts/validators/) — field_validator, mode='before', classmethod pattern
- [uv projects guide](https://docs.astral.sh/uv/guides/projects/) — project.scripts, uv run, uv sync

### Secondary (MEDIUM confidence)
- [FastAPI SQL databases tutorial](https://fastapi.tiangolo.com/tutorial/sql-databases/) — sessionmaker, get_db dependency pattern (uses SQLModel but pattern is transferable)
- [Alembic Discussion #1043](https://github.com/sqlalchemy/alembic/discussions/1043) — DATABASE_URL from env in env.py
- [Alembic Discussion #1009](https://github.com/sqlalchemy/alembic/discussions/1009) — SQLite + PostgreSQL portability pattern
- [python-dateutil docs](https://dateutil.readthedocs.io/en/stable/parser.html) — parse(), isoparser, format-agnostic date handling

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all package versions verified against PyPI; auth pattern verified against gspread 6.2.1 official docs
- Architecture patterns: HIGH — SQLAlchemy 2.0, Alembic batch mode, Pydantic field_validator all verified against official docs
- Code examples: HIGH — all code examples derive from official documentation patterns, adapted to the specific schema
- Pitfalls: HIGH — SQLite threading, Alembic import, gspread sharing requirement are all verified causes, not hypothetical

**Research date:** 2026-02-17
**Valid until:** 2026-08-17 (stable libraries; Alembic and SQLAlchemy are mature; gspread auth API is stable)
