"""
Scraper base infrastructure.

ScraperProtocol: typing.Protocol that all scraper modules satisfy structurally.
save_scrape_result(): centralized DB write function called by all scrapers.
"""
from datetime import datetime, timezone
from typing import Protocol
from sqlalchemy.orm import Session
from moxie.db.models import Building, Unit, ScrapeRun
from moxie.normalizer import normalize

CONSECUTIVE_ZERO_THRESHOLD = 5


class ScraperProtocol(Protocol):
    def scrape(self, building: Building) -> list[dict]:
        """Return list of raw unit dicts (pre-normalization). Empty list = no units."""
        ...


def save_scrape_result(
    db: Session,
    building: Building,
    raw_units: list[dict],
    *,
    scrape_succeeded: bool,
    error_message: str | None = None,
) -> None:
    """
    Write scrape results to the database. Called by all scrapers after scrape().

    On success (scrape_succeeded=True):
      - Deletes all existing units for this building (delete then re-insert)
      - If raw_units non-empty: inserts normalized units, resets consecutive_zero_count to 0
      - If raw_units empty: increments consecutive_zero_count; sets last_scrape_status
        to 'needs_attention' after CONSECUTIVE_ZERO_THRESHOLD consecutive zeros
      - Sets last_scrape_status='success' (or 'needs_attention' at threshold)
      - Sets last_scraped_at=now

    On failure (scrape_succeeded=False):
      - Retains existing units (no delete)
      - Sets last_scrape_status='failed', last_scraped_at=now
      - Does NOT increment consecutive_zero_count (errors != zero-unit success)

    Always logs a ScrapeRun record.
    """
    now = datetime.now(timezone.utc)

    if scrape_succeeded:
        db.query(Unit).filter(Unit.building_id == building.id).delete()

        if raw_units:
            for raw in raw_units:
                unit_dict = normalize(raw, building.id)
                db.add(Unit(**unit_dict))
            building.consecutive_zero_count = 0
            building.last_scrape_status = "success"
        else:
            building.consecutive_zero_count = (building.consecutive_zero_count or 0) + 1
            if building.consecutive_zero_count >= CONSECUTIVE_ZERO_THRESHOLD:
                building.last_scrape_status = "needs_attention"
            else:
                building.last_scrape_status = "success"

        building.last_scraped_at = now
    else:
        building.last_scrape_status = "failed"
        building.last_scraped_at = now

    db.add(ScrapeRun(
        building_id=building.id,
        run_at=now,
        status="success" if scrape_succeeded else "failed",
        unit_count=len(raw_units) if scrape_succeeded else 0,
        error_message=error_message,
    ))
    db.commit()
