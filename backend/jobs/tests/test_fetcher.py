"""Fetcher runs against a disposable Postgres, with every source, agent and HTTP call mocked.

The database tests need CAREER_NETWORKING_TEST_DATABASE_URL (see test_migrations.py).
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src import fetcher
from src.agents.evaluator import JobEvaluation, JobForEvaluation
from src.config import Settings, get_settings
from src.llm import LlmError, LlmOutputError
from src.models import AtsBoard, Company, Job, Preferences
from src.sources.ats_sweep import SweepResult
from src.sources.boards import BoardScan
from src.sources.google_jobs import SERPAPI_SEARCH_URL, GoogleJobsResult
from src.sources.providers.base import BoardRef, Posting
from src.sources.urls import normalize_url
from tests.conftest import FakeHttp, fixture_json

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)

ACME_BOARD = BoardRef("greenhouse", "acme", "Acme Corp", "https://job-boards.greenhouse.io/acme")
GLOBEX_BOARD = BoardRef("lever", "globex", None, "https://jobs.lever.co/globex")


def _posting(title: str, company: str, url: str, source: str, **extra: Any) -> Posting:
    return Posting(
        title=title,
        company=company,
        url=url,
        source=source,
        location="Remote, US",
        published_at=NOW - timedelta(days=1),
        description=f"{title} at {company}.",
        **extra,
    )


def _evaluation(score: int) -> JobEvaluation:
    return JobEvaluation(
        overall_score=score,
        experience_score=score,
        skill_score=score,
        industry_exp_score=score,
        work_arrangement="remote",
        location_country="US",
    )


@pytest.fixture
def sessions(alembic_config: Config) -> Iterator[sessionmaker[Session]]:
    command.upgrade(alembic_config, "head")
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        command.downgrade(alembic_config, "base")


class FakeSources:
    """Records what the fetcher asks of the mocked sources and agents."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.google: GoogleJobsResult | Exception | None = None
        self.sweep: SweepResult | Exception = SweepResult(skipped=True)
        self.tracked: dict[str, list[Posting] | Exception] = {}
        self.scores: dict[str, int | Exception] = {}
        self.polled: list[str] = []
        self.looked_up: list[str] = []
        self.enriched: list[str] = []
        self.recovered: list[str] = []
        self.evaluated: list[JobForEvaluation] = []
        monkeypatch.setattr(fetcher, "run_google_jobs", self._google)
        monkeypatch.setattr(fetcher, "run_sweep_batch", self._sweep)
        monkeypatch.setattr(fetcher, "scan_board", self._scan)
        monkeypatch.setattr(fetcher, "recover_full_description", self._recover)
        monkeypatch.setattr(fetcher, "lookup_company", self._lookup)
        monkeypatch.setattr(fetcher, "enrich_company", self._enrich)
        monkeypatch.setattr(fetcher, "evaluate_job", self._evaluate)

    @staticmethod
    def _result(value: Any) -> Any:
        if isinstance(value, Exception):
            raise value
        return value

    def _google(self, *_args: Any) -> GoogleJobsResult | None:
        return self._result(self.google)

    def _sweep(self, *_args: Any) -> SweepResult:
        return self._result(self.sweep)

    def _scan(self, board: BoardRef, *_args: Any) -> BoardScan:
        self.polled.append(board.board_key)
        matches = self._result(self.tracked.get(board.board_key, []))
        return BoardScan(board=board, fetched=len(matches) + 1, matches=matches)

    def _recover(self, posting: Posting, _client: Any) -> None:
        self.recovered.append(posting.url)

    def _lookup(self, _session: Session, name: str, _description: str | None = None) -> Company:
        self.looked_up.append(name)
        raise LlmError("model unavailable")

    def _enrich(self, _session: Session, company: Company, _description: str | None = None) -> None:
        self.enriched.append(company.name)
        company.description = f"{company.name} makes things."

    def _evaluate(self, _session: Session, job: JobForEvaluation, _prefs: Any) -> JobEvaluation:
        self.evaluated.append(job)
        return _evaluation(self._result(self.scores[job.title]))


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    return FakeSources(monkeypatch)


