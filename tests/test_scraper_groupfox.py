"""
Tests for the Groupfox /floorplans scraper.

All tests use static HTML fixtures — no real Crawl4AI or browser calls are made.
_fetch_rendered_html is monkeypatched to return controlled HTML strings.
"""
import pytest
from unittest.mock import MagicMock
from moxie.scrapers.tier2.groupfox import (
    _normalize_floorplans_url,
    _parse_floorplan_index,
    _parse_unit_rows,
    scrape,
    GroupfoxScraperError,
)

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------
INDEX_HTML = """
<div class="card text-center h-100">
  <div class="card-header bg-transparent border-bottom-0 pt-4 pb-0">
    <h2 class="card-title h4 font-weight-bold text-capitalize">Studio</h2>
    <ul class="list-unstyled list-inline mb-2 text-sm">
      <li class="list-inline-item mr-2"><div class="d-flex align-items-center"><span class="">Studio</span></div></li>
      <li class="list-inline-item mr-2"><div class="d-flex align-items-center"><span class="">1</span><span class="">Bath</span></div></li>
    </ul>
  </div>
  <div class="card-body">
    <a class="btn btn-primary btn-block btn-block track-apply floorplan-action-button" href="/floorplans/studio">Availability<span class="sr-only">for Studio</span></a>
  </div>
</div>
<div class="card text-center h-100">
  <div class="card-header bg-transparent border-bottom-0 pt-4 pb-0">
    <h2 class="card-title h4 font-weight-bold text-capitalize">One Bedroom</h2>
    <ul class="list-unstyled list-inline mb-2 text-sm">
      <li class="list-inline-item mr-2"><div class="d-flex align-items-center"><span class="">1</span><span class="">Bed</span></div></li>
      <li class="list-inline-item mr-2"><div class="d-flex align-items-center"><span class="">1</span><span class="">Bath</span></div></li>
    </ul>
  </div>
  <div class="card-body">
    <a class="btn btn-primary btn-block btn-block track-apply floorplan-action-button" href="/floorplans/one-bedroom">Availability<span class="sr-only">for One Bedroom</span></a>
  </div>
</div>
<div class="card text-center h-100">
  <div class="card-header bg-transparent border-bottom-0 pt-4 pb-0">
    <h2 class="card-title h4 font-weight-bold text-capitalize">Three Bedroom</h2>
    <ul class="list-unstyled list-inline mb-2 text-sm">
      <li class="list-inline-item mr-2"><div class="d-flex align-items-center"><span class="">3</span><span class="">Bed</span></div></li>
      <li class="list-inline-item mr-2"><div class="d-flex align-items-center"><span class="">2</span><span class="">Bath</span></div></li>
    </ul>
  </div>
  <div class="card-body">
    <a class="btn btn-primary btn-block btn-block track-dialog dialog-button floorplan-action-button" href="#myContactModal">Contact Us<span class="sr-only">for Three Bedroom</span></a>
  </div>
</div>
"""

UNIT_ROWS_HTML = """
<table>
  <tr class="unit-container" data-selenium-id="urow1" id="unit-container-123">
    <td class="td-card-name"><span class="head">Apartment:</span>#4414307</td>
    <td class="td-card-rent"><span class="head">Rent:</span>$1,865</td>
    <td class="td-card-available"><span class="head">Date:</span>2/22/2026</td>
    <td class="td-card-footer"><a>Apply Now</a></td>
  </tr>
  <tr class="unit-container" data-selenium-id="urow2" id="unit-container-456">
    <td class="td-card-name"><span class="head">Apartment:</span>#4415809</td>
    <td class="td-card-rent"><span class="head">Rent:</span>$1,910</td>
    <td class="td-card-available"><span class="head">Date:</span>3/8/2026</td>
    <td class="td-card-footer"><a>Apply Now</a></td>
  </tr>
</table>
"""

EMPTY_HTML = """
<div class="page-content">
  <p>No floorplans available.</p>
</div>
"""


# ---------------------------------------------------------------------------
# _normalize_floorplans_url tests
# ---------------------------------------------------------------------------

class TestNormalizeFloorplansUrl:
    def test_already_has_path(self):
        url = "https://axis.groupfox.com/floorplans"
        assert _normalize_floorplans_url(url) == url

    def test_root(self):
        result = _normalize_floorplans_url("https://axis.groupfox.com")
        assert result == "https://axis.groupfox.com/floorplans"

    def test_trailing_slash(self):
        result = _normalize_floorplans_url("https://axis.groupfox.com/")
        assert result == "https://axis.groupfox.com/floorplans"

    def test_with_other_path(self):
        result = _normalize_floorplans_url("https://axis.groupfox.com/about")
        assert result == "https://axis.groupfox.com/floorplans"

    def test_floorplans_trailing_slash_accepted(self):
        url = "https://axis.groupfox.com/floorplans/"
        result = _normalize_floorplans_url(url)
        assert "/floorplans" in result

    def test_subdomain_preserved(self):
        result = _normalize_floorplans_url("https://riverwood.groupfox.com")
        assert "riverwood.groupfox.com" in result
        assert result.endswith("/floorplans")


