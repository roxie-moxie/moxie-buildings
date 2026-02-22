# Phase 6: Fix Data Pipeline Bugs - Research

**Researched:** 2026-02-21
**Domain:** Python data pipeline bug fixes — normalizer/API contract alignment, failure-handling unification
**Confidence:** HIGH (all findings from direct source inspection; no external dependencies involved)

---

## Summary

Phase 6 fixes two precisely-located bugs surfaced by the v1.0 audit. Both are integration mismatches — places where two modules that should agree on a contract do not. No new dependencies are required; the fixes are pure Python code changes within existing files.

**Bug 1 — "Available Now" filter mismatch (AGENT-01):** The normalizer converts any "Available Now" input to today's YYYY-MM-DD date before storing it. The API filter at `api/routers/units.py` then checks `Unit.availability_date == "Available Now"`, which is a dead condition — that string is never in the DB. Units that were actually available immediately are returned by a no-filter query but silently excluded from any `available_before` date-filtered search. The fix is a one-line change to the API filter: replace the `== "Available Now"` condition with `<= available_before` (which already covers them, since today's date is always <= any reasonable future cutoff), or more explicitly, add `<= today` as the retained-units condition.

**Bug 2 — Dual failure-handling divergence (INFRA-03):** `save_scrape_result()` in `scrapers/base.py` retains existing units on failure (the original INFRA-03 contract). `scrape_one_building()` in `scheduler/runner.py` deletes units on failure (a Phase 3 user decision). The `validate-building` CLI and `scrape.py --save` use `save_scrape_result()` (retain). The batch runner uses `scrape_one_building()` (clear). Same scraper failure, two different DB states, depending on which entry point triggered the scrape. The success criteria require the retain-and-stale behavior to win: units retained, building marked stale.

