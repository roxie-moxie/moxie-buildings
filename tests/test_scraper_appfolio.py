"""
Tests for the AppFolio public listing HTML scraper.

Uses static HTML fixtures for parse tests (no network calls).
Uses pytest-httpx to mock HTTP responses for _fetch_html() tests.
"""
import pytest
from moxie.scrapers.tier2.appfolio import _parse_html, _fetch_html, AppFolioScraperError

# ---------------------------------------------------------------------------
# Static HTML fixture
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<div class="listing-item">
  <span class="bedroom-count">2 Bedrooms</span>
  <span class="price">$2,500</span>
  <span class="available-date">April 1, 2026</span>
  <span class="unit-number">3B</span>
</div>
"""

MULTI_UNIT_HTML = """
<div class="listing-item">
  <span class="bedroom-count">Studio</span>
  <span class="price">$1,300</span>
  <span class="available-date">Available Now</span>
  <span class="unit-number">1A</span>
</div>
<div class="listing-item">
  <span class="bedroom-count">1 Bedroom</span>
  <span class="price">$1,800</span>
  <span class="available-date">March 15, 2026</span>
  <span class="unit-number">2C</span>
</div>
"""

INCOMPLETE_HTML = """
<div class="listing-item">
  <span class="price">$2,500</span>
</div>
"""

NO_UNITS_HTML = """
<html>
  <body>
    <h1>Our Apartment Community</h1>
    <p>All units are currently occupied. Please check back soon.</p>
  </body>
</html>
"""


# ---------------------------------------------------------------------------
# _parse_html() tests — no network, pure HTML parsing
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_parse_html_empty_returns_empty_list(self):
        """Empty string returns empty list without error."""
        result = _parse_html("")
        assert result == []

    def test_parse_html_no_units_returns_empty(self):
        """HTML with no matching listing-item/unit-card selectors returns empty list."""
        result = _parse_html(NO_UNITS_HTML)
        assert result == []

    def test_parse_html_incomplete_rows_skipped(self):
        """Unit rows missing required bed or rent elements are skipped."""
        result = _parse_html(INCOMPLETE_HTML)
        assert result == []

    def test_parse_html_extracts_units(self):
        """HTML with listing-item elements returns correct list of dicts."""
        result = _parse_html(SAMPLE_HTML)
        assert len(result) == 1

    def test_parse_html_unit_fields(self):
        """Extracted unit has correct field values."""
        result = _parse_html(SAMPLE_HTML)
        unit = result[0]
        assert unit["unit_number"] == "3B"
        assert unit["bed_type"] == "2 Bedrooms"
        assert unit["rent"] == "$2,500"
        assert unit["availability_date"] == "April 1, 2026"

    def test_parse_html_multiple_units(self):
        """Multiple listing-item elements all extracted."""
        result = _parse_html(MULTI_UNIT_HTML)
        assert len(result) == 2

    def test_parse_html_returns_list_of_dicts(self):
        """Return type is list[dict] with expected keys."""
        result = _parse_html(MULTI_UNIT_HTML)
        for unit in result:
            assert isinstance(unit, dict)
            assert "unit_number" in unit
            assert "bed_type" in unit
            assert "rent" in unit
            assert "availability_date" in unit

    def test_parse_html_missing_unit_number_defaults_to_na(self):
        """Unit rows without unit number element default to 'N/A'."""
        html = """
        <div class="listing-item">
          <span class="bedroom-count">Studio</span>
          <span class="price">$1,200</span>
          <span class="available-date">Available Now</span>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["unit_number"] == "N/A"

    def test_parse_html_missing_availability_defaults_to_available_now(self):
        """Unit rows without availability element default to 'Available Now'."""
        html = """
        <div class="listing-item">
          <span class="bedroom-count">1 Bedroom</span>
          <span class="price">$1,600</span>
          <span class="unit-number">4D</span>
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
        """Non-2xx HTTP response raises AppFolioScraperError."""
        httpx_mock.add_response(
            url="https://example.appfolio.com/listings",
            status_code=404,
        )
        with pytest.raises(AppFolioScraperError) as exc_info:
            _fetch_html("https://example.appfolio.com/listings")
        assert "404" in str(exc_info.value)

    def test_fetch_html_raises_on_500(self, httpx_mock):
        """Server error (500) raises AppFolioScraperError."""
        httpx_mock.add_response(
            url="https://example.appfolio.com/listings",
            status_code=500,
        )
        with pytest.raises(AppFolioScraperError) as exc_info:
            _fetch_html("https://example.appfolio.com/listings")
        assert "500" in str(exc_info.value)

    def test_fetch_html_returns_content_on_200(self, httpx_mock):
        """200 OK response returns the HTML text."""
        expected_html = "<html><body>AppFolio Listings</body></html>"
        httpx_mock.add_response(
            url="https://example.appfolio.com/listings",
            status_code=200,
            text=expected_html,
        )
        result = _fetch_html("https://example.appfolio.com/listings")
        assert result == expected_html

    def test_fetch_html_error_message_includes_url(self, httpx_mock):
        """AppFolioScraperError message includes the failing URL."""
        url = "https://example.appfolio.com/listings"
        httpx_mock.add_response(url=url, status_code=403)
        with pytest.raises(AppFolioScraperError) as exc_info:
            _fetch_html(url)
        assert url in str(exc_info.value)
