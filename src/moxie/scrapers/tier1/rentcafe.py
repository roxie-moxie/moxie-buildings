"""
RentCafe/Yardi scraper — Tier 1 REST API.

Credential spike completed 2026-02-18. All field names and parameters are confirmed
from a live apartmentavailability API response (338-unit property, "dey" property code).

API endpoint: https://api.rentcafe.com/rentcafeapi.aspx
Required params: requestType=apartmentavailability, VoyagerPropertyCode, apiToken, showallunit=1

Confirmed apartmentavailability response fields:
  ApartmentName   — unit identifier (e.g. "110", "448")
  FloorplanName   — floor plan label (e.g. "A2", "B10")
  Beds            — bedroom count as integer (0=Studio, 1=1BR, 2=2BR, ...)
  Baths           — bathroom count as integer
  SQFT            — square footage as integer
  MinimumRent     — formatted rent string (e.g. "$2,515")
  MaximumRent     — formatted max rent string
  AvailableDate   — move-in date string in M/D/YYYY format, or "" if not available
  UnitStatus      — status string (e.g. "Notice Unrented", "Occupied No Notice")
  ApartmentId     — internal Yardi unit ID (not used)
  PropertyId      — internal Yardi property ID (not used)
  VoyagerPropertyCode — echoed back from request

Availability filter: only units where AvailableDate is non-empty are returned.
Units with empty AvailableDate are occupied or not actively listed.

DB credential mapping:
  building.rentcafe_property_id → VoyagerPropertyCode (e.g. "dey")
  building.rentcafe_api_token   → apiToken (UUID-like string)

Platform: 'rentcafe'
Coverage: ~220 buildings (55% of total)
"""
from urllib.parse import unquote

import httpx
from moxie.db.models import Building

RENTCAFE_API_BASE = "https://api.rentcafe.com/rentcafeapi.aspx"

# Error key returned by the API for invalid/missing credentials
_RENTCAFE_ERROR_KEY = "Error"


class RentCafeCredentialError(ValueError):
    """Raised when a building is missing RentCafe API credentials."""


class RentCafeAPIError(RuntimeError):
    """Raised when the RentCafe API returns an error response (e.g. Error:1020)."""


def _check_for_api_error(data: list) -> None:
    """Raise RentCafeAPIError if the response is an error object like [{"Error": "1020"}]."""
    if isinstance(data, list) and data and _RENTCAFE_ERROR_KEY in data[0]:
        raise RentCafeAPIError(f"RentCafe API error: {data[0][_RENTCAFE_ERROR_KEY]}")


def _fetch_units(voyager_property_code: str, api_token: str) -> list[dict]:
    """
    Call the RentCafe apartmentavailability endpoint.

    Returns all units for the property (available and occupied).
    Callers should filter with _is_available() before mapping.

    Raises:
        httpx.HTTPStatusError: on non-2xx response.
    """
    response = httpx.get(
        RENTCAFE_API_BASE,
        params={
            "requestType": "apartmentavailability",
            "VoyagerPropertyCode": voyager_property_code,
            "apiToken": api_token,
            "showallunit": "1",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _is_available(raw: dict) -> bool:
    """
    Return True if the unit is actively listed as available for rent.

    RentCafe sets AvailableDate to a non-empty date string (M/D/YYYY) for
    units that are available for rent now or in the future. Occupied units
    with no listed availability have an empty AvailableDate.
    """
    return bool(raw.get("AvailableDate"))


def _map_unit(raw: dict) -> dict:
    """
    Map a confirmed RentCafe apartmentavailability record to UnitInput dict shape.

    Field names confirmed from live API response (2026-02-18):
      ApartmentName → unit_number (the apartment number, e.g. "110", "448")
      Beds          → bed_type (integer; normalizer converts to canonical string)
      MinimumRent   → rent (formatted string, e.g. "$2,515")
      AvailableDate → availability_date (M/D/YYYY; empty string → "Available Now")
      FloorplanName → floor_plan_name
      Baths         → baths
      SQFT          → sqft
    """
    return {
        "unit_number": raw.get("ApartmentName", ""),
        "bed_type": str(raw.get("Beds", "")),
        "rent": raw.get("MinimumRent") or raw.get("MaximumRent", "0"),
        "availability_date": raw.get("AvailableDate") or "Available Now",
        "floor_plan_name": raw.get("FloorplanName"),
        "baths": str(raw.get("Baths", "")) or None,
        "sqft": raw.get("SQFT"),
    }


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability for a RentCafe/Yardi building via the REST API.

    Requires building.rentcafe_property_id (VoyagerPropertyCode) and
    building.rentcafe_api_token to be populated on the building record.

    Populate these by:
    1. Fetching the building's RentCafe page and extracting credentials from
       embedded JavaScript (VoyagerPropertyCode + apiToken), OR
    2. Setting them manually in the DB or via the Google Sheet.

    Returns list of raw unit dicts for normalize() / save_scrape_result().
    Only units with a non-empty AvailableDate are included.

    Raises:
        RentCafeCredentialError: if credentials are missing on the building record.
        RentCafeAPIError: if the API returns an error response (e.g. Error:1020).
        httpx.HTTPStatusError: on non-2xx HTTP response from the API.
    """
    if not building.rentcafe_property_id or not building.rentcafe_api_token:
        raise RentCafeCredentialError(
            f"Building {building.id} ({building.name!r}) is missing RentCafe credentials. "
            "Set rentcafe_property_id (VoyagerPropertyCode) and rentcafe_api_token on the "
            "building record. These are embedded in the building's RentCafe page JavaScript."
        )

    # Tokens may be stored URL-encoded (%3d instead of =) from browser capture.
    # Decode before passing to httpx, which will re-encode as needed.
    raw_response = _fetch_units(
        voyager_property_code=building.rentcafe_property_id,
        api_token=unquote(building.rentcafe_api_token),
    )

    _check_for_api_error(raw_response)

    # Filter to available units only before mapping
    return [_map_unit(item) for item in raw_response if _is_available(item)]
