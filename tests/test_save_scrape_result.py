"""
Behavioral tests for save_scrape_result() — all three execution paths.

Uses in-memory SQLite (no .env, no file DB required).
Tests: success+units, success+zero-units, zero-units-at-threshold, failure.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moxie.db.models import Base, Building, Unit, ScrapeRun
from moxie.scrapers.base import save_scrape_result, CONSECUTIVE_ZERO_THRESHOLD


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


@pytest.fixture
def building(db):
    """A minimal Building row inserted into the in-memory DB."""
    b = Building(
        name="Test Building",
        url="https://example.com",
        last_scrape_status="never",
        consecutive_zero_count=0,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


SAMPLE_RAW_UNIT = {
    "unit_number": "101",
    "bed_type": "1BR",
    "rent": "1500",
    "availability_date": "2026-04-01",
}

SAMPLE_RAW_UNIT_2 = {
    "unit_number": "202",
    "bed_type": "2BR",
    "rent": "2000",
    "availability_date": "2026-05-01",
}


# ---------------------------------------------------------------------------
# Helper: insert a pre-existing unit directly
# ---------------------------------------------------------------------------

def _insert_unit(db, building_id: int, unit_number: str = "999") -> Unit:
    """Insert a Unit row directly to simulate pre-existing scraped units."""
    from datetime import datetime, timezone
    u = Unit(
        building_id=building_id,
        unit_number=unit_number,
        bed_type="Studio",
        non_canonical=False,
        rent_cents=100000,
        availability_date="2026-01-01",
        scrape_run_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    return u


# ---------------------------------------------------------------------------
# Path 1: Success + Units
# ---------------------------------------------------------------------------

class TestSaveSuccessWithUnits:
    def test_old_units_deleted(self, db, building):
        """Pre-existing units are deleted before new ones are inserted."""
        _insert_unit(db, building.id, unit_number="OLD-1")
        _insert_unit(db, building.id, unit_number="OLD-2")

        save_scrape_result(
            db, building, [SAMPLE_RAW_UNIT], scrape_succeeded=True
        )

        units = db.query(Unit).filter(Unit.building_id == building.id).all()
        unit_numbers = {u.unit_number for u in units}
        assert "OLD-1" not in unit_numbers
        assert "OLD-2" not in unit_numbers

    def test_new_units_inserted(self, db, building):
        """New normalized units are inserted for the building."""
        save_scrape_result(
            db, building, [SAMPLE_RAW_UNIT, SAMPLE_RAW_UNIT_2], scrape_succeeded=True
        )

        units = db.query(Unit).filter(Unit.building_id == building.id).all()
        assert len(units) == 2
        unit_numbers = {u.unit_number for u in units}
        assert "101" in unit_numbers
        assert "202" in unit_numbers

    def test_consecutive_zero_count_reset_to_zero(self, db, building):
        """consecutive_zero_count is reset to 0 after a successful scrape with units."""
        building.consecutive_zero_count = 3
        db.commit()

        save_scrape_result(
            db, building, [SAMPLE_RAW_UNIT], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.consecutive_zero_count == 0

    def test_last_scrape_status_is_success(self, db, building):
        """last_scrape_status set to 'success' after successful scrape with units."""
        save_scrape_result(
            db, building, [SAMPLE_RAW_UNIT], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.last_scrape_status == "success"

    def test_scrape_run_logged_with_correct_count(self, db, building):
        """ScrapeRun is logged with status='success' and unit_count=N."""
        save_scrape_result(
            db, building, [SAMPLE_RAW_UNIT, SAMPLE_RAW_UNIT_2], scrape_succeeded=True
        )

        runs = db.query(ScrapeRun).filter(ScrapeRun.building_id == building.id).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "success"
        assert run.unit_count == 2
        assert run.error_message is None

    def test_units_normalized_correctly(self, db, building):
        """Units are normalized — rent stored as cents, bed_type canonical."""
        save_scrape_result(
            db, building, [SAMPLE_RAW_UNIT], scrape_succeeded=True
        )

        unit = db.query(Unit).filter(Unit.building_id == building.id).first()
        assert unit is not None
        assert unit.rent_cents == 150000  # $1500 * 100
        assert unit.bed_type == "1BR"
        assert unit.unit_number == "101"


# ---------------------------------------------------------------------------
# Path 2: Success + Zero Units (below threshold)
# ---------------------------------------------------------------------------

class TestSaveSuccessZeroUnits:
    def test_existing_units_deleted(self, db, building):
        """Even on zero-unit success, existing units are deleted."""
        _insert_unit(db, building.id, unit_number="EXISTING-1")

        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        unit_count = db.query(Unit).filter(Unit.building_id == building.id).count()
        assert unit_count == 0

    def test_consecutive_zero_count_incremented(self, db, building):
        """consecutive_zero_count increments by 1 on each zero-unit success."""
        building.consecutive_zero_count = 1
        db.commit()

        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.consecutive_zero_count == 2

    def test_last_scrape_status_is_success_below_threshold(self, db, building):
        """last_scrape_status='success' when zero-unit count is below threshold."""
        building.consecutive_zero_count = 1
        db.commit()

        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.last_scrape_status == "success"

    def test_scrape_run_logged_with_unit_count_zero(self, db, building):
        """ScrapeRun logged with status='success' and unit_count=0."""
        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        runs = db.query(ScrapeRun).filter(ScrapeRun.building_id == building.id).all()
        assert len(runs) == 1
        assert runs[0].status == "success"
        assert runs[0].unit_count == 0

    def test_first_zero_increments_from_zero(self, db, building):
        """First zero-unit success increments from 0 to 1."""
        assert building.consecutive_zero_count == 0

        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.consecutive_zero_count == 1


# ---------------------------------------------------------------------------
# Path 3: Zero Units at Threshold
# ---------------------------------------------------------------------------

class TestSaveZeroUnitsAtThreshold:
    def test_needs_attention_at_exact_threshold(self, db, building):
        """last_scrape_status='needs_attention' when consecutive_zero_count reaches CONSECUTIVE_ZERO_THRESHOLD."""
        building.consecutive_zero_count = CONSECUTIVE_ZERO_THRESHOLD - 1
        db.commit()

        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.consecutive_zero_count == CONSECUTIVE_ZERO_THRESHOLD
        assert building.last_scrape_status == "needs_attention"

    def test_needs_attention_above_threshold(self, db, building):
        """last_scrape_status='needs_attention' when count exceeds threshold."""
        building.consecutive_zero_count = CONSECUTIVE_ZERO_THRESHOLD + 2
        db.commit()

        save_scrape_result(
            db, building, [], scrape_succeeded=True
        )

        db.refresh(building)
        assert building.last_scrape_status == "needs_attention"

    def test_threshold_constant_is_five(self):
        """CONSECUTIVE_ZERO_THRESHOLD is 5 per specification."""
        assert CONSECUTIVE_ZERO_THRESHOLD == 5

    def test_five_consecutive_zeros_sets_needs_attention(self, db, building):
        """Simulate 5 consecutive zero-unit scrapes; final status is 'needs_attention'."""
        for _ in range(CONSECUTIVE_ZERO_THRESHOLD):
            save_scrape_result(
                db, building, [], scrape_succeeded=True
            )

        db.refresh(building)
        assert building.consecutive_zero_count == CONSECUTIVE_ZERO_THRESHOLD
        assert building.last_scrape_status == "needs_attention"

    def test_four_consecutive_zeros_still_success(self, db, building):
        """4 consecutive zeros (one below threshold) keeps status='success'."""
        for _ in range(CONSECUTIVE_ZERO_THRESHOLD - 1):
            save_scrape_result(
                db, building, [], scrape_succeeded=True
            )

        db.refresh(building)
        assert building.consecutive_zero_count == CONSECUTIVE_ZERO_THRESHOLD - 1
        assert building.last_scrape_status == "success"


# ---------------------------------------------------------------------------
# Path 4: Failure — units retained, zero count unchanged
# ---------------------------------------------------------------------------

class TestSaveFailureRetainsUnits:
    def test_existing_units_retained(self, db, building):
        """On scrape failure, pre-existing units are NOT deleted."""
        _insert_unit(db, building.id, unit_number="KEEP-1")
        _insert_unit(db, building.id, unit_number="KEEP-2")

        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message="Connection timeout"
        )

        unit_count = db.query(Unit).filter(Unit.building_id == building.id).count()
        assert unit_count == 2

    def test_unit_numbers_unchanged_after_failure(self, db, building):
        """The exact same units remain after a failed scrape."""
        _insert_unit(db, building.id, unit_number="KEEP-1")

        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message="Timeout"
        )

        units = db.query(Unit).filter(Unit.building_id == building.id).all()
        assert len(units) == 1
        assert units[0].unit_number == "KEEP-1"

    def test_last_scrape_status_is_failed(self, db, building):
        """last_scrape_status='failed' after a scrape failure."""
        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message="HTTP 500"
        )

        db.refresh(building)
        assert building.last_scrape_status == "failed"

    def test_consecutive_zero_count_not_incremented(self, db, building):
        """Failure does NOT increment consecutive_zero_count."""
        building.consecutive_zero_count = 2
        db.commit()

        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message="Network error"
        )

        db.refresh(building)
        assert building.consecutive_zero_count == 2

    def test_scrape_run_logged_with_failed_status(self, db, building):
        """ScrapeRun logged with status='failed' and unit_count=0."""
        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message="Connection refused"
        )

        runs = db.query(ScrapeRun).filter(ScrapeRun.building_id == building.id).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "failed"
        assert run.unit_count == 0

    def test_error_message_propagated_to_scrape_run(self, db, building):
        """Error message is stored in ScrapeRun.error_message."""
        error_msg = "HTTPError: 503 Service Unavailable"
        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message=error_msg
        )

        run = db.query(ScrapeRun).filter(ScrapeRun.building_id == building.id).first()
        assert run.error_message == error_msg

    def test_failure_with_no_error_message(self, db, building):
        """Failure with no error message stores None in ScrapeRun.error_message."""
        save_scrape_result(
            db, building, [], scrape_succeeded=False
        )

        run = db.query(ScrapeRun).filter(ScrapeRun.building_id == building.id).first()
        assert run.error_message is None
        assert run.status == "failed"

    def test_last_scraped_at_updated_on_failure(self, db, building):
        """last_scraped_at is updated even on failure."""
        assert building.last_scraped_at is None

        save_scrape_result(
            db, building, [], scrape_succeeded=False, error_message="Error"
        )

        db.refresh(building)
        assert building.last_scraped_at is not None


# ---------------------------------------------------------------------------
# Cross-path: Multiple calls, alternating outcomes
# ---------------------------------------------------------------------------

class TestMultipleCallBehavior:
    def test_recovery_from_zero_units_resets_count(self, db, building):
        """After zero-unit streak, a successful scrape with units resets count to 0."""
        # Drive up consecutive zeros
        for _ in range(3):
            save_scrape_result(db, building, [], scrape_succeeded=True)
        db.refresh(building)
        assert building.consecutive_zero_count == 3

        # Successful scrape with units
        save_scrape_result(db, building, [SAMPLE_RAW_UNIT], scrape_succeeded=True)
        db.refresh(building)
        assert building.consecutive_zero_count == 0
        assert building.last_scrape_status == "success"

    def test_failure_does_not_break_zero_streak(self, db, building):
        """Failures interspersed with zero-unit successes don't affect zero count."""
        save_scrape_result(db, building, [], scrape_succeeded=True)
        save_scrape_result(db, building, [], scrape_succeeded=False, error_message="err")
        save_scrape_result(db, building, [], scrape_succeeded=True)

        db.refresh(building)
        # Two zero-unit successes, one failure (not counted)
        assert building.consecutive_zero_count == 2