def _save_preferences(sessions: sessionmaker[Session], **values: Any) -> None:
    with sessions() as session, session.begin():
        session.add(Preferences(id=1, **values))


def _run(
    settings: Settings, sessions: sessionmaker[Session], fake_http: FakeHttp
) -> fetcher.RunSummary:
    return fetcher.run_fetch(
        settings,
        engine=sessions.kw["bind"],
        session_factory=sessions,
        client_factory=fake_http.client,
        now=NOW,
    )


def test_run_dedups_urls_matches_companies_and_routes_jobs_by_score(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
) -> None:
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country="US")
    with sessions() as session, session.begin():
        acme = Company(name="Acme Corp")
        session.add(acme)
        session.flush()
        acme_id = acme.id
        session.add(
            Job(
                company_id=acme_id,
                title="Backend Engineer",
                url="https://job-boards.greenhouse.io/acme/jobs/1",
                inbox_type="applied",
            )
        )

    already_saved = _posting(
        "Backend Engineer",
        "Acme Corp",
        "https://JOB-BOARDS.greenhouse.io/acme/jobs/1/?gh_src=abc&utm_source=google#apply",
        "google_jobs:LinkedIn",
    )
    acme_new = _posting(
        "Senior Backend Engineer",
        "ACME CORP",
        "https://job-boards.greenhouse.io/acme/jobs/2?utm_campaign=google_jobs_apply",
        "google_jobs:LinkedIn",
        board=ACME_BOARD,
    )
    globex_job = _posting(
        "Backend Engineer II", "Globex", "https://jobs.lever.co/globex/9", "lever"
    )
    sources.google = GoogleJobsResult(
        postings=[already_saved, acme_new], boards=[ACME_BOARD], searches=1
    )
    sources.sweep = SweepResult(
        boards_scanned=4,
        postings_fetched=12,
        matched_boards=[BoardScan(board=GLOBEX_BOARD, fetched=3, matches=[globex_job])],
    )
    # The Google-discovered board is polled in the same run and returns the same posting again.
    sources.tracked = {
        "acme": [
            _posting(
                "Senior Backend Engineer",
                "Acme Corp",
                "https://job-boards.greenhouse.io/acme/jobs/2",
                "greenhouse",
            )
        ]
    }
    sources.scores = {"Senior Backend Engineer": 85, "Backend Engineer II": 40}

    summary = _run(test_settings, sessions, fake_http)

    with sessions() as session:
        jobs = {job.title: job for job in session.scalars(select(Job).where(Job.id > 0))}
        companies = {company.name: company for company in session.scalars(select(Company))}
        boards = {board.board_key: board for board in session.scalars(select(AtsBoard))}

    assert len(jobs) == 3
    recommended = jobs["Senior Backend Engineer"]
    assert recommended.url == "https://job-boards.greenhouse.io/acme/jobs/2"
    assert recommended.company_id == acme_id
    assert recommended.inbox_type == "recommended"
    assert recommended.overall_score == 85
    assert recommended.work_arrangement == "remote"
    # ATS sources are ingested before Google postings, so the job keeps its ATS source and the
    # Google copy of it is a duplicate (no second evaluation, no description fetch).
    assert recommended.source == "greenhouse"

    ignored = jobs["Backend Engineer II"]
    assert ignored.inbox_type == "ignored"
    assert ignored.source == "lever"
    assert ignored.company_id == companies["Globex"].id
    assert companies["Globex"].website_url is None
    # No tokens on the company of an ignored job; the recommended job enriches its bare company.
    assert sources.looked_up == []
    assert sources.enriched == ["Acme Corp"]
    assert companies["Acme Corp"].description == "Acme Corp makes things."
    assert sources.recovered == []
    # ATS postings (sweep, then tracked boards) are evaluated before Google postings.
    assert [job.title for job in sources.evaluated] == [
        "Backend Engineer II",
        "Senior Backend Engineer",
    ]

    assert boards["acme"].discovered_via == "google_jobs"
    assert boards["acme"].company_name == "Acme Corp"
    assert boards["acme"].last_matched_at == NOW
    assert boards["globex"].discovered_via == "ats_sweep"
    assert boards["globex"].last_polled_at == NOW
    # The sweep just scanned globex, so only acme is polled as a tracked board.
    assert sources.polled == ["acme"]

    google = summary.sources["google_jobs"]
    assert (google.fetched, google.new, google.duplicate) == (2, 0, 2)
    assert (summary.sources["tracked_boards"].new, summary.sources["tracked_boards"].duplicate) == (
        1,
        0,
    )
    assert (summary.evaluated, summary.recommended, summary.ignored) == (2, 1, 1)


