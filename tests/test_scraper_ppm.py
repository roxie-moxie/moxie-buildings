"""
Tests for PPM single-page scraper.

Covers HTML parsing logic (_parse_ppm_html), building name matching (_matches_building),
and unit filtering in scrape(). No real HTTP calls — monkeypatch replaces
_fetch_all_ppm_units() for scrape() integration tests.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moxie.db.models import Base, Building
from moxie.scrapers.tier1 import ppm
from moxie.scrapers.tier1.ppm import (
    _parse_ppm_html,
    _matches_building,
    scrape,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory SQLite session. Created fresh for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_building(db, name: str = "Tower Building") -> Building:
    """Insert a Building and return it."""
    b = Building(
        name=name,
        url="https://ppmapartments.com",
        last_scrape_status="never",
        consecutive_zero_count=0,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def _make_card_html(rows: list[tuple]) -> str:
    """
    Build minimal HTML with div.unit cards matching the current PPM DOM structure.
    rows: list of (neighborhood, building, unit, availability, unit_type, floorplan, features, price)
    """
    cards = ""
    for neighborhood, building, unit, availability, unit_type, floorplan, features, price in rows:
        floorplan_link = f'<a href="#">{floorplan}</a>' if floorplan else ""
        cards += f"""
        <div class="unit">
            <div class="spec prop-remove">Neighborhood:{neighborhood}</div>
            <div class="spec prop-remove spec-building">Building:{building}</div>
            <div class="spec spec-sm">Unit:{unit}</div>
            <div class="spec">Availability:{availability}</div>
            <div class="spec">Unit Type:{unit_type}</div>
            <div class="spec">{floorplan_link}</div>
            <div class="spec spec-feature">Features:{features}</div>
            <div class="spec spec-sm">Price:{price}</div>
        </div>
        """
    return f'<div class="rm-listings-container">{cards}</div>'


# Keep old alias for any tests that might reference it
_make_table_html = _make_card_html


# ---------------------------------------------------------------------------
# HTML parsing tests
# ---------------------------------------------------------------------------

class TestParsePpmHtml:
    def test_parse_ppm_html_empty(self):
        """Empty HTML returns empty list."""
        result = _parse_ppm_html("")
        assert result == []

    def test_parse_ppm_html_skips_header_rows(self):
        """Rows with only th elements (no td cells) are skipped."""
        html = "<table><tr><th>Building</th><th>Unit</th></tr></table>"
        result = _parse_ppm_html(html)
        assert result == []

    def test_parse_ppm_html_extracts_units(self):
        """Valid rendered HTML with 2 data rows produces 2 unit dicts."""
        html = _make_table_html([
            ("River North", "Tower Building", "101", "Available Now", "1BR", "Plan A", "", "$1,500"),
            ("Lincoln Park", "Park Place", "202", "2026-04-01", "2BR", "Plan B", "", "$2,000"),
        ])
        result = _parse_ppm_html(html)
        assert len(result) == 2
        assert result[0]["unit_number"] == "101"
        assert result[0]["building_name"] == "Tower Building"
        assert result[0]["bed_type"] == "1BR"
        assert result[0]["rent"] == "$1,500"
        assert result[0]["availability_date"] == "Available Now"
        assert result[1]["unit_number"] == "202"
        assert result[1]["building_name"] == "Park Place"

    def test_parse_ppm_html_skips_cards_without_unit_type(self):
        """Cards with empty unit type are skipped."""
        html = _make_card_html([
            ("River North", "Tower Building", "101", "Available Now", "", "Plan A", "", "$1,500"),
        ])
        result = _parse_ppm_html(html)
        assert result == []

    def test_parse_ppm_html_skips_divs_without_building_spec(self):
        """Divs without spec-building class are skipped."""
        html = '<div class="rm-listings-container"><div class="unit"><div class="spec">Unit:101</div></div></div>'
        result = _parse_ppm_html(html)
        assert result == []

    def test_parse_ppm_html_floor_plan_none_when_empty(self):
        """floor_plan_name is None when the floorplan cell is empty."""
        html = _make_table_html([
            ("River North", "Tower Building", "301", "Available Now", "Studio", "", "", "$1,200"),
        ])
        result = _parse_ppm_html(html)
        assert result[0]["floor_plan_name"] is None

    def test_parse_ppm_html_availability_defaults_to_available_now(self):
        """Blank availability cell falls back to 'Available Now'."""
        html = _make_table_html([
            ("River North", "Tower Building", "401", "", "1BR", "Plan C", "", "$1,600"),
        ])
        result = _parse_ppm_html(html)
        assert result[0]["availability_date"] == "Available Now"


# ---------------------------------------------------------------------------
# Building name matching tests
# ---------------------------------------------------------------------------

class TestMatchesBuilding:
    def test_matches_building_exact(self):
        """Exact name match returns True."""
        assert _matches_building("Tower", "Tower") is True

    def test_matches_building_partial_db_has_prefix(self):
        """DB name contains the unit building name (DB has extra prefix)."""
        assert _matches_building("Streeterville Tower", "PPM - Streeterville Tower") is True

    def test_matches_building_partial_reverse(self):
        """Unit name is shorter than DB name — DB name is contained in unit name is not needed;
        unit name in DB name is sufficient."""
        assert _matches_building("Park Place", "PPM Park Place Apartments") is True

    def test_matches_building_no_match(self):
        """Completely different names return False."""
        assert _matches_building("River North Tower", "Lincoln Park Gardens") is False

    def test_matches_building_case_insensitive(self):
        """Matching is case-insensitive."""
        assert _matches_building("TOWER BUILDING", "tower building") is True

    def test_matches_building_strips_whitespace(self):
        """Leading/trailing whitespace is stripped before comparison."""
        assert _matches_building("  Tower  ", "Tower") is True


# ---------------------------------------------------------------------------
# scrape() integration tests (monkeypatched _fetch_all_ppm_units)
# ---------------------------------------------------------------------------

SAMPLE_UNITS = [
    {
        "building_name": "Streeterville Tower",
        "unit_number": "101",
        "availability_date": "Available Now",
        "bed_type": "1BR",
        "floor_plan_name": "Plan A",
        "rent": "$1,500",
    },
    {
        "building_name": "Streeterville Tower",
        "unit_number": "102",
        "availability_date": "2026-05-01",
        "bed_type": "2BR",
        "floor_plan_name": "Plan B",
        "rent": "$2,000",
    },
    {
        "building_name": "Lincoln Park Gardens",
        "unit_number": "201",
        "availability_date": "Available Now",
        "bed_type": "Studio",
        "floor_plan_name": None,
        "rent": "$1,100",
    },
]


class TestScrapeIntegration:
    def test_scrape_filters_to_building(self, db, monkeypatch):
        """scrape() returns only units matching the building name."""
        monkeypatch.setattr(ppm, "_fetch_all_ppm_units", lambda: SAMPLE_UNITS)
        building = _make_building(db, name="PPM - Streeterville Tower")
        result = scrape(building)
        # Should match both Streeterville Tower units
        assert len(result) == 2
        unit_numbers = {u["unit_number"] for u in result}
        assert "101" in unit_numbers
        assert "102" in unit_numbers

    def test_scrape_strips_building_name_from_output(self, db, monkeypatch):
        """Returned dicts do NOT contain the 'building_name' key."""
        monkeypatch.setattr(ppm, "_fetch_all_ppm_units", lambda: SAMPLE_UNITS)
        building = _make_building(db, name="Streeterville Tower")
        result = scrape(building)
        for unit in result:
            assert "building_name" not in unit

    def test_scrape_returns_empty_when_no_match(self, db, monkeypatch):
        """scrape() returns empty list when no units match the building name."""
        monkeypatch.setattr(ppm, "_fetch_all_ppm_units", lambda: SAMPLE_UNITS)
        building = _make_building(db, name="Completely Different Building")
        result = scrape(building)
        assert result == []

    def test_scrape_returns_correct_fields(self, db, monkeypatch):
        """Returned unit dicts contain expected fields (no building_name, has rent etc)."""
        monkeypatch.setattr(ppm, "_fetch_all_ppm_units", lambda: SAMPLE_UNITS)
        building = _make_building(db, name="Lincoln Park Gardens")
        result = scrape(building)
        assert len(result) == 1
        unit = result[0]
        assert unit["unit_number"] == "201"
        assert unit["bed_type"] == "Studio"
        assert unit["rent"] == "$1,100"
        assert unit["availability_date"] == "Available Now"
        assert "building_name" not in unit
