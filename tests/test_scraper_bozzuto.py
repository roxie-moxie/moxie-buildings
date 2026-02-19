"""
Tests for the Bozzuto HTML scraper.

Covers:
- _parse_html(): empty HTML, correct extraction from Bozzuto-like markup
- _fetch_html(): bot-detection on 403/429/503, generic HTTP error, 200 success
- scrape(): end-to-end with mocked HTTP error

Uses pytest-httpx to mock HTTP responses without real network calls.
"""
import pytest
import httpx
from pytest_httpx import HTTPXMock
from unittest.mock import MagicMock
from moxie.scrapers.tier2.bozzuto import (
    _fetch_html,
    _parse_html,
    scrape,
    BozzutoScraperError,
)


# ---------------------------------------------------------------------------
# Sample HTML fixture
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<div class="available-apartment">
  <span class="bedroom-count">1 Bedroom</span>
  <span class="fp-rent">$2,100</span>
  <span class="fp-available">March 15, 2026</span>
  <span class="fp-unit">1A</span>
</div>
<div class="available-apartment">
  <span class="bedroom-count">Studio</span>
  <span class="fp-rent">$1,650</span>
  <span class="fp-available">Available Now</span>
  <span class="fp-unit">5C</span>
</div>
"""

EMPTY_HTML = "<html><body><p>No units available</p></body></html>"

# HTML missing rent (should be skipped)
INCOMPLETE_UNIT_HTML = """
<div class="available-apartment">
  <span class="bedroom-count">1 Bedroom</span>
