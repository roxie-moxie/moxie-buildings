"""
Tests for src/moxie/normalizer.py

Covers: bed type normalization, rent normalization, date normalization,
optional fields, non_canonical flag, required field enforcement (ValidationError).
"""

import pytest
from datetime import date
from pydantic import ValidationError

from moxie.normalizer import normalize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base(overrides: dict | None = None) -> dict:
    """Return a minimal valid raw input dict, optionally with overrides."""
    raw = {
        "unit_number": "101",
        "bed_type": "1",
        "rent": "$1,500.00",
        "availability_date": "2026-03-01",
    }
    if overrides:
        raw.update(overrides)
    return raw


# ---------------------------------------------------------------------------
# Bed type normalization
# ---------------------------------------------------------------------------

class TestBedTypeNormalization:

    def test_zero_maps_to_studio(self):
        result = normalize(_base({"bed_type": "0"}), building_id=1)
        assert result["bed_type"] == "Studio"
        assert result["non_canonical"] is False

    def test_0br_maps_to_studio(self):
        result = normalize(_base({"bed_type": "0BR"}), building_id=1)
        assert result["bed_type"] == "Studio"
        assert result["non_canonical"] is False

    def test_studio_lowercase_maps_to_studio(self):
        result = normalize(_base({"bed_type": "studio"}), building_id=1)
        assert result["bed_type"] == "Studio"
        assert result["non_canonical"] is False

    def test_studio_titlecase_maps_to_studio(self):
        result = normalize(_base({"bed_type": "Studio"}), building_id=1)
        assert result["bed_type"] == "Studio"
        assert result["non_canonical"] is False

    def test_convertible_maps_to_convertible(self):
        result = normalize(_base({"bed_type": "convertible"}), building_id=1)
        assert result["bed_type"] == "Convertible"
        assert result["non_canonical"] is False

    def test_alcove_maps_to_convertible(self):
        result = normalize(_base({"bed_type": "alcove"}), building_id=1)
        assert result["bed_type"] == "Convertible"
        assert result["non_canonical"] is False

    def test_jr_1br_maps_to_convertible(self):
        result = normalize(_base({"bed_type": "jr 1br"}), building_id=1)
        assert result["bed_type"] == "Convertible"
        assert result["non_canonical"] is False

    def test_one_maps_to_1br(self):
        result = normalize(_base({"bed_type": "1"}), building_id=1)
        assert result["bed_type"] == "1BR"
        assert result["non_canonical"] is False

    def test_1br_maps_to_1br(self):
        result = normalize(_base({"bed_type": "1br"}), building_id=1)
        assert result["bed_type"] == "1BR"
        assert result["non_canonical"] is False

    def test_1_bed_maps_to_1br(self):
        result = normalize(_base({"bed_type": "1 bed"}), building_id=1)
        assert result["bed_type"] == "1BR"
        assert result["non_canonical"] is False

    def test_one_bedroom_maps_to_1br(self):
        result = normalize(_base({"bed_type": "one bedroom"}), building_id=1)
        assert result["bed_type"] == "1BR"
        assert result["non_canonical"] is False

    def test_1br_plus_den_titlecase_maps_to_1br_plus_den(self):
        result = normalize(_base({"bed_type": "1BR+Den"}), building_id=1)
        assert result["bed_type"] == "1BR+Den"
        assert result["non_canonical"] is False

    def test_1br_plus_den_lowercase_maps_to_1br_plus_den(self):
        result = normalize(_base({"bed_type": "1br+den"}), building_id=1)
        assert result["bed_type"] == "1BR+Den"
        assert result["non_canonical"] is False

    def test_1_bed_den_maps_to_1br_plus_den(self):
        result = normalize(_base({"bed_type": "1 bed den"}), building_id=1)
        assert result["bed_type"] == "1BR+Den"
        assert result["non_canonical"] is False

    def test_two_maps_to_2br(self):
        result = normalize(_base({"bed_type": "2"}), building_id=1)
        assert result["bed_type"] == "2BR"
        assert result["non_canonical"] is False

    def test_2br_maps_to_2br(self):
        result = normalize(_base({"bed_type": "2br"}), building_id=1)
        assert result["bed_type"] == "2BR"
        assert result["non_canonical"] is False

    def test_three_maps_to_3br_plus(self):
        result = normalize(_base({"bed_type": "3"}), building_id=1)
        assert result["bed_type"] == "3BR+"
        assert result["non_canonical"] is False

    def test_3br_maps_to_3br_plus(self):
        result = normalize(_base({"bed_type": "3br"}), building_id=1)
        assert result["bed_type"] == "3BR+"
        assert result["non_canonical"] is False

    def test_4br_maps_to_3br_plus(self):
        """4BR+ maps to 3BR+ per spec."""
        result = normalize(_base({"bed_type": "4br"}), building_id=1)
        assert result["bed_type"] == "3BR+"
        assert result["non_canonical"] is False

    def test_penthouse_is_non_canonical(self):
        result = normalize(_base({"bed_type": "PENTHOUSE"}), building_id=1)
        assert result["bed_type"] == "PENTHOUSE"
        assert result["non_canonical"] is True

    def test_5br_is_non_canonical(self):
        result = normalize(_base({"bed_type": "5BR"}), building_id=1)
        assert result["bed_type"] == "5BR"
        assert result["non_canonical"] is True


