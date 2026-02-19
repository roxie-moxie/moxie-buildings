"""
Tests for the Funnel/Nestio HTML scraper.

Uses static HTML fixtures for parse tests (no network calls).
Uses pytest-httpx to mock HTTP responses for _fetch_html() tests.

HTML structure is based on verified inspection of real Funnel-powered apartment sites
(e.g., imprintapts.com/floorplans/). Key attributes:
  - div.floor-plan[data-beds][data-price][data-baths][data-first-available-date]
  - h3.name (floor plan name, used as unit_number)
  - p.bedrooms, p.bathrooms, p.square-feet
  - p.starting-price (formatted, e.g., "Starting at $2,565")
  - p.first-available-date (e.g., "Available Now" or "Available 03/25/2026")
  - data-price="-1" means "Call for pricing" — excluded from results
"""
import pytest
from moxie.scrapers.tier2.funnel import _parse_html, _fetch_html, _normalize_floorplans_url, FunnelScraperError

# ---------------------------------------------------------------------------
# Static HTML fixture (verified against real Funnel/Greystar apartment pages)
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<div class="floor-plan selected-baths selected-beds selected-date selected-price"
     data-baths="1.00" data-beds="1" data-first-available-date="2026-02-13" data-price="2565">
  <h3 class="name">One Bedroom E</h3>
  <p class="bedrooms">1 Bed</p>
  <p class="bathrooms">1 Bath</p>
  <p class="square-feet">771 sf</p>
  <p class="available-units">3 Apartments Available</p>
  <p class="first-available-date">Available Now</p>
  <p class="starting-price">Starting at $2,565</p>
</div>
<div class="floor-plan selected-baths selected-beds selected-date selected-price"
     data-baths="1.00" data-beds="Studio" data-first-available-date="2026-03-25" data-price="1976">
  <h3 class="name">Studio C</h3>
  <p class="bedrooms">Studio</p>
  <p class="bathrooms">1 Bath</p>
  <p class="square-feet">496 sf</p>
  <p class="available-units">1 Apartment Available</p>
  <p class="first-available-date">Available 03/25/2026</p>
  <p class="starting-price">Starting at $1,976</p>
</div>
"""

CALL_FOR_PRICING_HTML = """
<div class="floor-plan" data-baths="2.00" data-beds="2" data-price="-1">
  <h3 class="name">Two Bedroom A</h3>
  <p class="bedrooms">2 Beds</p>
  <p class="bathrooms">2 Baths</p>
  <p class="square-feet">1074 sf</p>
  <p class="available-units">Call for pricing and availability</p>
  <p class="first-available-date"></p>
  <p class="starting-price"></p>
</div>
"""

NO_UNITS_HTML = """
<html>
  <body>
    <h1>Welcome to Our Community</h1>
    <p>No units currently available. Check back soon!</p>
  </body>
