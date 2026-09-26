"""Target companies: list, search, details, add, edit, like and delete (``/api/v1/companies``)."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import Row, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.api.v1.common import PAGE_SIZE, DbSession, PageCursor, PageLimit, fetch_page
from src.api.v1.schemas.companies import (
    CompanyCard,
    CompanyDetail,
    CompanyList,
    CompanyPatch,
    CompanyRead,
    CompanyWrite,
)
from src.api.v1.schemas.contacts import ContactRead
from src.api.v1.schemas.job_card import JobCard
from src.models import Company, Job
from src.services.paging import SortKey, as_bool, as_int, as_str
from src.services.search import name_matches, normalize_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])

COMPANY_NOT_FOUND = "Company not found"
COMPANY_HAS_JOBS = "Companies with jobs can't be deleted."
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


def _to_detail(company: Company, job_count: int) -> CompanyDetail:
    jobs = sorted(company.jobs, key=lambda job: (job.discovered_when, job.id), reverse=True)
    contacts = sorted(company.networking_contacts, key=lambda contact: contact.id)
    return CompanyDetail(
        **CompanyRead.from_model(company).model_dump(),
        job_count=job_count,
        jobs=[JobCard.from_model(job, company) for job in jobs],
        contacts=[ContactRead.from_model(contact) for contact in contacts],
    )


def _detail(session: Session, company_id: int) -> CompanyDetail:
    return _to_detail(*_load_company(session, company_id))


@router.get("/{company_id}")
def get_company(company_id: int, session: DbSession) -> CompanyDetail:
    """The company with its jobs (newest first), its contacts and ``job_count``."""
    return _detail(session, company_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyWrite, session: DbSession) -> CompanyDetail:
    company = Company(**body.model_dump())
    session.add(company)
    session.commit()
    logger.info("Company %d created", company.id)
    return _detail(session, company.id)


@router.put("/{company_id}")
def update_company(company_id: int, body: CompanyWrite, session: DbSession) -> CompanyDetail:
    """Replace every editable company field."""
    company, _ = _load_company(session, company_id)
    for field, value in body.model_dump().items():
        setattr(company, field, value)
    session.commit()
    logger.info("Company %d updated", company_id)
    return _detail(session, company_id)


@router.patch("/{company_id}")
def like_company(company_id: int, patch: CompanyPatch, session: DbSession) -> CompanyDetail:
    """Like or unlike a company; use ``PUT`` for the other fields."""
    company, job_count = _load_company(session, company_id)
    company.liked = patch.liked
    session.commit()
    logger.info("Company %d liked=%s", company_id, patch.liked)
    return _to_detail(company, job_count)


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
