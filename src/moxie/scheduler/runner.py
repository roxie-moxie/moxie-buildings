"""Per-building scrape wrapper with error isolation and clear-on-failure."""
import importlib
import logging
import time
from datetime import datetime, timezone

from moxie.db.models import Building, Unit, ScrapeRun
from moxie.db.session import SessionLocal
from moxie.scrapers.base import save_scrape_result
from moxie.scrapers.registry import PLATFORM_SCRAPERS
from moxie.normalizer import normalize
from pydantic import ValidationError

logger = logging.getLogger("moxie.scheduler")

# Inter-scrape delay per platform type (seconds)
BROWSER_DELAY = 1.0  # Crawl4AI/Playwright platforms — be polite
HTTP_DELAY = 0.2      # HTTP-only scrapers — lighter footprint

_BROWSER_PLATFORMS = {"rentcafe", "groupfox", "llm", "entrata", "mri", "funnel", "bozzuto", "ppm"}


def scrape_one_building(building_id: int, building_name: str, building_url: str, platform: str) -> dict:
    """
    Scrape a single building and save results to DB. Called from a thread pool thread.

    Args:
        building_id: Building primary key
        building_name: For logging/reporting
        building_url: For logging/reporting
        platform: Platform key from PLATFORM_SCRAPERS

    Returns:
        dict with keys: building_id, building_name, platform, status ("success"|"failed"),
        unit_count (int), error (str|None), scraped_at (str ISO)
    """
    now = datetime.now(timezone.utc)
    result = {
        "building_id": building_id,
        "building_name": building_name,
        "platform": platform,
        "status": "failed",
        "unit_count": 0,
        "error": None,
        "scraped_at": now.strftime("%Y-%m-%d %H:%M UTC"),
    }

    db = SessionLocal()
    try:
        building = db.get(Building, building_id)
        if building is None:
            result["error"] = f"Building ID {building_id} not found in DB"
            return result

        # Import and call the scraper
        mod = importlib.import_module(PLATFORM_SCRAPERS[platform])
        raw_units: list[dict] = mod.scrape(building)

        # Save success: delete old units, insert new normalized units
        db.query(Unit).filter(Unit.building_id == building.id).delete()

        saved_count = 0
        if raw_units:
            for raw in raw_units:
                try:
                    unit_dict = normalize(raw, building.id)
                    db.add(Unit(**unit_dict))
                    saved_count += 1
                except (ValidationError, ValueError):
                    pass  # Skip unparseable units

        # Update building status
        if saved_count > 0:
            building.consecutive_zero_count = 0
            building.last_scrape_status = "success"
        else:
            building.consecutive_zero_count = (building.consecutive_zero_count or 0) + 1
            if building.consecutive_zero_count >= 5:
                building.last_scrape_status = "needs_attention"
            else:
                building.last_scrape_status = "success"

        building.last_scraped_at = now

        # Log scrape run
        db.add(ScrapeRun(
            building_id=building.id,
            run_at=now,
            status="success",
            unit_count=saved_count,
        ))
        db.commit()

        result["status"] = "success"
        result["unit_count"] = saved_count
        logger.info(f"OK  {building_name}: {saved_count} units ({platform})")

    except Exception as e:
        db.rollback()
        error_msg = f"[{type(e).__name__}] {str(e)[:500]}"
        result["error"] = error_msg

        # Retain units on failure, mark building stale — delegates to save_scrape_result()
        try:
            building = db.get(Building, building_id)
            if building:
                save_scrape_result(
                    db,
                    building,
                    raw_units=[],
                    scrape_succeeded=False,
                    error_message=error_msg[:1000],
                )
        except Exception:
            logger.error(f"Failed to record failure for {building_name}: {e}")

        logger.warning(f"FAIL {building_name}: {error_msg} ({platform})")
    finally:
        db.close()

    # Inter-scrape delay (politeness)
    delay = BROWSER_DELAY if platform in _BROWSER_PLATFORMS else HTTP_DELAY
    time.sleep(delay)

    return result