# ---------------------------------------------------------------------------
# _parse_floorplan_index tests
# ---------------------------------------------------------------------------

class TestParseFloorplanIndex:
    def test_empty_html(self):
        assert _parse_floorplan_index("") == []

    def test_no_cards(self):
        assert _parse_floorplan_index(EMPTY_HTML) == []

    def test_extracts_available_plans(self):
        plans = _parse_floorplan_index(INDEX_HTML)
        # Should get Studio and One Bedroom, but NOT Three Bedroom (Contact Us)
        assert len(plans) == 2
        names = [p["name"] for p in plans]
        assert "Studio" in names
        assert "One Bedroom" in names
        assert "Three Bedroom" not in names

    def test_extracts_href(self):
        plans = _parse_floorplan_index(INDEX_HTML)
        studio = next(p for p in plans if p["name"] == "Studio")
        assert studio["href"] == "/floorplans/studio"

    def test_extracts_beds(self):
        plans = _parse_floorplan_index(INDEX_HTML)
        studio = next(p for p in plans if p["name"] == "Studio")
        assert "Studio" in studio["beds"]

    def test_skips_contact_us(self):
        plans = _parse_floorplan_index(INDEX_HTML)
        names = [p["name"] for p in plans]
        assert "Three Bedroom" not in names


# ---------------------------------------------------------------------------
# _parse_unit_rows tests
# ---------------------------------------------------------------------------

class TestParseUnitRows:
    def test_empty_html(self):
        assert _parse_unit_rows("", "Studio", "Studio", "1Bath") == []

    def test_extracts_units(self):
        units = _parse_unit_rows(UNIT_ROWS_HTML, "Studio", "Studio", "1Bath")
        assert len(units) == 2

    def test_unit_number_extracted(self):
        units = _parse_unit_rows(UNIT_ROWS_HTML, "Studio", "Studio", "1Bath")
        assert units[0]["unit_number"] == "4414307"
        assert units[1]["unit_number"] == "4415809"

    def test_rent_extracted(self):
        units = _parse_unit_rows(UNIT_ROWS_HTML, "Studio", "Studio", "1Bath")
        assert units[0]["rent"] == "$1,865"

    def test_availability_date_extracted(self):
        units = _parse_unit_rows(UNIT_ROWS_HTML, "Studio", "Studio", "1Bath")
        assert units[0]["availability_date"] == "2/22/2026"

    def test_floorplan_name_passed_through(self):
        units = _parse_unit_rows(UNIT_ROWS_HTML, "Studio", "Studio", "1Bath")
        assert units[0]["floor_plan_name"] == "Studio"

    def test_beds_baths_passed_through(self):
        units = _parse_unit_rows(UNIT_ROWS_HTML, "Studio", "Studio", "1Bath")
        assert units[0]["bed_type"] == "Studio"
        assert units[0]["baths"] == "1Bath"


# ---------------------------------------------------------------------------
# scrape() integration tests (monkeypatched)
# ---------------------------------------------------------------------------

class TestScrape:
    def test_raises_on_empty_html(self, monkeypatch):
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        with pytest.raises(GroupfoxScraperError, match="empty HTML"):
            groupfox_module.scrape(building)

    def test_returns_units_from_subpages(self, monkeypatch):
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            if url.endswith("/floorplans"):
                return INDEX_HTML
            elif "/floorplans/" in url:
                return UNIT_ROWS_HTML
            return ""

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        result = groupfox_module.scrape(building)
        # 2 floor plans with availability x 2 units each = 4 units
        assert len(result) == 4
        assert all("unit_number" in u for u in result)
        assert all("rent" in u for u in result)

    def test_fetches_correct_urls(self, monkeypatch):
        import moxie.scrapers.tier2.groupfox as groupfox_module

        captured_urls = []

        async def mock_fetch(url: str) -> str:
            captured_urls.append(url)
            if url.endswith("/floorplans"):
                return INDEX_HTML
            return UNIT_ROWS_HTML

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        groupfox_module.scrape(building)
        assert captured_urls[0] == "https://axis.groupfox.com/floorplans"
        assert "https://axis.groupfox.com/floorplans/studio" in captured_urls
        assert "https://axis.groupfox.com/floorplans/one-bedroom" in captured_urls

    def test_empty_subpage_skipped(self, monkeypatch):
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            if url.endswith("/floorplans"):
                return INDEX_HTML
            return ""  # empty sub-pages

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        result = groupfox_module.scrape(building)
        assert result == []

    def test_error_message_includes_url(self, monkeypatch):
        import moxie.scrapers.tier2.groupfox as groupfox_module

        async def mock_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(groupfox_module, "_fetch_rendered_html", mock_fetch)

        building = MagicMock()
        building.url = "https://axis.groupfox.com"

        with pytest.raises(GroupfoxScraperError, match="axis.groupfox.com"):
            groupfox_module.scrape(building)
