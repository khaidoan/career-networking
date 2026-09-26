"""One fetcher run: discover jobs, track ATS boards, dedup, evaluate and ingest.

Every run first deletes ignored jobs older than ``IGNORED_JOB_RETENTION``. Then, in order:
Google Jobs search (when enabled and due; its boards are tracked right away) -> full ATS sweep
-> polling of tracked boards the sweep did not cover -> ingestion of the Google Jobs postings
-> pruning. Google postings are ingested last so a job the ATS sources already found is not
evaluated a second time. Each source and each job is isolated, so a failure is logged and the
run continues. A Postgres advisory lock keeps two runs from overlapping.

LLM tokens are spent only on postings that pass the free filters (title, seniority, country,
7-day recency) and both duplicate checks; the company lookup runs only for recommended jobs.

The ``fetcher`` compose service runs this once a day. An on-demand
"Fetch now" is the same command run by hand; there is no API endpoint or UI button:

    docker compose exec fetcher python -m src.fetcher
"""

import logging
import re
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.agents.company_lookup import enrich_company, is_name_only, lookup_company
from src.agents.evaluator import JobEvaluation, JobForEvaluation, evaluate_job
from src.config import Settings, SettingsError, get_settings
from src.db.session import get_engine, get_sessionmaker
from src.logging_config import FETCHER_LOG_FILE_NAME, configure_logging
from src.models import (
    DISCOVERED_VIA_ATS_SWEEP,
    DISCOVERED_VIA_GOOGLE_JOBS,
    AtsBoard,
    Company,
    Job,
    Preferences,
)
from src.sources.ats_sweep import run_sweep_batch
from src.sources.boards import BoardScan, scan_board
from src.sources.filters import (
    SearchCriteria,
    is_recent,
    location_matches,
    seniority_matches,
    title_matches,
)
from src.sources.google_jobs import recover_full_description, run_google_jobs
from src.sources.locations import countries_in
from src.sources.providers import get_provider
from src.sources.providers.base import BoardRef, HttpClient, Posting, create_http_client
from src.sources.state import get_fetcher_state
from src.sources.urls import normalize_url

# Named explicitly: under `python -m src.fetcher` this module is `__main__`.
logger = logging.getLogger("src.fetcher")

# Fixed key for pg_try_advisory_lock ("cn_fetch" in ASCII); any other run holding it wins.
ADVISORY_LOCK_KEY = 0x636E5F6665746368
# Active boards whose last match is older than this stop being polled until rediscovered.
BOARD_PRUNE_AFTER = timedelta(days=30)
# Ignored jobs discovered longer ago than this are deleted. Postings are only ingested while
# under 7 days old, so a deleted job cannot come back through the same posting.
IGNORED_JOB_RETENTION = timedelta(days=7)
TRACKED_POLL_CONCURRENCY = 8
# How far back a Google posting is compared against ATS jobs for the cross-source duplicate check.
CROSS_SOURCE_DEDUP_WINDOW = timedelta(days=30)
# Legal-form words ignored when comparing company names ("Acme Corp" matches board slug "acme").
COMPANY_SUFFIXES = frozenset(
    [
        "the",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "llc",
        "llp",
        "ltd",
        "limited",
        "plc",
        "gmbh",
        "ag",
        "sa",
        "sas",
        "bv",
        "nv",
        "oy",
        "ab",
        "as",
        "srl",
        "spa",
        "pty",
        "pte",
        "kk",
    ]
)
JOB_URL_CONSTRAINT = "uq_jobs_url"

SOURCE_GOOGLE_JOBS = "google_jobs"
SOURCE_ATS_SWEEP = "ats_sweep"
SOURCE_TRACKED_BOARDS = "tracked_boards"
SOURCES = (SOURCE_GOOGLE_JOBS, SOURCE_ATS_SWEEP, SOURCE_TRACKED_BOARDS)

INBOX_RECOMMENDED = "recommended"
INBOX_IGNORED = "ignored"

STATUS_COMPLETED = "completed"
STATUS_LOCKED = "skipped: another run is in progress"
STATUS_PREFERENCES_INCOMPLETE = "skipped: preferences incomplete"

