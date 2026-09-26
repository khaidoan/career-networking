"""Phase 3 service layer: trigram migration, name search, keyset cursors and evaluation helpers.

The migration and search tests need CAREER_NETWORKING_TEST_DATABASE_URL (see test_migrations.py).
"""

from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from src.agents.evaluator import JobEvaluation
from src.config import get_settings
from src.llm import LlmOutputError
from src.models import Company, Job
from src.services.evaluation import (
    apply_evaluation_failure,
    apply_evaluation_success,
    can_move_inbox,
    job_for_evaluation,
)
from src.services.paging import (
    InvalidCursorError,
    SortKey,
    as_bool,
    as_datetime,
    as_int,
    decode_cursor,
    encode_cursor,
)
from src.services.search import escape_like, name_matches

THRESHOLD = 70
JOB_SORT = (
    SortKey(Job.liked, descending=True, decode=as_bool),
    SortKey(Job.discovered_when, descending=True, decode=as_datetime),
    SortKey(Job.id, descending=True, decode=as_int),
)


def _trigram_state() -> tuple[bool, bool]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            extension = connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")
            )
            index = connection.scalar(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_companies_name_trgm'")
            )
    finally:
        engine.dispose()
    return bool(extension), bool(index and "gin_trgm_ops" in index)


def test_migration_0010_adds_and_removes_the_trigram_index(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    try:
        assert _trigram_state() == (True, True)
        command.downgrade(alembic_config, "0009")
        assert _trigram_state() == (False, False)
        command.upgrade(alembic_config, "0010")
        assert _trigram_state() == (True, True)
    finally:
        command.downgrade(alembic_config, "base")


def test_name_search_matches_substrings_and_typos_case_insensitively(
    migrated_sessions: sessionmaker[Session],
) -> None:
    with migrated_sessions() as session, session.begin():
        for name in ("Stripe", "Acme Robotics", "Globex", "100% Juice_Co"):
            session.add(Company(name=name))

    def search(query: str) -> list[str]:
        with migrated_sessions() as session:
            statement = select(Company.name).where(name_matches(Company.name, query))
            return sorted(session.scalars(statement))

    assert search("ROBOT") == ["Acme Robotics"]
    assert search("strpe") == ["Stripe"]
    assert search("globx") == ["Globex"]
    assert search("0% J") == ["100% Juice_Co"]
    # `%` and `_` are literal characters, not wildcards.
    assert search("%") == ["100% Juice_Co"]
    assert search("e_C") == ["100% Juice_Co"]
    assert search("zzzz") == []
    assert escape_like("50%_\\") == "50\\%\\_\\\\"


def test_cursor_round_trips_and_malformed_cursors_are_rejected() -> None:
    discovered = datetime(2026, 9, 25, 12, 30, 15, 123456, tzinfo=UTC)
    cursor = encode_cursor([True, discovered, 42])

    assert "=" not in cursor and "+" not in cursor and "/" not in cursor
    assert decode_cursor(cursor, JOB_SORT) == [True, discovered, 42]

    for bad in (
        "not-a-cursor!",
        encode_cursor([True, discovered]),
        encode_cursor(["yes", discovered, 42]),
        encode_cursor([True, "yesterday", 42]),
        encode_cursor([True, "2026-09-25T12:00:00", 42]),
        encode_cursor([True, discovered, "42"]),
        "x" * 2000,
    ):
        with pytest.raises(InvalidCursorError):
            decode_cursor(bad, JOB_SORT)


def _evaluation(score: int) -> JobEvaluation:
    return JobEvaluation(
        overall_score=score,
        experience_score=score - 1,
        skill_score=score - 2,
        industry_exp_score=score - 3,
        work_arrangement="remote",
        seniority_level="senior",
        visa_sponsorship=True,
        location_country="US",
    )


def _job(inbox: str) -> Job:
    return Job(
        title="Backend Engineer",
        url="https://example.com/job",
        inbox_type=inbox,
        evaluation_error="LlmError: earlier failure",
    )


@pytest.mark.parametrize(
    ("inbox", "score", "expected_inbox"),
    [
        ("recommended", 40, "ignored"),
        ("ignored", 90, "recommended"),
        ("applied", 20, "applied"),
        ("need_attention", 95, "need_attention"),
    ],
)
def test_evaluation_success_copies_fields_and_moves_only_recommended_or_ignored_jobs(
    inbox: str, score: int, expected_inbox: str
) -> None:
    job = _job(inbox)

    apply_evaluation_success(
        job, _evaluation(score), THRESHOLD, allow_inbox_move=can_move_inbox(job)
    )

    assert job.inbox_type == expected_inbox
    assert (job.overall_score, job.experience_score, job.skill_score, job.industry_exp_score) == (
        score,
        score - 1,
        score - 2,
        score - 3,
    )
    assert (job.work_arrangement, job.seniority_level, job.visa_sponsorship) == (
        "remote",
        "senior",
        True,
    )
    assert job.location_country == "US"
    assert job.evaluation_error is None


def test_evaluation_failure_clears_scores_and_the_stored_job_builds_evaluator_input() -> None:
    job = _job("recommended")
    apply_evaluation_success(job, _evaluation(88), THRESHOLD, allow_inbox_move=True)

    apply_evaluation_failure(job, LlmOutputError("invalid JSON"), allow_inbox_move=False)

    assert job.inbox_type == "recommended"
    assert job.evaluation_error == "LlmOutputError: invalid JSON"
    assert job.overall_score is None and job.industry_exp_score is None

    job.company = Company(name="Acme")
    job.location_city, job.location_state, job.location_country = "Austin", None, "US"
    job.description = "Build APIs."
    subject = job_for_evaluation(job)
    assert (subject.title, subject.company, subject.location, subject.description) == (
        "Backend Engineer",
        "Acme",
        "Austin, US",
        "Build APIs.",
    )
