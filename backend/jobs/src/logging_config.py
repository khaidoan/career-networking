"""Process-wide logging: stdout plus a daily-rotated log file kept for ``LOG_RETENTION_DAYS``.

Each process writes its own file (the API to ``career_networking.log``, the fetcher to
``fetcher.log``) because two processes cannot safely rotate the same file.
"""

import logging
import logging.config
import time
from pathlib import Path

LOG_FILE_NAME = "career_networking.log"
FETCHER_LOG_FILE_NAME = "fetcher.log"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
# The current file plus this many days minus one of rotated files; nothing older is kept.
LOG_RETENTION_DAYS = 3

logger = logging.getLogger(__name__)


def configure_logging(
    log_folder: Path, level: str = "INFO", file_name: str = LOG_FILE_NAME
) -> None:
    """Send application logs to stdout and ``<log_folder>/<file_name>``, rotated at midnight UTC.

    Never pass passwords, tokens or secrets to a logger; log identifiers such as client IPs instead.
    """
    log_folder.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": LOG_FORMAT}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "standard",
                },
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": str(log_folder / file_name),
                    "when": "midnight",
                    "utc": True,
                    "backupCount": LOG_RETENTION_DAYS - 1,
                    "encoding": "utf-8",
                    "formatter": "standard",
                },
            },
            "root": {"level": level, "handlers": ["stdout", "file"]},
        }
    )
    remove_expired_logs(log_folder)


def remove_expired_logs(log_folder: Path, now: float | None = None) -> int:
    """Delete rotated log files last written more than ``LOG_RETENTION_DAYS`` ago.

    Rotation only prunes backups when a process logs past midnight, so this also covers files
    left behind by a process that went quiet (or by an older naming scheme).
    """
    cutoff = (now if now is not None else time.time()) - LOG_RETENTION_DAYS * 86400
    removed = 0
    for base in (LOG_FILE_NAME, FETCHER_LOG_FILE_NAME):
        for path in log_folder.glob(f"{base}.*"):
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError as error:
                logger.warning("Could not remove expired log file %s: %s", path.name, error)
    if removed:
        logger.info("Removed %d log files older than %d days", removed, LOG_RETENTION_DAYS)
    return removed
