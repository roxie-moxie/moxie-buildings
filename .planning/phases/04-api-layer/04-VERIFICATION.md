---
phase: 04-api-layer
verified: 2026-02-21T00:00:00Z
status: passed
score: 30/30 must-haves verified
re_verification: false
---

# Phase 04: API Layer Verification Report

**Phase Goal:** Authenticated FastAPI endpoints expose unit search with all filter parameters, admin account management, and admin scrape controls — fully testable against real database data from Phase 3 batch runs
**Verified:** 2026-02-21
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

Must-haves were drawn from all three plan frontmatter blocks (04-01, 04-02, 04-03).

#### Plan 04-01 Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A User row with role='admin' can be created via the create-admin CLI command | VERIFIED | `scripts/create_admin.py` creates User with `role="admin"`, hash_password called, IntegrityError handled |
| 2 | Passwords are hashed with Argon2 and never stored in plaintext | VERIFIED | `auth.py`: `PasswordHash.recommended()` (Argon2 by default); password_hash field in User model |
| 3 | A JWT can be created from a user ID and decoded back to that same user ID | VERIFIED | `create_access_token(user_id)` encodes `{"sub": str(user_id)}`; `decode_token()` returns `int(sub)` |
| 4 | An expired JWT is rejected on decode | VERIFIED | `decode_token()` uses `jwt.decode()` which raises `InvalidTokenError` on expired tokens; test `test_expired_token_returns_401` confirms |
| 5 | The FastAPI app starts with CORS configured from CORS_ORIGINS env var | VERIFIED | `main.py`: `cors_origins = [o.strip() for o in settings.cors_origins.split(",")]`; CORSMiddleware added |
| 6 | get_current_user dependency rejects requests with invalid/expired tokens | VERIFIED | `deps.py` wraps `decode_token()` in try/except, raises 401; test suite confirms |
| 7 | get_current_user dependency rejects requests for inactive users (is_active=False) | VERIFIED | `deps.py`: checks `user is None or not user.is_active`, raises 401; `test_deactivated_user_token_rejected` passes |
| 8 | require_admin dependency rejects non-admin users with 403 | VERIFIED | `deps.py`: `if current_user.role != "admin": raise HTTPException(status_code=403)`; confirmed by 8 separate admin tests |

