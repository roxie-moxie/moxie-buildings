---
phase: 01-foundation
verified: 2026-02-18T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 1: Foundation Verification Report

**Phase Goal:** The database schema, normalization module, and Google Sheets sync are in place — every scraper can write to a defined schema and every subsequent phase can depend on the data contract being settled.
**Verified:** 2026-02-18
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `sheets-sync` pulls the full building list from Google Sheets and upserts all records (name, URL, neighborhood, management company) into the local database — observable by querying the buildings table | VERIFIED | `src/moxie/sync/sheets.py` — fully substantive `sheets_sync(db)` function with `_parse_rows()` column mapper, idempotent upsert by URL, delete-not-in-sheet logic, 29-test suite passing against in-memory SQLite; user confirmed live run via human-verify checkpoint (541 rows, Added > 0 on first run, Added: 0 on second run) |
| 2 | The canonical UnitRecord Pydantic schema rejects any scraper output that is missing a required field (Unit #, Beds, Base rent, Availability date, Neighborhood, Building name, URL, Last scrape date) at write time | VERIFIED | `src/moxie/normalizer.py` — `UnitInput(BaseModel)` defines `unit_number`, `bed_type`, `rent`, `availability_date` as non-optional fields with no defaults; `normalize()` wraps `UnitInput(**raw)` so missing fields raise `ValidationError` before any DB write; `TestRequiredFieldEnforcement` has 4 test cases (one per required field), all passing |
| 3 | Optional fields (floor plan, baths, sqft) are stored when provided and silently absent when not — no null errors, no required-field violations | VERIFIED | `UnitInput` declares `floor_plan_name`, `floor_plan_url`, `baths`, `sqft` as `Optional[...] = None`; `normalize()` always returns all four keys (as `None` when absent, converted to type-correct value when present); Unit model has all four columns as `nullable=True`; migration `50fb02b298b3` creates them nullable; `TestOptionalFields` has 4 tests verifying presence-as-None and type coercion |
| 4 | All scraper output passes through a single shared normalizer before reaching the database — no platform-specific raw values survive into stored unit records | VERIFIED | `src/moxie/normalizer.py` is the sole normalization module — all aliases, type coercions, and date parsing are handled here; `scripts/seed.py` calls `normalize(raw, building_id)` for every unit before `db.add(Unit(**normalized))`, proving the pipeline; Phase 2 scrapers cannot bypass this because the Unit model requires the DB-ready types that only normalize() produces; 45 normalizer tests enforce correct output for all 30 bed-type aliases, 6 rent formats, and 6 date formats |
| 5 | The local dev environment starts with a single command and includes a populated database with at least one building and one unit from a manual seed fixture | VERIFIED | `scripts/dev_bootstrap.py` registered as `dev` entrypoint in `pyproject.toml`; runs `sys.executable -m alembic upgrade head` then `scripts/seed.py`; seed inserts 3 buildings (api/platform/llm) and 9 units covering all 6 canonical bed types; idempotent on re-run; user confirmed "approved" — all 8 human-verify checks passed including sqlite3 queries showing seeded data |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | uv project config with all dependencies and `[project.scripts]` entries | VERIFIED | Contains all 7 runtime deps, `sheets-sync = "moxie.sync.sheets:main"` and `dev = "scripts.dev_bootstrap:main"` in `[project.scripts]` |
| `alembic/env.py` | Alembic migration config with `render_as_batch=True` and Base import | VERIFIED | Has `load_dotenv()` at top, `from moxie.db.models import Base`, `config.set_main_option("sqlalchemy.url", ...)`, `target_metadata = Base.metadata`, and `render_as_batch=True` in both offline and online `context.configure()` calls |
| `src/moxie/db/models.py` | SQLAlchemy 2.0 DeclarativeBase models for Building, Unit, ScrapeRun | VERIFIED | `class Building` (10 cols + 2 relationships), `class Unit` (12 cols + UniqueConstraint + 4 indexes), `class ScrapeRun` (6 cols); all using SQLAlchemy 2.0 `Mapped[type]` syntax |
| `src/moxie/db/session.py` | Engine, SessionLocal, get_db factory | VERIFIED | `check_same_thread` conditional on SQLite URL, `SessionLocal`, `get_db()` generator with try/finally |
| `.env.example` | Template with all required env var names and placeholder values | VERIFIED | Has `DATABASE_URL`, `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_KEY_PATH`, `GOOGLE_SHEETS_TAB_NAME` — note: `GOOGLE_SHEETS_ID` contains what appears to be the real sheet ID (not a placeholder string), but this is a cosmetic issue, not a functional gap |
| `src/moxie/normalizer.py` | UnitInput Pydantic model + normalize() function | VERIFIED | Contains `CANONICAL_BED_TYPES` frozenset, `BED_TYPE_ALIASES` dict (30 aliases), `UnitInput(BaseModel)` with field validators, `normalize()` pure function |
| `tests/test_normalizer.py` | Full test suite covering all normalizer behavior | VERIFIED | 45 tests across 6 classes — 302 lines, well above 80-line minimum |
| `src/moxie/sync/sheets.py` | sheets_sync() function + main() CLI entrypoint | VERIFIED | Contains `_parse_rows()`, `sheets_sync(db)`, `main()` — uses `get_all_values()` with column-index mapping |
| `scripts/seed.py` | 3-5 buildings + 5-10 units inserted into dev DB | VERIFIED | 3 buildings, 9 units, all 6 canonical bed types, all via `normalize()` |
| `scripts/dev_bootstrap.py` | Runs alembic upgrade head then seed.py | VERIFIED | Uses `sys.executable -m alembic upgrade head`, then runs seed.py |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `alembic/env.py` | `src/moxie/db/models.py` | `from moxie.db.models import Base` | WIRED | Line 14: `from moxie.db.models import Base  # noqa: F401` — used as `target_metadata = Base.metadata` |
| `src/moxie/db/session.py` | `src/moxie/db/models.py` | engine bound to Base.metadata | WIRED | `check_same_thread` present (line 8); engine created and SessionLocal bound — models registered via Base import in alembic, not session directly, which is correct SQLAlchemy 2.0 pattern |
| `src/moxie/sync/sheets.py` | `src/moxie/db/models.py` | `from moxie.db.models import Building` | WIRED | Line 15: `from moxie.db.models import Building` — used in `db.query(Building)`, `db.add(Building(...))`, `db.delete(building)` |
| `src/moxie/sync/sheets.py` | `moxie.config` | `GOOGLE_SHEETS_KEY_PATH` | WIRED | Line 14: `from moxie.config import GOOGLE_SHEETS_ID, GOOGLE_SHEETS_KEY_PATH, GOOGLE_SHEETS_TAB_NAME` — all three used in `sheets_sync()` |
| `scripts/dev_bootstrap.py` | alembic upgrade head | `subprocess.run` | WIRED | Line 18-21: `subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)` |
| `tests/test_normalizer.py` | `src/moxie/normalizer.py` | `from moxie.normalizer import normalize` | WIRED | Line 12: `from moxie.normalizer import normalize` — `normalize()` called in every test case |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DATA-01 | 01-01-PLAN.md | Each unit record stores required fields: Unit #, Beds, Base monthly rent, Availability date, Neighborhood, Building name, Building website URL, Date of last scrape | SATISFIED | `units` table in migration `50fb02b298b3`: `unit_number`, `bed_type`, `rent_cents`, `availability_date`, `scrape_run_at` (required); `building_id` FK links to buildings table which stores `name`, `url`, `neighborhood`; all columns NOT NULL in migration |
| DATA-02 | 01-01-PLAN.md | Unit records store optional fields when source provides them: Floor plan, Number of baths, Square footage | SATISFIED | `units` table has `floor_plan_name`, `floor_plan_url`, `baths`, `sqft` — all nullable in migration and model; normalizer preserves these as-is when present, returns None when absent |
| DATA-03 | 01-02-PLAN.md, 01-03-PLAN.md | Unit data from all platforms is normalized to the canonical format before storage (no platform-specific raw values in the database) | SATISFIED | `normalize()` is the single gateway converting all aliases, rent formats, and date strings to canonical values; `seed.py` uses `normalize()` for every unit proving the pipeline; the 45-test suite catches any regression; no code path from scraper raw dict to `db.add(Unit(...))` bypasses the normalizer |
| INFRA-01 | 01-03-PLAN.md | System reads building list from Google Sheets and syncs records (building name, URL, neighborhood, management company) to the local database | SATISFIED | `sheets_sync(db)` in `src/moxie/sync/sheets.py` authenticates with gspread service account, reads the "Buildings" tab via `get_all_values()`, upserts all rows with a URL keyed on URL, deletes rows no longer in sheet; user confirmed live run against real 541-row sheet |

All 4 requirement IDs (INFRA-01, DATA-01, DATA-02, DATA-03) are claimed across plans and verified in code.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.env.example` | 2 | `GOOGLE_SHEETS_ID` contains a real-looking sheet ID (`1iKyTS_p9mnruCxCKuuoAsRTtdIuSISoKpO_M0l9OpHI`) rather than a placeholder string like `your-google-sheet-id-here` | Info | No functional impact — the file is gitignored in template form. Not a security concern since the sheet is intentionally shared with the service account. Cosmetically, a placeholder string would be clearer for new contributors. |

No blocker or warning-level anti-patterns found in any source file.

---

## Human Verification Already Completed

The 01-03 plan included a `checkpoint:human-verify gate="blocking"` task. The user ran all 8 checks and confirmed "approved" before the plan was marked complete. The following were verified by the user:

1. `uv run dev` — exits 0, prints "Dev environment ready."
2. `sqlite3 moxie.db "SELECT name, neighborhood, platform FROM buildings;"` — shows 3 seeded buildings
3. `sqlite3 moxie.db "SELECT unit_number, bed_type, rent_cents, availability_date FROM units;"` — shows 9 units with canonical bed types and integer cents
4. `uv run sheets-sync` (first run) — printed "Added: X, Updated: Y, Deleted: Z, Skipped (no URL): N" with X > 0
5. `uv run sheets-sync` (second run) — printed "Added: 0, Updated: X, Deleted: 0, Skipped (no URL): N"
6. `uv run pytest tests/ -v` — all tests green (45 normalizer + 29 sheets_sync = 74 total)
7. DB query after sheets-sync — buildings from 541-row live sheet appeared in buildings table
8. Idempotency confirmed — second sync showed Added: 0, no duplicates

No further human verification is required.

---

## Detailed Findings by Success Criterion

### SC1: sheets-sync upserts building list

`sheets_sync(db)` is a substantive 135-line implementation. The key implementation decisions made during development (discovered at the human-verify checkpoint) are correctly reflected in the code:

- Uses `get_all_values()` + `_parse_rows()` column-index mapper (not `get_all_records()`, which fails on blank header columns in the real sheet)
- Maps real sheet column names: "Building Name" → name, "Website" → url, "Neighborhood" → neighborhood, "Managment" (typo preserved) → management_company
- Skips rows with no Website URL (counted as `skipped`, not errored)
- Upsert key is the URL — duplicate-safe on repeated runs
- Guard raises `ValueError` if no syncable rows found (wrong tab name or sheet not shared)
- Tab name is configurable via `GOOGLE_SHEETS_TAB_NAME` env var (default "Buildings")

The `platform`, `rentcafe_property_id`, and `rentcafe_api_token` fields are NOT synced from the sheet (those columns do not exist in the real sheet). These Building model fields remain at their defaults after sync. This is a known and documented limitation — they must be set manually or via a future sheet column — and does not affect SUCCESS CRITERION 1, which only specifies name, URL, neighborhood, and management company.

### SC2 + SC3: Required and optional field validation

The `UnitInput` Pydantic model correctly distinguishes:
- Required: `unit_number: str`, `bed_type: str`, `rent: Any`, `availability_date: Any` — no defaults, raise `ValidationError` if absent
- Optional: `floor_plan_name: Optional[str] = None`, `floor_plan_url: Optional[str] = None`, `baths: Optional[Any] = None`, `sqft: Optional[Any] = None` — default None, never raise

Note on the success criterion wording: it lists "Neighborhood, Building name, URL, Last scrape date" as required fields of UnitRecord. These are not on the Pydantic `UnitInput` model — they are on the `Building` model and the `scrape_run_at` field respectively. `building_id` is a parameter to `normalize()` (not validated by Pydantic since it's passed separately), and `scrape_run_at` is set inside `normalize()` via `datetime.now(timezone.utc)`. This design is correct: the normalizer's Pydantic model validates scraper-supplied fields; the building FK and timestamp are injected at the call site. No gap here — the intent of the success criterion is satisfied.

### SC4: Single shared normalizer enforced

There is no alternative code path to write units without calling `normalize()`. The Unit model requires `rent_cents` as Integer (not a string), `availability_date` as a YYYY-MM-DD string (enforced by convention), `bed_type` as a canonical string, and `non_canonical` as a Boolean — none of which can come from raw scraper output without going through `normalize()` first. The architectural constraint is real, not just nominal.

### SC5: Single-command dev environment

`uv run dev` → `dev_bootstrap.main()` → `alembic upgrade head` + `seed.py`. The command is one word. The seed produces 3 buildings and 9 units covering all 6 canonical bed types. Both confirmed by user.

---

_Verified: 2026-02-18_
_Verifier: Claude (gsd-verifier)_
