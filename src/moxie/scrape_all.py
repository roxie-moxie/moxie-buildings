"""
Batch scrape CLI entrypoint.

Usage:
    scrape-all                    # Run batch immediately, then exit
    scrape-all --run-now          # Same as above (explicit)
    scrape-all --dry-run          # List buildings without scraping
    scrape-all --skip-sync        # Skip Google Sheets sync step

Entrypoint: moxie.scrape_all:main (registered as `scrape-all` in pyproject.toml)
"""
import argparse
import logging
import sys

from moxie.scheduler.batch import run_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a full batch scrape of all buildings."
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        default=True,
        help="Run batch immediately, then exit (default behavior)",
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

    # Configure console logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    results = run_batch(
        skip_sheets_sync=args.skip_sync,
        dry_run=args.dry_run,
    )

    # Print summary
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    total_units = sum(r["unit_count"] for r in results)

    print(f"\nBatch complete: {successes} ok, {failures} failed, {total_units} total units")

    if failures > 0:
        print(f"\nFailed buildings:")
        for r in results:
            if r["status"] == "failed":
                print(f"  {r['building_name']}: {r.get('error', 'unknown error')}")


if __name__ == "__main__":
    main()
