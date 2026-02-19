"""
RentCafe/Yardi scraper — Tier 1 REST API.

STATUS: STUBBED — API call is not implemented. The scraper structure is complete
and ready for real credentials. To activate:
1. Run the RentCafe credential spike (see RESEARCH.md Open Question 1)
2. Confirm requestType=apartmentavailability field names
3. Replace _fetch_units() stub with the real httpx call
4. Populate rentcafe_property_id and rentcafe_api_token on buildings via DB update

Platform: 'rentcafe'
Coverage: ~220 buildings (55% of total)
API: https://api.rentcafe.com/rentcafeapi.aspx
"""
import httpx
from moxie.db.models import Building

RENTCAFE_API_BASE = "https://api.rentcafe.com/rentcafeapi.aspx"

# Known error response from RentCafe API for invalid/missing credentials
_RENTCAFE_ERROR_KEY = "Error"


class RentCafeCredentialError(ValueError):
    """Raised when a building is missing RentCafe API credentials."""


class RentCafeAPIError(RuntimeError):
    """Raised when the RentCafe API returns an error response (e.g. Error:1020)."""


def _check_for_api_error(data: list) -> None:
    """Raise RentCafeAPIError if response contains an error object."""
    if isinstance(data, list) and data and _RENTCAFE_ERROR_KEY in data[0]:
        raise RentCafeAPIError(f"RentCafe API error: {data[0][_RENTCAFE_ERROR_KEY]}")


def _fetch_units(property_code: str, api_token: str) -> list[dict]:
    """
    STUBBED: Call the RentCafe apartmentavailability endpoint.

    Replace this stub once credentials and field names are confirmed via spike.
    The real implementation uses requestType=apartmentavailability with
    companyCode, propertyCode, apiToken, showallunit=1.

    Spike task: fetch 2-3 known RentCafe building URLs from DB, extract credentials
    from HTML/JS, hit the real endpoint, document exact field names.
    """
    raise NotImplementedError(
        f"RentCafe API stub — credentials not yet confirmed. "
        f"property_code={property_code!r}. "
        "Run the RentCafe credential spike before replacing this stub."
    )


def _map_unit(raw: dict) -> dict:
    """
    Map RentCafe API response fields to UnitInput dict shape.

    Field mapping (from RESEARCH.md + spike to confirm apartmentavailability fields):
      UnitNumber / ApartmentNumber → unit_number
      Beds / Bedrooms             → bed_type
      Rent / MinimumRent          → rent
      AvailableDate               → availability_date
      FloorplanName               → floor_plan_name
      Baths / Bathrooms           → baths
      SQFT                        → sqft

    NOTE: Exact field names for apartmentavailability endpoint are TBD (spike needed).
    This mapper uses the most likely field names based on RESEARCH.md findings.
    """
    return {
        "unit_number": raw.get("UnitNumber") or raw.get("ApartmentNumber", ""),
        "bed_type": str(raw.get("Beds") or raw.get("Bedrooms", "")),
        "rent": raw.get("Rent") or raw.get("MinimumRent", "0"),
        "availability_date": raw.get("AvailableDate") or raw.get("AvailabilityDate", "Available Now"),
        "floor_plan_name": raw.get("FloorplanName"),
        "baths": str(raw.get("Baths") or raw.get("Bathrooms", "")) or None,
        "sqft": raw.get("SQFT"),
    }


def scrape(building: Building) -> list[dict]:
    """
    Scrape unit availability for a RentCafe/Yardi building.

    Requires building.rentcafe_property_id and building.rentcafe_api_token.
    Returns list of raw unit dicts suitable for normalize() / save_scrape_result().

    Raises:
        RentCafeCredentialError: if credentials are missing on the building record.
        RentCafeAPIError: if the API returns an error response (e.g. Error:1020).
        NotImplementedError: until the stub is replaced with a real httpx call.
    """
    if not building.rentcafe_property_id or not building.rentcafe_api_token:
        raise RentCafeCredentialError(
            f"Building {building.id} ({building.name!r}) is missing RentCafe credentials. "
            "Set rentcafe_property_id and rentcafe_api_token on the building record."
        )

    raw_response = _fetch_units(
        property_code=building.rentcafe_property_id,
        api_token=building.rentcafe_api_token,
    )

    _check_for_api_error(raw_response)
    return [_map_unit(item) for item in raw_response]
