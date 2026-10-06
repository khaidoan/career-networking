"""Replace company names that are job board slugs ("capitalone") with the employer's name.

Older fetcher runs saved some companies under their board's slug because Ashby, Lever, BambooHR
and some Workday postings carry no company name. New runs ask the board instead (see
``scan_board``); this one-off repairs what is already saved:

    docker compose exec fetcher python -m src.fix_company_names

1. A slug-named company with a tracked board of the same key asks that board (no LLM tokens).
2. A slug-named company still left that has a recommended or applied job gets the company
   lookup agent's official name (one LLM call each).

A company is never renamed to a name another company already has; that is logged instead.
"""

import logging
import sys

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from src.agents.company_lookup import enrich_company, looks_like_slug
from src.config import SettingsError, get_settings
from src.db.session import get_sessionmaker
from src.logging_config import FETCHER_LOG_FILE_NAME, configure_logging
from src.models import AtsBoard, Company, Job
from src.sources.providers import get_provider
from src.sources.providers.base import HttpClient, create_http_client

logger = logging.getLogger(__name__)

NAMED_INBOXES = ("recommended", "applied")


def _name_taken(session: Session, company: Company, name: str) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(func.lower(Company.name) == name.lower(), Company.id != company.id)
            )
        )
    )


def _board_name(session: Session, company: Company, client: HttpClient) -> str | None:
    boards = session.scalars(
        select(AtsBoard).where(
            func.split_part(AtsBoard.board_key, "/", 1) == company.name,
            AtsBoard.provider.in_(("ashby", "lever", "bamboohr", "workday")),
        )
    ).all()
    for board in boards:
        provider = get_provider(board.provider)
        try:
            with client.cookie_session():
                name = provider.fetch_company_name(provider.board_ref(board.board_key), client)
        except Exception as error:
            logger.info("No name from %s/%s: %s", board.provider, board.board_key, error)
            continue
        if name:
            board.company_name = board.company_name or name
            return name
    return None


def _rename(session: Session, company: Company, name: str, how: str) -> bool:
    if _name_taken(session, company, name):
        logger.warning(
            "Company %d %r: %r is already another company's name; left as is",
            company.id,
            company.name,
            name,
        )
        return False
    logger.info("Company %d renamed %r -> %r (%s)", company.id, company.name, name, how)
    company.name = name
    return True


def fix_company_names(session: Session, client: HttpClient) -> tuple[int, int]:
    """Rename slug-named companies; returns (renamed, still a slug). Commits per company."""
    companies = [
        company
        for company in session.scalars(select(Company).order_by(Company.id))
        if looks_like_slug(company.name)
    ]
    renamed = 0
    for company in companies:
        name = _board_name(session, company, client)
        if name and _rename(session, company, name, "board"):
            renamed += 1
        elif not name and session.scalar(
            select(exists().where(Job.company_id == company.id, Job.inbox_type.in_(NAMED_INBOXES)))
        ):
            slug = company.name
            try:
                with session.begin_nested():
                    enrich_company(session, company)
            except Exception as error:
                logger.warning("Company %d lookup failed: %s", company.id, error)
            if company.name != slug:
                if _name_taken(session, company, company.name):
                    logger.warning(
                        "Company %d: %r is already another company's name; left as %r",
                        company.id,
                        company.name,
                        slug,
                    )
                    company.name = slug
                else:
                    logger.info(
                        "Company %d renamed %r -> %r (lookup)", company.id, slug, company.name
                    )
                    renamed += 1
        session.commit()
    left = sum(1 for company in companies if looks_like_slug(company.name))
    return renamed, left


def main() -> int:
    try:
        settings = get_settings()
    except SettingsError as error:
        print(error, file=sys.stderr)
        return 1
    configure_logging(settings.log_folder, file_name=FETCHER_LOG_FILE_NAME)
    with get_sessionmaker()() as session, create_http_client() as client:
        renamed, left = fix_company_names(session, client)
    logger.info("Company names fixed: %d renamed, %d still a board slug", renamed, left)
    return 0


if __name__ == "__main__":
    sys.exit(main())
