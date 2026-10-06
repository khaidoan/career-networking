"""Discovered jobs: inboxes, Job Details, like and apply (``/api/v1/jobs``)."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AfterValidator
from sqlalchemy import Row, select
from sqlalchemy.orm import Session, joinedload

from src.api.v1.common import (
    PAGE_SIZE,
    AppSettings,
    DbSession,
    PageCursor,
    PageLimit,
    fetch_feed_page,
    fetch_page,
    one_of,
)
from src.api.v1.schemas.contacts import ContactSearchStatus
from src.api.v1.schemas.job_card import JobCard
from src.api.v1.schemas.jobs import JobDetail, JobList, JobPatch
from src.config import Settings
from src.models import INBOX_PENDING, LISTED_INBOXES, Company, Job
from src.services.contacts import contact_search_availability
from src.services.paging import SortKey, as_datetime, as_int
from src.services.search import name_matches, normalize_search
from src.vocabularies import JOB_TYPES, SENIORITY_LEVELS, WORK_ARRANGEMENTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

INBOX_APPLIED = "applied"
JOB_NOT_FOUND = "Job not found"
MAX_SEARCH_LENGTH = 200

INBOX_RECOMMENDED = "recommended"

# Newest arrival in the inbox first (for Recommended, the newest scored); the id makes the key
# unique so paging is stable.
JOB_SORT = (
    SortKey(Job.inbox_entered_at, descending=True, decode=as_datetime),
    SortKey(Job.id, descending=True, decode=as_int),
)

# Pending (not yet scored) jobs are never listed.
InboxSlug = Annotated[str, AfterValidator(one_of(LISTED_INBOXES))]
SenioritySlug = Annotated[str, AfterValidator(one_of(SENIORITY_LEVELS))]
WorkArrangementSlug = Annotated[str, AfterValidator(one_of(WORK_ARRANGEMENTS))]
JobTypeSlug = Annotated[str, AfterValidator(one_of(JOB_TYPES))]


def _job_sort_values(row: Row[tuple[Job, Company]]) -> list[object]:
    job = row[0]
    return [job.inbox_entered_at, job.id]


@router.get("")
def list_jobs(
    session: DbSession,
    inbox: Annotated[InboxSlug, Query()],
    seniority: Annotated[list[SenioritySlug], Query()] = [],  # noqa: B006
    work_arrangement: Annotated[list[WorkArrangementSlug], Query()] = [],  # noqa: B006
    job_type: Annotated[list[JobTypeSlug], Query()] = [],  # noqa: B006
    visa: Annotated[Literal["yes", "no"] | None, Query()] = None,
    liked: Annotated[bool | None, Query()] = None,
    company: Annotated[str | None, Query(max_length=MAX_SEARCH_LENGTH)] = None,
    cursor: PageCursor = None,
    limit: PageLimit = PAGE_SIZE,
) -> JobList:
    """One page of an inbox, with optional filters and company search.

    Every inbox is newest arrival first. Recommended is a feed (see ``feed_page``): later pages
    first bring jobs scored since the list was opened, then older ones not shown yet, and its
    ``next_cursor`` never runs out, so asking again later returns newly scored jobs. The other
    inboxes end with ``next_cursor`` null.

    Filters of different kinds combine with AND; several values of one filter match any of them.
    """
    statement = select(Job, Company).join(Job.company).where(Job.inbox_type == inbox)
    if seniority:
        statement = statement.where(Job.seniority_level.in_(seniority))
    if work_arrangement:
        statement = statement.where(Job.work_arrangement.in_(work_arrangement))
    if job_type:
        statement = statement.where(Job.job_type_classification.in_(job_type))
    if visa is not None:
        statement = statement.where(Job.visa_sponsorship.is_(visa == "yes"))
    if liked is not None:
        statement = statement.where(Job.liked.is_(liked))
    search = normalize_search(company)
    if search:
        statement = statement.where(name_matches(Company.name, search))

    page = fetch_feed_page if inbox == INBOX_RECOMMENDED else fetch_page
    rows, next_cursor = page(
        session, statement, JOB_SORT, cursor=cursor, limit=limit, sort_values=_job_sort_values
    )
    return JobList(
        items=[JobCard.from_model(job, job_company) for job, job_company in rows],
        next_cursor=next_cursor,
    )


def _load_job(session: Session, job_id: int) -> Job:
    job = session.scalars(
        select(Job)
        .where(Job.id == job_id, Job.inbox_type != INBOX_PENDING)
        .options(joinedload(Job.company).selectinload(Company.networking_contacts))
    ).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, JOB_NOT_FOUND)
    return job


def _to_detail(session: Session, settings: Settings, job: Job) -> JobDetail:
    contacts = sorted(job.company.networking_contacts, key=lambda contact: contact.id)
    contact_search = ContactSearchStatus.from_availability(
        contact_search_availability(session, settings, job.company)
    )
    return JobDetail.from_model(job, job.company, contacts, contact_search)


@router.get("/{job_id}")
def get_job(job_id: int, session: DbSession, settings: AppSettings) -> JobDetail:
    """The job with its company, the company's networking contacts and contact search status."""
    return _to_detail(session, settings, _load_job(session, job_id))


@router.patch("/{job_id}")
def update_job(
    job_id: int, patch: JobPatch, session: DbSession, settings: AppSettings
) -> JobDetail:
    """Like or unlike a job; nothing else is editable."""
    job = _load_job(session, job_id)
    job.liked = patch.liked
    session.commit()
    logger.info("Job %d liked=%s", job_id, patch.liked)
    return _to_detail(session, settings, job)


@router.post("/{job_id}/apply")
def apply_to_job(job_id: int, session: DbSession, settings: AppSettings) -> JobDetail:
    """Move the job to Applied; calling it again keeps the first ``applied_when``."""
    job = _load_job(session, job_id)
    job.inbox_type = INBOX_APPLIED
    if job.applied_when is None:
        job.applied_when = datetime.now(UTC)
    session.commit()
    logger.info("Job %d marked as applied", job_id)
    return _to_detail(session, settings, job)
