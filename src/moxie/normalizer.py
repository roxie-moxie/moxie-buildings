"""
Unit normalizer — pure function that converts raw scraper output to a DB-ready dict.

Every scraper calls normalize(raw, building_id) before writing to the database.
This module never touches the database.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from dateutil import parser as dateutil_parser
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Canonical bed type definitions
# ---------------------------------------------------------------------------

CANONICAL_BED_TYPES: frozenset[str] = frozenset({
    "Studio",
    "Convertible",
    "1BR",
    "1BR+Den",
    "2BR",
    "3BR+",
})

# Maps lowercased + stripped raw values to canonical bed type strings.
# Covers all known scraper aliases.
BED_TYPE_ALIASES: dict[str, str] = {
    # Studio aliases
    "0": "Studio",
    "0br": "Studio",
    "studio": "Studio",
    "studio/1 bath": "Studio",
    "studio/1bath": "Studio",
    # Convertible aliases
    "convertible": "Convertible",
    "alcove": "Convertible",
    "jr 1br": "Convertible",
    "jr one bedroom/1 bath": "Convertible",
    "junior one bedroom/1 bath": "Convertible",
    "convertible/1 bath": "Convertible",
    "convertible/1bath": "Convertible",
    # 1BR aliases
    "1": "1BR",
    "1br": "1BR",
    "1 bed": "1BR",
    "one bedroom": "1BR",
    "1 bedroom/1bath": "1BR",
    "1 bedroom/1 bath": "1BR",
    # 1BR+Den aliases
    "1br+den": "1BR+Den",
    "1 bed den": "1BR+Den",
    "1+den": "1BR+Den",
    # 2BR aliases
    "2": "2BR",
    "2br": "2BR",
    "2 bed": "2BR",
    "2 beds": "2BR",
    "two bedroom": "2BR",
    "2 bedroom/1 bath": "2BR",
    "2 bedroom/1bath": "2BR",
    "2 bedroom/2 bath": "2BR",
    "2 bedroom/2bath": "2BR",
    # 3BR+ aliases (4BR+ also maps to 3BR+ per spec)
    "3": "3BR+",
    "3br": "3BR+",
    "3 bed": "3BR+",
    "3 beds": "3BR+",
    "3+": "3BR+",
    "4br": "3BR+",
    "4 beds": "3BR+",
    "4 bed": "3BR+",
    "3 bedroom/3 bath": "3BR+",
    "3 bedroom/2 bath": "3BR+",
    "3 bedroom/3bath": "3BR+",
    # Non-standard types that have a clear canonical equivalent
    "loft studio": "Studio",          # open loft-style studio
    "convertible deluxe": "Convertible",  # larger convertible variant
    # Note: "Duplex", "Penthouse", "Loft" etc. are intentionally NOT mapped here —
    # they are preserved as-is and flagged non_canonical=True in the output.
}


# ---------------------------------------------------------------------------
# Pydantic input model with field validators
# ---------------------------------------------------------------------------

class UnitInput(BaseModel):
    unit_number: str
    bed_type: str
    rent: Any  # accepts "$1,500.00", "1500", 1500 — normalized to int cents
    availability_date: Any  # accepts any parseable date string
    floor_plan_name: Optional[str] = None
    floor_plan_url: Optional[str] = None
    baths: Optional[Any] = None
    sqft: Optional[Any] = None

    @field_validator("bed_type", mode="before")
    @classmethod
    def normalize_bed_type(cls, v: Any) -> str:
        """Map raw bed type to canonical alias, or preserve original casing for unknowns."""
        stripped = str(v).strip()
        lowered = stripped.lower()
        return BED_TYPE_ALIASES.get(lowered, stripped)

    @field_validator("rent", mode="before")
    @classmethod
    def normalize_rent(cls, v: Any) -> int:
        """Return rent as integer cents. Strips $, commas, /mo, 'Starting at', and decimal suffixes."""
        s = str(v).strip()
        # Strip "Starting at" prefix (Funnel-style floor plan pricing)
        s_lower = s.lower()
        if s_lower.startswith("starting at"):
            s = s[len("starting at"):].strip()
        s = s.replace("$", "").replace(",", "").replace("/mo", "").strip()
        # Handle price ranges: "$2,211 – $2,799" or "$2211-$2799" — take the lower value
        for sep in [" – ", " - ", "–", "-"]:
            if sep in s:
                parts = s.split(sep)
                s = parts[0].replace("$", "").replace(",", "").strip()
                break
        # Convert to float first to handle ".00" and fractional cents, then to cents
        try:
            cents = round(float(s) * 100)
        except ValueError:
            raise ValueError(f"Cannot parse rent value: {v!r}")
        return int(cents)

    @field_validator("availability_date", mode="before")
    @classmethod
    def normalize_date(cls, v: Any) -> str:
        """Return YYYY-MM-DD string. Handles 'Available Now' → today's date.

        Also strips 'Available ' prefix (e.g., 'Available 03/25/2026' → '03/25/2026')
        before parsing with dateutil.
        """
        s = str(v).strip().lower()
        if s in ("available now", "available", "now", "immediate", "immediately", ""):
            return datetime.today().strftime("%Y-%m-%d")
        # Strip "available" prefix (e.g., "Available 03/25/2026" -> "03/25/2026")
        original = str(v).strip()
        if s.startswith("available "):
            date_part = original[len("available "):].strip()
        else:
            date_part = original
        try:
            parsed = dateutil_parser.parse(date_part)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Unknown string format: {v}") from exc
        return parsed.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Public normalize() function
# ---------------------------------------------------------------------------

def normalize(raw: dict, building_id: int) -> dict:
    """
    Normalize raw scraper output to a DB-ready unit dict.

    Args:
        raw: Dict from a scraper with keys: unit_number, bed_type, rent,
             availability_date, and optionally floor_plan_name, floor_plan_url,
             baths, sqft.
        building_id: FK to the buildings table.

    Returns:
        Dict with keys: building_id, unit_number, bed_type, non_canonical,
        rent_cents, availability_date, floor_plan_name, floor_plan_url,
        baths, sqft, scrape_run_at.

    Raises:
        pydantic.ValidationError: if any required field is missing or unparseable.
    """
    inp = UnitInput(**raw)
    non_canonical = inp.bed_type not in CANONICAL_BED_TYPES

    return {
        "building_id": building_id,
        "unit_number": inp.unit_number,
        "bed_type": inp.bed_type,
        "non_canonical": non_canonical,
        "rent_cents": inp.rent,  # already int cents from validator
        "availability_date": inp.availability_date,
        "floor_plan_name": inp.floor_plan_name,
        "floor_plan_url": inp.floor_plan_url,
        "baths": str(inp.baths) if inp.baths is not None else None,
        "sqft": int(inp.sqft) if inp.sqft is not None else None,
        "scrape_run_at": datetime.now(timezone.utc),
    }