# Where a job goes when its evaluation fails. It is saved with null scores and the failure
# reason, and never re-evaluated.
EVALUATION_FAILURE_INBOX = INBOX_IGNORED
EVALUATION_ERROR_MAX_CHARS = 1000


def describe_evaluation_error(error: Exception) -> str:
    """A one-line, length-capped reason such as ``LlmOutputError: invalid JSON after retry``."""
    message = " ".join(str(error).split())
    reason = f"{type(error).__name__}: {message}" if message else type(error).__name__
    if len(reason) > EVALUATION_ERROR_MAX_CHARS:
        reason = reason[: EVALUATION_ERROR_MAX_CHARS - 1] + "…"
    return reason


def apply_evaluation_failure(job: Job, error: Exception) -> None:
    """Save the job unscored in ``EVALUATION_FAILURE_INBOX`` with the failure reason."""
    job.inbox_type = EVALUATION_FAILURE_INBOX
    job.evaluation_error = describe_evaluation_error(error)
    logger.warning(
        "Evaluation failed for %r at %s; saved unscored to %s: %s",
        job.title,
        job.url,
        EVALUATION_FAILURE_INBOX,
        error,
    )


def inbox_for(evaluation: JobEvaluation, match_threshold: int) -> str:
    return INBOX_RECOMMENDED if evaluation.overall_score >= match_threshold else INBOX_IGNORED


@dataclass
class SourceStats:
    """Per-source counts. ``failed`` covers failed searches or boards and jobs not ingested."""

    fetched: int = 0
    matched: int = 0
    new: int = 0
    duplicate: int = 0
    failed: int = 0

    def describe(self) -> str:
        return (
            f"fetched={self.fetched} matched={self.matched} new={self.new} "
            f"duplicate={self.duplicate} failed={self.failed}"
        )


@dataclass
class RunSummary:
    status: str = STATUS_COMPLETED
    sources: dict[str, SourceStats] = field(
        default_factory=lambda: {source: SourceStats() for source in SOURCES}
    )
    evaluated: int = 0
    evaluation_failed: int = 0
    recommended: int = 0
    ignored: int = 0
    boards_pruned: int = 0
    ignored_jobs_deleted: int = 0
    duration_seconds: float = 0.0

    def describe(self) -> str:
        per_source = "; ".join(f"{name} {stats.describe()}" for name, stats in self.sources.items())
        return (
            f"Fetcher run finished in {self.duration_seconds:.1f}s: {per_source}; "
            f"evaluated={self.evaluated} evaluation_failed={self.evaluation_failed} "
            f"recommended={self.recommended} ignored={self.ignored} "
            f"boards_pruned={self.boards_pruned} ignored_jobs_deleted={self.ignored_jobs_deleted}"
        )


@contextmanager
def advisory_lock(engine: Engine, key: int = ADVISORY_LOCK_KEY) -> Iterator[bool]:
    """Hold a session-level advisory lock on a dedicated connection; yields whether it was won."""
    connection = engine.connect()
    try:
        acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
        connection.commit()
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                    connection.commit()
                except Exception:
                    # A broken connection must not go back to the pool; closing it on the
                    # server side releases the lock anyway.
                    logger.exception("Could not release the fetcher lock")
                    connection.invalidate()
    finally:
        connection.close()


def load_preferences(session_factory: sessionmaker[Session]) -> Preferences | None:
    with session_factory() as session:
        return session.get(Preferences, 1)


