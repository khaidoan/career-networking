"""Reverse ATS sweep over the public job-board-aggregator company directories.

Each run scans the next ``ceil(total / RUNS_PER_FULL_PASS)`` boards of the combined directory;
with the fetcher running once a day and ``RUNS_PER_FULL_PASS = 1``, every run is a full pass.
Boards with matching postings are returned so the fetcher can track them in ``ats_boards``.

Ported from Career-Ops ``scan-ats-full.mjs`` (https://github.com/career-ops-hq/career-ops),
Copyright (c) 2026 Santiago Fernández de Valderrama, used under the MIT License. The company
directories are downloaded at run time from Feashliaa/job-board-aggregator
(https://github.com/Feashliaa/job-board-aggregator) by Riley Dorrington. The project's code is
MIT licensed, but its ``data/`` datasets are licensed CC BY-NC 4.0: free for non-commercial use
with attribution; commercial use needs the author's permission. They are not redistributed here.
"""

import json
import logging
import math
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import zip_longest
from pathlib import Path

from src.sources.boards import BoardScan, scan_board
from src.sources.filters import SearchCriteria
from src.sources.providers import get_provider
from src.sources.providers.base import BoardRef, HttpClient, SourceError
from src.sources.state import FetcherState, write_atomically
from src.vocabularies import ATS_PROVIDERS

logger = logging.getLogger(__name__)

DIRECTORY_BASE_URL = "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data"
DIRECTORY_CACHE_TTL = timedelta(hours=24)
DIRECTORY_TIMEOUT_SECONDS = 60.0
DIRECTORY_MAX_BYTES = 20 * 1024 * 1024
# The fetcher runs once a day, so each run scans the whole directory (about 50,000 boards).
# Raising this spreads a pass over several runs; the rotation cursor keeps working.
RUNS_PER_FULL_PASS = 1
SWEEP_CONCURRENCY = 24

SLUG = re.compile(r"^[A-Za-z0-9._-]+$")
# Part of the Workday directory holds instance names ("wd5") in the tenant field; they never
# resolve to a real board.
WORKDAY_JUNK_TENANT = re.compile(r"^wd\d+$", re.IGNORECASE)


@dataclass
class SweepResult:
    skipped: bool = False
    boards_scanned: int = 0
    boards_failed: int = 0
    postings_fetched: int = 0
    # Only boards with at least one matching posting.
    matched_boards: list[BoardScan] = field(default_factory=list)


def directory_url(provider: str) -> str:
    return f"{DIRECTORY_BASE_URL}/{provider}_companies.json"


def run_sweep_batch(
    criteria: SearchCriteria,
    client: HttpClient,
    state: FetcherState,
    now: datetime | None = None,
) -> SweepResult:
    """Scan this run's slice of the directory and advance the rotation cursor."""
    now = now or datetime.now(UTC)
    directory = load_directory(client, state, now)
    if not directory:
        logger.warning("ATS sweep skipped: no company directory available")
        return SweepResult(skipped=True)

    total = len(directory)
    batch_size = math.ceil(total / RUNS_PER_FULL_PASS)
    cursor = state.get_sweep_cursor()
    if cursor >= total:
        cursor = 0
    batch = [directory[(cursor + offset) % total] for offset in range(batch_size)]
    logger.info("ATS sweep: scanning boards %d-%d of %d", cursor, cursor + batch_size - 1, total)

    result = SweepResult(boards_scanned=len(batch))
    with ThreadPoolExecutor(max_workers=SWEEP_CONCURRENCY) as pool:
        scans = pool.map(lambda board: _scan_quietly(board, criteria, client, now), batch)
        for scan in scans:
            if scan is None:
                result.boards_failed += 1
                continue
            result.postings_fetched += scan.fetched
            if scan.matches:
                result.matched_boards.append(scan)

    state.set_sweep_cursor((cursor + batch_size) % total)
    return result


def _scan_quietly(
    board: BoardRef, criteria: SearchCriteria, client: HttpClient, now: datetime
) -> BoardScan | None:
    # Directory boards are often gone (404) or blocked; that is normal and only logged at debug.
    try:
        return scan_board(board, criteria, client, now)
    except Exception as error:
        logger.debug("ATS sweep: %s/%s failed: %s", board.provider, board.board_key, error)
        return None


def load_directory(client: HttpClient, state: FetcherState, now: datetime) -> list[BoardRef]:
    """Every directory board, interleaved across providers so each batch spreads over hosts."""
    per_provider = [
        list(_boards(provider, _directory_entries(provider, client, state, now)))
        for provider in ATS_PROVIDERS
    ]
    return [board for group in zip_longest(*per_provider) for board in group if board is not None]


def _directory_entries(
    provider: str, client: HttpClient, state: FetcherState, now: datetime
) -> list[object]:
    """The provider's directory: fresh cache, else a download, else the stale cache, else []."""
    cache_file = state.directory_cache_dir() / f"{provider}_companies.json"
    cached_at = _modified_at(cache_file)
    if cached_at is not None and now - cached_at < DIRECTORY_CACHE_TTL:
        entries = _read_cache(cache_file)
        if entries is not None:
            return entries

    try:
        entries = client.get_json(
            directory_url(provider),
            timeout=DIRECTORY_TIMEOUT_SECONDS,
            max_bytes=DIRECTORY_MAX_BYTES,
        )
        if not isinstance(entries, list):
            raise SourceError("directory is not a JSON list")
        write_atomically(cache_file, json.dumps(entries).encode("utf-8"))
        return entries
    except (SourceError, OSError) as error:
        logger.warning("ATS sweep: could not download the %s directory: %s", provider, error)

    stale = _read_cache(cache_file)
    if stale is not None:
        logger.info("ATS sweep: using the cached %s directory", provider)
        return stale
    return []


def _read_cache(cache_file: Path) -> list[object] | None:
    try:
        entries = json.loads(cache_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("ATS sweep: the cached directory %s is unreadable", cache_file.name)
        return None
    return entries if isinstance(entries, list) else None


def _modified_at(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def _boards(provider: str, entries: Iterable[object]) -> Iterable[BoardRef]:
    ats = get_provider(provider)
    for entry in entries:
        board_key = directory_board_key(provider, entry)
        if board_key:
            yield ats.board_ref(board_key)


def directory_board_key(provider: str, entry: object) -> str | None:
    """The ``ats_boards.board_key`` for one directory entry; invalid entries give ``None``.

    Entries are slugs, except Workday's ``tenant|instance|site`` triples.
    """
    if not isinstance(entry, str):
        return None
    if provider == "workday":
        parts = entry.split("|")
        if len(parts) != 3 or not all(part and SLUG.match(part) for part in parts):
            return None
        tenant, instance, site = parts
        if WORKDAY_JUNK_TENANT.match(tenant):
            return None
        entry = f"{tenant}/{instance}/{site}"
    elif not SLUG.match(entry):
        return None
    return get_provider(provider).normalize_key(entry)
