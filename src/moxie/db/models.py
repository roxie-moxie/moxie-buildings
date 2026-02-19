from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    neighborhood: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    management_company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rentcafe_property_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rentcafe_api_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_scrape_status: Mapped[str] = mapped_column(
        String, server_default="never", nullable=False
    )
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    consecutive_zero_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    units: Mapped[list["Unit"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )
    scrape_runs: Mapped[list["ScrapeRun"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("building_id", "unit_number", name="uq_unit_building_number"),
        Index("ix_units_bed_type", "bed_type"),
        Index("ix_units_rent_cents", "rent_cents"),
        Index("ix_units_availability_date", "availability_date"),
        Index("ix_units_building_id", "building_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    unit_number: Mapped[str] = mapped_column(String, nullable=False)
    bed_type: Mapped[str] = mapped_column(String, nullable=False)
    non_canonical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    rent_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_date: Mapped[str] = mapped_column(String, nullable=False)
    floor_plan_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    floor_plan_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    baths: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sqft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scrape_run_at: Mapped[datetime] = mapped_column(nullable=False)

    building: Mapped["Building"] = relationship(back_populates="units")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    building: Mapped["Building"] = relationship(back_populates="scrape_runs")