def run_fetch(
    settings: Settings,
    *,
    engine: Engine,
    session_factory: sessionmaker[Session],
    client_factory: Callable[[], HttpClient] = create_http_client,
    now: datetime | None = None,
) -> RunSummary:
    """One complete fetcher run; source and job failures are logged, never raised."""
    started = time.monotonic()
    now = now or datetime.now(UTC)
    summary = RunSummary()
    with advisory_lock(engine) as acquired:
        if not acquired:
            logger.info("Fetcher skipped: another run is in progress")
            summary.status = STATUS_LOCKED
            return summary

        # Housekeeping runs even when discovery is paused below.
        try:
            summary.ignored_jobs_deleted = delete_expired_ignored_jobs(session_factory, now)
        except Exception:
            logger.exception("Could not delete expired ignored jobs; continuing")

        preferences = load_preferences(session_factory)
        criteria = SearchCriteria.from_preferences(preferences)
        if criteria is None:
            logger.info(
                "Fetcher skipped: preferences incomplete (set desired titles and country "
                "on the Profile page)"
            )
            summary.status = STATUS_PREFERENCES_INCOMPLETE
            return summary

        logger.info("Fetcher run started")
        client = client_factory()
        try:
            run = FetcherRun(settings, session_factory, preferences, criteria, client, now, summary)
            run.execute()
        finally:
            client.close()
    summary.duration_seconds = time.monotonic() - started
    logger.info(summary.describe())
    return summary


