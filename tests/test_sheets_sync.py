"""
Unit tests for moxie.sync.sheets.

All external calls (gspread, service account) are mocked. DB tests use an
in-memory SQLite session so no external state is required.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from moxie.config import GOOGLE_SHEETS_TAB_NAME
from moxie.db.models import Base, Building
from moxie.sync.sheets import sheets_sync, _parse_rows


# ---------------------------------------------------------------------------
# Real sheet headers (Building Prices tab) — used to build realistic raw data
# ---------------------------------------------------------------------------

SHEET_HEADERS = [
    "",               # Column A — building name, no header
    "Neighborhood", "Date", "Comission", "Concession",
    "Studio Gross", "Studio Net", "Conv. Gross", "Conv. Net",
    "1b Gross", "1B Net", "1B+D Gross", "1B+D Net",
    "2B Gross", "2B Net", "3B Gross", "3B Net",
    "Website", "Laundry", "Months free", "Duration",
    "Phone", "Email", "Parking", "Key words",
    "Scheduling", "Invoicing", "Managment", "Address",
    "Works with Guarantors", "Moxie",
]

_COL = {h: i for i, h in enumerate(SHEET_HEADERS) if h}


def _make_row(
    name="Test Building",
    url="https://example.com/building",
    neighborhood="River North",
    management_company="Greystar",
) -> list:
    """Return a raw sheet row with the correct column positions."""
    row = [""] * len(SHEET_HEADERS)
    row[0] = name
    row[_COL["Website"]] = url
    row[_COL["Neighborhood"]] = neighborhood
    row[_COL["Managment"]] = management_company
    return row


def _raw(*rows) -> list[list]:
    """Wrap data rows with the header row to form get_all_values() output."""
    return [SHEET_HEADERS] + list(rows)


def _mock_gc(raw: list[list]) -> MagicMock:
    """Return a mocked gspread client that serves the given raw values."""
    mock_ws = MagicMock()
    mock_ws.get_all_values.return_value = raw
    mock_sh = MagicMock()
    mock_sh.worksheet.return_value = mock_ws
    mock_gc = MagicMock()
    mock_gc.open_by_key.return_value = mock_sh
    return mock_gc


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
# Test _parse_rows — pure parsing, no DB or network
# ---------------------------------------------------------------------------

class TestParseRows:
    def test_building_name_from_column_a(self):
        result = _parse_rows(_raw(_make_row(name="The Reed")))
        assert result[0]["name"] == "The Reed"

    def test_url_from_website_column(self):
        result = _parse_rows(_raw(_make_row(url="https://thereed.com")))
        assert result[0]["url"] == "https://thereed.com"

    def test_neighborhood_mapped(self):
        result = _parse_rows(_raw(_make_row(neighborhood="South Loop")))
        assert result[0]["neighborhood"] == "South Loop"

    def test_management_company_from_managment_column(self):
        result = _parse_rows(_raw(_make_row(management_company="Related Midwest")))
        assert result[0]["management_company"] == "Related Midwest"

    def test_blank_neighborhood_returns_none(self):
        result = _parse_rows(_raw(_make_row(neighborhood="")))
        assert result[0]["neighborhood"] is None

    def test_blank_management_returns_none(self):
        result = _parse_rows(_raw(_make_row(management_company="")))
        assert result[0]["management_company"] is None

    def test_blank_rows_skipped(self):
        blank = [""] * len(SHEET_HEADERS)
        result = _parse_rows(_raw(_make_row(), blank, _make_row(url="https://other.com")))
        assert len(result) == 2

    def test_row_without_url_included_with_empty_url(self):
        """Rows with a name but no URL are returned — caller decides to skip."""
        result = _parse_rows(_raw(_make_row(url="")))
        assert result[0]["url"] == ""
        assert result[0]["name"] == "Test Building"

    def test_pricing_columns_not_in_output(self):
        result = _parse_rows(_raw(_make_row()))
        assert "Studio Gross" not in result[0]
        assert "1B Net" not in result[0]
        assert "Website" not in result[0]

    def test_only_expected_keys_in_output(self):
        result = _parse_rows(_raw(_make_row()))
        assert set(result[0].keys()) == {"name", "url", "neighborhood", "management_company"}

    def test_empty_raw_returns_empty_list(self):
        assert _parse_rows([]) == []

    def test_header_only_returns_empty_list(self):
        assert _parse_rows([SHEET_HEADERS]) == []

    def test_blank_trailing_columns_ignored(self):
        headers_with_blanks = SHEET_HEADERS + ["", ""]
        row = _make_row() + ["junk", "junk"]
        result = _parse_rows([headers_with_blanks, row])
        assert len(result) == 1
        assert result[0]["name"] == "Test Building"

    def test_multiple_buildings_all_parsed(self):
        result = _parse_rows(_raw(
            _make_row(name="Building A", url="https://a.com"),
            _make_row(name="Building B", url="https://b.com"),
        ))
        assert len(result) == 2
        assert result[0]["name"] == "Building A"
        assert result[1]["name"] == "Building B"


# ---------------------------------------------------------------------------
# Test sheets_sync — DB upsert logic with mocked gspread
# ---------------------------------------------------------------------------

class TestNewBuildings:
    def test_single_new_building_added(self, db):
        raw = _raw(_make_row(url="https://example.com/a"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)
        assert result["added"] == 1
        assert result["updated"] == 0
        assert result["deleted"] == 0

    def test_multiple_new_buildings_added(self, db):
        raw = _raw(
            _make_row(url="https://example.com/a"),
            _make_row(url="https://example.com/b"),
            _make_row(url="https://example.com/c"),
        )
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)
        assert result["added"] == 3

    def test_new_building_appears_in_db(self, db):
        raw = _raw(_make_row(name="River Tower", url="https://rivertower.com"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            sheets_sync(db)
        building = db.query(Building).filter_by(url="https://rivertower.com").first()
        assert building is not None
        assert building.name == "River Tower"
        assert building.last_scrape_status == "never"


class TestExistingBuildingsUpdated:
    def test_existing_building_updated_not_duplicated(self, db):
        db.add(Building(name="Old Name", url="https://example.com/b", last_scrape_status="never"))
        db.commit()

        raw = _raw(_make_row(name="New Name", url="https://example.com/b"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)

        assert result["added"] == 0
        assert result["updated"] == 1
        buildings = db.query(Building).all()
        assert len(buildings) == 1
        assert buildings[0].name == "New Name"

    def test_neighborhood_and_mgmt_updated(self, db):
        db.add(Building(name="Tower", url="https://example.com/b",
                        neighborhood="Old Hood", last_scrape_status="never"))
        db.commit()

        raw = _raw(_make_row(url="https://example.com/b",
                             neighborhood="West Loop", management_company="Golub"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            sheets_sync(db)

        db.expire_all()
        b = db.query(Building).filter_by(url="https://example.com/b").first()
        assert b.neighborhood == "West Loop"
        assert b.management_company == "Golub"


class TestMissingBuildingsDeleted:
    def test_building_not_in_sheet_is_deleted(self, db):
        db.add(Building(name="Gone", url="https://example.com/gone", last_scrape_status="never"))
        db.commit()

        raw = _raw(_make_row(url="https://example.com/present"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)

        assert result["deleted"] == 1
        assert db.query(Building).filter_by(url="https://example.com/gone").first() is None

    def test_delete_count_matches_missing_buildings(self, db):
        for i in range(3):
            db.add(Building(name=f"Old {i}", url=f"https://example.com/old-{i}",
                            last_scrape_status="never"))
        db.commit()

        raw = _raw(_make_row(url="https://example.com/new"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)

        assert result["deleted"] == 3
        assert result["added"] == 1


class TestEmptyAndNoURLGuard:
    def test_empty_raw_raises_value_error(self, db):
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = []
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc_obj = MagicMock()
        mock_gc_obj.open_by_key.return_value = mock_sh

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc_obj):
            with pytest.raises(ValueError, match="no buildings with a URL"):
                sheets_sync(db)

    def test_all_rows_missing_url_raises_value_error(self, db):
        """If every row has a name but no Website, sync can't proceed."""
        raw = _raw(_make_row(url=""), _make_row(url=""))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            with pytest.raises(ValueError, match="no buildings with a URL"):
                sheets_sync(db)


