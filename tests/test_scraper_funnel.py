"""
Tests for the Funnel/Nestio HTML scraper.

Uses static HTML fixtures for parse tests (no network calls).
Uses pytest-httpx to mock HTTP responses for _fetch_html() tests.
"""
import pytest
from moxie.scrapers.tier2.funnel import _parse_html, _fetch_html, FunnelScraperError

# ---------------------------------------------------------------------------
# Static HTML fixture
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<div class="unit-listing">
  <span class="bedrooms">1 Bed</span>
  <span class="price">$1,800/mo</span>
  <span class="availability">Available Now</span>
  <span class="unit-number">101</span>
</div>
<div class="unit-listing">
  <span class="bedrooms">Studio</span>
  <span class="price">$1,400/mo</span>
  <span class="availability">March 1, 2026</span>
  <span class="unit-number">202</span>
</div>
"""

INCOMPLETE_HTML = """
<div class="unit-listing">
  <span class="price">$1,800/mo</span>
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

    def test_parse_html_incomplete_rows_skipped(self):
        """Unit rows missing required bed or rent elements are skipped."""
        result = _parse_html(INCOMPLETE_HTML)
        assert result == []

    def test_parse_html_extracts_units(self):
        """HTML with unit-listing elements returns correct list of dicts."""
        result = _parse_html(SAMPLE_HTML)
        assert len(result) == 2

    def test_parse_html_first_unit_fields(self):
        """First extracted unit has correct field values."""
        result = _parse_html(SAMPLE_HTML)
        first = result[0]
        assert first["unit_number"] == "101"
        assert first["bed_type"] == "1 Bed"
        assert first["rent"] == "$1,800/mo"
        assert first["availability_date"] == "Available Now"

    def test_parse_html_second_unit_fields(self):
        """Second extracted unit has correct field values."""
        result = _parse_html(SAMPLE_HTML)
        second = result[1]
        assert second["unit_number"] == "202"
        assert second["bed_type"] == "Studio"
        assert second["rent"] == "$1,400/mo"
        assert second["availability_date"] == "March 1, 2026"

    def test_parse_html_returns_list_of_dicts(self):
        """Return type is list[dict] with expected keys."""
        result = _parse_html(SAMPLE_HTML)
        for unit in result:
            assert isinstance(unit, dict)
            assert "unit_number" in unit
            assert "bed_type" in unit
            assert "rent" in unit
            assert "availability_date" in unit

    def test_parse_html_missing_availability_defaults_to_available_now(self):
        """Unit rows without availability element default to 'Available Now'."""
        html = """
        <div class="unit-listing">
          <span class="bedrooms">2 Bed</span>
          <span class="price">$2,200/mo</span>
          <span class="unit-number">305</span>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["availability_date"] == "Available Now"

    def test_parse_html_missing_unit_number_defaults_to_na(self):
        """Unit rows without a unit number element default to 'N/A'."""
        html = """
        <div class="unit-listing">
          <span class="bedrooms">Studio</span>
          <span class="price">$1,200/mo</span>
          <span class="availability">Available Now</span>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["unit_number"] == "N/A"


# ---------------------------------------------------------------------------
# _fetch_html() tests — httpx mocked via pytest-httpx
# ---------------------------------------------------------------------------

class TestFetchHtml:
    def test_fetch_html_raises_on_non_200(self, httpx_mock):
        """Non-2xx HTTP response raises FunnelScraperError."""
        httpx_mock.add_response(
            url="https://example.funnelleasing.com/listings",
            status_code=404,
        )
        with pytest.raises(FunnelScraperError) as exc_info:
            _fetch_html("https://example.funnelleasing.com/listings")
        assert "404" in str(exc_info.value)

    def test_fetch_html_raises_on_500(self, httpx_mock):
        """Server error (500) raises FunnelScraperError."""
        httpx_mock.add_response(
            url="https://example.funnelleasing.com/listings",
            status_code=500,
        )
        with pytest.raises(FunnelScraperError) as exc_info:
            _fetch_html("https://example.funnelleasing.com/listings")
        assert "500" in str(exc_info.value)

    def test_fetch_html_returns_html_on_200(self, httpx_mock):
        """200 OK response returns the HTML text."""
        expected_html = "<html><body>Listing page</body></html>"
        httpx_mock.add_response(
            url="https://example.funnelleasing.com/listings",
            status_code=200,
            text=expected_html,
        )
        result = _fetch_html("https://example.funnelleasing.com/listings")
        assert result == expected_html

    def test_fetch_html_error_message_includes_url(self, httpx_mock):
        """FunnelScraperError message includes the failing URL."""
        url = "https://example.funnelleasing.com/listings"
        httpx_mock.add_response(url=url, status_code=403)
        with pytest.raises(FunnelScraperError) as exc_info:
            _fetch_html(url)
        assert url in str(exc_info.value)
