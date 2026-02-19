"""
Tests for RentCafe/Yardi scraper — real implementation (spike completed 2026-02-18).

Covers:
- Missing credential detection (RentCafeCredentialError)
- Error:1020 API response guard (RentCafeAPIError)
- _map_unit() field mapping with confirmed field names
- _is_available() availability filter
- scrape() full flow with mocked httpx (pytest-httpx)

All confirmed field names from live apartmentavailability API response:
  ApartmentName, Beds, MinimumRent, AvailableDate, FloorplanName, Baths, SQFT
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pytest_httpx import HTTPXMock

from moxie.db.models import Base, Building
from moxie.scrapers.tier1.rentcafe import (
    RENTCAFE_API_BASE,
    scrape,
    _check_for_api_error,
    _fetch_units,
    _is_available,
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
        "rentcafe_property_id": "dey",
        "rentcafe_api_token": "8a92be8b-6c61-4be5-983d-547c0c68c544",
    }
    defaults.update(kwargs)
    b = Building(**defaults)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


# Realistic unit records using confirmed field names from live API
_UNIT_AVAILABLE = {
    "PropertyId": "1350140",
    "ApartmentId": "11111",
    "ApartmentName": "110",
    "FloorplanName": "A2",
    "Beds": 1,
    "Baths": 1,
    "SQFT": 750,
    "MinimumRent": "$2,515",
    "MaximumRent": "$3,850",
    "AvailableDate": "3/24/2026",
    "UnitStatus": "Notice Unrented",
    "Deposit": "",
    "ApplyOnlineURL": "https://example.securecafe.com/apply",
    "Specials": "",
    "Amenities": "",
}

_UNIT_OCCUPIED = {
    "PropertyId": "1350140",
    "ApartmentId": "22222",
    "ApartmentName": "448",
    "FloorplanName": "A1",
    "Beds": 1,
    "Baths": 1,
    "SQFT": 720,
    "MinimumRent": "$2,510",
    "MaximumRent": "$4,115",
    "AvailableDate": "",        # Empty = not available
    "UnitStatus": "Occupied No Notice",
    "Deposit": "",
    "ApplyOnlineURL": "",
    "Specials": "",
    "Amenities": "",
}

_UNIT_STUDIO_AVAILABLE = {
    "PropertyId": "1350140",
    "ApartmentId": "33333",
    "ApartmentName": "201",
    "FloorplanName": "S1",
    "Beds": 0,          # 0 = Studio
    "Baths": 1,
    "SQFT": 500,
    "MinimumRent": "$1,950",
    "MaximumRent": "$2,500",
    "AvailableDate": "4/1/2026",
    "UnitStatus": "Vacant Unrented",
    "Deposit": "",
    "ApplyOnlineURL": "",
    "Specials": "",
    "Amenities": "",
}


# ---------------------------------------------------------------------------
# Credential validation
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
        _check_for_api_error([{"ApartmentName": "101", "Beds": 1}])  # should not raise

    def test_check_for_api_error_passes_on_empty_list(self):
        """_check_for_api_error does not raise on empty list."""
        _check_for_api_error([])

    def test_check_for_api_error_raises_on_any_error_key(self):
        """_check_for_api_error raises for any Error key value, not just 1020."""
        with pytest.raises(RentCafeAPIError) as exc_info:
            _check_for_api_error([{"Error": "Invalid API Token"}])
        assert "RentCafe API error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Availability filter
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def test_unit_with_available_date_is_available(self):
        """_is_available returns True when AvailableDate is a non-empty string."""
        assert _is_available({"AvailableDate": "3/24/2026"}) is True

    def test_unit_with_empty_available_date_is_not_available(self):
        """_is_available returns False when AvailableDate is an empty string."""
        assert _is_available({"AvailableDate": ""}) is False

    def test_unit_with_missing_available_date_is_not_available(self):
        """_is_available returns False when AvailableDate key is absent."""
        assert _is_available({"ApartmentName": "101"}) is False


# ---------------------------------------------------------------------------
# Field mapping (confirmed field names from live API)
# ---------------------------------------------------------------------------

class TestMapUnit:
    def test_map_unit_confirmed_field_names(self):
        """_map_unit correctly maps confirmed apartmentavailability field names."""
        result = _map_unit(_UNIT_AVAILABLE)
        assert result["unit_number"] == "110"
        assert result["bed_type"] == "1"
        assert result["rent"] == "$2,515"
        assert result["availability_date"] == "3/24/2026"
        assert result["floor_plan_name"] == "A2"
        assert result["baths"] == "1"
        assert result["sqft"] == 750

    def test_map_unit_studio_beds_zero(self):
        """_map_unit maps Beds=0 (Studio) as the string '0'."""
        result = _map_unit(_UNIT_STUDIO_AVAILABLE)
        assert result["unit_number"] == "201"
        assert result["bed_type"] == "0"

    def test_map_unit_falls_back_to_max_rent_when_min_absent(self):
        """_map_unit uses MaximumRent when MinimumRent is absent or falsy."""
        raw = {**_UNIT_AVAILABLE, "MinimumRent": "", "MaximumRent": "$3,850"}
        result = _map_unit(raw)
        assert result["rent"] == "$3,850"

    def test_map_unit_defaults_availability_date_when_empty(self):
        """_map_unit defaults availability_date to 'Available Now' when AvailableDate is empty."""
        raw = {**_UNIT_AVAILABLE, "AvailableDate": ""}
        result = _map_unit(raw)
        assert result["availability_date"] == "Available Now"

    def test_map_unit_optional_fields_none_when_absent(self):
        """_map_unit returns None for optional fields not present in raw data."""
        raw = {"ApartmentName": "101", "Beds": 2, "MinimumRent": "$2,000", "AvailableDate": "5/1/2026"}
        result = _map_unit(raw)
        assert result["floor_plan_name"] is None
        assert result["baths"] is None
        assert result["sqft"] is None


# ---------------------------------------------------------------------------
# HTTP fetch (mocked)
# ---------------------------------------------------------------------------

class TestFetchUnits:
    def test_fetch_units_calls_correct_endpoint(self, httpx_mock: HTTPXMock):
        """_fetch_units sends GET to rentcafeapi.aspx with correct parameters."""
        httpx_mock.add_response(
            url=f"{RENTCAFE_API_BASE}?requestType=apartmentavailability"
                "&VoyagerPropertyCode=dey&apiToken=TOKEN&showallunit=1",
            json=[_UNIT_AVAILABLE],
        )
        result = _fetch_units("dey", "TOKEN")
        assert len(result) == 1
        assert result[0]["ApartmentName"] == "110"

    def test_fetch_units_returns_all_units_including_occupied(self, httpx_mock: HTTPXMock):
        """_fetch_units returns raw response including occupied units (filtering is caller's job)."""
        httpx_mock.add_response(
            url=f"{RENTCAFE_API_BASE}?requestType=apartmentavailability"
                "&VoyagerPropertyCode=dey&apiToken=TOKEN&showallunit=1",
            json=[_UNIT_AVAILABLE, _UNIT_OCCUPIED],
        )
        result = _fetch_units("dey", "TOKEN")
        assert len(result) == 2

    def test_fetch_units_raises_on_http_error(self, httpx_mock: HTTPXMock):
        """_fetch_units raises httpx.HTTPStatusError on non-2xx response."""
        import httpx as httpx_lib
        httpx_mock.add_response(
            url=f"{RENTCAFE_API_BASE}?requestType=apartmentavailability"
                "&VoyagerPropertyCode=dey&apiToken=TOKEN&showallunit=1",
            status_code=500,
        )
        with pytest.raises(httpx_lib.HTTPStatusError):
            _fetch_units("dey", "TOKEN")


# ---------------------------------------------------------------------------
# Full scrape() flow
# ---------------------------------------------------------------------------

class TestScrapeIntegration:
    def test_scrape_returns_only_available_units(self, db, httpx_mock: HTTPXMock):
        """scrape() returns only units with non-empty AvailableDate."""
        httpx_mock.add_response(
            json=[_UNIT_AVAILABLE, _UNIT_OCCUPIED, _UNIT_STUDIO_AVAILABLE],
        )
        building = _make_building(db)
        result = scrape(building)
        # Only _UNIT_AVAILABLE and _UNIT_STUDIO_AVAILABLE have AvailableDate
        assert len(result) == 2
        unit_numbers = {r["unit_number"] for r in result}
        assert unit_numbers == {"110", "201"}

    def test_scrape_raises_api_error_on_error_1020(self, db, httpx_mock: HTTPXMock):
        """scrape() raises RentCafeAPIError when API returns Error:1020."""
        httpx_mock.add_response(json=[{"Error": "1020"}])
        building = _make_building(db)
        with pytest.raises(RentCafeAPIError):
            scrape(building)

    def test_scrape_returns_empty_list_when_no_units_available(self, db, httpx_mock: HTTPXMock):
        """scrape() returns [] when all units are occupied (no AvailableDate)."""
        httpx_mock.add_response(json=[_UNIT_OCCUPIED])
        building = _make_building(db)
        result = scrape(building)
        assert result == []

    def test_scrape_uses_building_credentials(self, db, httpx_mock: HTTPXMock):
        """scrape() passes building.rentcafe_property_id and rentcafe_api_token to the API."""
        httpx_mock.add_response(json=[_UNIT_AVAILABLE])
        building = _make_building(db, rentcafe_property_id="myprop", rentcafe_api_token="mytoken")
        scrape(building)
        request = httpx_mock.get_requests()[0]
        assert "VoyagerPropertyCode=myprop" in str(request.url)
        assert "apiToken=mytoken" in str(request.url)