def test_failed_evaluation_saves_the_job_unscored_in_the_ignored_inbox(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
) -> None:
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country="US")
    job = _posting("Backend Engineer", "Initech", "https://jobs.lever.co/initech/1", "lever")
    sources.sweep = SweepResult(
        boards_scanned=1,
        matched_boards=[BoardScan(board=BoardRef("lever", "initech"), fetched=1, matches=[job])],
    )
    sources.scores = {"Backend Engineer": LlmOutputError("invalid JSON after retry")}

    summary = _run(test_settings, sessions, fake_http)

    with sessions() as session:
        saved = session.scalars(select(Job)).one()
    assert saved.inbox_type == fetcher.EVALUATION_FAILURE_INBOX == "ignored"
    assert saved.overall_score is None
    assert saved.skill_score is None
    assert saved.evaluation_error == "LlmOutputError: invalid JSON after retry"
    assert (summary.evaluated, summary.evaluation_failed, summary.ignored) == (0, 1, 1)


def test_evaluation_error_is_one_line_and_capped() -> None:
    reason = fetcher.describe_evaluation_error(RuntimeError("line one\n  line two " + "x" * 2000))
    assert reason.startswith("RuntimeError: line one line two x")
    assert len(reason) == fetcher.EVALUATION_ERROR_MAX_CHARS
    assert reason.endswith("…")
    assert fetcher.describe_evaluation_error(TimeoutError()) == "TimeoutError"


def test_google_jobs_postings_older_than_seven_days_or_undated_are_not_processed(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
) -> None:
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country="US")
    fresh = _posting(
        "Backend Engineer", "Initech", "https://example.com/jobs/1", "google_jobs:Indeed"
    )
    stale = _posting(
        "Backend Engineer", "Initech", "https://example.com/jobs/2", "google_jobs:Indeed"
    )
    stale.published_at = NOW - timedelta(days=8)
    undated = _posting(
        "Backend Engineer", "Initech", "https://example.com/jobs/3", "google_jobs:Indeed"
    )
    undated.published_at = None
    sources.google = GoogleJobsResult(postings=[fresh, stale, undated], boards=[], searches=1)
    sources.scores = {"Backend Engineer": 80}

    summary = _run(test_settings, sessions, fake_http)

    with sessions() as session:
        urls = list(session.scalars(select(Job.url)))
    assert urls == ["https://example.com/jobs/1"]
    assert sources.recovered == [fresh.url]
    google = summary.sources["google_jobs"]
    assert (google.fetched, google.matched, google.new) == (3, 1, 1)


