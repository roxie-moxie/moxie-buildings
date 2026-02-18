"""
Dev database seed script.

Inserts 3 representative downtown Chicago apartment buildings and 9 units into the
development database. Uses normalize() for all unit data to prove the pipeline works
end-to-end.

Covers all 6 canonical bed types: Studio, Convertible, 1BR, 1BR+Den, 2BR, 3BR+
Mix of platforms: api, platform, llm

Idempotent: skips buildings that already exist by URL. Skips units that already exist
by (building_id, unit_number).

Usage:
    uv run python scripts/seed.py
"""

from moxie.db.session import SessionLocal
from moxie.db.models import Building, Unit
from moxie.normalizer import normalize


# ---------------------------------------------------------------------------
# Seed data definition
# ---------------------------------------------------------------------------

SEED_BUILDINGS = [
    {
        "name": "The Reed at Southbank",
        "url": "https://www.thereedatsouthbank.com/",
        "neighborhood": "South Loop",
        "management_company": "Related Midwest",
        "platform": "api",
        "rentcafe_property_id": "mock-reed-001",
        "rentcafe_api_token": None,
        # Units: Studio, 1BR, 2BR — uses raw formats to prove normalizer
        "units": [
            {
                "unit_number": "101",
                "bed_type": "studio",       # alias -> Studio
                "rent": "$1,750.00",        # dollar + comma + .00
                "availability_date": "Available Now",
                "floor_plan_name": "Studio S1",
                "sqft": "520",
            },
            {
                "unit_number": "205",
                "bed_type": "1 bed",        # alias -> 1BR
                "rent": "2850",             # plain integer string
                "availability_date": "2026-03-01",
                "baths": "1",
                "sqft": 750,
            },
            {
                "unit_number": "812",
                "bed_type": "2br",          # alias -> 2BR
                "rent": "$3,500/mo",        # dollar + comma + /mo
                "availability_date": "March 15, 2026",
                "baths": "2",
                "sqft": 1100,
            },
        ],
    },
    {
        "name": "727 West Madison",
        "url": "https://www.727westmadison.com/",
        "neighborhood": "West Loop",
        "management_company": "Golub",
        "platform": "platform",
        "rentcafe_property_id": None,
        "rentcafe_api_token": None,
        # Units: Convertible, 1BR+Den — varied date formats
        "units": [
            {
                "unit_number": "302",
                "bed_type": "convertible",  # alias -> Convertible
                "rent": "2,200/mo",         # comma + /mo (no dollar)
                "availability_date": "now", # alias -> today
                "floor_plan_name": "Convertible C1",
                "sqft": 600,
            },
            {
                "unit_number": "505",
                "bed_type": "1 bed den",    # alias -> 1BR+Den
                "rent": 2950,               # int (not string)
                "availability_date": "04/01/26",  # 2-digit year slash format
                "baths": "1.5",
                "sqft": 880,
            },
        ],
    },
    {
        "name": "Moment River North",
        "url": "https://www.momentapts.com/",
        "neighborhood": "River North",
        "management_company": "Greystar",
        "platform": "llm",
        "rentcafe_property_id": None,
        "rentcafe_api_token": None,
        # Units: 3BR+ — proves upper end of canonical range
        "units": [
            {
                "unit_number": "1201",
                "bed_type": "3br",          # alias -> 3BR+
                "rent": "$4,200.00",
                "availability_date": "2026-04-15",
                "baths": "2",
                "sqft": 1450,
            },
            {
                "unit_number": "1501",
                "bed_type": "4br",          # alias -> 3BR+ (per spec: 4BR+ maps to 3BR+)
                "rent": "5,500",            # comma only
                "availability_date": "May 1, 2026",
                "baths": "3",
                "sqft": 1850,
            },
            {
                "unit_number": "602",
                "bed_type": "1br",          # alias -> 1BR
                "rent": 2650,
                "availability_date": "2026-03-15",
                "baths": "1",
                "sqft": 710,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

def main():
    db = SessionLocal()
    building_count = 0
    unit_count = 0

    try:
        for building_data in SEED_BUILDINGS:
            units_raw = building_data.pop("units")

            # Idempotent: skip if building already exists
            existing = db.query(Building).filter_by(url=building_data["url"]).first()
            if existing:
                print(f"  Skipping (already exists): {building_data['name']}")
                building_data["units"] = units_raw  # restore for re-runs
                continue

            building = Building(**building_data)
            db.add(building)
            db.flush()  # get building.id without committing

            for raw_unit in units_raw:
                # Check if unit already exists (idempotent)
                existing_unit = (
                    db.query(Unit)
                    .filter_by(building_id=building.id, unit_number=raw_unit["unit_number"])
                    .first()
                )
                if existing_unit:
                    continue

                normalized = normalize(raw_unit, building.id)
                unit = Unit(**normalized)
                db.add(unit)
                unit_count += 1

            building_data["units"] = units_raw  # restore for re-runs
            building_count += 1

        db.commit()
        print(f"Seeded: {building_count} buildings, {unit_count} units")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
