"""Target companies: list, search, details, add, edit, like, delete and contact search
(``/api/v1/companies``)."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Row, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.agents.networking import find_contacts
from src.api.v1.common import (
    PAGE_SIZE,
    AppSettings,
    DbSession,
    OutboundHttp,
    PageCursor,
    PageLimit,
    fetch_page,
)
from src.api.v1.schemas.companies import (
    CompanyCard,
    CompanyDetail,
    CompanyList,
    CompanyPatch,
    CompanyRead,
    CompanyWrite,
)
from src.api.v1.schemas.contacts import ContactRead, ContactSearchResult, ContactSearchStatus
from src.api.v1.schemas.job_card import JobCard
from src.config import Settings
from src.llm import LlmError
from src.models import Company, CompanyNetworking, Job, Preferences
from src.services.contacts import (
    CompanyNotFoundError,
    contact_search_availability,
    has_eligible_job,
    latest_eligible_job,
    upsert_contacts,
)
from src.services.paging import SortKey, as_bool, as_int, as_str
from src.services.search import name_matches, normalize_search
from src.sources.serpapi import SerpApiError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])

COMPANY_NOT_FOUND = "Company not found"
COMPANY_HAS_JOBS = "Companies with jobs can't be deleted."
JOB_NOT_FOUND = "Job not found"
JOB_NOT_AT_COMPANY = "Value error, the job does not belong to this company"
NO_SERPAPI_KEY = "Contact search needs a SerpApi key. See the README."
NOT_ELIGIBLE = "Contact search is available for companies with a recommended or applied job."
SEARCH_FAILED = "Contact search failed: the search service could not be reached. Try again later."
SELECTION_FAILED = "Contact search failed: the AI model could not be reached. Try again later."
PREFERENCES_ROW_ID = 1
MAX_SEARCH_LENGTH = 200
MAX_INDUSTRY_FILTERS = 50

SORT_NAME = func.lower(Company.name)
# Liked first, then alphabetical (case-insensitive); the id makes the key unique.
COMPANY_SORT = (
    SortKey(Company.liked, descending=True, decode=as_bool),
    SortKey(SORT_NAME, descending=False, decode=as_str),
    SortKey(Company.id, descending=False, decode=as_int),
)


def _company_sort_values(row: Row[Any]) -> list[object]:
    company, sort_name = row
    return [company.liked, sort_name, company.id]


def _job_count(company_id: int) -> Any:
    return select(func.count(Job.id)).where(Job.company_id == company_id).scalar_subquery()


@router.get("")
def list_companies(
    session: DbSession,
    q: Annotated[str | None, Query(max_length=MAX_SEARCH_LENGTH)] = None,
    industry: Annotated[list[str], Query(max_length=MAX_INDUSTRY_FILTERS)] = [],  # noqa: B006
    cursor: PageCursor = None,
    limit: PageLimit = PAGE_SIZE,
) -> CompanyList:
    """One page of companies, liked first then by name; ``industry`` matches any of the values."""
    statement = select(Company, SORT_NAME.label("sort_name"))
    search = normalize_search(q)
    if search:
        statement = statement.where(name_matches(Company.name, search))
    industries = [value.strip() for value in industry if value.strip()]
    if industries:
        statement = statement.where(Company.industries.overlap(industries))

    rows, next_cursor = fetch_page(
        session,
        statement,
        COMPANY_SORT,
        cursor=cursor,
        limit=limit,
        sort_values=_company_sort_values,
    )
    return CompanyList(
        items=[CompanyCard.from_model(company) for company, _sort_name in rows],
        next_cursor=next_cursor,
    )


@router.get("/industries")
def list_industries(session: DbSession) -> list[str]:
    """Every distinct industry across companies, sorted case-insensitively."""
    industry = func.unnest(Company.industries).label("industry")
    values = session.scalars(select(industry).distinct()).all()
    return sorted((value for value in values if value), key=lambda value: (value.casefold(), value))


def _load_company(session: Session, company_id: int) -> tuple[Company, int]:
    row = session.execute(
        select(Company, _job_count(company_id).label("job_count"))
        .where(Company.id == company_id)
        .options(selectinload(Company.jobs), selectinload(Company.networking_contacts))
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, COMPANY_NOT_FOUND)
    company, job_count = row
    return company, job_count


def _contact_search(session: Session, settings: Settings, company: Company) -> ContactSearchStatus:
    return ContactSearchStatus.from_availability(
        contact_search_availability(session, settings, company)
    )


def _to_detail(
    session: Session, settings: Settings, company: Company, job_count: int
) -> CompanyDetail:
    jobs = sorted(company.jobs, key=lambda job: (job.discovered_when, job.id), reverse=True)
    contacts = sorted(company.networking_contacts, key=lambda contact: contact.id)
    return CompanyDetail(
        **CompanyRead.from_model(company).model_dump(),
        job_count=job_count,
        jobs=[JobCard.from_model(job, company) for job in jobs],
        contacts=[ContactRead.from_model(contact) for contact in contacts],
        contact_search=_contact_search(session, settings, company),
    )


def _detail(session: Session, settings: Settings, company_id: int) -> CompanyDetail:
    return _to_detail(session, settings, *_load_company(session, company_id))


@router.get("/{company_id}")
def get_company(company_id: int, session: DbSession, settings: AppSettings) -> CompanyDetail:
    """The company with its jobs (newest first), its contacts, contact search status and
    ``job_count``."""
    return _detail(session, settings, company_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyWrite, session: DbSession, settings: AppSettings) -> CompanyDetail:
    company = Company(**body.model_dump())
    session.add(company)
    session.commit()
    logger.info("Company %d created", company.id)
    return _detail(session, settings, company.id)


@router.put("/{company_id}")
def update_company(
    company_id: int, body: CompanyWrite, session: DbSession, settings: AppSettings
) -> CompanyDetail:
    """Replace every editable company field."""
    company, _ = _load_company(session, company_id)
    for field, value in body.model_dump().items():
        setattr(company, field, value)
    session.commit()
    logger.info("Company %d updated", company_id)
    return _detail(session, settings, company_id)


@router.patch("/{company_id}")
def like_company(
    company_id: int, patch: CompanyPatch, session: DbSession, settings: AppSettings
) -> CompanyDetail:
    """Like or unlike a company; use ``PUT`` for the other fields."""
    company, job_count = _load_company(session, company_id)
    company.liked = patch.liked
    session.commit()
    logger.info("Company %d liked=%s", company_id, patch.liked)
    return _to_detail(session, settings, company, job_count)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, session: DbSession) -> Response:
    """Delete a company and its contacts; 409 while the company still has jobs."""
    job_count = session.scalar(select(_job_count(company_id)))
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, COMPANY_NOT_FOUND)
    if job_count:
        raise HTTPException(status.HTTP_409_CONFLICT, COMPANY_HAS_JOBS)
    session.delete(company)
    try:
        session.commit()
    except IntegrityError:
        # A job was added after the check (the fetcher runs independently); ON DELETE RESTRICT.
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, COMPANY_HAS_JOBS) from None
    logger.info("Company %d deleted", company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _requested_job(session: Session, company: Company, job_id: int) -> Job:
    """The given job; 404 when unknown, 422 when it belongs to another company."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, JOB_NOT_FOUND)
    if job.company_id != company.id:
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("query", "job_id"), "msg": JOB_NOT_AT_COMPANY}]
        )
    return job


