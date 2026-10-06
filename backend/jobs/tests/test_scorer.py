"""The scorer against a disposable Postgres, with the evaluator and company lookup mocked.

The database tests need CAREER_NETWORKING_TEST_DATABASE_URL (see test_migrations.py).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src import scorer
from src.agents.evaluator import JobEvaluation, JobForEvaluation
from src.config import Settings
from src.llm import LlmError
from src.models import Company, Job

NOW = datetime.now(UTC)


class FakeAgents:
    """Scores by title (an int, or an exception to raise) and records company fill-ins."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.scores: dict[str, int | Exception] = {}
        self.evaluated: list[JobForEvaluation] = []
        self.enriched: list[str] = []
        monkeypatch.setattr(scorer, "evaluate_job", self._evaluate)
        monkeypatch.setattr(scorer, "enrich_company", self._enrich)

    def _evaluate(self, _session: Session, job: JobForEvaluation, _prefs: Any) -> JobEvaluation:
        self.evaluated.append(job)
        score = self.scores[job.title]
        if isinstance(score, Exception):
            raise score
        return JobEvaluation(
            overall_score=score,
            experience_score=score,
            skill_score=score,
            industry_exp_score=score,
            location_country="US",
        )

    def _enrich(self, _session: Session, company: Company, _description: str | None = None) -> None:
        self.enriched.append(company.name)
        company.description = f"{company.name} makes things."


@pytest.fixture
def agents(monkeypatch: pytest.MonkeyPatch) -> FakeAgents:
    return FakeAgents(monkeypatch)


def _add_job(
    sessions: sessionmaker[Session],
    title: str,
    *,
    company: str = "Acme Corp",
    discovered: datetime = NOW,
    **values: Any,
) -> int:
    with sessions() as session, session.begin():
        owner = session.scalars(select(Company).where(Company.name == company)).first()
        if owner is None:
            owner = Company(name=company)
            session.add(owner)
            session.flush()
        job = Job(
            company_id=owner.id,
            title=title,
            url=f"https://jobs.example.com/{title.replace(' ', '-').lower()}",
            description=f"{title} at {company}.",
            posting_location="Austin, TX",
            discovered_when=discovered,
            **values,
        )
        session.add(job)
        session.flush()
        return job.id


def _job(sessions: sessionmaker[Session], job_id: int) -> Job:
    with sessions() as session:
        job = session.get(Job, job_id)
        assert job is not None
        return job


def test_scores_pending_jobs_posted_in_the_last_24_hours_and_deletes_none(
    test_settings: Settings, sessions: sessionmaker[Session], agents: FakeAgents
) -> None:
    good = _add_job(sessions, "Backend Engineer")
    weak = _add_job(sessions, "Data Analyst", company="Globex")
    # Found just now but posted 23 hours ago: still in the window, so scored.
    recent = _add_job(sessions, "Platform Engineer", posted_at=NOW - timedelta(hours=23))
    # Posted 25 hours ago, or (with no posting date) found 25 hours ago: left waiting.
    old_post = _add_job(sessions, "Security Engineer", posted_at=NOW - timedelta(hours=25))
    old_find = _add_job(sessions, "Mobile Engineer", discovered=NOW - timedelta(hours=25))
    waiting = _add_job(
        sessions, "Site Reliability Engineer", next_scoring_at=NOW + timedelta(minutes=5)
    )
    applied = _add_job(sessions, "Staff Engineer", inbox_type="applied")
    agents.scores = {"Backend Engineer": 85, "Data Analyst": 30, "Platform Engineer": 40}

    summary = scorer.score_batch(test_settings, sessions, now=NOW)

    assert summary.outcomes == {"recommended": 1, "ignored": 2}
    recommended, ignored = _job(sessions, good), _job(sessions, weak)
    assert (recommended.inbox_type, recommended.overall_score) == ("recommended", 85)
    assert (ignored.inbox_type, ignored.overall_score) == ("ignored", 30)
    # Moving out of pending stamps when the job entered its inbox (the scored time).
    assert recommended.inbox_entered_at >= NOW - timedelta(seconds=5)
    # The evaluator gets the posting's own location; only the recommended job's company is
    # filled in.
    assert {job.location for job in agents.evaluated} == {"Austin, TX"}
    assert agents.enriched == ["Acme Corp"]
    assert _job(sessions, recent).overall_score == 40
    # Outside the window, waiting for a retry, or not pending: untouched, and nothing is deleted.
    for job_id in (old_post, old_find, waiting):
        assert _job(sessions, job_id).inbox_type == "pending"
    assert _job(sessions, applied).inbox_type == "applied"


def test_a_failed_evaluation_is_retried_then_saved_unscored_in_ignored(
    test_settings: Settings, sessions: sessionmaker[Session], agents: FakeAgents
) -> None:
    job_id = _add_job(sessions, "Backend Engineer")
    agents.scores = {"Backend Engineer": LlmError("model unavailable")}

    first = scorer.score_batch(test_settings, sessions, now=NOW)
    after_first = _job(sessions, job_id)
    # Not due again until the retry delay has passed.
    too_soon = scorer.score_batch(test_settings, sessions, now=NOW + timedelta(minutes=1))
    second = scorer.score_batch(test_settings, sessions, now=NOW + timedelta(minutes=6))
    third = scorer.score_batch(test_settings, sessions, now=NOW + timedelta(minutes=40))

    assert first.outcomes == {"retry": 1}
    assert after_first.inbox_type == "pending" and after_first.scoring_attempts == 1
    assert after_first.next_scoring_at == NOW + scorer.RETRY_DELAYS[0]
    assert too_soon.outcomes == {}
    assert second.outcomes == {"retry": 1}
    assert third.outcomes == {"failed": 1}
    failed = _job(sessions, job_id)
    assert (failed.inbox_type, failed.scoring_attempts) == ("ignored", scorer.MAX_SCORING_ATTEMPTS)
    assert failed.overall_score is None
    assert failed.evaluation_error == "LlmError: model unavailable"
    assert len(agents.evaluated) == scorer.MAX_SCORING_ATTEMPTS


def test_a_job_locked_by_another_scorer_is_skipped(
    test_settings: Settings, sessions: sessionmaker[Session], agents: FakeAgents
) -> None:
    job_id = _add_job(sessions, "Backend Engineer")
    agents.scores = {"Backend Engineer": 85}

    with sessions() as other, other.begin():
        other.scalars(select(Job).where(Job.id == job_id).with_for_update()).one()
        outcome = scorer.score_job(job_id, test_settings, sessions, NOW)

    assert outcome == scorer.OUTCOME_SKIPPED
    assert agents.evaluated == []
    assert _job(sessions, job_id).inbox_type == "pending"
