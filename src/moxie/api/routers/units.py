from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from moxie.api.deps import get_current_user
from moxie.api.schemas.units import UnitOut, UnitsResponse
from moxie.db.models import Building, Unit, User
from moxie.db.session import get_db

router = APIRouter(tags=["units"])


def _to_unit_out(unit: Unit) -> UnitOut:
    """Convert a Unit ORM object (with joined building) to UnitOut."""
    return UnitOut(
        id=unit.id,
        building_id=unit.building_id,
        building_name=unit.building.name,
        building_url=unit.building.url,
        unit_number=unit.unit_number,
        bed_type=unit.bed_type,
        rent_cents=unit.rent_cents,
        availability_date=unit.availability_date,
        floor_plan_name=unit.floor_plan_name,
        baths=unit.baths,
        sqft=unit.sqft,
        neighborhood=unit.building.neighborhood,
        last_scraped=unit.building.last_scraped_at,
    )


@router.get("/units", response_model=UnitsResponse)
def search_units(
    beds: Optional[list[str]] = Query(default=None),
    rent_min: Optional[int] = Query(default=None, ge=0),
    rent_max: Optional[int] = Query(default=None, ge=0),
    available_before: Optional[str] = Query(default=None),
    neighborhood: Optional[list[str]] = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnitsResponse:
    """Search available units with optional filters. (AGENT-01)

    All filters are optional and combinable.
    - beds: multi-select bed types (e.g. ?beds=1BR&beds=2BR)
    - rent_min/rent_max: dollar amounts (DB stores cents)
    - available_before: YYYY-MM-DD string; also includes 'Available Now' units
    - neighborhood: multi-select neighborhood names
    """
    # Validate rent range
    if rent_min is not None and rent_max is not None and rent_max < rent_min:
        raise HTTPException(status_code=422, detail="rent_max must be >= rent_min")

    query = (
        db.query(Unit)
        .join(Building)
        .filter(Unit.non_canonical == False)  # noqa: E712 -- SQLAlchemy requires == not is
    )

    if beds:
        query = query.filter(Unit.bed_type.in_(beds))

    if rent_min is not None:
        query = query.filter(Unit.rent_cents >= rent_min * 100)

    if rent_max is not None:
        query = query.filter(Unit.rent_cents <= rent_max * 100)

    if available_before is not None:
        # "Available Now" units are stored as today's YYYY-MM-DD by the normalizer,
        # so a simple <= comparison includes them for any same-day or future cutoff.
        query = query.filter(Unit.availability_date <= available_before)

    if neighborhood:
        query = query.filter(Building.neighborhood.in_(neighborhood))

    units = query.all()
    unit_outs = [_to_unit_out(u) for u in units]
    return UnitsResponse(units=unit_outs, total=len(unit_outs))
