import logging
import logging.handlers
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.logging_config import (
    FETCHER_LOG_FILE_NAME,
    LOG_FILE_NAME,
    LOG_RETENTION_DAYS,
    configure_logging,
    remove_expired_logs,
)


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers, root.level = handlers, level


def _age(path: Path, days: float) -> None:
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


def test_each_process_gets_its_own_daily_rotated_file(
    tmp_path: Path, restore_root_logger: None
) -> None:
    configure_logging(tmp_path, file_name=FETCHER_LOG_FILE_NAME)
    logging.getLogger("src.fetcher").info("hello")

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.handlers.TimedRotatingFileHandler)
    ]
    assert len(handlers) == 1
    handler = handlers[0]
    assert Path(handler.baseFilename) == tmp_path / FETCHER_LOG_FILE_NAME
    assert (handler.when, handler.utc, handler.backupCount) == ("MIDNIGHT", True, 2)
    assert "hello" in (tmp_path / FETCHER_LOG_FILE_NAME).read_text(encoding="utf-8")
    assert not (tmp_path / LOG_FILE_NAME).exists()


def test_rotated_files_older_than_the_retention_are_removed(tmp_path: Path) -> None:
    expired = [
        tmp_path / f"{LOG_FILE_NAME}.2026-09-20",
        tmp_path / f"{FETCHER_LOG_FILE_NAME}.2026-09-21",
    ]
    kept = [
        tmp_path / f"{LOG_FILE_NAME}.2026-09-24",
        tmp_path / LOG_FILE_NAME,  # the live file is never removed here
        tmp_path / "unrelated.log.2026-09-01",
    ]
    for path in expired + kept:
        path.write_text("x", encoding="utf-8")
    for path in expired + kept[1:]:
        _age(path, LOG_RETENTION_DAYS + 1)
    _age(kept[0], LOG_RETENTION_DAYS - 1)

    assert remove_expired_logs(tmp_path) == 2
    assert not any(path.exists() for path in expired)
    assert all(path.exists() for path in kept)
