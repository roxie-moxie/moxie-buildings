"""Batch scrape orchestrator: sheets_sync -> parallel scrape -> summary."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from moxie.db.models import Building
from moxie.db.session import SessionLocal
from moxie.scrapers.registry import PLATFORM_SCRAPERS, SKIP_PLATFORMS
from moxie.scheduler.runner import scrape_one_building
from moxie.sync.sheets import sheets_sync

logger = logging.getLogger("moxie.scheduler")

# Per-platform concurrency: browser-based = 1, HTTP-based = 2
PLATFORM_CONCURRENCY: dict[str, int] = {
    "rentcafe": 1,   # Crawl4AI / Playwright
    "groupfox": 1,
    "llm":      1,
    "entrata":  1,
    "mri":      1,
    "funnel":   1,
    "bozzuto":  1,
    "ppm":      1,   # Shared page — serialize to avoid duplicate fetches
    "sightmap": 2,   # HTTP only
    "appfolio": 2,
    "realpage": 1,
}

# Thread-safe semaphores — created once, shared across threads
_semaphores: dict[str, threading.Semaphore] = {
    p: threading.Semaphore(n) for p, n in PLATFORM_CONCURRENCY.items()
}
_default_sem = threading.Semaphore(1)

MAX_WORKERS = 8  # Thread pool size — most threads block on I/O or semaphore


def _prune_old_runs(days: int = 30) -> int:
    """Delete scrape_runs rows older than `days` days. Returns count deleted."""
    from moxie.db.models import ScrapeRun
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        count = db.query(ScrapeRun).filter(ScrapeRun.run_at < cutoff).delete()
        db.commit()
        logger.info(f"Pruned {count} scrape_runs older than {days} days")
        return count
    except Exception as e:
        logger.error(f"Failed to prune old scrape_runs: {e}")
        return 0
    finally:
        db.close()


def _scrape_with_semaphore(building_id: int, name: str, url: str, platform: str) -> dict:
    """Acquire platform semaphore, then call scrape_one_building."""
    sem = _semaphores.get(platform, _default_sem)
    with sem:
        return scrape_one_building(building_id, name, url, platform)


def run_batch(*, skip_sheets_sync: bool = False, dry_run: bool = False) -> list[dict]:
    """
    Execute a full batch scrape cycle.

    1. Pull building list from Google Sheets (unless skip_sheets_sync=True)
    2. Fan out scrapes across threads with per-platform semaphores
    3. Return list of per-building result dicts

    Args:
        skip_sheets_sync: Skip the Sheets pull step (useful for testing)
        dry_run: Log which buildings would be scraped, but don't actually scrape

    Returns:
        List of result dicts from scrape_one_building
    """
    start_time = datetime.now(timezone.utc)
    logger.info("=== Batch scrape starting ===")

    # Step 1: Sheets sync (pull building list)
    if not skip_sheets_sync:
        logger.info("Step 1: Syncing building list from Google Sheets...")
        db = SessionLocal()
        try:
            sync_result = sheets_sync(db)
            logger.info(
                f"Sheets sync: added={sync_result['added']}, "
                f"updated={sync_result['updated']}, "
                f"deleted={sync_result['deleted']}, "
                f"skipped={sync_result['skipped']}"
            )
        except Exception as e:
            logger.error(f"Sheets sync failed: {e} — continuing with existing building list")
        finally:
            db.close()
    else:
        logger.info("Step 1: Skipping sheets sync (--skip-sync)")

    # Step 2: Load all scrapeable buildings
    db = SessionLocal()
    try:
        buildings = db.query(Building).filter(
            Building.platform.notin_(SKIP_PLATFORMS),
            Building.platform.isnot(None),
        ).all()

        # Build list of (id, name, url, platform) tuples — detach from session
        building_specs = []
        for b in buildings:
            platform = b.platform
            if platform not in PLATFORM_SCRAPERS:
                logger.debug(f"Skipping {b.name}: platform '{platform}' has no scraper")
                continue
            building_specs.append((b.id, b.name, b.url, platform))
    finally:
        db.close()

    logger.info(f"Step 2: {len(building_specs)} buildings to scrape")

    if dry_run:
        logger.info("DRY RUN — listing buildings without scraping:")
        results = []
        for bid, name, url, platform in building_specs:
            logger.info(f"  [dry-run] {name} ({platform})")
            results.append({
                "building_id": bid,
                "building_name": name,
                "platform": platform,
                "status": "dry_run",
                "unit_count": 0,
                "error": None,
                "scraped_at": start_time.strftime("%Y-%m-%d %H:%M UTC"),
            })
        return results

    # Step 3: Fan out scrapes with thread pool
    logger.info(f"Step 3: Scraping with {MAX_WORKERS} workers...")
    results = []
    completed = 0
    total = len(building_specs)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_scrape_with_semaphore, bid, name, url, platform): (bid, name)
            for bid, name, url, platform in building_specs
        }
        for future in as_completed(futures):
            bid, name = futures[future]
            try:
                result = future.result()
            except Exception as e:
                # Should not reach here — scrape_one_building handles all exceptions
                result = {
                    "building_id": bid,
                    "building_name": name,
                    "platform": "unknown",
                    "status": "error",
                    "unit_count": 0,
                    "error": f"Unhandled: {e}",
                    "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                }
            results.append(result)
            completed += 1
            if completed % 50 == 0 or completed == total:
                logger.info(f"  Progress: {completed}/{total}")

    # Summary
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    total_units = sum(r["unit_count"] for r in results)
    logger.info(
        f"=== Batch complete: {successes} ok, {failures} failed, "
        f"{total_units} total units, {elapsed:.0f}s elapsed ==="
    )

    # Step 4: Push status to Google Sheets
    from moxie.scheduler.sheets_status import push_batch_status
    push_batch_status(results)

    # Step 5: Push updated availability data to Google Sheets
    try:
        from moxie.sync.push_availability import push_availability
        db = SessionLocal()
        try:
            count = push_availability(db)
            logger.info(f"Pushed {count} units to Availability tab")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to push availability to Sheets: {e}")

    # Step 6: Prune old scrape_runs
    _prune_old_runs()

    return results
