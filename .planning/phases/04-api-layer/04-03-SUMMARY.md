---
phase: 04-api-layer
plan: 03
subsystem: testing
tags: [pytest, fastapi, testclient, sqlite, in-memory, jwt, sqlalchemy, dependency-override]

# Dependency graph
requires:
  - phase: 04-02
    provides: "FastAPI app with /auth/login, /admin/*, /units endpoints and schemas"
  - phase: 04-01
    provides: "JWT auth helpers, password hashing, User model, dependency chain"
provides:
  - "42-test integration suite covering all 5 API requirements (AGENT-01, ADMIN-01..04)"
  - "conftest.py with in-memory SQLite per-test isolation via dependency_overrides"
  - "Auth tests: login success/failure, JWT validation, expired/deactivated user rejection"
  - "Admin tests: user CRUD, deactivation lifecycle, building list, role enforcement"
  - "Unit search tests: all filter combinations, non-canonical exclusion, response shape"
  - "Re-scrape tests: trigger/poll lifecycle, duplicate 409, mock scraper pattern"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "StaticPool in-memory SQLite engine for test isolation without file I/O"
    - "app.dependency_overrides[get_db] for injecting test DB into FastAPI app"
    - "Base.metadata.create_all/drop_all per test for clean schema"
    - "Patching moxie.scheduler.runner.scrape_one_building (not admin router) because of local import pattern"
    - "_building_jobs dict manipulation to simulate in-progress job for 409 test"

key-files:
  created:
    - tests/api/__init__.py
    - tests/api/conftest.py
    - tests/api/test_auth.py
    - tests/api/test_admin.py
    - tests/api/test_units.py
  modified: []

key-decisions:
  - "Patched moxie.scheduler.runner.scrape_one_building rather than admin module path — local import inside _run_scrape_job means the name doesn't exist at module level"
  - "FastAPI HTTPBearer returns 401 (not 403) for missing Authorization header in current version — test expectation corrected"
  - "409 duplicate rescrape test uses direct _building_jobs dict injection (not async mock) — async tasks complete before test can trigger duplicate"

patterns-established:
  - "Fixture chain: db_session -> client (dependency override) -> admin_user/agent_user -> admin_headers/agent_headers"
  - "seed_building_with_units() helper: creates building + units in one call, returns Building ORM object"
  - "Pre-existing test failures (test_scraper_appfolio, test_scraper_llm) documented in deferred-items.md, not fixed"

requirements-completed: [AGENT-01, ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04]

# Metrics
duration: 25min
completed: 2026-02-22
---

# Phase 4 Plan 03: API Integration Test Suite Summary

**42-test FastAPI integration suite with in-memory SQLite proving all 5 requirements (AGENT-01, ADMIN-01..04) end-to-end via HTTP request-response cycle**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-02-22T~18:30Z
- **Completed:** 2026-02-22T~18:55Z
- **Tasks:** 2
- **Files modified:** 5 created

## Accomplishments
- Full test conftest with per-test DB isolation via FastAPI dependency override (no file DB, no env required)
- 9 auth tests: login success/failure/inactive, JWT validation, expired token, deactivated user rejection
- 12 admin tests: user creation (201/409/422), deactivation lifecycle, building list with ordering, role enforcement (403)
- 15 unit search tests: all filter params individually and combined, non-canonical exclusion, Available Now date handling
- 6 re-scrape tests: trigger/poll lifecycle, 409 on duplicate, 404 on nonexistent, admin-only access

## Task Commits

Each task was committed atomically:

1. **Task 1: conftest, auth, and admin endpoint tests** - `2ec2f7b` (test)
2. **Task 2: unit search and re-scrape endpoint tests** - `db01328` (test)

**Plan metadata:** (committed below)

## Files Created/Modified
- `tests/api/__init__.py` - Empty package marker
- `tests/api/conftest.py` - DB fixtures, TestClient with dependency override, user/auth helpers
- `tests/api/test_auth.py` - 9 login and JWT protection tests
- `tests/api/test_admin.py` - 12 user management, deactivation, and building list tests
- `tests/api/test_units.py` - 21 unit search filter and re-scrape lifecycle tests

## Decisions Made
- Patched `moxie.scheduler.runner.scrape_one_building` (not `moxie.api.routers.admin.scrape_one_building`) because `_run_scrape_job` uses a local import — the name doesn't exist at the admin module level
- 409 duplicate rescrape tested via direct `_building_jobs` dict injection — async tasks complete near-instantly in TestClient context, making timing-based mocks unreliable
- FastAPI HTTPBearer returns 401 (not 403) for missing Authorization header in current version; test expectation corrected from plan

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected test_no_token_returns_403 expected status code**
- **Found during:** Task 1 (auth tests)
- **Issue:** Plan specified `test_no_token_returns_403` with expected status 403 ("HTTPBearer behavior"), but the current FastAPI/Starlette version returns 401 with `WWW-Authenticate: Bearer` header for missing credentials
- **Fix:** Renamed test to `test_no_token_returns_401` and corrected assertion to `assert resp.status_code == 401`
- **Files modified:** tests/api/test_auth.py
- **Verification:** Test passes; behavior confirmed by direct request inspection
- **Committed in:** 2ec2f7b (Task 1 commit)

**2. [Rule 1 - Bug] Fixed mock patch path for scrape_one_building**
- **Found during:** Task 2 (re-scrape tests)
- **Issue:** `patch("moxie.api.routers.admin.scrape_one_building")` failed with AttributeError — the function is imported inside `_run_scrape_job` (local import to avoid heavy deps at module load), so it doesn't exist at admin module scope
- **Fix:** Changed patch target to `moxie.scheduler.runner.scrape_one_building` — patches at the source before the local import executes
- **Files modified:** tests/api/test_units.py
- **Verification:** All 6 re-scrape tests pass
- **Committed in:** db01328 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs — incorrect test expectations based on actual runtime behavior)
**Impact on plan:** Both fixes required for tests to accurately reflect API behavior. No scope creep.

## Issues Encountered
- Pre-existing test failures discovered (not caused by this plan):
  - `tests/test_scraper_appfolio.py`: ImportError — `_parse_html`/`_fetch_html` removed in quick-5 rewrite
  - `tests/test_scraper_llm.py`: 7 failures — FakeResult mock missing `success` attribute added in quick-5 LLM update
  - Documented in `.planning/phases/04-api-layer/deferred-items.md`; not fixed (out of scope)

## User Setup Required
None - no external service configuration required. Tests run with `uv run pytest tests/api/ -v`.

## Next Phase Readiness
- Phase 4 (API Layer) complete: scaffold (04-01), endpoints (04-02), tests (04-03)
- Phase 5 ready to begin: all 5 API requirements proven by passing tests
- API can be started with `uv run uvicorn moxie.api.main:app --reload`
- Pre-existing test failures in scraper test suite should be fixed before Phase 5 if test health matters

---
*Phase: 04-api-layer*
*Completed: 2026-02-22*