#### Plan 04-02 Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 9 | An agent can POST /auth/login with email+password and receive a JWT access token | VERIFIED | `routers/auth.py`: `POST /auth/login` verifies password, checks is_active, returns TokenResponse; `test_login_valid_credentials` passes |
| 10 | Invalid credentials return 401, not 500 | VERIFIED | auth router raises HTTPException(401) on bad email or wrong password; `test_login_invalid_email` and `test_login_invalid_password` pass |
| 11 | An inactive account cannot log in (returns 401) | VERIFIED | auth router checks `not user.is_active` after password verify; `test_login_inactive_account` passes |
| 12 | An admin can POST /admin/users to create a new agent account | VERIFIED | `routers/admin.py`: `POST /admin/users` with router-level `Depends(require_admin)`; returns 201 with UserOut; `test_admin_creates_agent` passes |
| 13 | An admin can PATCH /admin/users/{id}/deactivate to disable an agent | VERIFIED | `routers/admin.py`: `PATCH /admin/users/{user_id}/deactivate` sets `is_active=False`; `test_admin_deactivates_agent` passes |
| 14 | A deactivated agent's existing JWT is rejected on the next request | VERIFIED | `get_current_user` reads is_active from DB on every request (not cached in JWT); `test_deactivated_agent_jwt_rejected` passes |
| 15 | An admin can GET /admin/buildings to see all buildings with platform and last_scraped_at | VERIFIED | `routers/admin.py`: `GET /admin/buildings` queries all Buildings ordered by name; BuildingOut includes platform and last_scraped_at; `test_admin_lists_buildings` passes |
| 16 | An admin can POST /admin/rescrape/{building_id} and receive a job_id | VERIFIED | `routers/admin.py`: `POST /admin/rescrape/{building_id}` returns 202 with RescrapeJobOut containing job_id; `test_trigger_rescrape_returns_202` passes |
| 17 | Attempting a second re-scrape on the same building returns 409 | VERIFIED | Checks `building_id in _building_jobs` before proceeding; `test_rescrape_duplicate_returns_409` passes |
| 18 | An admin can GET /admin/rescrape/{job_id} to poll for scrape completion | VERIFIED | `GET /admin/rescrape/{job_id}` looks up `_jobs` dict; `test_poll_rescrape_returns_status` passes |
| 19 | An agent can GET /units with filter params and receive matching units with last_scraped timestamps | VERIFIED | `routers/units.py`: all 5 filter params implemented; `_to_unit_out()` maps `unit.building.last_scraped_at` to `last_scraped`; 15 filter tests pass |
| 20 | Non-admin users receive 403 on all /admin/* endpoints | VERIFIED | Router-level `dependencies=[Depends(require_admin)]` on admin router; 4 role-enforcement tests pass |
| 21 | Unauthenticated requests to protected endpoints return 401 | VERIFIED | HTTPBearer raises 401 for missing/invalid tokens; confirmed by `test_no_token_returns_401` and `test_unauthenticated_returns_401` |

#### Plan 04-03 Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 22 | Test suite proves an agent can log in and access protected endpoints | VERIFIED | `test_login_returns_working_jwt` + `test_login_valid_credentials` pass |
| 23 | Test suite proves admin can create and deactivate agent accounts | VERIFIED | `TestCreateUser` (4 tests) + `TestDeactivateUser` (5 tests) pass |
| 24 | Test suite proves a deactivated user's JWT is rejected | VERIFIED | `test_deactivated_agent_jwt_rejected` passes (login, deactivate via DB, same token rejected) |
| 25 | Test suite proves building list returns real building data | VERIFIED | `test_admin_lists_buildings` seeds 2 buildings, verifies name/url/platform/last_scraped_at in response |
| 26 | Test suite proves re-scrape trigger returns job_id and rejects duplicates | VERIFIED | `test_trigger_rescrape_returns_202` + `test_rescrape_duplicate_returns_409` pass |
| 27 | Test suite proves unit search filters work correctly (beds, rent range, date, neighborhood) | VERIFIED | 11 individual and combined filter tests pass |
| 28 | Test suite proves non-canonical units are excluded from search results | VERIFIED | `test_search_excludes_non_canonical` passes |
| 29 | Test suite proves unauthenticated requests are rejected | VERIFIED | `test_no_token_returns_401` + `test_unauthenticated_returns_401` pass |
| 30 | Test suite proves non-admin users cannot access admin endpoints | VERIFIED | `test_agent_cannot_create_user`, `test_agent_cannot_deactivate`, `test_agent_cannot_list_buildings`, `test_agent_cannot_trigger_rescrape` all pass |

**Score:** 30/30 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/moxie/db/models.py` | User model with all required fields | VERIFIED | `class User` with id, name, email, password_hash, role, is_active, created_at — all present |
| `src/moxie/api/settings.py` | Settings class with secret_key, database_url, cors_origins | VERIFIED | `class Settings(BaseSettings)` with all three fields; `@lru_cache` wrapped `get_settings()` |
| `src/moxie/api/auth.py` | JWT and password hashing helpers | VERIFIED | Exports: `create_access_token`, `decode_token`, `hash_password`, `verify_password` — all present and substantive |
| `src/moxie/api/deps.py` | FastAPI dependency chain for auth | VERIFIED | `get_current_user` and `require_admin` both present and fully implemented |
| `src/moxie/api/main.py` | FastAPI app factory with CORS middleware | VERIFIED | `create_app()` with CORSMiddleware; all 3 routers mounted; module-level `app` for uvicorn |
| `scripts/create_admin.py` | CLI to bootstrap first admin user | VERIFIED | argparse with --email, --password, --name; hashes password; handles IntegrityError |
| `src/moxie/api/routers/auth.py` | POST /auth/login endpoint | VERIFIED | `router.post("/login", response_model=TokenResponse)` with full logic |
| `src/moxie/api/routers/admin.py` | Admin CRUD + buildings + re-scrape endpoints | VERIFIED | 6 endpoints; router-level require_admin; asyncio.to_thread pattern; _jobs/_building_jobs tracking |
| `src/moxie/api/routers/units.py` | GET /units search endpoint with filters | VERIFIED | All 5 filters; Unit.join(Building); non_canonical filter; _to_unit_out() helper |
| `src/moxie/api/schemas/auth.py` | LoginRequest and TokenResponse models | VERIFIED | Both classes present |
| `src/moxie/api/schemas/admin.py` | UserCreate, UserOut, BuildingOut, RescrapeJobOut models | VERIFIED | All 4 classes present with correct fields |
| `src/moxie/api/schemas/units.py` | UnitOut and UnitsResponse models | VERIFIED | Both present; UnitOut has building_name, building_url, neighborhood, last_scraped |
| `alembic/versions/b89cce9ed1af_add_users_table.py` | Alembic migration for users table | VERIFIED | File exists; `alembic current` shows b89cce9ed1af (head) |
| `tests/api/conftest.py` | Test fixtures with in-memory SQLite and dependency override | VERIFIED | `dependency_overrides[get_db]`; `Base.metadata.create_all`; all fixture helpers present |
| `tests/api/test_auth.py` | Login endpoint tests | VERIFIED | 9 tests, all passing; 81 lines |
| `tests/api/test_admin.py` | Admin endpoint tests | VERIFIED | 12 tests, all passing; 136 lines |
| `tests/api/test_units.py` | Unit search endpoint tests | VERIFIED | 21 tests (15 unit search + 6 re-scrape), all passing; 328 lines |

---

### Key Link Verification

#### Plan 04-01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/moxie/api/deps.py` | `src/moxie/api/auth.py` | `decode_token` call in `get_current_user` | WIRED | Line 19: `user_id = decode_token(token)` |
| `src/moxie/api/deps.py` | `src/moxie/db/models.py` | User lookup by ID from decoded JWT | WIRED | Line 26: `user = db.get(User, user_id)` |
| `src/moxie/api/auth.py` | `src/moxie/api/settings.py` | SECRET_KEY for JWT signing | WIRED | `settings = get_settings()` in both `create_access_token` and `decode_token` |
| `scripts/create_admin.py` | `src/moxie/api/auth.py` | `hash_password` for admin password | WIRED | Line 11: `from moxie.api.auth import hash_password`; used in User construction |

#### Plan 04-02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/moxie/api/routers/auth.py` | `src/moxie/api/auth.py` | `verify_password` + `create_access_token` on login | WIRED | Line 4: imports both; both called in login handler |
| `src/moxie/api/routers/admin.py` | `src/moxie/api/deps.py` | Router-level `dependencies=[Depends(require_admin)]` | WIRED | Line 16-20: `router = APIRouter(..., dependencies=[Depends(require_admin)])` |
| `src/moxie/api/routers/admin.py` | `src/moxie/scheduler/runner.py` | `asyncio.to_thread(scrape_one_building, ...)` for re-scrape | WIRED | `_run_scrape_job` coroutine: local import + `await asyncio.to_thread(scrape_one_building, ...)` |
| `src/moxie/api/routers/units.py` | `src/moxie/db/models.py` | `Unit.join(Building)` query for last_scraped_at | WIRED | Line 55-58: `db.query(Unit).join(Building)`; `_to_unit_out` maps `unit.building.last_scraped_at` |
| `src/moxie/api/main.py` | `src/moxie/api/routers/` | `app.include_router` for all 3 routers | WIRED | Lines 37-39: all three `include_router` calls present |

#### Plan 04-03 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/api/conftest.py` | `src/moxie/api/main.py` | `TestClient(app)` with dependency override | WIRED | Line 91: `app.dependency_overrides[get_db] = override_get_db` |
| `tests/api/conftest.py` | `src/moxie/db/models.py` | `Base.metadata.create_all` for in-memory test DB | WIRED | Line 72: `Base.metadata.create_all(engine)` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AGENT-01 | 04-01, 04-02, 04-03 | Agent can log in with credentials created by an admin | SATISFIED | Full login flow + GET /units with auth enforced; 42 tests prove end-to-end |
| ADMIN-01 | 04-01, 04-02, 04-03 | Admin can create new agent accounts | SATISFIED | `POST /admin/users` returns 201; duplicate email returns 409; 4 tests cover all cases |
| ADMIN-02 | 04-01, 04-02, 04-03 | Admin can disable or deactivate agent accounts | SATISFIED | `PATCH /admin/users/{id}/deactivate`; deactivated JWT rejected immediately; 5 tests |
| ADMIN-03 | 04-02, 04-03 | Admin can view full building list | SATISFIED | `GET /admin/buildings` returns all buildings ordered by name with platform and last_scraped_at; 3 tests |
| ADMIN-04 | 04-02, 04-03 | Admin can manually trigger re-scrape and see when it completes | SATISFIED | `POST /admin/rescrape/{id}` (202, 409 conflict) + `GET /admin/rescrape/{job_id}` (poll); 6 tests |

No orphaned requirements — all 5 requirement IDs (AGENT-01, ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04) appear in plan frontmatter and are implemented.

REQUIREMENTS.md traceability table marks all 5 as complete at Phase 4.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/moxie/api/settings.py` | 7 | `secret_key: str = "change-me-in-production"` | Info | Default secret key is short (23 bytes); PyJWT warns during tests. No blocker — production deployment must set SECRET_KEY env var. Expected for internal tool. |

No stubs, no placeholder implementations, no empty handlers, no TODO/FIXME/HACK comments in any implemented file.

---

### Human Verification Required

None — all behaviors are verifiable programmatically. The 42-test suite covers every requirement end-to-end via HTTP request-response cycle. The phase goal is fully verified by tests.

**One note for deployment context (not a test gap):**

The `create-admin` CLI entry point (`uv run create-admin ...`) does not register as an `.exe` script due to the locked `scrape-all.exe` process preventing `uv sync`. The script works correctly via `uv run python scripts/create_admin.py`. This will auto-register on the next successful `uv sync`. This is a known deviation documented in 04-01-SUMMARY.md.

---

### Gaps Summary

No gaps. All 30 must-haves from all three plans are verified.

---

## Test Execution Summary

```
42 passed, 71 warnings in 4.07s
```

All 42 API integration tests pass against in-memory SQLite with per-test isolation:
- 9 auth tests (`test_auth.py`)
- 12 admin tests (`test_admin.py`)
- 21 unit search + re-scrape tests (`test_units.py`)

The warning about HMAC key length (23 bytes, minimum recommended 32) is from the default `secret_key = "change-me-in-production"` used in tests. This is expected and not a blocker.

---

## Committed Artifacts

| Commit | Description |
|--------|-------------|
| 819fc70 | feat(04-01): add FastAPI deps, User model, and users table migration |
| f9e8101 | feat(04-01): API scaffold -- settings, auth, deps, app factory, create-admin CLI |
| 22d0e2b | feat(04-02): auth login router + admin router (user CRUD, buildings, re-scrape) + schemas |
| eb3fe99 | feat(04-02): unit search router + schemas + wire all routers into app |
| 2ec2f7b | test(04-03): add conftest, auth, and admin endpoint tests |
| db01328 | test(04-03): add unit search and re-scrape endpoint tests |

---

_Verified: 2026-02-21_
_Verifier: Claude (gsd-verifier)_