# ---------------------------------------------------------------------------
# Rent normalization
# ---------------------------------------------------------------------------

class TestRentNormalization:

    def test_dollar_comma_decimal_rent(self):
        result = normalize(_base({"rent": "$1,500.00"}), building_id=1)
        assert result["rent_cents"] == 150000
        assert isinstance(result["rent_cents"], int)

    def test_dollar_no_comma_rent(self):
        result = normalize(_base({"rent": "$1500"}), building_id=1)
        assert result["rent_cents"] == 150000

    def test_integer_rent(self):
        result = normalize(_base({"rent": 1500}), building_id=1)
        assert result["rent_cents"] == 150000

    def test_comma_per_mo_rent(self):
        result = normalize(_base({"rent": "2,250/mo"}), building_id=1)
        assert result["rent_cents"] == 225000

    def test_dollar_comma_decimal_3000(self):
        result = normalize(_base({"rent": "$3,000.00"}), building_id=1)
        assert result["rent_cents"] == 300000

    def test_dollar_995(self):
        result = normalize(_base({"rent": "$995"}), building_id=1)
        assert result["rent_cents"] == 99500

    def test_rent_cents_is_int_not_float(self):
        """rent_cents must be an integer, never a float."""
        result = normalize(_base({"rent": "$1,500.00"}), building_id=1)
        assert type(result["rent_cents"]) is int


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

class TestDateNormalization:

    def test_available_now_returns_today(self):
        result = normalize(_base({"availability_date": "Available Now"}), building_id=1)
        assert result["availability_date"] == date.today().strftime("%Y-%m-%d")

    def test_now_returns_today(self):
        result = normalize(_base({"availability_date": "now"}), building_id=1)
        assert result["availability_date"] == date.today().strftime("%Y-%m-%d")

    def test_iso_date_passthrough(self):
        result = normalize(_base({"availability_date": "2026-03-01"}), building_id=1)
        assert result["availability_date"] == "2026-03-01"

    def test_long_date_format(self):
        result = normalize(_base({"availability_date": "March 1, 2026"}), building_id=1)
        assert result["availability_date"] == "2026-03-01"

    def test_us_slash_date_format(self):
        result = normalize(_base({"availability_date": "03/01/2026"}), building_id=1)
        assert result["availability_date"] == "2026-03-01"

    def test_short_year_date_format(self):
        result = normalize(_base({"availability_date": "3/1/26"}), building_id=1)
        assert result["availability_date"] == "2026-03-01"


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------

class TestOptionalFields:

    def test_optional_fields_present_when_provided(self):
        raw = _base({
            "floor_plan_name": "Plan A",
            "floor_plan_url": "https://example.com/plan-a",
            "baths": "2",
            "sqft": 850,
        })
        result = normalize(raw, building_id=1)
        assert result["floor_plan_name"] == "Plan A"
        assert result["floor_plan_url"] == "https://example.com/plan-a"
        assert result["baths"] == "2"
        assert result["sqft"] == 850

    def test_optional_fields_none_when_absent(self):
        result = normalize(_base(), building_id=1)
        assert "floor_plan_name" in result
        assert result["floor_plan_name"] is None
        assert "floor_plan_url" in result
        assert result["floor_plan_url"] is None
        assert "baths" in result
        assert result["baths"] is None
        assert "sqft" in result
        assert result["sqft"] is None

    def test_baths_stored_as_string(self):
        result = normalize(_base({"baths": 2}), building_id=1)
        assert isinstance(result["baths"], str)

    def test_sqft_stored_as_int(self):
        result = normalize(_base({"sqft": "950"}), building_id=1)
        assert result["sqft"] == 950
        assert isinstance(result["sqft"], int)


# ---------------------------------------------------------------------------
# Output dict structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    def test_building_id_in_output(self):
        result = normalize(_base(), building_id=42)
        assert result["building_id"] == 42

    def test_all_required_keys_present(self):
        result = normalize(_base(), building_id=1)
        expected_keys = {
            "building_id", "unit_number", "bed_type", "non_canonical",
            "rent_cents", "availability_date", "floor_plan_name",
            "floor_plan_url", "baths", "sqft", "scrape_run_at",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_scrape_run_at_is_datetime(self):
        from datetime import datetime
        result = normalize(_base(), building_id=1)
        assert isinstance(result["scrape_run_at"], datetime)


# ---------------------------------------------------------------------------
# Required field enforcement (ValidationError)
# ---------------------------------------------------------------------------

class TestRequiredFieldEnforcement:

    def test_missing_unit_number_raises(self):
        raw = {"bed_type": "1", "rent": "1500", "availability_date": "2026-03-01"}
        with pytest.raises(ValidationError):
            normalize(raw, building_id=1)

    def test_missing_bed_type_raises(self):
        raw = {"unit_number": "101", "rent": "1500", "availability_date": "2026-03-01"}
        with pytest.raises(ValidationError):
            normalize(raw, building_id=1)

    def test_missing_rent_raises(self):
        raw = {"unit_number": "101", "bed_type": "1", "availability_date": "2026-03-01"}
        with pytest.raises(ValidationError):
            normalize(raw, building_id=1)

    def test_missing_availability_date_raises(self):
        raw = {"unit_number": "101", "bed_type": "1", "rent": "1500"}
        with pytest.raises(ValidationError):
            normalize(raw, building_id=1)