</html>
"""


# ---------------------------------------------------------------------------
# _normalize_floorplans_url() tests
# ---------------------------------------------------------------------------

class TestNormalizeFloorplansUrl:
    def test_appends_floorplans_to_base_url(self):
        """Base URL without /floorplans gets /floorplans/ appended."""
        result = _normalize_floorplans_url("https://imprintapts.com/")
        assert result == "https://imprintapts.com/floorplans/"

    def test_url_already_on_floorplans_unchanged(self):
        """URL already on /floorplans is returned as-is."""
        result = _normalize_floorplans_url("https://imprintapts.com/floorplans/")
        assert "/floorplans" in result

    def test_handles_url_without_trailing_slash(self):
        """URL without trailing slash still gets /floorplans/ appended correctly."""
        result = _normalize_floorplans_url("https://imprintapts.com")
        assert result == "https://imprintapts.com/floorplans/"


# ---------------------------------------------------------------------------
# _parse_html() tests — no network, pure HTML parsing
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_parse_html_empty_returns_empty_list(self):
        """Empty string returns empty list without error."""
        result = _parse_html("")
        assert result == []

    def test_parse_html_no_units_returns_empty(self):
        """HTML with no matching selectors returns empty list."""
        result = _parse_html(NO_UNITS_HTML)
        assert result == []

    def test_parse_html_call_for_pricing_skipped(self):
        """Floor plans with data-price='-1' (call for pricing) are excluded."""
        result = _parse_html(CALL_FOR_PRICING_HTML)
        assert result == []

    def test_parse_html_extracts_units(self):
        """HTML with floor-plan divs with data-beds returns correct list of dicts."""
        result = _parse_html(SAMPLE_HTML)
        assert len(result) == 2

    def test_parse_html_first_unit_fields(self):
        """First extracted floor plan has correct field values."""
        result = _parse_html(SAMPLE_HTML)
        first = result[0]
        assert first["unit_number"] == "One Bedroom E"
        assert first["floor_plan_name"] == "One Bedroom E"
        assert first["bed_type"] == "1 Bed"
        assert first["rent"] == "Starting at $2,565"
        assert first["availability_date"] == "Available Now"
        assert first["baths"] == "1 Bath"
        assert first["sqft"] == 771

    def test_parse_html_second_unit_fields(self):
        """Second extracted floor plan has correct field values."""
        result = _parse_html(SAMPLE_HTML)
        second = result[1]
        assert second["unit_number"] == "Studio C"
        assert second["bed_type"] == "Studio"
        assert second["rent"] == "Starting at $1,976"
        assert second["availability_date"] == "Available 03/25/2026"
        assert second["sqft"] == 496

    def test_parse_html_returns_list_of_dicts(self):
        """Return type is list[dict] with expected keys."""
        result = _parse_html(SAMPLE_HTML)
        for unit in result:
            assert isinstance(unit, dict)
            assert "unit_number" in unit
            assert "floor_plan_name" in unit
            assert "bed_type" in unit
            assert "rent" in unit
            assert "availability_date" in unit

    def test_parse_html_missing_name_defaults_to_na(self):
        """Floor plan without h3.name defaults unit_number to 'N/A'."""
        html = """
        <div class="floor-plan" data-beds="1" data-baths="1.00" data-price="2000">
          <p class="bedrooms">1 Bed</p>
          <p class="starting-price">Starting at $2,000</p>
          <p class="first-available-date">Available Now</p>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["unit_number"] == "N/A"

    def test_parse_html_missing_availability_defaults_to_available_now(self):
        """Floor plan without p.first-available-date defaults to 'Available Now'."""
        html = """
        <div class="floor-plan" data-beds="Studio" data-baths="1.00" data-price="1500">
          <h3 class="name">Studio A</h3>
          <p class="bedrooms">Studio</p>
          <p class="starting-price">Starting at $1,500</p>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["availability_date"] == "Available Now"


# ---------------------------------------------------------------------------
# _fetch_html() tests — httpx mocked via pytest-httpx
# ---------------------------------------------------------------------------

class TestFetchHtml:
    def test_fetch_html_raises_on_non_200(self, httpx_mock):
        """Non-2xx HTTP response raises FunnelScraperError."""
        httpx_mock.add_response(
            url="https://imprintapts.com/floorplans/",
            status_code=404,
        )
        with pytest.raises(FunnelScraperError) as exc_info:
            _fetch_html("https://imprintapts.com/floorplans/")
        assert "404" in str(exc_info.value)

    def test_fetch_html_raises_on_500(self, httpx_mock):
        """Server error (500) raises FunnelScraperError."""
        httpx_mock.add_response(
            url="https://imprintapts.com/floorplans/",
            status_code=500,
        )
        with pytest.raises(FunnelScraperError) as exc_info:
            _fetch_html("https://imprintapts.com/floorplans/")
        assert "500" in str(exc_info.value)

    def test_fetch_html_returns_html_on_200(self, httpx_mock):
        """200 OK response returns the HTML text."""
        expected_html = "<html><body>Listing page</body></html>"
        httpx_mock.add_response(
            url="https://imprintapts.com/floorplans/",
            status_code=200,
            text=expected_html,
        )
        result = _fetch_html("https://imprintapts.com/floorplans/")
        assert result == expected_html

    def test_fetch_html_error_message_includes_url(self, httpx_mock):
        """FunnelScraperError message includes the failing URL."""
        url = "https://imprintapts.com/floorplans/"
        httpx_mock.add_response(url=url, status_code=403)
        with pytest.raises(FunnelScraperError) as exc_info:
            _fetch_html(url)
        assert url in str(exc_info.value)
