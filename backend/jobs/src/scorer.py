"""The scorer: evaluates the jobs the fetcher saved as "pending", a few at a time.

The ``scorer`` compose service runs ``python -m src.scorer``, which loops until stopped:

- Only jobs discovered in the last ``SCORING_WINDOW`` (24 hours) are scored. Pending jobs older
  than that are deleted without being scored.
- Up to ``CAREER_NETWORKING_SCORER_CONCURRENCY`` jobs are evaluated at once. Each job is locked
  while it is scored (``FOR UPDATE SKIP LOCKED``), so a job is never scored twice.
- A scored job moves to Recommended or Ignored by ``CAREER_NETWORKING_MATCH_THRESHOLD``; moving
  stamps ``inbox_entered_at``, which orders the inboxes. A recommended job's company, if it was
  saved by name only, is filled in by the company lookup agent.
- A failed evaluation is retried after ``RETRY_DELAYS``; after ``MAX_SCORING_ATTEMPTS`` the job
  goes to Ignored unscored, with the reason in ``jobs.evaluation_error``.
"""

import logging
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import FrameType

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, sessionmaker

from src.agents.company_lookup import enrich_company, is_name_only
from src.agents.evaluator import JobForEvaluation, evaluate_job
from src.config import Settings, SettingsError, get_settings
from src.db.session import get_sessionmaker
from src.logging_config import SCORER_LOG_FILE_NAME, configure_logging
from src.models import INBOX_PENDING, Job, Preferences
from src.services.evaluation import (
    INBOX_RECOMMENDED,
    apply_evaluation_failure,
    apply_evaluation_success,
)

logger = logging.getLogger(__name__)

SCORING_WINDOW = timedelta(hours=24)
MAX_SCORING_ATTEMPTS = 3
# Wait before the 2nd and 3rd attempts; long enough to ride out a short provider outage.
RETRY_DELAYS = (timedelta(minutes=5), timedelta(minutes=30))
# How long to wait for new pending jobs when there is nothing to score.
IDLE_POLL_SECONDS = 30
PREFERENCES_ROW_ID = 1

OUTCOME_RECOMMENDED = "recommended"
OUTCOME_IGNORED = "ignored"
OUTCOME_RETRY = "retry"
OUTCOME_FAILED = "failed"
OUTCOME_SKIPPED = "skipped"


@dataclass
class BatchSummary:
    deleted: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)

    @property
    def attempted(self) -> int:
        return sum(count for outcome, count in self.outcomes.items() if outcome != OUTCOME_SKIPPED)

    def describe(self) -> str:
        counts = " ".join(f"{name}={count}" for name, count in sorted(self.outcomes.items()))
        return f"Scorer batch: {counts or 'nothing scored'}; stale_pending_deleted={self.deleted}"


def delete_stale_pending(session_factory: sessionmaker[Session], now: datetime) -> int:
    """Delete pending jobs discovered more than ``SCORING_WINDOW`` ago; they are never scored."""
    with session_factory() as session, session.begin():
        result = session.execute(
            delete(Job).where(
                Job.inbox_type == INBOX_PENDING, Job.discovered_when < now - SCORING_WINDOW
            )
        )
    deleted = result.rowcount or 0
    if deleted:
        logger.info("Deleted %d pending jobs older than 24 hours without scoring them", deleted)
    return deleted


def due_job_ids(session_factory: sessionmaker[Session], now: datetime, limit: int) -> list[int]:
    """Pending jobs from the scoring window that are not waiting for a retry, oldest first."""
    with session_factory() as session:
        return list(
            session.scalars(
                select(Job.id)
                .where(
                    Job.inbox_type == INBOX_PENDING,
                    Job.discovered_when >= now - SCORING_WINDOW,
                    or_(Job.next_scoring_at.is_(None), Job.next_scoring_at <= now),
                )
                .order_by(Job.discovered_when, Job.id)
                .limit(limit)
            )
        )


