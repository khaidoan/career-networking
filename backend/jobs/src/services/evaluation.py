"""Applying an evaluator outcome to a job; shared by the fetcher and the Re-evaluate endpoint.

A success copies the scores and extracted fields onto the job and clears ``evaluation_error``.
A failure stores the one-line reason and clears the scores. Only the caller decides whether the
job may change inbox: the fetcher always places new jobs, Re-evaluate only moves jobs that are
still in Recommended or Ignored.
"""

import logging

from src.agents.evaluator import JobEvaluation, JobForEvaluation
from src.models import Job
from src.models.job import SCORE_COLUMNS

logger = logging.getLogger(__name__)

INBOX_RECOMMENDED = "recommended"
INBOX_IGNORED = "ignored"
# Applied and Need Attention reflect the user's actions, so a new score never moves them.
MOVABLE_INBOXES = frozenset({INBOX_RECOMMENDED, INBOX_IGNORED})

# Where a new job goes when its evaluation fails. It is saved with null scores and the reason.
EVALUATION_FAILURE_INBOX = INBOX_IGNORED
EVALUATION_ERROR_MAX_CHARS = 1000


def describe_evaluation_error(error: Exception) -> str:
    """A one-line, length-capped reason such as ``LlmOutputError: invalid JSON after retry``."""
    message = " ".join(str(error).split())
    reason = f"{type(error).__name__}: {message}" if message else type(error).__name__
    if len(reason) > EVALUATION_ERROR_MAX_CHARS:
        reason = reason[: EVALUATION_ERROR_MAX_CHARS - 1] + "…"
    return reason


def inbox_for(evaluation: JobEvaluation, match_threshold: int) -> str:
    return INBOX_RECOMMENDED if evaluation.overall_score >= match_threshold else INBOX_IGNORED


def can_move_inbox(job: Job) -> bool:
    """Whether a re-evaluation may move this job (only Recommended and Ignored jobs move)."""
    return job.inbox_type in MOVABLE_INBOXES


def apply_evaluation_success(
    job: Job, evaluation: JobEvaluation, match_threshold: int, *, allow_inbox_move: bool
) -> None:
    """Copy every evaluated field onto the job, clear the error and, if allowed, pick the inbox."""
    for name, value in evaluation.model_dump().items():
        setattr(job, name, value)
    job.evaluation_error = None
    if allow_inbox_move:
        job.inbox_type = inbox_for(evaluation, match_threshold)


def apply_evaluation_failure(job: Job, error: Exception, *, allow_inbox_move: bool = True) -> None:
    """Store the failure reason and clear the scores; move to ``EVALUATION_FAILURE_INBOX`` if
    allowed."""
    for column in SCORE_COLUMNS:
        setattr(job, column, None)
    job.evaluation_error = describe_evaluation_error(error)
    if allow_inbox_move:
        job.inbox_type = EVALUATION_FAILURE_INBOX
    logger.warning(
        "Evaluation failed for %r at %s; saved unscored in %s: %s",
        job.title,
        job.url,
        job.inbox_type,
        error,
    )


def job_for_evaluation(job: Job) -> JobForEvaluation:
    """The evaluator input for a stored job; its company must be loaded."""
    location_parts = (job.location_city, job.location_state, job.location_country)
    location = ", ".join(part.strip() for part in location_parts if part and part.strip())
    return JobForEvaluation(
        title=job.title,
        company=job.company.name,
        location=location or None,
        description=job.description,
    )