**Primary recommendation:** Fix the API filter with a targeted SQLAlchemy condition; fix the runner by calling `save_scrape_result(scrape_succeeded=False)` in the exception handler instead of manually deleting units. Add regression tests for both.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGENT-01 | Agent can filter units by availability date ("available on or before" a selected date) | Bug 1 fix: aligning the API `available_before` filter so "Available Now" units (stored as today's YYYY-MM-DD) are correctly included in date-filtered searches |
| INFRA-03 | On scrape failure, last known unit data is retained and the building is marked as stale | Bug 2 fix: replacing `runner.py`'s clear-on-failure block with a call to `save_scrape_result(scrape_succeeded=False)`, which implements retain-and-stale |
</phase_requirements>

---

## Standard Stack

No new libraries. All fixes use existing project dependencies.

### Core (existing — no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | Already installed | ORM — used for the API filter query | Project ORM; fix is a query change |
| pytest | Already installed | Test framework | Existing test suite pattern |
| FastAPI TestClient | Already installed | API integration tests | Used in `tests/api/` already |

### Supporting (existing)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy `or_`, `func` | stdlib of SQLAlchemy | Building the corrected OR condition | Fix the filter logic in `units.py` |
| `datetime.date.today()` | Python stdlib | Compute today's date for comparison | Optional explicit form of the filter |

**Installation:** None required.

---

## Architecture Patterns

### Recommended Project Structure

No new files required. Changes are confined to:

```
src/moxie/
├── api/routers/units.py         # Bug 1 fix: available_before filter condition
├── scheduler/runner.py          # Bug 2 fix: exception handler calls save_scrape_result()
tests/
├── api/test_units.py            # Regression test for Bug 1
└── test_save_scrape_result.py   # Already tests save_scrape_result; may need runner test
```

One new test file is appropriate for Bug 2's E2E verification:
```
tests/
└── test_runner_failure.py       # E2E: trigger failure via runner, assert retain+stale
```

### Pattern 1: Bug 1 Fix — Correcting the available_before Filter

**What:** The existing filter has a dead `Unit.availability_date == "Available Now"` branch. Since the normalizer converts "Available Now" to today's YYYY-MM-DD, the fix is to replace that branch with a date comparison that covers "Available Now" units (stored dates that are <= the cutoff).

**Current broken code** (`api/routers/units.py`, lines 70-78):
```python
if available_before is not None:
    from sqlalchemy import or_
    query = query.filter(
        or_(
            Unit.availability_date == "Available Now",  # DEAD: normalizer never stores this
            Unit.availability_date <= available_before,
        )
    )
```

**Fixed code — Option A (simplest, correct because today <= available_before for any future date):**
```python
if available_before is not None:
    query = query.filter(Unit.availability_date <= available_before)
```

**Fixed code — Option B (explicit, makes intent clear if available_before could equal today):**
```python
if available_before is not None:
    from datetime import date
    from sqlalchemy import or_
    today_str = date.today().strftime("%Y-%m-%d")
    query = query.filter(
        or_(
            Unit.availability_date <= today_str,          # captures "available now" units
            Unit.availability_date <= available_before,   # captured by the simpler form below
        )
    )
    # simplifies to: Unit.availability_date <= available_before
    # since today_str <= available_before for any valid future cutoff
```

**Verdict:** Option A is correct and sufficient. The normalizer stores today's date for "Available Now" units. If an agent queries `available_before=2026-03-15`, today's date (2026-02-21) is <= 2026-03-15, so those units are included automatically. The `or_()` is not needed.

**Caution:** Verify that `available_before` is always a future or same-day date in practice. If an agent passes yesterday's date, they'd miss units that became available today (normalized to today). This is an acceptable edge case — the existing test (`test_available_now_included_with_date_filter`) uses `available_before=2026-03-01` against today 2026-02-21, so the simple `<=` comparison works.

**When to use:** Single-condition filter is always simpler and avoids the `or_()` import.

### Pattern 2: Bug 2 Fix — Unifying Failure Handling in runner.py

**What:** `scrape_one_building()` in `runner.py` has its own failure-handling block that manually deletes units and sets building status. This duplicates (and contradicts) `save_scrape_result()`. The fix is to replace the manual block with a call to `save_scrape_result(scrape_succeeded=False, error_message=error_msg)`.

**Current broken code** (`scheduler/runner.py`, lines 97-120, in the `except Exception` block):
```python
except Exception as e:
    db.rollback()
    error_msg = f"[{type(e).__name__}] {str(e)[:500]}"
    result["error"] = error_msg

    # Clear-on-failure: delete units (user decision — stale data is NOT real data)
    try:
        building = db.get(Building, building_id)
        if building:
            db.query(Unit).filter(Unit.building_id == building.id).delete()  # BUG: clears units
            building.last_scrape_status = "failed"
            building.last_scraped_at = now
            db.add(ScrapeRun(
                building_id=building.id,
                run_at=now,
                status="failed",
                unit_count=0,
                error_message=error_msg[:1000],
            ))
            db.commit()
    except Exception:
        logger.error(f"Failed to record failure for {building_name}: {e}")
```

**Fixed code:**
```python
except Exception as e:
    db.rollback()
    error_msg = f"[{type(e).__name__}] {str(e)[:500]}"
    result["error"] = error_msg

    # Retain units on failure, mark building stale — delegates to save_scrape_result()
    try:
        building = db.get(Building, building_id)
        if building:
            save_scrape_result(
                db,
                building,
                raw_units=[],
                scrape_succeeded=False,
                error_message=error_msg[:1000],
            )
    except Exception:
        logger.error(f"Failed to record failure for {building_name}: {e}")
```

**Key facts about `save_scrape_result()` on failure path:**
- Does NOT delete existing units (lines 82-84: only sets status and timestamp)
- Sets `building.last_scrape_status = "failed"`
- Sets `building.last_scraped_at = now`
- Does NOT increment `consecutive_zero_count` (correct — errors != zero results)
- Logs a `ScrapeRun` row with `status="failed"`, `unit_count=0`, `error_message=error_msg`
- Calls `db.commit()` internally

**Import requirement:** `save_scrape_result` is already importable from `moxie.scrapers.base` — it is not currently imported in `runner.py`. Add: `from moxie.scrapers.base import save_scrape_result`

**Note on `raw_units` variable scope:** The `raw_units` variable may not be defined when an exception occurs before `mod.scrape()` returns (e.g., import error, building not found). The call to `save_scrape_result(raw_units=[], ...)` is safe because the failure path doesn't use raw_units — pass `[]` explicitly.

### Pattern 3: Test Pattern — Existing Infrastructure to Leverage

**For Bug 1 regression test (`tests/api/test_units.py`):**

The existing `TestUnitSearch.test_available_now_included_with_date_filter` test (line 166) is the key regression test. It seeds a unit with `availability_date="Available Now"` and tests that it appears when filtering. **This test is currently broken** — it seeds the literal string "Available Now" directly into the DB (bypassing the normalizer), so the current dead-branch API filter actually makes it pass. After fixing the API filter, this test will need its seed data updated to reflect the real normalized form (today's YYYY-MM-DD).

**Corrected test approach:**
```python
def test_available_now_included_with_date_filter(self, client, agent_headers, db_session):
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    seed_building_with_units(db_session, "Test Building", "River North", [
        {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000,
         "availability_date": today},        # normalized form of "Available Now"
        {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000,
         "availability_date": "2026-04-01"},  # future unit
    ])
    resp = client.get("/units", params={"available_before": "2026-03-01"}, headers=agent_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["units"][0]["unit_number"] == "101"
```

**For Bug 2 regression test (`tests/test_runner_failure.py`):**

Follow the `test_save_scrape_result.py` pattern — in-memory SQLite, no real scraper calls. Mock `importlib.import_module` to raise an exception, then verify DB state (units retained, `last_scrape_status == "failed"`).

```python
# Skeleton
def test_runner_retains_units_on_failure(db, building):
    # Pre-seed units
    _insert_unit(db, building.id, "EXISTING-1")

    with patch("importlib.import_module", side_effect=RuntimeError("Network timeout")):
        scrape_one_building(building.id, building.name, building.url, "sightmap")

    db.refresh(building)
    unit_count = db.query(Unit).filter(Unit.building_id == building.id).count()
    assert unit_count == 1                              # units retained
    assert building.last_scrape_status == "failed"     # marked stale
```

The E2E verification requirement (trigger failure via both batch runner and CLI, confirm identical DB state) can be covered by:
1. `test_runner_failure.py` — batch runner path (via `scrape_one_building`)
2. Confirming `save_scrape_result(scrape_succeeded=False)` behavior is already tested in `test_save_scrape_result.py::TestSaveFailureRetainsUnits` (7 tests, all passing)

After the fix, both entry points call `save_scrape_result(scrape_succeeded=False)`, so behavior is identical by construction.

### Anti-Patterns to Avoid

- **Do not change the normalizer:** The normalizer converting "Available Now" to today's date is correct behavior. The bug is in the API consumer, not the producer.
- **Do not add a new `stale` flag or DB column:** INFRA-03 says "building is marked stale" — the existing `last_scrape_status = "failed"` is the stale flag. No schema migration needed.
- **Do not remove the `scrape_succeeded` parameter from `save_scrape_result()`:** The `validate-building` CLI calls it with `scrape_succeeded=True` unconditionally even after scraper errors propagate. That is a pre-existing issue handled by the CLI's own `except Exception` block (which exits rather than saving). Do not change that behavior here.
- **Do not refactor `runner.py` beyond the failure block:** The success path in `runner.py` is correct and handles its own normalization loop. Only the `except Exception` block needs to change.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Available Now" date comparison | Custom date parsing in the filter | Simple `<=` SQLAlchemy comparison | The normalizer already produced YYYY-MM-DD; string comparison on ISO dates is lexicographically correct |
| Failure-state recording | Custom unit-delete + ScrapeRun insert in runner.py | `save_scrape_result(scrape_succeeded=False)` | Already implemented, tested (7 tests), and correct |

**Key insight:** Both bugs are solved by removing code, not adding it. The infrastructure already exists and is correct; it just isn't being used consistently.

---

## Common Pitfalls

### Pitfall 1: Updating the Wrong Side of the Mismatch
**What goes wrong:** Changing the normalizer to store "Available Now" literally instead of today's date.
**Why it happens:** "Fix it at the source" instinct. But the normalizer is correctly converting an unstructured string to a structured date so the DB column stays uniform.
**How to avoid:** Fix the consumer (API filter), not the producer (normalizer). The normalizer's contract is correct.
**Warning signs:** If you find yourself touching `normalizer.py`'s `normalize_date` method, stop.

### Pitfall 2: Breaking the Existing test_available_now_included_with_date_filter Test
**What goes wrong:** After fixing the API filter, the existing test still passes if it seeds `availability_date="Available Now"` literally — because the filter `<= available_before` still matches no rows when the string "Available Now" is compared to a date string lexicographically (strings starting with "A" sort before "2026-...").
**Why it happens:** The test seeds data that bypasses the normalizer, creating a subtle false-positive.
**How to avoid:** Update the test seed data to use today's YYYY-MM-DD to match what the normalizer actually produces. Run the updated test against both the old and new API filter to confirm it fails before fix and passes after.
**Warning signs:** Test passes with both the broken and fixed filter.

### Pitfall 3: Scope Creep — runner.py Success Path
**What goes wrong:** While fixing the failure handler in `runner.py`, also refactoring the success path to call `save_scrape_result()`.
**Why it happens:** The success path in `runner.py` duplicates some `save_scrape_result()` logic too. It's tempting to unify everything.
**How to avoid:** Phase 6 requirements are AGENT-01 and INFRA-03 only. The success path duplication is tech debt but not a bug — leave it for Phase 7.
**Warning signs:** Touching lines 58-95 of `runner.py` (the success branch).

### Pitfall 4: Missing Import in runner.py
**What goes wrong:** The fix adds a `save_scrape_result()` call but the function is not imported.
**Why it happens:** `runner.py` currently imports from `moxie.scrapers.registry` and `moxie.normalizer` but not from `moxie.scrapers.base`.
**How to avoid:** Add `from moxie.scrapers.base import save_scrape_result` to `runner.py` imports.
**Warning signs:** `NameError: name 'save_scrape_result' is not defined` at runtime.

### Pitfall 5: raw_units NameError in Exception Handler
**What goes wrong:** If the exception is raised before `raw_units` is assigned (e.g., during `importlib.import_module()`), referencing `raw_units` in the except block causes a `NameError`.
**Why it happens:** The except block for Bug 2 passes `raw_units=[]` explicitly, so this is safe — but if you try to pass the actual `raw_units` variable, it may be undefined.
**How to avoid:** Always pass `raw_units=[]` in the failure path of `save_scrape_result()`. The failure path ignores raw_units entirely (it doesn't insert any units).
**Warning signs:** `NameError: name 'raw_units' is not defined` in edge-case failure tests.

---

## Code Examples

### Bug 1 Fix — units.py available_before filter

```python
# File: src/moxie/api/routers/units.py
# Lines 70-78 — BEFORE (broken):
if available_before is not None:
    from sqlalchemy import or_
    query = query.filter(
        or_(
            Unit.availability_date == "Available Now",  # dead condition
            Unit.availability_date <= available_before,
        )
    )

# AFTER (fixed):
if available_before is not None:
    query = query.filter(Unit.availability_date <= available_before)
```

The `or_` import can be removed entirely from this function. The `from sqlalchemy import or_` line at the top of the file should be checked for other uses; if this was its only use, remove it.

### Bug 2 Fix — runner.py exception handler

```python
# File: src/moxie/scheduler/runner.py
# Add to imports at top:
from moxie.scrapers.base import save_scrape_result

# Lines 97-120 — BEFORE (broken, clears units):
except Exception as e:
    db.rollback()
    error_msg = f"[{type(e).__name__}] {str(e)[:500]}"
    result["error"] = error_msg

    try:
        building = db.get(Building, building_id)
        if building:
            db.query(Unit).filter(Unit.building_id == building.id).delete()
            building.last_scrape_status = "failed"
            building.last_scraped_at = now
            db.add(ScrapeRun(
                building_id=building.id,
                run_at=now,
                status="failed",
                unit_count=0,
                error_message=error_msg[:1000],
            ))
            db.commit()
    except Exception:
        logger.error(f"Failed to record failure for {building_name}: {e}")

# AFTER (fixed, retains units):
except Exception as e:
    db.rollback()
    error_msg = f"[{type(e).__name__}] {str(e)[:500]}"
    result["error"] = error_msg

    try:
        building = db.get(Building, building_id)
        if building:
            save_scrape_result(
                db,
                building,
                raw_units=[],
                scrape_succeeded=False,
                error_message=error_msg[:1000],
            )
    except Exception:
        logger.error(f"Failed to record failure for {building_name}: {e}")
```

Note: `save_scrape_result()` calls `db.commit()` internally, so no explicit `db.commit()` is needed after.

### Bug 2 Regression Test Skeleton

```python
# File: tests/test_runner_failure.py
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from moxie.db.models import Base, Building, Unit
from moxie.scheduler.runner import scrape_one_building


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def building(db):
    from datetime import datetime, timezone
    b = Building(
        name="Test Building",
        url="https://test.com",
        platform="sightmap",
        last_scrape_status="success",
        consecutive_zero_count=0,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def _insert_unit(db, building_id, unit_number="KEEP-1"):
    from datetime import datetime, timezone
    u = Unit(
        building_id=building_id,
        unit_number=unit_number,
        bed_type="1BR",
        non_canonical=False,
        rent_cents=200000,
        availability_date="2026-03-01",
        scrape_run_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    return u


class TestRunnerFailureHandling:
    def test_units_retained_on_scraper_exception(self, db, building):
        """After a scraper error, pre-existing units are NOT deleted."""
        _insert_unit(db, building.id, "KEEP-1")

        with patch("moxie.scrapers.registry.PLATFORM_SCRAPERS",
                   {"sightmap": "moxie.scrapers.tier2.sightmap"}), \
             patch("importlib.import_module", side_effect=RuntimeError("Network timeout")):
            scrape_one_building(building.id, building.name, building.url, "sightmap")

        db.refresh(building)
        count = db.query(Unit).filter(Unit.building_id == building.id).count()
        assert count == 1
        assert building.last_scrape_status == "failed"

    def test_building_marked_stale_on_failure(self, db, building):
        """Building last_scrape_status='failed' after scraper error."""
        with patch("importlib.import_module", side_effect=ConnectionError("Timeout")):
            scrape_one_building(building.id, building.name, building.url, "sightmap")

        db.refresh(building)
        assert building.last_scrape_status == "failed"
        assert building.last_scraped_at is not None

    def test_scrape_run_logged_on_failure(self, db, building):
        """ScrapeRun is written with status='failed' after error."""
        from moxie.db.models import ScrapeRun
        with patch("importlib.import_module", side_effect=RuntimeError("Error")):
            scrape_one_building(building.id, building.name, building.url, "sightmap")

        run = db.query(ScrapeRun).filter(ScrapeRun.building_id == building.id).first()
        assert run is not None
        assert run.status == "failed"
        assert run.unit_count == 0
```

**Mock strategy note:** The simplest way to trigger the failure path in `runner.py` is to mock `importlib.import_module` to raise. Alternatively, mock the scraper module's `scrape` function to raise. Both paths land in the `except Exception` block.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `or_(availability_date == "Available Now", availability_date <= cutoff)` | `availability_date <= cutoff` | Phase 6 fix | Removes dead branch; filter now works correctly |
| Manual delete + ScrapeRun insert in runner.py exception handler | `save_scrape_result(scrape_succeeded=False)` | Phase 6 fix | Single source of truth for failure handling |

**Deprecated/outdated after this phase:**
- The `Unit.availability_date == "Available Now"` branch in `units.py`: dead code, removed
- Manual unit deletion in `runner.py` except block: replaced by `save_scrape_result()`

---

## Open Questions

1. **Should `validate-building` CLI also call `save_scrape_result(scrape_succeeded=False)` on exception?**
   - What we know: `push_availability.py main()` catches `Exception` and calls `sys.exit(1)` — it does NOT save a failure record. So a failed `validate-building` run leaves the DB unchanged.
   - What's unclear: Is this intentional? The CLI is a development tool, not production — so not recording failure state is arguably fine.
   - Recommendation: Leave as-is for Phase 6. The success criteria only specify batch runner and CLI matching behavior. The `validate-building` tool is a dev validation workflow, not a production path. Phase 6 success criteria require batch runner and CLI (`scrape --save`) to be identical; `validate-building` is separate.

2. **Does `scrape.py --save` also diverge from INFRA-03?**
   - What we know: `scrape.py main()` calls `save_scrape_result(db, building, raw_units, scrape_succeeded=True)` on success, but the outer `except Exception` block prints an error and exits without calling `save_scrape_result(scrape_succeeded=False)`. Pre-existing units are neither cleared nor updated.
   - What's unclear: Is the `scrape` CLI entry point considered a "production" path that needs INFRA-03 compliance?
   - Recommendation: The success criteria say "batch runner or CLI" — interpret CLI as `validate-building` and `scrape --save` both. However, since `scrape.py` without `--save` is a dry-run tool, focus Phase 6 fixes on `runner.py`. If time allows, add the `save_scrape_result(scrape_succeeded=False)` call to `scrape.py`'s exception handler too.

---

## Sources

### Primary (HIGH confidence)
- Direct source inspection: `src/moxie/api/routers/units.py` (lines 70-78) — confirms dead `"Available Now"` branch
- Direct source inspection: `src/moxie/normalizer.py` (lines 144-147) — confirms "Available Now" normalized to today's YYYY-MM-DD
- Direct source inspection: `src/moxie/scheduler/runner.py` (lines 97-120) — confirms manual clear-on-failure
- Direct source inspection: `src/moxie/scrapers/base.py` (lines 82-84) — confirms retain-on-failure in `save_scrape_result()`
- Direct source inspection: `tests/test_save_scrape_result.py` — 25 passing tests covering `save_scrape_result()` failure path
- Direct source inspection: `tests/api/test_units.py` — existing `test_available_now_included_with_date_filter` reveals current test gap
- `.planning/v1.0-MILESTONE-AUDIT.md` — canonical description of both bugs, audit severity ratings

### Secondary (MEDIUM confidence)
- SQLAlchemy string comparison behavior: ISO 8601 dates (YYYY-MM-DD) sort correctly with lexicographic comparison — this is a well-known SQLite property

---

## Metadata

**Confidence breakdown:**
- Bug identification: HIGH — both bugs directly observed in source code
- Fix approach: HIGH — both fixes are obvious one-for-one replacements with existing correct infrastructure
- Test strategy: HIGH — existing test patterns in `test_save_scrape_result.py` and `tests/api/conftest.py` are directly reusable
- Side effects: HIGH — fixes are strictly subtractive (removing dead code, replacing manual logic with existing function)

**Research date:** 2026-02-21
**Valid until:** Until `units.py`, `runner.py`, or `base.py` are significantly refactored (stable)