class TestSkippedRows:
    def test_row_without_url_counted_as_skipped(self, db):
        raw = _raw(
            _make_row(name="Has URL", url="https://example.com/a"),
            _make_row(name="No URL", url=""),
        )
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)

        assert result["added"] == 1
        assert result["skipped"] == 1
        assert db.query(Building).filter_by(name="No URL").first() is None

    def test_idempotent_sync_shows_zero_added(self, db):
        raw = _raw(_make_row(url="https://example.com/building"))
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result1 = sheets_sync(db)
            result2 = sheets_sync(db)

        assert result1["added"] == 1
        assert result2["added"] == 0
        assert result2["updated"] == 1


class TestBlankHeaderColumns:
    def test_blank_trailing_columns_do_not_break_sync(self, db):
        headers_with_blanks = SHEET_HEADERS + ["", "", ""]
        row = _make_row() + ["", "", ""]
        raw = [headers_with_blanks, row]
        with patch("moxie.sync.sheets.gspread.service_account", return_value=_mock_gc(raw)):
            result = sheets_sync(db)
        assert result["added"] == 1


class TestTabName:
    def test_worksheet_opened_with_configured_tab_name(self, db):
        raw = _raw(_make_row())
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = raw
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc_obj = MagicMock()
        mock_gc_obj.open_by_key.return_value = mock_sh

        with patch("moxie.sync.sheets.gspread.service_account", return_value=mock_gc_obj):
            sheets_sync(db)

        mock_sh.worksheet.assert_called_once_with(GOOGLE_SHEETS_TAB_NAME)
