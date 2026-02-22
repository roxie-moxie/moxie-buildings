"""
Regression tests for scrape_one_building() failure handling.

Proves that when a scraper raises an exception:
  - Existing units in the DB are retained (not deleted)
  - The building is marked stale (last_scrape_status='failed')
  - A ScrapeRun record is logged with status='failed'

Uses in-memory SQLite (no .env, no file DB required).
Patches SessionLocal in moxie.scheduler.runner to return a fresh session
from the test engine. Uses a separate inspection session to verify state
after the runner closes its own session.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from moxie.db.models import Base, Building, Unit, ScrapeRun


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """In-memory SQLite engine with schema created. Shared within one test."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def Session(engine):
    """Session factory for the test engine."""
    return sessionmaker(bind=engine)


@pytest.fixture
def building(Session):
    """A minimal Building row inserted into the in-memory DB."""
    with Session() as s:
        b = Building(
            name="Test Building",
            url="https://example.com",
            platform="sightmap",
            last_scrape_status="success",
            consecutive_zero_count=0,
        )
        s.add(b)
        s.commit()
        building_id = b.id
    return building_id


def _insert_unit(Session, building_id: int, unit_number: str = "101") -> None:
    """Insert a Unit row directly to simulate pre-existing scraped units."""
    with Session() as s:
        u = Unit(
            building_id=building_id,
            unit_number=unit_number,
            bed_type="1BR",
            non_canonical=False,
            rent_cents=200000,
            availability_date="2026-03-01",
            scrape_run_at=datetime.now(timezone.utc),
        )
        s.add(u)
        s.commit()


# ---------------------------------------------------------------------------
# Helper: run scrape_one_building with patched session factory and failing import
# ---------------------------------------------------------------------------

def _run_with_failure(Session, building_id):
    """
    Call scrape_one_building() with:
      - SessionLocal patched to use the test Session factory
      - importlib.import_module patched to raise RuntimeError("Network timeout")
      - time.sleep suppressed

    The runner calls db = SessionLocal() then db.close() in the finally block.
    Since we patch SessionLocal to our test factory, the runner gets a real
    session backed by the in-memory DB, and after close() the data is persisted
    in the engine.
    """
    from moxie.scheduler.runner import scrape_one_building

    with (
        patch("moxie.scheduler.runner.SessionLocal", Session),
        patch(
            "moxie.scheduler.runner.PLATFORM_SCRAPERS",
            {"sightmap": "moxie.scrapers.tier2.sightmap"},
        ),
        patch("moxie.scheduler.runner.time") as mock_time,
    ):
        mock_time.sleep.return_value = None
        # Patch importlib at the runner module level so setup patches are already active
        with patch(
            "moxie.scheduler.runner.importlib.import_module",
            side_effect=RuntimeError("Network timeout"),
        ):
            return scrape_one_building(
                building_id=building_id,
                building_name="Test Building",
                building_url="https://example.com",
                platform="sightmap",
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunnerFailureHandling:
    def test_units_retained_on_scraper_exception(self, Session, building):
        """Pre-seeded units are NOT deleted when the scraper raises an exception."""
        _insert_unit(Session, building, unit_number="101")

        result = _run_with_failure(Session, building)

        # Inspect DB state via a fresh session (runner closed its own session)
        with Session() as inspect:
            unit_count = inspect.query(Unit).filter(Unit.building_id == building).count()

        assert unit_count == 1, (
            f"Expected 1 unit retained after failure, got {unit_count}. "
            f"Runner result: {result}"
        )

    def test_building_marked_stale_on_failure(self, Session, building):
        """Building.last_scrape_status='failed' and last_scraped_at is set after exception."""
        _run_with_failure(Session, building)

        # Inspect DB state via a fresh session (runner closed its own session)
        with Session() as inspect:
            b = inspect.get(Building, building)
            status = b.last_scrape_status
            scraped_at = b.last_scraped_at

        assert status == "failed", (
            f"Expected last_scrape_status='failed', got '{status}'"
        )
        assert scraped_at is not None, (
            "Expected last_scraped_at to be set after failure, but it is None"
        )

    def test_scrape_run_logged_on_failure(self, Session, building):
        """A ScrapeRun record is logged with status='failed', unit_count=0, and error_message."""
        _run_with_failure(Session, building)

        # Inspect DB state via a fresh session (runner closed its own session)
        with Session() as inspect:
            runs = inspect.query(ScrapeRun).filter(ScrapeRun.building_id == building).all()
            run_data = [(r.status, r.unit_count, r.error_message) for r in runs]

        assert len(run_data) == 1, f"Expected 1 ScrapeRun record, got {len(run_data)}"

        status, unit_count, error_message = run_data[0]
        assert status == "failed", f"Expected status='failed', got '{status}'"
        assert unit_count == 0, f"Expected unit_count=0, got {unit_count}"
        assert error_message is not None, "Expected error_message to be set"
        assert "Network timeout" in error_message, (
            f"Expected 'Network timeout' in error_message, got: '{error_message}'"
        )