class FetcherRun:
    """The state of one run: in-run URL dedup, boards already scanned and the counters."""

    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        preferences: Preferences | None,
        criteria: SearchCriteria,
        client: HttpClient,
        now: datetime,
        summary: RunSummary,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.preferences = preferences
        self.criteria = criteria
        self.client = client
        self.now = now
        self.summary = summary
        self.state = get_fetcher_state(settings)
        self.seen_urls: set[str] = set()
        # Google postings wait until the ATS sources have been ingested (cross-source dedup).
        self.google_postings: list[Posting] = []
        # (company key, title key) -> countries named, for ATS jobs handled in this run.
        self.ats_jobs: dict[tuple[str, str], list[set[str]]] = {}
        # Boards scanned by the sweep this run; polling them again would repeat the same fetch.
        self.scanned_boards: set[tuple[str, str]] = set()

    def execute(self) -> None:
        steps: list[tuple[str, Callable[[], None]]] = [
            (SOURCE_GOOGLE_JOBS, self.google_jobs),
            (SOURCE_ATS_SWEEP, self.ats_sweep),
            (SOURCE_TRACKED_BOARDS, self.tracked_boards),
            (SOURCE_GOOGLE_JOBS, self.ingest_google_jobs),
            ("pruning", self.prune),
        ]
        for name, step in steps:
            try:
                step()
            except Exception:
                logger.exception("Fetcher step %s failed; continuing with the next step", name)
                if name in self.summary.sources:
                    self.summary.sources[name].failed += 1

    # Sources -------------------------------------------------------------------------------

    def google_jobs(self) -> None:
        stats = self.summary.sources[SOURCE_GOOGLE_JOBS]
        result = run_google_jobs(self.settings, self.criteria, self.client, self.state, self.now)
        if result is None:
            return
        # The same free filters as the ATS sources, so no token is spent on a posting that an
        # ATS board would have dropped. The search is country-scoped, so a bare "Remote" is kept.
        postings = [posting for posting in result.postings if self._google_posting_matches(posting)]
        stats.fetched = len(result.postings)
        stats.matched = len(postings)
        stats.failed += result.failed_searches
        upsert_boards(self.session_factory, result.boards, DISCOVERED_VIA_GOOGLE_JOBS, self.now)
        self.google_postings = postings

    def _google_posting_matches(self, posting: Posting) -> bool:
        return (
            title_matches(posting.title, self.criteria.desired_titles)
            and seniority_matches(posting.title, self.criteria.seniority)
            and location_matches(posting.location, self.criteria.country)
            and is_recent(posting.published_at, self.now)
        )

    def ingest_google_jobs(self) -> None:
        """Ingest the Google postings that no ATS source already covered."""
        stats = self.summary.sources[SOURCE_GOOGLE_JOBS]
        postings, self.google_postings = self.google_postings, []
        if not postings:
            return
        known = self._recent_ats_jobs()
        fresh = []
        for posting in postings:
            # An ATS apply link is deduplicated by URL; this catches LinkedIn, Indeed and other
            # links to a job an ATS board already gave us.
            if posting.board is None and self._covered_by_ats(posting, known):
                self.seen_urls.add(normalize_url(posting.url) or posting.url)
                stats.duplicate += 1
            else:
                fresh.append(posting)
        self.ingest(fresh, stats, recover_descriptions=True)

    def _recent_ats_jobs(self) -> dict[tuple[str, str], list[set[str]]]:
        """ATS jobs from this run and the last ``CROSS_SOURCE_DEDUP_WINDOW`` in the database."""
        known = {key: list(countries) for key, countries in self.ats_jobs.items()}
        with self.session_factory() as session:
            rows = session.execute(
                select(Company.name, Job.title, Job.location_country)
                .join(Company, Job.company_id == Company.id)
                .where(
                    Job.discovered_when >= self.now - CROSS_SOURCE_DEDUP_WINDOW,
                    Job.source.not_like(f"{SOURCE_GOOGLE_JOBS}:%"),
                )
            ).all()
        for row in rows:
            key = (company_key(row.name), title_key(row.title))
            known.setdefault(key, []).append(
                {row.location_country} if row.location_country else set()
            )
        return known

    @staticmethod
    def _covered_by_ats(posting: Posting, known: dict[tuple[str, str], list[set[str]]]) -> bool:
        countries = countries_in(posting.location or "")
        for ats_countries in known.get(
            (company_key(posting.company), title_key(posting.title)), []
        ):
            # Unknown locations on either side count as the same job.
            if not countries or not ats_countries or countries & ats_countries:
                return True
        return False

    def ats_sweep(self) -> None:
        stats = self.summary.sources[SOURCE_ATS_SWEEP]
        result = run_sweep_batch(self.criteria, self.client, self.state, self.now)
        if result.skipped:
            return
        stats.fetched = result.postings_fetched
        stats.failed += result.boards_failed
        boards = [scan.board for scan in result.matched_boards]
        self.scanned_boards.update(_board_identity(board) for board in boards)
        upsert_boards(self.session_factory, boards, DISCOVERED_VIA_ATS_SWEEP, self.now, polled=True)
        postings = [posting for scan in result.matched_boards for posting in scan.matches]
        stats.matched = len(postings)
        self._remember_ats(postings)
        self.ingest(postings, stats)

    def tracked_boards(self) -> None:
        stats = self.summary.sources[SOURCE_TRACKED_BOARDS]
        with self.session_factory() as session:
            rows = session.execute(
                select(AtsBoard.id, AtsBoard.provider, AtsBoard.board_key, AtsBoard.company_name)
                .where(AtsBoard.is_active)
                .order_by(AtsBoard.id)
            ).all()
        boards = {
            row.id: (row.provider, row.board_key, row.company_name)
            for row in rows
            if (row.provider, row.board_key) not in self.scanned_boards
        }
        logger.info("Tracked boards: polling %d active boards", len(boards))

        with ThreadPoolExecutor(max_workers=TRACKED_POLL_CONCURRENCY) as pool:
            scans = dict(zip(boards, pool.map(self._poll_board, boards.values()), strict=True))

        polled = [board_id for board_id, scan in scans.items() if scan is not None]
        matched = [board_id for board_id, scan in scans.items() if scan and scan.matches]
        stats.failed += len(boards) - len(polled)
        with self.session_factory() as session, session.begin():
            if polled:
                session.execute(
                    update(AtsBoard)
                    .where(AtsBoard.id.in_(polled))
                    .values(last_polled_at=self.now, updated_at=func.now())
                )
            if matched:
                session.execute(
                    update(AtsBoard)
                    .where(AtsBoard.id.in_(matched))
                    .values(last_matched_at=self.now, updated_at=func.now())
                )

        postings = [posting for scan in scans.values() if scan for posting in scan.matches]
        stats.fetched = sum(scan.fetched for scan in scans.values() if scan)
        stats.matched = len(postings)
        self._remember_ats(postings)
        self.ingest(postings, stats)

    def _remember_ats(self, postings: Sequence[Posting]) -> None:
        for posting in postings:
            key = (company_key(posting.company), title_key(posting.title))
            self.ats_jobs.setdefault(key, []).append(countries_in(posting.location or ""))

    def _poll_board(self, board: tuple[str, str, str | None]) -> BoardScan | None:
        provider, board_key, company_name = board
        try:
            ref = get_provider(provider).board_ref(board_key, company_name)
            return scan_board(ref, self.criteria, self.client, self.now)
        except Exception as error:
            logger.warning(
                "Tracked board %s/%s could not be polled: %s", provider, board_key, error
            )
            return None

    def prune(self) -> None:
        self.summary.boards_pruned = prune_boards(self.session_factory, self.now)

    # Ingestion -----------------------------------------------------------------------------

    def ingest(
        self, postings: Sequence[Posting], stats: SourceStats, *, recover_descriptions: bool = False
    ) -> None:
        """Dedup ``postings`` (in-run, then one query against ``jobs``) and ingest the new ones."""
        candidates: dict[str, Posting] = {}
        for posting in postings:
            url = normalize_url(posting.url)
            if url is None:
                logger.warning("Skipping a %s posting without a valid URL", posting.source)
                stats.failed += 1
            elif url in self.seen_urls:
                stats.duplicate += 1
            else:
                self.seen_urls.add(url)
                candidates[url] = posting
        if not candidates:
            return

        with self.session_factory() as session:
            existing = set(session.scalars(select(Job.url).where(Job.url.in_(list(candidates)))))
        for url, posting in candidates.items():
            if url in existing:
                stats.duplicate += 1
                continue
            try:
                if recover_descriptions:
                    recover_full_description(posting, self.client)
                self.ingest_one(url, posting, stats)
            except Exception:
                stats.failed += 1
                logger.exception("Could not ingest %r from %s", posting.title, posting.source)

    def ingest_one(self, url: str, posting: Posting, stats: SourceStats) -> None:
        """Evaluation, company and job insert for one new posting, in one transaction.

        The job is evaluated first so the company lookup (more tokens) only runs when the job is
        recommended; companies of ignored jobs are saved by name and enriched if a later job of
        theirs is recommended.
        """
        job = Job(
            title=posting.title.strip(),
            url=url,
            description=posting.description,
            source=posting.source,
        )
        try:
            with self.session_factory() as session, session.begin():
                evaluated = self._evaluate(session, job, posting)
                inbox = job.inbox_type
                company = find_or_create_company(
                    session, posting, look_up=inbox == INBOX_RECOMMENDED
                )
                job.company_id = company.id
                session.add(job)
        except IntegrityError as error:
            if _constraint_name(error) != JOB_URL_CONSTRAINT:
                raise
            logger.info("Job at %s was inserted concurrently; skipping", url)
            stats.duplicate += 1
            return

        stats.new += 1
        if evaluated:
            self.summary.evaluated += 1
        else:
            self.summary.evaluation_failed += 1
        if inbox == INBOX_RECOMMENDED:
            self.summary.recommended += 1
        else:
            self.summary.ignored += 1

    def _evaluate(self, session: Session, job: Job, posting: Posting) -> bool:
        """Fill the job's scores, extracted fields and inbox; ``False`` when evaluation failed."""
        subject = JobForEvaluation(
            title=job.title,
            company=posting.company,
            location=posting.location or None,
            description=posting.description,
        )
        try:
            evaluation = evaluate_job(session, subject, self.preferences)
        except Exception as error:
            apply_evaluation_failure(job, error)
            return False
        for name, value in evaluation.model_dump().items():
            setattr(job, name, value)
        job.inbox_type = inbox_for(evaluation, self.settings.match_threshold)
        return True


