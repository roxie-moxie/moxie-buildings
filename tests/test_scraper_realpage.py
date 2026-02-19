"""
Tests for the RealPage/G5 scraper.

All tests use static HTML fixtures — no real Crawl4AI or browser calls are made.
_fetch_rendered_html is monkeypatched to return controlled HTML strings.
"""
import pytest
from unittest.mock import MagicMock
from moxie.scrapers.tier2.realpage import (
    _parse_html,
    scrape,
    RealPageScraperError,
)

# ---------------------------------------------------------------------------
# HTML fixture
# ---------------------------------------------------------------------------
SAMPLE_HTML = """
<div class="available-unit">
  <span class="bedrooms">2 Bedrooms</span>
  <span class="unit-price">$2,800</span>
  <span class="unit-availability">April 1, 2026</span>
  <span class="unit-number">201</span>
</div>
"""

MULTI_UNIT_HTML = """
<div class="available-unit">
  <span class="bedrooms">1 Bedroom</span>
  <span class="unit-price">$1,900</span>
  <span class="unit-availability">Available Now</span>
  <span class="unit-number">101</span>
</div>
<div class="available-unit">
  <span class="bedrooms">Studio</span>
  <span class="unit-price">$1,500</span>
  <span class="unit-number">102</span>
</div>
"""

NO_UNITS_HTML = """
<div class="page-content">
  <p>No units available at this time.</p>
</div>
"""

# Incomplete unit — missing rent (should be skipped)
INCOMPLETE_UNIT_HTML = """
<div class="available-unit">
  <span class="bedrooms">2 Bedrooms</span>
</div>
"""


# ---------------------------------------------------------------------------
# _parse_html tests
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_parse_html_empty_returns_empty(self):
        result = _parse_html("")
        assert result == []

    def test_parse_html_no_matching_elements_returns_empty(self):
        result = _parse_html(NO_UNITS_HTML)
        assert result == []

    def test_parse_html_extracts_units(self):
        result = _parse_html(SAMPLE_HTML)
        assert len(result) == 1
        unit = result[0]
        assert "bed_type" in unit
        assert "rent" in unit
        assert "2 Bedrooms" in unit["bed_type"]
        assert "$2,800" in unit["rent"]

    def test_parse_html_extracts_unit_number(self):
        result = _parse_html(SAMPLE_HTML)
        assert result[0]["unit_number"] == "201"

    def test_parse_html_extracts_availability_date(self):
        result = _parse_html(SAMPLE_HTML)
        assert result[0]["availability_date"] == "April 1, 2026"

    def test_parse_html_defaults_availability_to_available_now(self):
        result = _parse_html(MULTI_UNIT_HTML)
        # Second unit has no availability element
        studio = next(u for u in result if "Studio" in u["bed_type"])
        assert studio["availability_date"] == "Available Now"

    def test_parse_html_defaults_unit_number_to_na_when_missing(self):
        # Build HTML with no unit-number element
        html = """
        <div class="available-unit">
          <span class="bedrooms">1 Bedroom</span>
          <span class="unit-price">$1,800</span>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["unit_number"] == "N/A"

    def test_parse_html_skips_incomplete_units(self):
        # Unit missing rent should be skipped
        result = _parse_html(INCOMPLETE_UNIT_HTML)
        assert result == []

    def test_parse_html_extracts_multiple_units(self):
        result = _parse_html(MULTI_UNIT_HTML)
        assert len(result) == 2
        bed_types = [u["bed_type"] for u in result]
        assert any("1 Bedroom" in bt for bt in bed_types)
        assert any("Studio" in bt for bt in bed_types)


# ---------------------------------------------------------------------------
# scrape() integration tests (monkeypatched)
# ---------------------------------------------------------------------------

class TestScrape:
    def test_scrape_raises_on_empty_html(self, monkeypatch):
        """Empty HTML from Crawl4AI should raise RealPageScraperError."""
        import moxie.scrapers.tier2.realpage as realpage_module

        async def mock_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(realpage_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://example.realpage.com/apartments"

        with pytest.raises(RealPageScraperError, match="empty HTML"):
            realpage_module.scrape(building)

    def test_scrape_returns_units_on_valid_html(self, monkeypatch):
        """Valid HTML from Crawl4AI should return parsed units."""
        import moxie.scrapers.tier2.realpage as realpage_module

        async def mock_fetch(url: str) -> str:
            return SAMPLE_HTML

        monkeypatch.setattr(realpage_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://example.realpage.com/apartments"

        result = realpage_module.scrape(building)
        assert isinstance(result, list)
        assert len(result) == 1
        assert "bed_type" in result[0]
        assert "rent" in result[0]

    def test_scrape_passes_building_url_to_fetch(self, monkeypatch):
        """scrape() must pass building.url to _fetch_rendered_html."""
        import moxie.scrapers.tier2.realpage as realpage_module

        captured_urls = []

        async def mock_fetch(url: str) -> str:
            captured_urls.append(url)
            return SAMPLE_HTML

        monkeypatch.setattr(realpage_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://example.realpage.com/apartments"

        realpage_module.scrape(building)
        assert captured_urls == ["https://example.realpage.com/apartments"]

    def test_scrape_empty_html_error_message_includes_url(self, monkeypatch):
        """RealPageScraperError message should include the building URL."""
        import moxie.scrapers.tier2.realpage as realpage_module

        async def mock_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(realpage_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://example.realpage.com/test"

        with pytest.raises(RealPageScraperError, match="example.realpage.com"):
            realpage_module.scrape(building)
