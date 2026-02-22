from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    name: str
    email: str
    password: str  # min_length enforced at router level (8 chars -- reasonable for internal tool)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    neighborhood: str | None
    management_company: str | None
    platform: str | None
    last_scraped_at: datetime | None
    last_scrape_status: str


class RescrapeJobOut(BaseModel):
    job_id: str
    status: str
    building_id: int
    unit_count: int | None = None
    error: str | None = None
    duration_seconds: float | None = None