def test_incomplete_preferences_skip_the_run_and_exit_zero(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country=None)
    sources.google = RuntimeError("must not be called")
    monkeypatch.setattr(fetcher, "get_settings", lambda: test_settings)
    monkeypatch.setattr(fetcher, "configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(fetcher, "get_engine", lambda: sessions.kw["bind"])
    monkeypatch.setattr(fetcher, "get_sessionmaker", lambda: sessions)

    with caplog.at_level(logging.INFO, logger="src.fetcher"):
        exit_code = fetcher.main()

    assert exit_code == 0
    assert any(
        "skipped: preferences incomplete" in record.getMessage() for record in caplog.records
    )
    assert sources.polled == []


def test_failing_sources_do_not_stop_polling_and_stale_boards_are_pruned(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
) -> None:
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country="US")
    with sessions() as session, session.begin():
        for key, matched_days_ago in (("stale", 31), ("fresh", 5), ("broken", 10)):
            session.add(
                AtsBoard(
                    provider="greenhouse",
                    board_key=key,
                    discovered_via="ats_sweep",
                    last_matched_at=NOW - timedelta(days=matched_days_ago),
                )
            )
    sources.google = RuntimeError("SerpApi exploded")
    sources.sweep = RuntimeError("directory exploded")
    sources.tracked = {"broken": RuntimeError("HTTP 500")}

    summary = _run(test_settings, sessions, fake_http)

    with sessions() as session:
        boards = {board.board_key: board for board in session.scalars(select(AtsBoard))}
    assert sorted(sources.polled) == ["broken", "fresh", "stale"]
    assert boards["stale"].is_active is False
    assert boards["fresh"].is_active is True
    assert boards["fresh"].last_polled_at == NOW
    assert boards["broken"].is_active is True
    assert boards["broken"].last_polled_at is None
    assert summary.boards_pruned == 1
    assert summary.sources["google_jobs"].failed == 1
    assert summary.sources["ats_sweep"].failed == 1
    assert summary.sources["tracked_boards"].failed == 1


def test_normalize_url_strips_tracking_and_formatting_differences() -> None:
    assert (
        normalize_url(
            "HTTPS://Jobs.Lever.co:443/acme/123/?lever-source=LinkedIn&utm_medium=x&team=eng#top"
        )
        == "https://jobs.lever.co/acme/123?team=eng"
    )
    assert normalize_url("https://example.com/job?id=7&ref=feed") == "https://example.com/job?id=7"
    assert normalize_url("mailto:jobs@example.com") is None


def test_a_run_exits_cleanly_while_another_run_holds_the_advisory_lock(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country="US")
    sources.google = RuntimeError("must not be called while locked")
    sources.sweep = RuntimeError("must not be called while locked")

    with fetcher.advisory_lock(sessions.kw["bind"]) as first_run_holds_lock:
        assert first_run_holds_lock
        with caplog.at_level(logging.INFO, logger="src.fetcher"):
            summary = _run(test_settings, sessions, fake_http)

    assert summary.status == fetcher.STATUS_LOCKED
    assert all(stats.failed == 0 for stats in summary.sources.values())
    assert sources.polled == [] and fake_http.requests == []
    assert "another run is in progress" in caplog.text
    # The lock is released with the first run, so the next scheduled run goes ahead.
    sources.google = None
    sources.sweep = SweepResult(skipped=True)
    assert _run(test_settings, sessions, fake_http).status == fetcher.STATUS_COMPLETED


def _serpapi_result(title: str, company: str, via: str, apply_link: str) -> dict[str, Any]:
    return {
        "title": title,
        "company_name": company,
        "location": "Remote, United States",
        "via": via,
        "description": f"{company} is hiring a {title} to build Python services. " * 8,
        "detected_extensions": {"posted_at": "2 days ago"},
        "apply_options": [{"title": via, "link": apply_link}],
    }


