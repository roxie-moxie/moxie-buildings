from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    building_id: int
    building_name: str
    building_url: str
    unit_number: str
    bed_type: str
    rent_cents: int
    availability_date: str
    floor_plan_name: str | None
    baths: str | None
    sqft: int | None
    neighborhood: str | None
    last_scraped: datetime | None


class UnitsResponse(BaseModel):
    units: list[UnitOut]
    total: int
