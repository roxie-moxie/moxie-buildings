import asyncio
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moxie.api.auth import hash_password
from moxie.api.deps import require_admin
from moxie.api.schemas.admin import BuildingOut, RescrapeJobOut, UserCreate, UserOut
from moxie.db.models import Building, User
from moxie.db.session import get_db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

# In-memory job tracking (process lifetime; resets on restart)
_jobs: dict[str, dict[str, Any]] = {}         # job_id -> status dict
_building_jobs: dict[int, str] = {}           # building_id -> active job_id


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """Create a new agent account. (ADMIN-01)"""
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    new_user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role="agent",
        is_active=True,
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    return UserOut.model_validate(new_user)


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db)) -> UserOut:
    """Disable an agent account. (ADMIN-02)"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    """List all users. (supporting ADMIN-01/02)"""
    users = db.query(User).order_by(User.created_at).all()
    return [UserOut.model_validate(u) for u in users]


# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------


@router.get("/buildings", response_model=list[BuildingOut])
def list_buildings(db: Session = Depends(get_db)) -> list[BuildingOut]:
    """Return all buildings with platform and last_scraped_at. (ADMIN-03)"""
    buildings = db.query(Building).order_by(Building.name).all()
    return [BuildingOut.model_validate(b) for b in buildings]


# ---------------------------------------------------------------------------
# Re-scrape jobs
# ---------------------------------------------------------------------------


@router.post("/rescrape/{building_id}", response_model=RescrapeJobOut, status_code=202)
async def trigger_rescrape(building_id: int, db: Session = Depends(get_db)) -> RescrapeJobOut:
    """Trigger an async re-scrape for a building. (ADMIN-04 -- trigger)"""
    # Check if building already has an active job
    if building_id in _building_jobs:
        raise HTTPException(
            status_code=409,
            detail="Scrape already in progress for this building",
        )

    building = db.get(Building, building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "building_id": building_id,
        "unit_count": None,
        "error": None,
        "duration_seconds": None,
    }
    _building_jobs[building_id] = job_id

    # Launch background task (non-blocking)
    asyncio.create_task(
        _run_scrape_job(
            job_id=job_id,
            building_id=building_id,
            building_name=building.name,
            building_url=building.url,
            platform=building.platform if building.platform and building.platform not in ("needs_classification",) else "llm",
        )
    )

    return RescrapeJobOut(**_jobs[job_id])


@router.get("/rescrape/{job_id}", response_model=RescrapeJobOut)
def poll_rescrape(job_id: str) -> RescrapeJobOut:
    """Poll a re-scrape job for status. (ADMIN-04 -- poll)"""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return RescrapeJobOut(**job)


# ---------------------------------------------------------------------------
# Background scrape runner
# ---------------------------------------------------------------------------


async def _run_scrape_job(
    job_id: str,
    building_id: int,
    building_name: str,
    building_url: str,
    platform: str,
) -> None:
    """Run scrape_one_building in a thread and update job status."""
    from moxie.scheduler.runner import scrape_one_building  # local import avoids heavy deps at module load

    _jobs[job_id]["status"] = "running"
    start = time.monotonic()
    try:
        result = await asyncio.to_thread(
            scrape_one_building,
            building_id,
            building_name,
            building_url,
            platform,
        )
        duration = time.monotonic() - start
        _jobs[job_id].update(
            {
                "status": result["status"],
                "unit_count": result.get("unit_count"),
                "error": result.get("error"),
                "duration_seconds": round(duration, 2),
            }
        )
    except Exception as exc:
        duration = time.monotonic() - start
        _jobs[job_id].update(
            {
                "status": "failed",
                "error": f"[{type(exc).__name__}] {str(exc)[:500]}",
                "duration_seconds": round(duration, 2),
            }
        )
    finally:
        _building_jobs.pop(building_id, None)