def test_google_jobs_boards_are_tracked_and_polled_again_on_the_next_run(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    fake_http: FakeHttp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real Google Jobs, sweep and board polling code; only HTTP and the agents are mocked."""
    settings = test_settings.model_copy(update={"serpapi_api_key": SecretStr("serpapi-key")})
    _save_preferences(sessions, desired_titles=["Backend Engineer"], country="US")
    with sessions() as session, session.begin():
        # Pruned earlier; a Google Jobs apply link rediscovers it.
        session.add(
            AtsBoard(
                provider="lever",
                board_key="globex",
                discovered_via="ats_sweep",
                is_active=False,
                last_matched_at=NOW - timedelta(days=40),
            )
        )
    looked_up: list[str] = []

    def failing_lookup(_session: Session, name: str, _description: str | None = None) -> Company:
        looked_up.append(name)
        raise LlmError("model unavailable")

    def failing_enrich(
        _session: Session, company: Company, _description: str | None = None
    ) -> None:
        looked_up.append(f"enrich {company.name}")
        raise LlmError("model unavailable")

    monkeypatch.setattr(fetcher, "lookup_company", failing_lookup)
    monkeypatch.setattr(fetcher, "enrich_company", failing_enrich)
    monkeypatch.setattr(fetcher, "evaluate_job", lambda *_args: _evaluation(80))

    greenhouse_jobs = fixture_json("ats/greenhouse.json")
    fake_http.add(
        SERPAPI_SEARCH_URL,
        json={
            "jobs_results": [
                _serpapi_result(
                    "Senior Backend Engineer",
                    "Acme Corp",
                    "LinkedIn",
                    "https://job-boards.greenhouse.io/acme/jobs/101?gh_src=google",
                ),
                _serpapi_result(
                    "Backend Engineer",
                    "Globex",
                    "Glassdoor",
                    "https://jobs.lever.co/globex/7f3c2a10-aaaa-bbbb-cccc-1234567890ab/apply",
                ),
            ]
        },
    )
    # First poll: only the job Google already found. Second poll: the whole board.
    fake_http.add(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        json={"jobs": [greenhouse_jobs["jobs"][0]]},
    )
    fake_http.add("https://boards-api.greenhouse.io/v1/boards/acme/jobs", json=greenhouse_jobs)
    fake_http.add("https://api.lever.co/v0/postings/globex", json=[])

    first = _run(settings, sessions, fake_http)
    first_requests = len(fake_http.requests)
    second = fetcher.run_fetch(
        settings,
        engine=sessions.kw["bind"],
        session_factory=sessions,
        client_factory=fake_http.client,
        now=NOW + timedelta(hours=1),
    )

    with sessions() as session:
        boards = {board.board_key: board for board in session.scalars(select(AtsBoard))}
        jobs = {job.url: job for job in session.scalars(select(Job))}

    acme, globex = boards["acme"], boards["globex"]
    assert (acme.provider, acme.discovered_via, acme.company_name) == (
        "greenhouse",
        "google_jobs",
        "Acme Corp",
    )
    assert acme.is_active and acme.last_polled_at == acme.last_matched_at == NOW + timedelta(
        hours=1
    )
    assert globex.is_active and globex.company_name == "Globex"
    assert globex.last_matched_at == NOW
    assert globex.last_polled_at == NOW + timedelta(hours=1)

    # The acme board Google found is polled in the same run and yields job 101 first; the Google
    # copy (with ?gh_src) is then a duplicate. Globex's Lever job comes only from Google.
    assert (first.sources["tracked_boards"].new, first.sources["tracked_boards"].duplicate) == (
        1,
        0,
    )
    assert (first.sources["google_jobs"].new, first.sources["google_jobs"].duplicate) == (1, 1)
    # Google Jobs is not due again for 24 hours, so the second run only polls tracked boards.
    assert not any(
        request.url.host == "serpapi.com" for request in fake_http.requests[first_requests:]
    )
    assert (second.sources["google_jobs"].fetched, second.sources["tracked_boards"].new) == (0, 1)
    assert second.sources["tracked_boards"].duplicate == 1

    assert set(jobs) == {
        "https://job-boards.greenhouse.io/acme/jobs/101",
        "https://jobs.lever.co/globex/7f3c2a10-aaaa-bbbb-cccc-1234567890ab/apply",
        "https://job-boards.greenhouse.io/acme/jobs/106",
    }
    assert jobs["https://job-boards.greenhouse.io/acme/jobs/101"].source == "greenhouse"
    globex_job = jobs["https://jobs.lever.co/globex/7f3c2a10-aaaa-bbbb-cccc-1234567890ab/apply"]
    assert globex_job.source == "google_jobs:Glassdoor"
    tracked_job = jobs["https://job-boards.greenhouse.io/acme/jobs/106"]
    assert tracked_job.source == "greenhouse" and tracked_job.inbox_type == "recommended"
    assert (
        tracked_job.company_id == jobs["https://job-boards.greenhouse.io/acme/jobs/101"].company_id
    )
    # Both jobs are recommended, so both new companies are looked up (and fail, leaving names);
    # run 2's recommended job 106 then retries the still name-only Acme Corp.
    assert looked_up == ["Acme Corp", "Globex", "enrich Acme Corp"]


def test_ignored_jobs_older_than_seven_days_are_deleted_even_when_discovery_is_paused(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
) -> None:
    # No desired titles, so discovery is skipped; the cleanup still runs.
    _save_preferences(sessions, country="US")
    sources.google = RuntimeError("must not be called while preferences are incomplete")
    with sessions() as session, session.begin():
        company = Company(name="Initech")
        session.add(company)
        session.flush()
        for slug, inbox, age in [
            ("old-ignored", "ignored", timedelta(days=7, minutes=1)),
            ("new-ignored", "ignored", timedelta(days=6, hours=23)),
            ("old-recommended", "recommended", timedelta(days=30)),
            ("old-applied", "applied", timedelta(days=30)),
        ]:
            session.add(
                Job(
                    company_id=company.id,
                    title=slug,
                    url=f"https://example.com/{slug}",
                    inbox_type=inbox,
                    discovered_when=NOW - age,
                )
            )

    summary = _run(test_settings, sessions, fake_http)

    with sessions() as session:
        titles = set(session.scalars(select(Job.title)))
    assert titles == {"new-ignored", "old-recommended", "old-applied"}
    assert summary.status == fetcher.STATUS_PREFERENCES_INCOMPLETE
    assert summary.ignored_jobs_deleted == 1


def test_google_postings_get_the_free_filters_and_skip_jobs_an_ats_board_already_gave_us(
    test_settings: Settings,
    sessions: sessionmaker[Session],
    sources: FakeSources,
    fake_http: FakeHttp,
) -> None:
    _save_preferences(
        sessions, desired_titles=["Backend Engineer"], country="US", seniority=["senior"]
    )
    ats_job = _posting(
        "Senior Backend Engineer",
        "acme",
        "https://job-boards.greenhouse.io/acme/jobs/5",
        "greenhouse",
    )
    sources.sweep = SweepResult(
        boards_scanned=1,
        matched_boards=[
            BoardScan(board=BoardRef("greenhouse", "acme"), fetched=1, matches=[ats_job])
        ],
    )

    def google(title: str, url: str, location: str = "New York, NY") -> Posting:
        posting = _posting(title, "Acme Corp, Inc.", url, "google_jobs:LinkedIn")
        posting.location = location
        return posting

    same_job_on_linkedin = google("Senior Backend Engineer", "https://www.linkedin.com/jobs/view/1")
    new_job = google("Senior Backend Engineer", "https://www.linkedin.com/jobs/view/2")
    new_job.company = "Initech"
    wrong_country = google(
        "Senior Backend Engineer", "https://www.linkedin.com/jobs/view/3", "Berlin, Germany"
    )
    wrong_level = google("Backend Engineering Intern", "https://www.linkedin.com/jobs/view/4")
    wrong_title = google("Senior Frontend Engineer", "https://www.linkedin.com/jobs/view/5")
    sources.google = GoogleJobsResult(
        postings=[same_job_on_linkedin, new_job, wrong_country, wrong_level, wrong_title],
        boards=[],
        searches=1,
    )
    sources.scores = {"Senior Backend Engineer": 80}

    summary = _run(test_settings, sessions, fake_http)

    with sessions() as session:
        urls = set(session.scalars(select(Job.url)))
    assert urls == {ats_job.url, new_job.url}
    # Two evaluations: the ATS job and the one genuinely new Google job.
    assert len(sources.evaluated) == 2
    google_stats = summary.sources["google_jobs"]
    assert (google_stats.fetched, google_stats.matched) == (5, 2)
    assert (google_stats.new, google_stats.duplicate) == (1, 1)


def test_company_names_and_titles_are_compared_loosely_for_cross_source_dedup() -> None:
    assert fetcher.company_key("Acme Corp, Inc.") == fetcher.company_key("acme") == "acme"
    assert fetcher.company_key("The Home Depot") == "homedepot"
    assert fetcher.company_key("Inc") == "inc"
    assert fetcher.title_key("Senior  Backend-Engineer (C++)") == "senior backend engineer c++"