def company_key(name: str) -> str:
    """A company name reduced for comparison: "Acme Corp, Inc." -> "acme"."""
    words = re.findall(r"[a-z0-9]+", name.casefold())
    return "".join(word for word in words if word not in COMPANY_SUFFIXES) or "".join(words)


def title_key(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#]+", title.casefold()))


def find_or_create_company(session: Session, posting: Posting, *, look_up: bool) -> Company:
    """Case-insensitive exact name match, else a new company.

    With ``look_up`` (the job is recommended) a new company is filled by the lookup agent and a
    name-only one is enriched; otherwise no tokens are spent and a new company is saved by name.
    """
    name = posting.company.strip()
    if not name:
        raise ValueError("posting has no company name")
    company = session.scalars(
        select(Company)
        .where(func.lower(Company.name) == func.lower(name))
        .order_by(Company.id)
        .limit(1)
    ).first()
    if company is not None:
        if look_up and is_name_only(company):
            try:
                with session.begin_nested():
                    enrich_company(session, company, posting.description)
            except Exception as error:
                logger.warning(
                    "Company lookup failed for %r; keeping the name only: %s", name, error
                )
        return company
    if look_up:
        try:
            with session.begin_nested():
                return lookup_company(session, name, posting.description)
        except Exception as error:
            logger.warning("Company lookup failed for %r; saving the name only: %s", name, error)
    company = Company(name=name)
    session.add(company)
    session.flush()
    return company


def _board_identity(board: BoardRef) -> tuple[str, str]:
    return board.provider, board.board_key


def upsert_boards(
    session_factory: sessionmaker[Session],
    boards: Iterable[BoardRef],
    discovered_via: str,
    now: datetime,
    *,
    polled: bool = False,
) -> None:
    """Track matched boards: insert new ones, and mark existing ones matched and active.

    ``discovered_via`` records the first discovery and is kept on conflict. A stored company
    name is never replaced (directory boards only know their slug).
    """
    rows = {}
    for board in boards:
        rows.setdefault(
            _board_identity(board),
            {
                "provider": board.provider,
                "board_key": board.board_key,
                "board_url": board.board_url,
                "company_name": board.company_name,
                "discovered_via": discovered_via,
                "is_active": True,
                "last_matched_at": now,
                "last_polled_at": now if polled else None,
            },
        )
    if not rows:
        return
    statement = pg_insert(AtsBoard)
    statement = statement.on_conflict_do_update(
        index_elements=[AtsBoard.provider, AtsBoard.board_key],
        set_={
            "is_active": True,
            "last_matched_at": statement.excluded.last_matched_at,
            "last_polled_at": func.coalesce(
                statement.excluded.last_polled_at, AtsBoard.last_polled_at
            ),
            "board_url": func.coalesce(statement.excluded.board_url, AtsBoard.board_url),
            "company_name": func.coalesce(AtsBoard.company_name, statement.excluded.company_name),
            "updated_at": func.now(),
        },
    )
    with session_factory() as session, session.begin():
        session.execute(statement, list(rows.values()))


def prune_boards(session_factory: sessionmaker[Session], now: datetime) -> int:
    """Deactivate boards with no match for ``BOARD_PRUNE_AFTER``; discovery reactivates them."""
    cutoff = now - BOARD_PRUNE_AFTER
    with session_factory() as session, session.begin():
        result = session.execute(
            update(AtsBoard)
            .where(
                AtsBoard.is_active,
                func.coalesce(AtsBoard.last_matched_at, AtsBoard.created_at) < cutoff,
            )
            .values(is_active=False, updated_at=func.now())
        )
    pruned = result.rowcount or 0
    if pruned:
        logger.info("Pruned %d boards with no match in %d days", pruned, BOARD_PRUNE_AFTER.days)
    return pruned


def delete_expired_ignored_jobs(session_factory: sessionmaker[Session], now: datetime) -> int:
    """Delete jobs in the ignored inbox discovered more than ``IGNORED_JOB_RETENTION`` ago."""
    cutoff = now - IGNORED_JOB_RETENTION
    with session_factory() as session, session.begin():
        result = session.execute(
            delete(Job).where(Job.inbox_type == INBOX_IGNORED, Job.discovered_when < cutoff)
        )
    deleted = result.rowcount or 0
    if deleted:
        logger.info(
            "Deleted %d ignored jobs older than %d days", deleted, IGNORED_JOB_RETENTION.days
        )
    return deleted


def _constraint_name(error: IntegrityError) -> str | None:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def main() -> int:
    """``python -m src.fetcher``: exit 0 for completed and skipped runs, 1 if the run crashed."""
    try:
        settings = get_settings()
    except SettingsError as error:
        print(error, file=sys.stderr)
        return 1
    configure_logging(settings.log_folder, file_name=FETCHER_LOG_FILE_NAME)
    try:
        run_fetch(settings, engine=get_engine(), session_factory=get_sessionmaker())
    except Exception:
        logger.exception("Fetcher run failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