def score_job(
    job_id: int, settings: Settings, session_factory: sessionmaker[Session], now: datetime
) -> str:
    """Evaluate one pending job and return what happened to it (an ``OUTCOME_*`` value)."""
    with session_factory() as session, session.begin():
        job = session.scalars(
            select(Job)
            .where(Job.id == job_id, Job.inbox_type == INBOX_PENDING)
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            # Scored, deleted or locked by another scorer since it was picked.
            return OUTCOME_SKIPPED
        subject = JobForEvaluation(
            title=job.title,
            company=job.company.name,
            location=job.posting_location,
            description=job.description,
        )
        try:
            evaluation = evaluate_job(
                session, subject, session.get(Preferences, PREFERENCES_ROW_ID)
            )
        except Exception as error:
            return _record_failure(job, error, now)

        apply_evaluation_success(job, evaluation, settings.match_threshold)
        job.next_scoring_at = None
        if job.inbox_type != INBOX_RECOMMENDED:
            return OUTCOME_IGNORED
        if is_name_only(job.company):
            try:
                with session.begin_nested():
                    enrich_company(session, job.company, job.description)
            except Exception as error:
                logger.warning(
                    "Company lookup failed for %r; keeping the name only: %s",
                    job.company.name,
                    error,
                )
        return OUTCOME_RECOMMENDED


def _record_failure(job: Job, error: Exception, now: datetime) -> str:
    job.scoring_attempts += 1
    if job.scoring_attempts >= MAX_SCORING_ATTEMPTS:
        # Moves the job to Ignored with the reason; it is not tried again.
        apply_evaluation_failure(job, error)
        return OUTCOME_FAILED
    job.next_scoring_at = now + RETRY_DELAYS[job.scoring_attempts - 1]
    logger.warning(
        "Scoring %r failed (attempt %d of %d); retrying after %s: %s",
        job.title,
        job.scoring_attempts,
        MAX_SCORING_ATTEMPTS,
        job.next_scoring_at.isoformat(timespec="minutes"),
        error,
    )
    return OUTCOME_RETRY


def score_batch(
    settings: Settings, session_factory: sessionmaker[Session], now: datetime | None = None
) -> BatchSummary:
    """Delete stale pending jobs, then score up to two rounds of ``scorer_concurrency`` jobs."""
    now = now or datetime.now(UTC)
    summary = BatchSummary(deleted=delete_stale_pending(session_factory, now))
    job_ids = due_job_ids(session_factory, now, limit=settings.scorer_concurrency * 2)
    if not job_ids:
        return summary
    with ThreadPoolExecutor(max_workers=settings.scorer_concurrency) as pool:
        outcomes = pool.map(
            lambda job_id: _score_quietly(job_id, settings, session_factory, now), job_ids
        )
        for outcome in outcomes:
            summary.outcomes[outcome] = summary.outcomes.get(outcome, 0) + 1
    logger.info(summary.describe())
    return summary


def _score_quietly(
    job_id: int, settings: Settings, session_factory: sessionmaker[Session], now: datetime
) -> str:
    # A database error on one job must not stop the others; it stays pending and is retried.
    try:
        return score_job(job_id, settings, session_factory, now)
    except Exception:
        logger.exception("Could not score job %d; it stays pending", job_id)
        return OUTCOME_SKIPPED


def run_forever(
    settings: Settings, session_factory: sessionmaker[Session], stop: threading.Event
) -> None:
    """Score batches until ``stop`` is set, waiting ``IDLE_POLL_SECONDS`` when idle."""
    logger.info("Scorer started (concurrency %d)", settings.scorer_concurrency)
    while not stop.is_set():
        try:
            summary = score_batch(settings, session_factory)
        except Exception:
            logger.exception("Scorer batch failed; trying again shortly")
            summary = BatchSummary()
        if summary.attempted == 0:
            stop.wait(IDLE_POLL_SECONDS)
    logger.info("Scorer stopped")


def main() -> int:
    """``python -m src.scorer``: run until SIGTERM or SIGINT; exit 1 only on a settings error."""
    try:
        settings = get_settings()
    except SettingsError as error:
        print(error, file=sys.stderr)
        return 1
    configure_logging(settings.log_folder, file_name=SCORER_LOG_FILE_NAME)
    stop = threading.Event()

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        # Jobs being scored finish (or roll back and stay pending); no new batch starts.
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    run_forever(settings, get_sessionmaker(), stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
