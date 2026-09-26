"""Fetcher run state: Google Jobs last-run time, sweep cursor and the directory cache folder.

[UNCONFIRMED: D3] State lives in files under ``CAREER_NETWORKING_JOB_DATA/_fetcher/``. Every
other module uses only the ``FetcherState`` interface returned by ``get_fetcher_state``, so the
storage can move (for example to a database table) by changing this module alone. Losing the
files only resets the Google Jobs schedule and the sweep rotation.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from src.config import Settings

logger = logging.getLogger(__name__)

STATE_FOLDER_NAME = "_fetcher"
STATE_FILE_NAME = "state.json"
DIRECTORY_CACHE_FOLDER_NAME = "directory_cache"


class FetcherState(Protocol):
    def get_google_jobs_last_run(self) -> datetime | None: ...

    def set_google_jobs_last_run(self, when: datetime) -> None: ...

    def get_sweep_cursor(self) -> int: ...

    def set_sweep_cursor(self, cursor: int) -> None: ...

    def directory_cache_dir(self) -> Path: ...


def write_atomically(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` through a temporary file so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(descriptor, "wb") as temp_file:
            temp_file.write(data)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


class FileFetcherState:
    """``FetcherState`` backed by one small JSON file."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder
        self._state_file = folder / STATE_FILE_NAME

    def get_google_jobs_last_run(self) -> datetime | None:
        value = self._read().get("google_jobs_last_run")
        if value is None:
            return None
        try:
            when = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            logger.warning("Fetcher state: invalid Google Jobs last-run time, resetting")
            return None
        return when if when.tzinfo else None

    def set_google_jobs_last_run(self, when: datetime) -> None:
        self._update(google_jobs_last_run=when.isoformat())

    def get_sweep_cursor(self) -> int:
        value = self._read().get("sweep_cursor", 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            logger.warning("Fetcher state: invalid sweep cursor, resetting")
            return 0
        return value

    def set_sweep_cursor(self, cursor: int) -> None:
        self._update(sweep_cursor=cursor)

    def directory_cache_dir(self) -> Path:
        folder = self._folder / DIRECTORY_CACHE_FOLDER_NAME
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            logger.warning("Fetcher state file is unreadable, starting from defaults")
            return {}
        if not isinstance(data, dict):
            logger.warning("Fetcher state file is malformed, starting from defaults")
            return {}
        return data

    def _update(self, **values: Any) -> None:
        data = self._read() | values
        write_atomically(self._state_file, json.dumps(data, indent=2).encode("utf-8"))


def get_fetcher_state(settings: Settings) -> FetcherState:
    return FileFetcherState(settings.job_data / STATE_FOLDER_NAME)
