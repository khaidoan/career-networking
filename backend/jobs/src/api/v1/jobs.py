"""Discovered jobs: inboxes, Job Details, like, apply and re-evaluate (``/api/v1/jobs``)."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AfterValidator
from sqlalchemy import Row, select
from sqlalchemy.orm import Session, joinedload

from src.agents.evaluator import evaluate_job
from src.api.v1.common import (
    PAGE_SIZE,
    AppSettings,
    DbSession,
    PageCursor,
    PageLimit,
    fetch_page,
    one_of,
)
from src.api.v1.schemas.job_card import JobCard
from src.api.v1.schemas.jobs import JobDetail, JobList, JobPatch
from src.models import INBOX_TYPES, Company, Job, Preferences
from src.services.evaluation import (
    apply_evaluation_failure,
    apply_evaluation_success,
    can_move_inbox,
    job_for_evaluation,
)
from src.services.paging import SortKey, as_bool, as_datetime, as_int
from src.services.search import name_matches, normalize_search
from src.vocabularies import JOB_TYPES, SENIORITY_LEVELS, WORK_ARRANGEMENTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

INBOX_APPLIED = "applied"
PREFERENCES_ROW_ID = 1
JOB_NOT_FOUND = "Job not found"
MAX_SEARCH_LENGTH = 200

# Liked first, then newest; the id makes the key unique so paging is stable.
JOB_SORT = (
    SortKey(Job.liked, descending=True, decode=as_bool),
    SortKey(Job.discovered_when, descending=True, decode=as_datetime),
    SortKey(Job.id, descending=True, decode=as_int),
)

InboxSlug = Annotated[str, AfterValidator(one_of(INBOX_TYPES))]
SenioritySlug = Annotated[str, AfterValidator(one_of(SENIORITY_LEVELS))]
WorkArrangementSlug = Annotated[str, AfterValidator(one_of(WORK_ARRANGEMENTS))]
JobTypeSlug = Annotated[str, AfterValidator(one_of(JOB_TYPES))]


def _job_sort_values(row: Row[tuple[Job, Company]]) -> list[object]:
    job = row[0]
    return [job.liked, job.discovered_when, job.id]


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
    """One page of an inbox, liked first then newest, with optional filters and company search.

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

    rows, next_cursor = fetch_page(
        session, statement, JOB_SORT, cursor=cursor, limit=limit, sort_values=_job_sort_values
    )
    return JobList(
        items=[JobCard.from_model(job, job_company) for job, job_company in rows],
        next_cursor=next_cursor,
    )


def _load_job(session: Session, job_id: int) -> Job:
    job = session.scalars(
        select(Job)
        .where(Job.id == job_id)
        .options(joinedload(Job.company).selectinload(Company.networking_contacts))
    ).first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, JOB_NOT_FOUND)
    return job


def _to_detail(job: Job) -> JobDetail:
    contacts = sorted(job.company.networking_contacts, key=lambda contact: contact.id)
    return JobDetail.from_model(job, job.company, contacts)


@router.get("/{job_id}")
def get_job(job_id: int, session: DbSession) -> JobDetail:
    """The job with its company and the company's networking contacts."""
    return _to_detail(_load_job(session, job_id))


@router.patch("/{job_id}")
def update_job(job_id: int, patch: JobPatch, session: DbSession) -> JobDetail:
    """Like or unlike a job; nothing else is editable."""
    job = _load_job(session, job_id)
    job.liked = patch.liked
    session.commit()
    logger.info("Job %d liked=%s", job_id, patch.liked)
    return _to_detail(job)


@router.post("/{job_id}/apply")
def apply_to_job(job_id: int, session: DbSession) -> JobDetail:
    """Move the job to Applied; calling it again keeps the first ``applied_when``."""
    job = _load_job(session, job_id)
    job.inbox_type = INBOX_APPLIED
    if job.applied_when is None:
        job.applied_when = datetime.now(UTC)
    session.commit()
    logger.info("Job %d marked as applied", job_id)
    return _to_detail(job)


@router.post("/{job_id}/re-evaluate")
def re_evaluate_job(job_id: int, session: DbSession, settings: AppSettings) -> JobDetail:
    """Run the evaluator again with the current preferences; 200 even when evaluation fails.

    Success updates the scores and extracted fields and clears ``evaluation_error``; failure
    stores the new reason and clears the scores. Only Recommended and Ignored jobs may change
    inbox, and only on success; Applied and Need Attention jobs keep theirs.
    """
    job = _load_job(session, job_id)
    preferences = session.get(Preferences, PREFERENCES_ROW_ID)
    try:
        evaluation = evaluate_job(session, job_for_evaluation(job), preferences)
    except Exception as error:
        apply_evaluation_failure(job, error, allow_inbox_move=False)
    else:
        apply_evaluation_success(
            job, evaluation, settings.match_threshold, allow_inbox_move=can_move_inbox(job)
        )
    session.commit()
    logger.info(
        "Job %d re-evaluated: inbox=%s scored=%s", job_id, job.inbox_type, not job.evaluation_error
    )
    return _to_detail(job)