@router.post("/{company_id}/contacts/search")
def search_contacts(
    company_id: int,
    session: DbSession,
    settings: AppSettings,
    client: OutboundHttp,
    job_id: Annotated[int | None, Query()] = None,
) -> ContactSearchResult:
    """Find people at the company with one SerpApi search and one LLM pick, then store them.

    Runs synchronously and only when the user asks; nothing is sent to LinkedIn. The role comes
    from ``job_id`` when given (it must belong to the company), else from the company's newest
    recommended or applied job. Checks run in this order: 404 unknown company or job, 422 job at
    another company, 503 no SerpApi key, 409 no recommended or applied job. A failed search or
    LLM call is a 502 and writes nothing. There is deliberately no cap, cooldown or rate-limit
    header: each click is one search on the user's own SerpApi quota.
    """
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, COMPANY_NOT_FOUND)
    job = _requested_job(session, company, job_id) if job_id is not None else None
    if settings.serpapi_api_key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_SERPAPI_KEY)
    if job is None:
        job = latest_eligible_job(session, company.id)
        if job is None:
            raise HTTPException(status.HTTP_409_CONFLICT, NOT_ELIGIBLE)
    elif not has_eligible_job(session, company.id):
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_ELIGIBLE)

    preferences = session.get(Preferences, PREFERENCES_ROW_ID)
    try:
        result = find_contacts(session, settings, client, company, job, preferences)
    except SerpApiError as error:
        session.rollback()
        logger.warning("Contact search company=%d failed: search error: %s", company_id, error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SEARCH_FAILED) from None
    except LlmError as error:
        session.rollback()
        logger.warning(
            "Contact search company=%d failed: LLM error: %s", company_id, type(error).__name__
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, SELECTION_FAILED) from None

    try:
        stored = upsert_contacts(session, company.id, result.found)
    except CompanyNotFoundError:
        # Deleted while the search ran.
        session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, COMPANY_NOT_FOUND) from None
    session.commit()
    logger.info(
        "Contact search company=%d stored: %d new, %d updated",
        company_id,
        stored.created,
        stored.updated,
    )

    contacts = session.scalars(
        select(CompanyNetworking)
        .where(CompanyNetworking.company_id == company.id)
        .order_by(CompanyNetworking.id)
    ).all()
    return ContactSearchResult(
        found=len(result.found),
        created=stored.created,
        updated=stored.updated,
        contacts=[ContactRead.from_model(contact) for contact in contacts],
        contact_search=_contact_search(session, settings, company),
    )
