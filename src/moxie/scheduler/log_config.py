"""Logging configuration for batch scrape runs."""
import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(log_dir: str = "logs") -> None:
    """
    Configure moxie.scheduler logger with rotating file handler.

    Creates the log directory if it doesn't exist.
    File: logs/scrape_batch.log (5 MB per file, 7 backups = ~40 MB max)
    """
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, "scrape_batch.log"),
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))

    logger = logging.getLogger("moxie.scheduler")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
