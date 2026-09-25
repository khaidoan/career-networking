"""Process-wide logging: stdout plus the central ``career_networking.log`` file."""

import logging.config
from pathlib import Path

LOG_FILE_NAME = "career_networking.log"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(log_folder: Path, level: str = "INFO") -> None:
    """Send application logs to stdout and ``<log_folder>/career_networking.log``.

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
                    "class": "logging.FileHandler",
                    "filename": str(log_folder / LOG_FILE_NAME),
                    "encoding": "utf-8",
                    "formatter": "standard",
                },
            },
            "root": {"level": level, "handlers": ["stdout", "file"]},
        }
    )
