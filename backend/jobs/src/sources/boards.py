"""Scan one ATS board: fetch its postings and keep those matching the user's criteria.

Used by the directory sweep and by the fetcher when it polls tracked ``ats_boards``.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.sources.filters import (
    SearchCriteria,
    bare_remote_allowed,
    is_recent,
    location_matches,
    recency_cutoff,
    seniority_matches,
    title_matches,
)
from src.sources.providers import get_provider
from src.sources.providers.base import AtsProvider, BoardRef, HttpClient, Posting

logger = logging.getLogger(__name__)


@dataclass
class BoardScan:
    board: BoardRef
    fetched: int = 0
    matches: list[Posting] = field(default_factory=list)


def scan_board(
    board: BoardRef, criteria: SearchCriteria, client: HttpClient, now: datetime
) -> BoardScan:
    """Postings on ``board`` matching title, country and recency; fetch errors propagate."""
    provider = get_provider(board.provider)
    postings = provider.fetch_postings(board, client, since=recency_cutoff(now))
    scan = BoardScan(board=board, fetched=len(postings))
    # Judged from the board's known locations; boards that list no locations keep bare "Remote".
    allow_bare_remote = bare_remote_allowed(
        [posting.location for posting in postings if not posting.extra.get("location_pending")],
        criteria.country,
    )
    for posting in postings:
        if _keep(posting, provider, criteria, client, now, allow_bare_remote):
            scan.matches.append(posting)
    return scan


def _keep(
    posting: Posting,
    provider: AtsProvider,
    criteria: SearchCriteria,
    client: HttpClient,
    now: datetime,
    allow_bare_remote: bool,
) -> bool:
    if not title_matches(posting.title, criteria.desired_titles):
        return False
    if not seniority_matches(posting.title, criteria.seniority):
        return False
    # A dated posting outside the window is dropped before any extra request is spent on it.
    if posting.published_at is not None and not is_recent(posting.published_at, now):
        return False
    location_pending = posting.extra.get("location_pending", False)
    if not location_pending and not location_matches(
        posting.location, criteria.country, allow_bare_remote=allow_bare_remote
    ):
        return False
    if location_pending or posting.published_at is None or not posting.description:
        _enrich(posting, provider, client)
    return location_matches(
        posting.location, criteria.country, allow_bare_remote=allow_bare_remote
    ) and is_recent(posting.published_at, now)


def _enrich(posting: Posting, provider: AtsProvider, client: HttpClient) -> None:
    try:
        provider.enrich(posting, client)
    except Exception as error:
        # The posting keeps what the board list gave; undated postings are then skipped.
        logger.info("Could not enrich a %s posting: %s", provider.name, error)
