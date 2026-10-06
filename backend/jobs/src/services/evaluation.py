"""Applying an evaluator outcome to a pending job; used by the scorer.

A success copies the scores and extracted fields onto the job, clears ``evaluation_error`` and
places it in Recommended or Ignored by its score. A failure stores the one-line reason, clears
the scores and places it in Ignored.
"""

import logging

from src.agents.evaluator import JobEvaluation
from src.models import Job
from src.models.job import SCORE_COLUMNS

logger = logging.getLogger(__name__)

INBOX_RECOMMENDED = "recommended"
INBOX_IGNORED = "ignored"

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


def apply_evaluation_success(job: Job, evaluation: JobEvaluation, match_threshold: int) -> None:
    """Copy every evaluated field onto the job, clear the error and pick the inbox by score."""
    for name, value in evaluation.model_dump().items():
        setattr(job, name, value)
    job.evaluation_error = None
    job.inbox_type = inbox_for(evaluation, match_threshold)


def apply_evaluation_failure(job: Job, error: Exception) -> None:
    """Store the failure reason, clear the scores and move to ``EVALUATION_FAILURE_INBOX``."""
    for column in SCORE_COLUMNS:
        setattr(job, column, None)
    job.score_explanation = None
    job.evaluation_error = describe_evaluation_error(error)
    job.inbox_type = EVALUATION_FAILURE_INBOX
    logger.warning(
        "Evaluation failed for %r at %s; saved unscored in %s: %s",
        job.title,
        job.url,
        job.inbox_type,
        error,
    )