</div>
"""


# ---------------------------------------------------------------------------
# Tests: _parse_html()
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_parse_html_empty_returns_empty_list(self):
        """HTML with no recognizable unit containers returns empty list."""
        result = _parse_html(EMPTY_HTML)
        assert result == []

    def test_parse_html_extracts_units(self):
        """Bozzuto-like HTML fixture returns list of unit dicts."""
        result = _parse_html(SAMPLE_HTML)
        assert len(result) == 2

    def test_parse_html_unit_numbers_extracted(self):
        """Unit numbers extracted from .fp-unit elements."""
        result = _parse_html(SAMPLE_HTML)
        unit_numbers = {u["unit_number"] for u in result}
        assert "1A" in unit_numbers
        assert "5C" in unit_numbers

    def test_parse_html_bed_types_extracted(self):
        """Bed types extracted from .bedroom-count elements."""
        result = _parse_html(SAMPLE_HTML)
        bed_types = {u["bed_type"] for u in result}
        assert "1 Bedroom" in bed_types
        assert "Studio" in bed_types

    def test_parse_html_rents_extracted(self):
        """Rent strings extracted from .fp-rent elements."""
        result = _parse_html(SAMPLE_HTML)
        rents = {u["rent"] for u in result}
        assert "$2,100" in rents
        assert "$1,650" in rents

    def test_parse_html_availability_dates_extracted(self):
        """Availability dates extracted from .fp-available elements."""
        result = _parse_html(SAMPLE_HTML)
        dates = {u["availability_date"] for u in result}
        assert "March 15, 2026" in dates
        assert "Available Now" in dates

    def test_parse_html_skips_units_missing_rent(self):
        """Units missing rent element are skipped (not partially inserted)."""
        result = _parse_html(INCOMPLETE_UNIT_HTML)
        assert result == []

    def test_parse_html_unit_dict_keys(self):
        """Each unit dict has the required keys."""
        result = _parse_html(SAMPLE_HTML)
        assert len(result) > 0
        for unit in result:
            assert "unit_number" in unit
            assert "bed_type" in unit
            assert "rent" in unit
            assert "availability_date" in unit

    def test_parse_html_fallback_unit_number_na(self):
        """When no unit number element found, unit_number defaults to 'N/A'."""
        html_no_unit_num = """
        <div class="available-apartment">
          <span class="bedroom-count">2 Bedroom</span>
          <span class="fp-rent">$3,000</span>
        </div>
        """
        result = _parse_html(html_no_unit_num)
        assert len(result) == 1
        assert result[0]["unit_number"] == "N/A"

    def test_parse_html_fallback_availability_available_now(self):
        """When no availability element found, availability_date defaults to 'Available Now'."""
        html_no_avail = """
        <div class="available-apartment">
          <span class="bedroom-count">Studio</span>
          <span class="fp-rent">$1,500</span>
          <span class="fp-unit">3B</span>
        </div>
        """
        result = _parse_html(html_no_avail)
        assert len(result) == 1
        assert result[0]["availability_date"] == "Available Now"


# ---------------------------------------------------------------------------
# Tests: _fetch_html()
# ---------------------------------------------------------------------------

class TestFetchHtml:
    def test_fetch_html_raises_bot_detection_on_403(self, httpx_mock: HTTPXMock):
        """403 response raises BozzutoScraperError with 'bot detection' in message."""
        httpx_mock.add_response(url="https://example.bozzuto.com/floorplans", status_code=403)
        with pytest.raises(BozzutoScraperError) as exc_info:
            _fetch_html("https://example.bozzuto.com/floorplans")
        assert "bot detection" in str(exc_info.value).lower()

    def test_fetch_html_raises_bot_detection_on_429(self, httpx_mock: HTTPXMock):
        """429 (rate limit) response raises BozzutoScraperError with 'bot detection' in message."""
        httpx_mock.add_response(url="https://example.bozzuto.com/floorplans", status_code=429)
        with pytest.raises(BozzutoScraperError) as exc_info:
            _fetch_html("https://example.bozzuto.com/floorplans")
        assert "bot detection" in str(exc_info.value).lower()

    def test_fetch_html_raises_bot_detection_on_503(self, httpx_mock: HTTPXMock):
        """503 response raises BozzutoScraperError with 'bot detection' in message."""
        httpx_mock.add_response(url="https://example.bozzuto.com/floorplans", status_code=503)
        with pytest.raises(BozzutoScraperError) as exc_info:
            _fetch_html("https://example.bozzuto.com/floorplans")
        assert "bot detection" in str(exc_info.value).lower()

    def test_fetch_html_bot_detection_message_mentions_crawl4ai(self, httpx_mock: HTTPXMock):
        """Bot detection error message recommends Crawl4AI upgrade."""
        httpx_mock.add_response(url="https://example.bozzuto.com/floorplans", status_code=403)
        with pytest.raises(BozzutoScraperError) as exc_info:
            _fetch_html("https://example.bozzuto.com/floorplans")
        assert "Crawl4AI" in str(exc_info.value)

    def test_fetch_html_raises_on_generic_error(self, httpx_mock: HTTPXMock):
        """500 response raises BozzutoScraperError (non-bot generic error)."""
        httpx_mock.add_response(url="https://example.bozzuto.com/floorplans", status_code=500)
        with pytest.raises(BozzutoScraperError) as exc_info:
            _fetch_html("https://example.bozzuto.com/floorplans")
        assert "500" in str(exc_info.value)

    def test_fetch_html_raises_on_404(self, httpx_mock: HTTPXMock):
        """404 response raises BozzutoScraperError."""
        httpx_mock.add_response(url="https://example.bozzuto.com/floorplans", status_code=404)
        with pytest.raises(BozzutoScraperError) as exc_info:
            _fetch_html("https://example.bozzuto.com/floorplans")
        assert "404" in str(exc_info.value)

    def test_fetch_html_returns_html_on_200(self, httpx_mock: HTTPXMock):
        """200 response returns the HTML body as a string."""
        expected_html = "<html><body>Units here</body></html>"
        httpx_mock.add_response(
            url="https://example.bozzuto.com/floorplans",
            status_code=200,
            text=expected_html,
        )
        result = _fetch_html("https://example.bozzuto.com/floorplans")
        assert result == expected_html


# ---------------------------------------------------------------------------
# Tests: scrape() — end-to-end
# ---------------------------------------------------------------------------

class TestScrape:
    def test_scrape_raises_on_http_error(self, httpx_mock: HTTPXMock):
        """scrape() propagates BozzutoScraperError on non-200 HTTP response."""
        httpx_mock.add_response(url="https://mybuilding.bozzuto.com/", status_code=404)
        building = MagicMock()
        building.url = "https://mybuilding.bozzuto.com/"
        with pytest.raises(BozzutoScraperError):
            scrape(building)

    def test_scrape_returns_list_on_success(self, httpx_mock: HTTPXMock):
        """scrape() returns list of unit dicts when HTML parses successfully."""
        httpx_mock.add_response(
            url="https://mybuilding.bozzuto.com/",
            status_code=200,
            text=SAMPLE_HTML,
        )
        building = MagicMock()
        building.url = "https://mybuilding.bozzuto.com/"
        result = scrape(building)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_scrape_returns_empty_list_on_no_units(self, httpx_mock: HTTPXMock):
        """scrape() returns empty list when page has no recognizable unit containers."""
        httpx_mock.add_response(
            url="https://mybuilding.bozzuto.com/",
            status_code=200,
            text=EMPTY_HTML,
        )
        building = MagicMock()
        building.url = "https://mybuilding.bozzuto.com/"
        result = scrape(building)
        assert result == []

    def test_scrape_raises_bot_detection_on_403(self, httpx_mock: HTTPXMock):
        """scrape() raises BozzutoScraperError with bot detection message on 403."""
        httpx_mock.add_response(url="https://mybuilding.bozzuto.com/", status_code=403)
        building = MagicMock()
        building.url = "https://mybuilding.bozzuto.com/"
        with pytest.raises(BozzutoScraperError) as exc_info:
            scrape(building)
        assert "bot detection" in str(exc_info.value).lower()
