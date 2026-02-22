"""
Tests for the AppFolio public listing HTML scraper.

Uses static HTML fixtures for parse tests (no network calls).
Uses pytest-httpx to mock HTTP responses for _fetch_html() tests.
"""
import pytest
from moxie.scrapers.tier2.appfolio import _parse_listings_html, _fetch_html, AppFolioScraperError

# ---------------------------------------------------------------------------
# Static HTML fixture
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<div class="js-listing-item">
  <img alt="123 Main St , Unit 3B, Chicago, IL 60610" />
  <div class="detail-box__value">$2,500</div>
  <div class="detail-box__value">2 bd / 1 ba</div>
  <div class="js-listing-available">April 1, 2026</div>
</div>
"""

MULTI_UNIT_HTML = """
<div class="js-listing-item">
  <img alt="123 Main St , Unit 1A, Chicago, IL 60610" />
  <div class="detail-box__value">$1,300</div>
  <div class="detail-box__value">0 bd / 1 ba</div>
  <div class="js-listing-available">Now</div>
</div>
<div class="js-listing-item">
  <img alt="123 Main St , Unit 2C, Chicago, IL 60610" />
  <div class="detail-box__value">$1,800</div>
  <div class="detail-box__value">1 bd / 1 ba</div>
  <div class="js-listing-available">March 15, 2026</div>
</div>
"""

INCOMPLETE_HTML = """
<div class="js-listing-item">
  <img alt="123 Main St , Chicago, IL 60610" />
  <div class="detail-box__value">$2,500</div>
  <div class="detail-box__value">2 bd / 1 ba</div>
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
# _parse_listings_html() tests — no network, pure HTML parsing
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_parse_html_empty_returns_empty_list(self):
        """Empty string returns empty list without error."""
        result = _parse_listings_html("")
        assert result == []

    def test_parse_html_no_units_returns_empty(self):
        """HTML with no matching .js-listing-item selectors returns empty list."""
        result = _parse_listings_html(NO_UNITS_HTML)
        assert result == []

    def test_parse_html_incomplete_rows_skipped(self):
        """Cards without 'Unit NNN' in img alt are skipped entirely."""
        result = _parse_listings_html(INCOMPLETE_HTML)
        assert result == []

    def test_parse_html_extracts_units(self):
        """HTML with .js-listing-item elements returns correct list of dicts."""
        result = _parse_listings_html(SAMPLE_HTML)
        assert len(result) == 1

    def test_parse_html_unit_fields(self):
        """Extracted unit has correct field values."""
        result = _parse_listings_html(SAMPLE_HTML)
        unit = result[0]
        assert unit["unit_number"] == "3B"
        assert unit["bed_type"] == "2 bd / 1 ba"
        assert unit["rent"] == "$2,500"
        assert unit["availability_date"] == "April 1, 2026"

    def test_parse_html_multiple_units(self):
        """Multiple .js-listing-item elements all extracted."""
        result = _parse_listings_html(MULTI_UNIT_HTML)
        assert len(result) == 2

    def test_parse_html_returns_list_of_dicts(self):
        """Return type is list[dict] with expected keys."""
        result = _parse_listings_html(MULTI_UNIT_HTML)
        for unit in result:
            assert isinstance(unit, dict)
            assert "unit_number" in unit
            assert "bed_type" in unit
            assert "rent" in unit
            assert "availability_date" in unit

    def test_parse_html_missing_unit_number_skipped(self):
        """Cards without 'Unit NNN' in img alt are skipped entirely."""
        html = """
        <div class="js-listing-item">
          <img alt="123 Main St , Chicago, IL 60610" />
          <div class="detail-box__value">$1,200</div>
          <div class="detail-box__value">0 bd / 1 ba</div>
          <div class="js-listing-available">Now</div>
        </div>
        """
        result = _parse_listings_html(html)
        assert result == []

    def test_parse_html_missing_availability_defaults_to_available_now(self):
        """Cards without .js-listing-available default to 'Available Now'."""
        html = """
        <div class="js-listing-item">
          <img alt="123 Main St , Unit 4D, Chicago, IL 60610" />
          <div class="detail-box__value">$1,600</div>
          <div class="detail-box__value">1 bd / 1 ba</div>
        </div>
        """
        result = _parse_listings_html(html)
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
