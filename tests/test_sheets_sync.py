"""
Unit tests for moxie.sync.sheets.sheets_sync().

All external calls (gspread, service account) are mocked. DB tests use an
in-memory SQLite session so no external state is required.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from moxie.config import GOOGLE_SHEETS_TAB_NAME
from moxie.db.models import Base, Building
from moxie.sync.sheets import sheets_sync


# ---------------------------------------------------------------------------
# In-memory SQLite session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Helper: build a mock gspread worksheet
# ---------------------------------------------------------------------------

def _make_mock_worksheet(rows: list[dict]):
    """Return a mocked gspread worksheet that returns the given rows."""
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = rows
    mock_sh = MagicMock()
    mock_sh.worksheet.return_value = mock_ws
    mock_gc = MagicMock()
    mock_gc.open_by_key.return_value = mock_sh
    return mock_gc


def _sample_row(
    name="Test Building",
    url="https://example.com/building",
    neighborhood="River North",
    management_company="Greystar",
    platform="llm",
    rentcafe_property_id="",
    rentcafe_api_token="",
) -> dict:
    return {
        "name": name,
        "url": url,
        "neighborhood": neighborhood,
        "management_company": management_company,
        "platform": platform,
        "rentcafe_property_id": rentcafe_property_id,
        "rentcafe_api_token": rentcafe_api_token,
    }


# ---------------------------------------------------------------------------
# Test 1: New buildings are added — added count increments
# ---------------------------------------------------------------------------

class TestNewBuildings:
    def test_single_new_building_added(self, db):
        rows = [_sample_row(url="https://example.com/a")]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            result = sheets_sync(db)

        assert result["added"] == 1
        assert result["updated"] == 0
        assert result["deleted"] == 0

    def test_multiple_new_buildings_added(self, db):
        rows = [
            _sample_row(url="https://example.com/a"),
            _sample_row(url="https://example.com/b"),
            _sample_row(url="https://example.com/c"),
        ]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            result = sheets_sync(db)

        assert result["added"] == 3
        assert result["updated"] == 0
        assert result["deleted"] == 0

    def test_new_building_appears_in_db(self, db):
        rows = [_sample_row(name="River Tower", url="https://example.com/river")]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            sheets_sync(db)

        building = db.query(Building).filter_by(url="https://example.com/river").first()
        assert building is not None
        assert building.name == "River Tower"
        assert building.last_scrape_status == "never"


# ---------------------------------------------------------------------------
# Test 2: Existing buildings (same URL) are updated — no duplicates
# ---------------------------------------------------------------------------

class TestExistingBuildingsUpdated:
    def test_existing_building_updated_not_duplicated(self, db):
        # Pre-populate DB with one building
        existing = Building(
            name="Old Name",
            url="https://example.com/building",
            last_scrape_status="never",
        )
        db.add(existing)
        db.commit()

        # Sheet has same URL but new name
        rows = [_sample_row(name="New Name", url="https://example.com/building")]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            result = sheets_sync(db)

        assert result["added"] == 0
        assert result["updated"] == 1
        assert result["deleted"] == 0

        # Verify only one record exists and name was updated
        buildings = db.query(Building).all()
        assert len(buildings) == 1
        assert buildings[0].name == "New Name"

    def test_updated_building_fields_are_persisted(self, db):
        existing = Building(
            name="Old Name",
            url="https://example.com/building",
            neighborhood="Old Neighborhood",
            last_scrape_status="never",
        )
        db.add(existing)
        db.commit()

        rows = [_sample_row(
            name="New Name",
            url="https://example.com/building",
            neighborhood="West Loop",
            management_company="Golub",
            platform="platform",
        )]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            sheets_sync(db)

        db.expire_all()
        updated = db.query(Building).filter_by(url="https://example.com/building").first()
        assert updated.name == "New Name"
        assert updated.neighborhood == "West Loop"
        assert updated.management_company == "Golub"
        assert updated.platform == "platform"


# ---------------------------------------------------------------------------
# Test 3: Buildings missing from Sheet are deleted from DB
# ---------------------------------------------------------------------------

class TestMissingBuildingsDeleted:
    def test_building_not_in_sheet_is_deleted(self, db):
        # Add a building to DB that isn't in the Sheet
        building_to_delete = Building(
            name="Gone Building",
            url="https://example.com/gone",
            last_scrape_status="never",
        )
        db.add(building_to_delete)
        db.commit()

        # Sheet has a different building
        rows = [_sample_row(url="https://example.com/present")]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            result = sheets_sync(db)

        assert result["deleted"] == 1
        assert result["added"] == 1

        # Verify the gone building is no longer in DB
        gone = db.query(Building).filter_by(url="https://example.com/gone").first()
        assert gone is None

    def test_delete_count_matches_missing_buildings(self, db):
        for i in range(3):
            db.add(Building(
                name=f"Building {i}",
                url=f"https://example.com/old-{i}",
                last_scrape_status="never",
            ))
        db.commit()

        # Sheet has only new buildings
        rows = [_sample_row(url="https://example.com/new")]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            result = sheets_sync(db)

        assert result["deleted"] == 3
        assert result["added"] == 1


# ---------------------------------------------------------------------------
# Test 4: len(rows) < 1 raises ValueError
# ---------------------------------------------------------------------------

class TestEmptyRowsGuard:
    def test_empty_rows_raises_value_error(self, db):
        mock_gc = _make_mock_worksheet([])

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            with pytest.raises(ValueError, match="suspiciously few rows"):
                sheets_sync(db)

    def test_empty_rows_error_includes_row_count(self, db):
        mock_gc = _make_mock_worksheet([])

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            with pytest.raises(ValueError, match="0"):
                sheets_sync(db)


# ---------------------------------------------------------------------------
# Test 5: Empty string rentcafe fields stored as None
# ---------------------------------------------------------------------------

class TestEmptyStringToNone:
    def test_empty_rentcafe_property_id_stored_as_none(self, db):
        rows = [_sample_row(
            url="https://example.com/api-building",
            rentcafe_property_id="",  # empty string from Sheet
        )]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            sheets_sync(db)

        building = db.query(Building).filter_by(url="https://example.com/api-building").first()
        assert building.rentcafe_property_id is None, (
            f"Expected None, got {building.rentcafe_property_id!r}"
        )

    def test_empty_rentcafe_api_token_stored_as_none(self, db):
        rows = [_sample_row(
            url="https://example.com/api-building",
            rentcafe_api_token="",  # empty string from Sheet
        )]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            sheets_sync(db)

        building = db.query(Building).filter_by(url="https://example.com/api-building").first()
        assert building.rentcafe_api_token is None, (
            f"Expected None, got {building.rentcafe_api_token!r}"
        )

    def test_non_empty_rentcafe_fields_stored_as_given(self, db):
        rows = [_sample_row(
            url="https://example.com/api-building",
            rentcafe_property_id="12345",
            rentcafe_api_token="tok_abc",
        )]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            sheets_sync(db)

        building = db.query(Building).filter_by(url="https://example.com/api-building").first()
        assert building.rentcafe_property_id == "12345"
        assert building.rentcafe_api_token == "tok_abc"

    def test_worksheet_opened_with_configured_tab_name(self, db):
        """sheets_sync must open the tab from GOOGLE_SHEETS_TAB_NAME, not a hardcoded string."""
        rows = [_sample_row()]
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = rows
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open_by_key.return_value = mock_sh

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            sheets_sync(db)

        mock_sh.worksheet.assert_called_once_with(GOOGLE_SHEETS_TAB_NAME)

    def test_idempotent_sync_shows_zero_added(self, db):
        """Running sync twice should show added=0 on the second run."""
        rows = [_sample_row(url="https://example.com/building")]
        mock_gc = _make_mock_worksheet(rows)

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc):
            result1 = sheets_sync(db)
            result2 = sheets_sync(db)

        assert result1["added"] == 1
        assert result2["added"] == 0
        assert result2["updated"] == 1
