"""
Batch scrape CLI entrypoint.

Usage:
    scrape-all                    # Run batch immediately, then exit
    scrape-all --run-now          # Same as above (explicit)
    scrape-all --schedule         # Enter scheduled mode (2 AM Central daily, blocks)
    scrape-all --dry-run          # List buildings without scraping
    scrape-all --skip-sync        # Skip Google Sheets sync step

Entrypoint: moxie.scrape_all:main (registered as `scrape-all` in pyproject.toml)
"""
import argparse
import logging
import sys

from moxie.scheduler.batch import run_batch
from moxie.scheduler.log_config import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a full batch scrape of all buildings."
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--run-now",
        action="store_true",
        default=False,
        help="Run batch immediately, then exit (default if no mode specified)",
    )
    mode_group.add_argument(
        "--schedule",
        action="store_true",
        default=False,
        help="Enter scheduled mode: APScheduler fires at 2 AM Central daily (blocks)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List buildings to scrape without actually scraping",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        default=False,
        help="Skip the Google Sheets building list sync step",
    )
    args = parser.parse_args()

    # Configure logging: rotating file + console
    configure_logging()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    # Default to run-now if neither --run-now nor --schedule specified
    if not args.schedule:
        # Immediate run mode
        results = run_batch(
            skip_sheets_sync=args.skip_sync,
            dry_run=args.dry_run,
        )

        successes = sum(1 for r in results if r["status"] == "success")
        failures = sum(1 for r in results if r["status"] == "failed")
        total_units = sum(r["unit_count"] for r in results)

        print(f"\nBatch complete: {successes} ok, {failures} failed, {total_units} total units")

        if failures > 0:
            print(f"\nFailed buildings:")
            for r in results:
                if r["status"] == "failed":
                    print(f"  {r['building_name']}: {r.get('error', 'unknown error')}")
    else:
        # Scheduled mode: APScheduler blocks, fires at 2 AM Central daily
        from zoneinfo import ZoneInfo
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        from datetime import datetime as _datetime
        tz = ZoneInfo("America/Chicago")
        scheduler = BlockingScheduler(timezone=tz)
        job = scheduler.add_job(
            run_batch,
            CronTrigger(hour=2, minute=0),
            id="daily_scrape",
            name="Daily full-building scrape",
            misfire_grace_time=3600,   # Run within 1h of missed trigger
            coalesce=True,              # Only run once if multiple firings missed
            max_instances=1,            # Never run two batch jobs concurrently
        )

        # next_run_time is only set after scheduler.start(); use trigger directly
        next_run = job.trigger.get_next_fire_time(None, _datetime.now(tz))

        logger = logging.getLogger("moxie.scheduler")
        logger.info(f"Scheduler started. Next run: {next_run}")
        print(f"Scheduler started. Next run at {next_run}. Press Ctrl+C to stop.")

        try:
            scheduler.start()  # Blocks until KeyboardInterrupt or SystemExit
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler shutting down...")
            scheduler.shutdown()
            print("Scheduler stopped.")


if __name__ == "__main__":
    main()
