# Phase 4: API Layer - Research

**Researched:** 2026-02-21
**Domain:** FastAPI, JWT auth, SQLAlchemy dependency injection, background job polling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Auth & token behavior**
- JWT access tokens with 8-hour lifetime (one login per work shift)
- No refresh tokens — agents re-login when token expires
- No lockout on failed login — return 401, no attempt tracking
- Check `is_active` on every authenticated request — disabling an account immediately revokes access (existing JWTs rejected)

**Admin bootstrap & role model**
- Single `users` table with a `role` column (admin / agent)
- First admin created via CLI seed command (e.g., `uv run create-admin --email ... --password ...`)
- Single admin expected (just Alex) — no multi-admin promotion flow needed
- Admin is the only role that can access /admin/* endpoints

**Search endpoint design**
- GET /units with query params for all filters (beds, rent_min, rent_max, available_before, neighborhood)
- No pagination — return all matching units in a single response (dataset is ~2-5K units total)
- Each unit in the response includes `last_scraped` timestamp from its building — frontend uses this for green/yellow/red freshness indicator
- Flat error messages: `{"detail": "rent_max must be positive"}` — no per-field breakdown

**Re-scrape workflow**
- Async with polling: POST /admin/rescrape/{building_id} returns a job ID
- Poll GET /admin/rescrape/{job_id} for status
- Completion response includes status + unit count + duration (not full scrape log)
- One re-scrape at a time per building — 409 Conflict if already running
- Admin-only endpoint — agents cannot trigger re-scrapes

**Deployment & infrastructure**
- Hosting decision deferred — build host-agnostic API
- No rate limiting — 7 agents, internal tool, not worth the complexity now
- CORS origins configured via environment variable (CORS_ORIGINS), defaults to localhost

### Claude's Discretion
- Password complexity rules (reasonable defaults for an internal tool)
- Exact API route naming conventions
- Response envelope structure (bare list vs wrapped object)
- JWT signing algorithm and secret management approach
- Re-scrape job storage mechanism (in-memory vs database)

### Deferred Ideas (OUT OF SCOPE)
- **Stale data handling change** — Currently scrapers delete unit data on failure. User wants to change this: keep last successful scrape data on failure, mark building as stale via timestamp, only replace data on success. Reasoning: stale data with a warning is better than no data. Should be addressed before or during Phase 5 when the freshness indicator becomes visible to agents.
- **Rate limiting** — Noted as cheap insurance (60 req/min per user) but deferred. Revisit if the API becomes externally accessible or team grows.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGENT-01 | Agent can log in with credentials created by an admin | JWT auth flow: POST /auth/login → 8-hour JWT → protected routes check `is_active` on every request |
| ADMIN-01 | Admin can create new agent accounts (name, email, password) | POST /admin/users endpoint, admin dependency, pwdlib hashing, Alembic migration for users table |
| ADMIN-02 | Admin can disable or deactivate agent accounts | PATCH /admin/users/{id}/deactivate sets is_active=False; `is_active` checked in get_current_user dependency |
| ADMIN-03 | Admin can view the full building list as synced from Google Sheets | GET /admin/buildings returns existing buildings table (name, url, neighborhood, management_company, platform) |
| ADMIN-04 | Admin can manually trigger a re-scrape for a specific building and see when it completes | POST /admin/rescrape/{building_id} → asyncio.create_task(scrape_one_building(...)) → in-memory job dict → GET /admin/rescrape/{job_id} polls status |
</phase_requirements>

---

## Summary

Phase 4 builds an authenticated FastAPI HTTP layer on top of the existing SQLAlchemy/SQLite backend from Phases 1-3. The primary technical work is: (1) a new `users` table with role-based access, (2) JWT token issuance and validation, (3) a `GET /units` search endpoint that joins units to buildings for the `last_scraped` timestamp, and (4) an async re-scrape trigger with in-memory job polling.

The existing project already uses SQLAlchemy 2.0, Pydantic v2, and `get_db()` as a generator dependency — these are exactly the patterns FastAPI uses natively. The `scrape_one_building()` function in `moxie.scheduler.runner` can be called directly from the re-scrape endpoint, wrapped in `asyncio.create_task()` with a thread executor since it is synchronous and does blocking I/O.

The ecosystem has shifted since late 2024: `python-jose` is abandoned and FastAPI's official docs now recommend `PyJWT`. `passlib` is similarly unmaintained and FastAPI docs now recommend `pwdlib[argon2]`. Both are confirmed via official FastAPI PR activity and the live docs page.

**Primary recommendation:** Use FastAPI + PyJWT + pwdlib[argon2] + pydantic-settings. Add a `users` table via Alembic. Use router-level `dependencies=[Depends(require_admin)]` for all /admin/* routes. Store re-scrape jobs in a module-level dict keyed by UUID — sufficient for one-at-a-time single-building scrapes.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | latest (0.115+) | HTTP framework, routing, dependency injection | Already implied by project; de-facto standard for Python async APIs |
| uvicorn | latest | ASGI server | Standard FastAPI server |
| PyJWT | 2.x | JWT encode/decode | Official FastAPI docs migrated from python-jose to PyJWT (PR #11589, merged 2024) |
| pwdlib[argon2] | latest | Password hashing | Official FastAPI docs migrated from passlib to pwdlib (PR #13917); Argon2 is memory-hard, bcrypt-compatible fallback available |
| pydantic-settings | 2.x | Settings from env vars | Official FastAPI recommendation; already have pydantic>=2.0 |
| python-multipart | latest | Required for form data support | Needed if using OAuth2PasswordRequestForm; even if JSON-only login, include for completeness |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | latest | Async test support | If writing async tests against FastAPI routes |
| httpx | already installed | AsyncClient for tests | TestClient uses requests-like API; AsyncClient needed for async test fixtures |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | python-jose abandoned (last release ~3 years ago); PyJWT is actively maintained, now official FastAPI recommendation |
| pwdlib[argon2] | passlib[bcrypt] | passlib unmaintained; crypt module deprecated in Python 3.12 and removed in 3.13; pwdlib is actively maintained replacement |
| asyncio.create_task + in-memory dict | Celery+Redis | Celery far too heavy for one-at-a-time single-building scrapes; in-memory is fine given single-server deployment |
| Custom JSON login endpoint | OAuth2PasswordRequestForm | Form-data required for OAuth2PasswordRequestForm; JSON body is cleaner for this internal tool and avoids `python-multipart` dependency on the critical path |

**Installation:**
```bash
uv add fastapi uvicorn PyJWT "pwdlib[argon2]" pydantic-settings python-multipart
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/moxie/
├── api/                    # FastAPI application (new)
│   ├── __init__.py
│   ├── main.py             # FastAPI app factory, CORS, router inclusion
│   ├── settings.py         # pydantic-settings BaseSettings (SECRET_KEY, CORS_ORIGINS, etc.)
│   ├── deps.py             # Shared dependencies: get_db, get_current_user, require_admin
│   ├── auth.py             # JWT helpers: create_token, decode_token, hash_password, verify_password
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py         # POST /auth/login
│   │   ├── units.py        # GET /units (agent-accessible)
│   │   └── admin.py        # /admin/* (admin-only)
│   └── schemas/
│       ├── __init__.py
│       ├── auth.py         # LoginRequest, TokenResponse
│       ├── units.py        # UnitOut, UnitsResponse
│       └── admin.py        # UserCreate, UserOut, BuildingOut, RescrapeJobOut
├── db/
│   └── models.py           # Add User model here (alongside Building, Unit, ScrapeRun)
└── ...existing modules...
```

### Pattern 1: JWT Token Issuance and Validation

**What:** Create a signed JWT on login. On every protected request, decode the JWT, look up the user, check `is_active`. The `is_active` check happens at request time (not embedded in the token) — this is the key design decision for immediate account deactivation.

**When to use:** All protected routes.

**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ (updated to PyJWT + pwdlib)
import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()  # Uses Argon2 by default
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8  # User decision: 8-hour shifts

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> int:
    """Raises InvalidTokenError if invalid/expired. Returns user_id."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("sub")
    if user_id is None:
        raise InvalidTokenError("No sub claim")
    return int(user_id)
```

### Pattern 2: Dependency Chain (get_current_user → require_admin)

**What:** FastAPI dependency injection chain. `get_current_user` decodes JWT and checks `is_active`. `require_admin` wraps it and also checks role.

**When to use:** All protected routes. Admin routes use `require_admin` via router-level `dependencies=[]` parameter.

**Example:**
```python
# Source: FastAPI official docs + project patterns
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from moxie.db.models import User
from moxie.db.session import get_db

bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        user_id = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account inactive or not found",
                            headers={"WWW-Authenticate": "Bearer"})
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

### Pattern 3: Router-Level Admin Protection

**What:** Apply `require_admin` to an entire router, not per-endpoint. Cleaner than decorating each route.

**Example:**
```python
# src/moxie/api/routers/admin.py
from fastapi import APIRouter, Depends
from moxie.api.deps import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.get("/buildings")
def list_buildings(db: Session = Depends(get_db)):
    ...  # No need to add Depends(require_admin) here — inherited from router
```

### Pattern 4: Re-scrape with asyncio + In-Memory Job Store

**What:** POST returns a job ID immediately. Background coroutine runs `scrape_one_building()` in a thread (because it's synchronous). GET /admin/rescrape/{job_id} returns status from in-memory dict. 409 if already running.

**Critical caveat:** `scrape_one_building()` in `moxie/scheduler/runner.py` is a synchronous blocking function (uses `time.sleep`, creates its own `SessionLocal`). It MUST be run with `asyncio.get_event_loop().run_in_executor(None, ...)` or `asyncio.to_thread()` — NOT called directly as a coroutine.

**Example:**
```python
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Literal
from moxie.scheduler.runner import scrape_one_building

# Module-level in-memory store: job_id -> status dict
_jobs: dict[str, dict] = {}
# Track active job per building to enforce one-at-a-time
_building_jobs: dict[int, str] = {}  # building_id -> job_id

async def _run_scrape_job(job_id: str, building_id: int, building_name: str,
                           building_url: str, platform: str) -> None:
    """Background coroutine — runs sync scrape_one_building in thread."""
    start = datetime.now(timezone.utc)
    _jobs[job_id]["status"] = "running"
    try:
        result = await asyncio.to_thread(
            scrape_one_building, building_id, building_name, building_url, platform
        )
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        _jobs[job_id].update({
            "status": result["status"],   # "success" or "failed"
            "unit_count": result["unit_count"],
            "error": result.get("error"),
            "duration_seconds": duration,
        })
    finally:
        _building_jobs.pop(building_id, None)

@router.post("/rescrape/{building_id}", status_code=202)
async def trigger_rescrape(building_id: int, db: Session = Depends(get_db)):
    if building_id in _building_jobs:
        raise HTTPException(status_code=409, detail="Scrape already in progress for this building")
    building = db.get(Building, building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "building_id": building_id}
    _building_jobs[building_id] = job_id
    asyncio.create_task(_run_scrape_job(job_id, building.id, building.name, building.url, building.platform or "llm"))
    return {"job_id": job_id}

@router.get("/rescrape/{job_id}")
def get_rescrape_status(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

### Pattern 5: CORS from Environment Variable

```python
# src/moxie/api/main.py
import os
from fastapi.middleware.cors import CORSMiddleware

cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Note:** `allow_credentials=True` requires explicit origins — cannot use `["*"]` with credentials.

### Pattern 6: Units Search with Join to Building

**What:** GET /units queries units table joined to buildings for `last_scraped`. All filter params are optional query params.

```python
@router.get("/units")
def search_units(
    beds: list[str] | None = Query(default=None),
    rent_min: int | None = Query(default=None, ge=0),
    rent_max: int | None = Query(default=None, ge=0),
    available_before: str | None = Query(default=None),  # "YYYY-MM-DD"
    neighborhood: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # require auth
):
    q = db.query(Unit).join(Building)
    if beds:
        q = q.filter(Unit.bed_type.in_(beds))
    if rent_min is not None:
        q = q.filter(Unit.rent_cents >= rent_min * 100)
    if rent_max is not None:
        q = q.filter(Unit.rent_cents <= rent_max * 100)
    if available_before:
        q = q.filter(Unit.availability_date <= available_before)
    if neighborhood:
        q = q.filter(Building.neighborhood.in_(neighborhood))
    units = q.all()
    return [_to_unit_out(u) for u in units]
```

**Note:** `beds` and `neighborhood` as `list[str]` with `Query(default=None)` requires multi-value query params: `?beds=1BR&beds=2BR`. This is standard in FastAPI.

### Pattern 7: pydantic-settings for API Config

```python
# src/moxie/api/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    secret_key: str = "change-me-in-production"
    database_url: str = "sqlite:///./moxie.db"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Pattern 8: FastAPI Testing with DB Override

```python
# tests/api/conftest.py
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from moxie.db.models import Base
from moxie.db.session import get_db
from moxie.api.main import app

SQLALCHEMY_TEST_URL = "sqlite://"
engine = create_engine(SQLALCHEMY_TEST_URL,
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine)

@pytest.fixture
def client():
    Base.metadata.create_all(engine)
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
```

### Anti-Patterns to Avoid

- **Checking is_active only at login, not on every request:** A disabled account's existing JWT would continue to work until expiry. The correct pattern checks `is_active` in `get_current_user` on every request.
- **Embedding role in JWT payload and trusting it:** Role changes would not take effect until token expiry. Always re-read role from DB on each request (same reason as is_active).
- **Calling `scrape_one_building()` as a coroutine:** It is synchronous and uses `time.sleep`. It will block the event loop. Use `asyncio.to_thread()`.
- **Using `allow_origins=["*"]` with `allow_credentials=True`:** FastAPI/Starlette raises an error. Must use explicit origins when credentials=True.
- **Storing jobs in a list and scanning linearly:** Use a dict keyed by UUID for O(1) lookup.
- **Using `BackgroundTasks` for the re-scrape job:** `BackgroundTasks` runs after the response but shares the request context; `asyncio.create_task()` allows true concurrent tracking via the job store. For polling semantics, create_task is the right abstraction.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt wrapper | `pwdlib[argon2]` | Salt handling, timing-safe verify, algorithm agility |
| JWT encode/decode | Custom base64 logic | `PyJWT` | Signature validation, expiry handling, algorithm choices |
| Settings from env | Manual `os.getenv` everywhere | `pydantic-settings` | Type coercion, validation, dotenv loading, lru_cache |
| Route-level auth checks | Repeating `if current_user.role != "admin"` | Router-level `dependencies=[Depends(require_admin)]` | Single point of enforcement |

---

## Common Pitfalls

### Pitfall 1: python-jose / passlib Dependency Rot

**What goes wrong:** Pip installs successfully, tests pass, but `passlib` uses `crypt` module which is removed in Python 3.13. `python-jose` has unpatched CVEs.
**Why it happens:** Both were the FastAPI-recommended libraries until mid-2024.
**How to avoid:** Use `PyJWT` and `pwdlib[argon2]` from the start. These are the current official FastAPI recommendations as of 2024-2025.
**Warning signs:** Any project install guide that references `python-jose` or `passlib[bcrypt]` is outdated.

### Pitfall 2: Blocking Event Loop with Synchronous Scraper

**What goes wrong:** `asyncio.create_task(_run_scrape_job(...))` calls `scrape_one_building()` directly → event loop blocks for the entire scrape duration → all API requests hang.
**Why it happens:** `scrape_one_building()` uses `time.sleep()`, `SessionLocal()`, and blocking HTTP calls.
**How to avoid:** Always wrap sync functions in `await asyncio.to_thread(scrape_one_building, ...)`.
**Warning signs:** API requests that time out during an active re-scrape operation.

### Pitfall 3: CORS + Credentials Misconfiguration

**What goes wrong:** `allow_origins=["*"]` with `allow_credentials=True` raises `ValueError` at startup.
**Why it happens:** The CORS spec prohibits wildcard origins with credentials.
**How to avoid:** Always use explicit origins (from `CORS_ORIGINS` env var). Default to `http://localhost:3000,http://localhost:5173` for dev.
**Warning signs:** `ValueError: Cannot use wildcard in allow_origins when allow_credentials is True`.

### Pitfall 4: JWT User ID vs Username as `sub`

**What goes wrong:** Using `username` or `email` as the `sub` claim. User gets renamed (or email changes) → old tokens break.
**Why it happens:** FastAPI tutorial examples use fake DB with username as key.
**How to avoid:** Use integer `user_id` as `sub`. `payload = {"sub": str(user.id), "exp": ...}`.
**Warning signs:** Token decode fails after any user update.

### Pitfall 5: In-Memory Job Store Lost on Restart

**What goes wrong:** Server restarts during a re-scrape → job_id is lost → client polls forever getting 404.
**Why it happens:** `_jobs` dict is module-level, not persisted.
**How to avoid:** Acceptable for this use case (admin-only, rare operation). Document the behavior. If a restart occurs, admin should check `scrape_runs` table directly. Could persist to DB if needed in future.
**Warning signs:** Only a risk during active re-scrapes — low probability for the single-admin use case.

### Pitfall 6: Migration Order — Users Table Before API

**What goes wrong:** FastAPI app imports `User` model that doesn't exist in the DB yet → startup error.
**Why it happens:** Forgot to run `alembic upgrade head` after adding `User` to `models.py`.
**How to avoid:** Migration is the first task in the phase plan. Generate with `alembic revision --autogenerate -m "add users table"` after updating models.py.

---

## Code Examples

### Login Endpoint (JSON body, not form data)

```python
# Source: FastAPI docs pattern adapted for JSON + PyJWT + pwdlib
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

router = APIRouter()

@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)
```

### CLI Seed Command (create-admin)

```python
# scripts/create_admin.py  — registered as `uv run create-admin`
import argparse
from moxie.db.session import SessionLocal
from moxie.db.models import User
from moxie.api.auth import get_password_hash

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    user = User(name=args.name, email=args.email,
                password_hash=get_password_hash(args.password),
                role="admin", is_active=True)
    db.add(user)
    db.commit()
    print(f"Admin created: {args.email}")
    db.close()
```

### User Model (add to models.py)

```python
# Add to src/moxie/db/models.py
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, server_default="agent")  # "admin" | "agent"
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
```

---

## Existing Codebase Integration Notes

These are facts about the existing codebase that affect Phase 4 implementation:

**`get_db()` already exists** in `src/moxie/db/session.py` and follows the FastAPI generator pattern (`yield`). The API can use it directly as `Depends(get_db)`.

**`scrape_one_building()` in `src/moxie/scheduler/runner.py`** is the correct function to call for single-building re-scrapes. It accepts `(building_id, building_name, building_url, platform)` and returns a result dict with `status`, `unit_count`, `error`. It creates its own `SessionLocal` session internally — no session needs to be passed.

**`Building` model already has** `last_scraped_at`, `last_scrape_status`, `platform`, `neighborhood`, `management_company`, `name`, `url` — all needed for ADMIN-03 (`/admin/buildings`) and the `last_scraped` field in unit search responses.

**`ScrapeRun` model already exists** — re-scrape endpoint completion can be confirmed by checking for a new row with matching `building_id` and `run_at` near the job start time.

**SQLite WAL mode** is already enabled in `session.py` — safe for concurrent API reads during batch scrape writes.

**Existing test pattern** uses in-memory SQLite with `Base.metadata.create_all(engine)` — the API test suite should follow the same pattern with `app.dependency_overrides[get_db]`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-jose` for JWT | `PyJWT` | FastAPI docs updated 2024 (PR #11589) | python-jose has CVEs; PyJWT is actively maintained |
| `passlib[bcrypt]` for passwords | `pwdlib[argon2]` | FastAPI docs updated 2024-2025 (PR #13917) | passlib unmaintained; crypt removed in Python 3.13 |
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` | Pydantic v2 split (2023) | pydantic-settings is now a separate package |

---

## Open Questions

1. **Job store persistence on restart**
   - What we know: In-memory dict is lost on restart. Active re-scrapes in progress would leave orphaned `_building_jobs` entries.
   - What's unclear: Whether admin needs job history between restarts.
   - Recommendation: Accept the limitation. Document that job polling is ephemeral. Admin can verify completion via the `scrape_runs` table. If persistence becomes needed, add a `scrape_jobs` table in a future phase.

2. **`asyncio.create_task` vs `BackgroundTasks` for re-scrape**
   - What we know: Both run in the same process. `asyncio.create_task` gives direct control over task lifecycle and a stable job ID. `BackgroundTasks` is simpler but scoped to request context.
   - Recommendation: Use `asyncio.create_task` — it integrates cleanly with the module-level job store dict and gives a stable reference for polling.

3. **Response envelope: bare list vs `{items: [...], count: N}`**
   - What we know: Left to Claude's discretion. Dataset is small (~2-5K units).
   - Recommendation: Wrapped object `{"units": [...], "total": N}` — easier to extend later without breaking API contract. Phase 5 frontend can display total count for UX context.

---

## Sources

### Primary (HIGH confidence)
- `https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/` — Current JWT tutorial showing PyJWT + pwdlib (live page verified)
- `https://fastapi.tiangolo.com/tutorial/background-tasks/` — BackgroundTasks documentation (live page verified)
- `https://fastapi.tiangolo.com/tutorial/cors/` — CORSMiddleware configuration (live page verified)
- `https://github.com/fastapi/fastapi/pull/11589` — PR confirming python-jose → PyJWT migration in FastAPI docs
- `https://github.com/fastapi/fastapi/pull/13917` — PR confirming passlib → pwdlib migration in FastAPI docs

### Secondary (MEDIUM confidence)
- Multiple WebSearch results confirming PyJWT and pwdlib as current recommendations (2024-2025)
- Project codebase: `src/moxie/db/session.py`, `src/moxie/scheduler/runner.py`, `src/moxie/db/models.py` — verified by direct read

### Tertiary (LOW confidence)
- In-memory job store pattern for FastAPI polling — common pattern seen across multiple sources; no single canonical FastAPI doc, but widely used and appropriate for the scale

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed via live FastAPI docs and official PRs
- Architecture: HIGH — based on verified existing codebase + official FastAPI patterns
- Pitfalls: HIGH — most verified against official docs; job store restart risk is architectural reasoning
- Integration facts: HIGH — read directly from existing source files

**Research date:** 2026-02-21
**Valid until:** 2026-05-01 (stable libraries; FastAPI ecosystem moves slowly for core auth patterns)
