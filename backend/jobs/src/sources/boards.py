"""Scan one ATS board: fetch its postings and keep those matching the user's criteria.

Used by the directory sweep and by the fetcher when it polls tracked ``ats_boards``.
"""

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime

from src.sources.filters import (
    SearchCriteria,
    bare_remote_allowed,
    is_recent,
    location_matches,
    recency_cutoff,
    relocation_matches,
    seniority_matches,
    title_matches,
)
from src.sources.providers import get_provider
from src.sources.providers.base import AtsProvider, BoardRef, HttpClient, Posting, company_for

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
    # Cookies a board sets (some sit behind bot protection) last for this board's requests only.
    with client.cookie_session():
        postings = provider.fetch_postings(board, client, since=recency_cutoff(now))
        scan = BoardScan(board=board, fetched=len(postings))
        # Judged from the board's known locations; boards that list none keep bare "Remote".
        allow_bare_remote = bare_remote_allowed(
            [p.location for p in postings if not p.extra.get("location_pending")],
            criteria.country,
        )
        for posting in postings:
            if _keep(posting, provider, criteria, client, now, allow_bare_remote):
                scan.matches.append(posting)
        if scan.matches and not board.company_name:
            _name_board(scan, provider, client)
    return scan


def _name_board(scan: BoardScan, provider: AtsProvider, client: HttpClient) -> None:
    """Ask the board for the employer's name so matches are not saved under the board's slug.

    Only boards with matches are asked (one request each). The name is kept on the board, so a
    tracked board does not need asking again; a failure leaves the slug.
    """
    slug_name = company_for(scan.board)
    try:
        name = provider.fetch_company_name(scan.board, client)
    except Exception as error:
        logger.debug(
            "No company name for %s/%s: %s", scan.board.provider, scan.board.board_key, error
        )
        return
    if not name:
        return
    scan.board = replace(scan.board, company_name=name)
    for posting in scan.matches:
        # Keep a name the posting itself reported (Workday's hiring organization, for example).
        if posting.company == slug_name:
            posting.company = name
        posting.board = scan.board


def _keep(
    posting: Posting,
    provider: AtsProvider,
    criteria: SearchCriteria,
    client: HttpClient,
    now: datetime,
    allow_bare_remote: bool,
) -> bool:
    if not title_matches(posting.title, criteria.desired_titles, criteria.excluded_title_words):
        return False
    if not seniority_matches(posting.title, criteria.seniority):
        return False
    # A dated posting outside the window is dropped before any extra request is spent on it.
    if posting.published_at is not None and not is_recent(posting.published_at, now):
        return False
    location_pending = posting.extra.get("location_pending", False)
    if not location_pending and not _location_ok(posting, criteria, allow_bare_remote):
        return False
    if location_pending or posting.published_at is None or not posting.description:
        _enrich(posting, provider, client)
    return _location_ok(posting, criteria, allow_bare_remote) and is_recent(
        posting.published_at, now
    )


def _location_ok(posting: Posting, criteria: SearchCriteria, allow_bare_remote: bool) -> bool:
    return location_matches(
        posting.location, criteria.country, allow_bare_remote=allow_bare_remote
    ) and relocation_matches(posting.location, criteria)


def _enrich(posting: Posting, provider: AtsProvider, client: HttpClient) -> None:
    try:
        provider.enrich(posting, client)
    except Exception as error:
        # The posting keeps what the board list gave; undated postings are then skipped.
        logger.info("Could not enrich a %s posting: %s", provider.name, error)
