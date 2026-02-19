"""
Tests for the Groupfox /floorplans scraper.

All tests use static HTML fixtures — no real Crawl4AI or browser calls are made.
_fetch_rendered_html is monkeypatched to return controlled HTML strings.
"""
import pytest
from unittest.mock import MagicMock
from moxie.scrapers.tier2.groupfox import (
    _normalize_floorplans_url,
    _parse_html,
    scrape,
    GroupfoxScraperError,
)

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------
SAMPLE_HTML = """
<div class="floorplan-card">
  <h3 class="fp-name">Birch</h3>
  <span class="bedrooms">1 Bedroom</span>
  <span class="fp-rent">$2,100</span>
  <span class="available">Available Now</span>
</div>
"""

MULTI_FLOORPLAN_HTML = """
<div class="floorplan-card">
  <h3 class="fp-name">Oak</h3>
  <span class="bedrooms">Studio</span>
  <span class="fp-rent">$1,600</span>
  <span class="available">March 1, 2026</span>
</div>
<div class="floorplan-card">
  <h3 class="fp-name">Maple</h3>
  <span class="bedrooms">2 Bedrooms</span>
  <span class="fp-rent">$2,800</span>
</div>
"""

NO_FLOORPLANS_HTML = """
<div class="page-content">
  <p>No floorplans available.</p>
</div>
"""

INCOMPLETE_FLOORPLAN_HTML = """
<div class="floorplan-card">
  <h3 class="fp-name">Ash</h3>
  <span class="bedrooms">1 Bedroom</span>
</div>
"""


# ---------------------------------------------------------------------------
# _normalize_floorplans_url tests
# ---------------------------------------------------------------------------

class TestNormalizeFloorplansUrl:
    def test_normalize_floorplans_url_already_has_path(self):
        """URL already ending in /floorplans should be returned unchanged."""
        url = "https://axis.groupfox.com/floorplans"
        assert _normalize_floorplans_url(url) == url

    def test_normalize_floorplans_url_root(self):
        """Root URL should get /floorplans appended."""
        result = _normalize_floorplans_url("https://axis.groupfox.com")
        assert result == "https://axis.groupfox.com/floorplans"

    def test_normalize_floorplans_url_trailing_slash(self):
        """URL with trailing slash should get /floorplans (not //floorplans)."""
        result = _normalize_floorplans_url("https://axis.groupfox.com/")
        assert result == "https://axis.groupfox.com/floorplans"

    def test_normalize_floorplans_url_with_other_path(self):
        """URL with non-floorplans path should replace path with /floorplans."""
        result = _normalize_floorplans_url("https://axis.groupfox.com/about")
        assert result == "https://axis.groupfox.com/floorplans"

    def test_normalize_floorplans_url_with_trailing_slash_on_floorplans(self):
        """URL already ending in /floorplans/ should be treated as already normalized."""
        url = "https://axis.groupfox.com/floorplans/"
        result = _normalize_floorplans_url(url)
        # Either returning as-is or normalized — both acceptable if /floorplans is present
        assert "/floorplans" in result

    def test_normalize_floorplans_url_subdomain_preserved(self):
        """Subdomain must be preserved when appending /floorplans."""
        result = _normalize_floorplans_url("https://riverwood.groupfox.com")
        assert "riverwood.groupfox.com" in result
        assert result.endswith("/floorplans")


# ---------------------------------------------------------------------------
# _parse_html tests
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_parse_html_empty_returns_empty(self):
        result = _parse_html("")
        assert result == []

    def test_parse_html_no_matching_elements_returns_empty(self):
        result = _parse_html(NO_FLOORPLANS_HTML)
        assert result == []

    def test_parse_html_extracts_floorplans(self):
        result = _parse_html(SAMPLE_HTML)
        assert len(result) == 1
        fp = result[0]
        assert "bed_type" in fp
        assert "rent" in fp
        assert "1 Bedroom" in fp["bed_type"]
        assert "$2,100" in fp["rent"]

    def test_parse_html_extracts_floorplan_name(self):
        result = _parse_html(SAMPLE_HTML)
        assert result[0]["floor_plan_name"] == "Birch"
        assert result[0]["unit_number"] == "Birch"

    def test_parse_html_extracts_availability_date(self):
        result = _parse_html(SAMPLE_HTML)
        assert result[0]["availability_date"] == "Available Now"

    def test_parse_html_defaults_availability_to_available_now(self):
        result = _parse_html(MULTI_FLOORPLAN_HTML)
        maple = next(u for u in result if u.get("floor_plan_name") == "Maple")
        assert maple["availability_date"] == "Available Now"

    def test_parse_html_skips_incomplete_floorplans(self):
        """Floorplan missing rent should be skipped."""
        result = _parse_html(INCOMPLETE_FLOORPLAN_HTML)
        assert result == []

    def test_parse_html_extracts_multiple_floorplans(self):
        result = _parse_html(MULTI_FLOORPLAN_HTML)
        assert len(result) == 2
        names = [u["floor_plan_name"] for u in result]
        assert "Oak" in names
        assert "Maple" in names

    def test_parse_html_floor_plan_name_defaults_to_na(self):
        """Floorplan with no name element should default to 'N/A'."""
        html = """
        <div class="floorplan-card">
          <span class="bedrooms">Studio</span>
          <span class="fp-rent">$1,500</span>
        </div>
        """
        result = _parse_html(html)
        assert len(result) == 1
        assert result[0]["floor_plan_name"] == "N/A"
        assert result[0]["unit_number"] == "N/A"


# ---------------------------------------------------------------------------
# scrape() integration tests (monkeypatched)
# ---------------------------------------------------------------------------

class TestScrape:
    def test_scrape_raises_on_empty_html(self, monkeypatch):
        """Empty HTML from Crawl4AI should raise GroupfoxScraperError."""
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        with pytest.raises(GroupfoxScraperError, match="empty HTML"):
            groupfox_module.scrape(building)

    def test_scrape_calls_normalized_url(self, monkeypatch):
        """scrape() must call _fetch_rendered_html with the /floorplans URL."""
        import moxie.scrapers.tier2.groupfox as groupfox_module

        captured_urls = []

        async def mock_fetch(url: str) -> str:
            captured_urls.append(url)
            return SAMPLE_HTML

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        groupfox_module.scrape(building)

        assert len(captured_urls) == 1
        assert captured_urls[0] == "https://axis.groupfox.com/floorplans"

    def test_scrape_calls_normalized_url_when_already_normalized(self, monkeypatch):
        """When URL already has /floorplans, it should be passed as-is."""
        import moxie.scrapers.tier2.groupfox as groupfox_module

        captured_urls = []

        async def mock_fetch(url: str) -> str:
            captured_urls.append(url)
            return SAMPLE_HTML

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com/floorplans"

        groupfox_module.scrape(building)
        assert "/floorplans" in captured_urls[0]

    def test_scrape_returns_parsed_units(self, monkeypatch):
        """Valid HTML should return parsed floorplan list."""
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            return SAMPLE_HTML

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        result = groupfox_module.scrape(building)
        assert isinstance(result, list)
        assert len(result) == 1
        assert "bed_type" in result[0]
        assert "rent" in result[0]

    def test_scrape_error_message_includes_url(self, monkeypatch):
        """GroupfoxScraperError message should include the normalized URL."""
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        with pytest.raises(GroupfoxScraperError, match="axis.groupfox.com"):
            groupfox_module.scrape(building)
