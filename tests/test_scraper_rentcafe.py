"""
Tests for RentCafe/Yardi scraper stub behavior.

Covers:
- Missing credential detection (RentCafeCredentialError)
- Error:1020 API response guard (RentCafeAPIError)
- _map_unit() field mapping
- Stub raises NotImplementedError when credentials are present

No real HTTP calls are made — the scraper is stubbed and _fetch_units() always
raises NotImplementedError until replaced with a real implementation.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moxie.db.models import Base, Building
from moxie.scrapers.tier1.rentcafe import (
    scrape,
    _check_for_api_error,
    _map_unit,
    RentCafeCredentialError,
    RentCafeAPIError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory SQLite session. Created fresh for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_building(db, **kwargs) -> Building:
    """Insert a Building into the in-memory DB and return it."""
    defaults = {
        "name": "Test Building",
        "url": "https://example.com",
        "last_scrape_status": "never",
        "consecutive_zero_count": 0,
        "rentcafe_property_id": "PROP123",
        "rentcafe_api_token": "TOKEN456",
    }
    defaults.update(kwargs)
    b = Building(**defaults)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


# ---------------------------------------------------------------------------
# Credential error tests
# ---------------------------------------------------------------------------

class TestCredentialValidation:
    def test_scrape_raises_credential_error_when_property_id_missing(self, db):
        """scrape() raises RentCafeCredentialError when rentcafe_property_id is None."""
        building = _make_building(db, rentcafe_property_id=None)
        with pytest.raises(RentCafeCredentialError) as exc_info:
            scrape(building)
        assert "missing RentCafe credentials" in str(exc_info.value)

    def test_scrape_raises_credential_error_when_api_token_missing(self, db):
        """scrape() raises RentCafeCredentialError when rentcafe_api_token is None."""
        building = _make_building(db, rentcafe_api_token=None)
        with pytest.raises(RentCafeCredentialError) as exc_info:
            scrape(building)
        assert "missing RentCafe credentials" in str(exc_info.value)

    def test_scrape_raises_credential_error_when_property_id_empty_string(self, db):
        """scrape() raises RentCafeCredentialError when rentcafe_property_id is empty string."""
        building = _make_building(db, rentcafe_property_id="")
        with pytest.raises(RentCafeCredentialError):
            scrape(building)

    def test_scrape_raises_credential_error_when_api_token_empty_string(self, db):
        """scrape() raises RentCafeCredentialError when rentcafe_api_token is empty string."""
        building = _make_building(db, rentcafe_api_token="")
        with pytest.raises(RentCafeCredentialError):
            scrape(building)


# ---------------------------------------------------------------------------
# Error:1020 API response guard
# ---------------------------------------------------------------------------

class TestAPIErrorGuard:
    def test_check_for_api_error_raises_on_error_1020(self):
        """_check_for_api_error raises RentCafeAPIError when response has Error:1020."""
        with pytest.raises(RentCafeAPIError) as exc_info:
            _check_for_api_error([{"Error": "1020"}])
        assert "RentCafe API error" in str(exc_info.value)
        assert "1020" in str(exc_info.value)

    def test_check_for_api_error_passes_on_valid_data(self):
        """_check_for_api_error does not raise when response contains valid unit data."""
        # Should not raise
        _check_for_api_error([{"UnitNumber": "101", "Beds": "1"}])

    def test_check_for_api_error_passes_on_empty_list(self):
        """_check_for_api_error does not raise on empty list."""
        _check_for_api_error([])

    def test_check_for_api_error_raises_on_any_error_key(self):
        """_check_for_api_error raises for any Error key, not just 1020."""
        with pytest.raises(RentCafeAPIError) as exc_info:
            _check_for_api_error([{"Error": "Invalid API Token"}])
        assert "RentCafe API error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

class TestMapUnit:
    def test_map_unit_basic_fields(self):
        """_map_unit maps primary RentCafe fields to UnitInput dict shape."""
        raw = {
            "UnitNumber": "1A",
            "Beds": "2",
            "Rent": "2500",
            "AvailableDate": "2026-04-01",
            "FloorplanName": "The Lakeview",
            "Baths": "2",
            "SQFT": 950,
        }
        result = _map_unit(raw)
        assert result["unit_number"] == "1A"
        assert result["bed_type"] == "2"
        assert result["rent"] == "2500"
        assert result["availability_date"] == "2026-04-01"
        assert result["floor_plan_name"] == "The Lakeview"
        assert result["baths"] == "2"
        assert result["sqft"] == 950

    def test_map_unit_fallback_field_names(self):
        """_map_unit falls back to alternate field names (ApartmentNumber, Bedrooms, MinimumRent)."""
        raw = {
            "ApartmentNumber": "2B",
            "Bedrooms": "1",
            "MinimumRent": "1800",
            "AvailabilityDate": "2026-05-01",
        }
        result = _map_unit(raw)
        assert result["unit_number"] == "2B"
        assert result["bed_type"] == "1"
        assert result["rent"] == "1800"
        assert result["availability_date"] == "2026-05-01"

    def test_map_unit_missing_optional_fields_are_none(self):
        """_map_unit returns None for optional fields not present in raw data."""
        raw = {
            "UnitNumber": "3C",
            "Beds": "Studio",
            "Rent": "1200",
        }
        result = _map_unit(raw)
        assert result["floor_plan_name"] is None
        assert result["baths"] is None
        assert result["sqft"] is None

    def test_map_unit_defaults_availability_date_when_missing(self):
        """_map_unit defaults availability_date to 'Available Now' when not present."""
        raw = {"UnitNumber": "4D", "Beds": "0", "Rent": "1100"}
        result = _map_unit(raw)
        assert result["availability_date"] == "Available Now"


# ---------------------------------------------------------------------------
# Stub behavior (NotImplementedError when credentials present)
# ---------------------------------------------------------------------------

class TestStubBehavior:
    def test_scrape_raises_not_implemented_when_stub_active(self, db):
        """scrape() raises NotImplementedError when building has valid credentials (stub in place)."""
        building = _make_building(
            db,
            rentcafe_property_id="PROP123",
            rentcafe_api_token="TOKEN456",
        )
        with pytest.raises(NotImplementedError) as exc_info:
            scrape(building)
        assert "RentCafe API stub" in str(exc_info.value)
        assert "PROP123" in str(exc_info.value)

    def test_not_implemented_message_contains_upgrade_path(self, db):
        """NotImplementedError message includes a hint about the credential spike."""
        building = _make_building(db)
        with pytest.raises(NotImplementedError) as exc_info:
            scrape(building)
        error_msg = str(exc_info.value)
        assert "spike" in error_msg.lower() or "stub" in error_msg.lower()
