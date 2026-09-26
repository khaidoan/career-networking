"""Migration tests against a real PostgreSQL named by CAREER_NETWORKING_TEST_DATABASE_URL.

The database must be disposable: the tests migrate it up to head and back down to base.
"""

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from src.config import get_settings
from tests.conftest import ALEMBIC_INI

APP_TABLES = {"companies", "preferences", "jobs", "company_networking", "prompts", "ats_boards"}
EXPECTED_REVISION_ORDER = [
    "create_companies_table",
    "create_preferences_table",
    "create_jobs_table",
    "create_company_networking_table",
    "create_prompts_table",
    "drop_preferences_skills",
    "preferences_seniority_array",
    "create_ats_boards_table",
    "add_jobs_evaluation_error",
    "add_companies_name_trigram_index",
    "add_companies_contacts_searched_at",
    "normalize_company_networking_linkedin_urls",
    "add_company_networking_linkedin_url_unique_index",
]


def _table_names() -> set[str]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _execute(sql: str) -> list[tuple]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        with engine.begin() as connection:
            result = connection.execute(text(sql))
            return [tuple(row) for row in result] if result.returns_rows else []
    finally:
        engine.dispose()


def _preferences_columns() -> dict[str, str]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        columns = inspect(engine).get_columns("preferences")
        return {column["name"]: str(column["type"]) for column in columns}
    finally:
        engine.dispose()


def test_upgrade_creates_all_tables_and_downgrade_removes_them(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    try:
        assert _table_names() >= APP_TABLES
    finally:
        command.downgrade(alembic_config, "base")

    assert _table_names() <= {"alembic_version"}


def test_revisions_form_a_single_chain_in_the_required_order() -> None:
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))

    assert len(script.get_heads()) == 1
    revisions = list(reversed(list(script.walk_revisions("base", "heads"))))
    assert [revision.doc.replace(" ", "_") for revision in revisions] == EXPECTED_REVISION_ORDER


def test_jobs_evaluation_error_column_is_added_and_removed(alembic_config: Config) -> None:
    def job_columns() -> set[str]:
        engine = create_engine(get_settings().sqlalchemy_database_url)
        try:
            return {column["name"] for column in inspect(engine).get_columns("jobs")}
        finally:
            engine.dispose()

    command.upgrade(alembic_config, "head")
    try:
        assert "evaluation_error" in job_columns()
        command.downgrade(alembic_config, "0008")
        assert "evaluation_error" not in job_columns()
    finally:
        command.downgrade(alembic_config, "base")


def test_ats_boards_has_unique_board_and_allowed_provider_constraints(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    try:
        engine = create_engine(get_settings().sqlalchemy_database_url)
        try:
            inspector = inspect(engine)
            unique_columns = [
                constraint["column_names"]
                for constraint in inspector.get_unique_constraints("ats_boards")
            ]
            checks = " ".join(
                constraint["sqltext"]
                for constraint in inspector.get_check_constraints("ats_boards")
            )
            indexed = [index["column_names"] for index in inspector.get_indexes("ats_boards")]
        finally:
            engine.dispose()

        assert ["provider", "board_key"] in unique_columns
        for provider in ("greenhouse", "lever", "ashby", "workday", "icims", "bamboohr"):
            assert provider in checks
        assert "google_jobs" in checks
        assert ["is_active"] in indexed

        insert = (
            "INSERT INTO ats_boards (provider, board_key, discovered_via) "
            "VALUES ('{provider}', 'acme', 'ats_sweep')"
        )
        _execute(insert.format(provider="greenhouse"))
        with pytest.raises(IntegrityError):
            _execute(insert.format(provider="greenhouse"))
        with pytest.raises(IntegrityError):
            _execute(insert.format(provider="smartrecruiters"))
    finally:
        command.downgrade(alembic_config, "base")


def test_seniority_is_wrapped_into_an_array_and_downgrade_keeps_the_first_level(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "0006")
    try:
        _execute("INSERT INTO preferences (id, seniority) VALUES (1, 'senior')")

        command.upgrade(alembic_config, "0007")
        assert _execute("SELECT seniority FROM preferences") == [(["senior"],)]

        _execute("UPDATE preferences SET seniority = ARRAY['mid', 'senior']")
        command.downgrade(alembic_config, "0006")
        assert _execute("SELECT seniority FROM preferences") == [("mid",)]
    finally:
        command.downgrade(alembic_config, "base")


def test_downgrade_from_head_to_phase_one_schema_restores_skills(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    try:
        columns = _preferences_columns()
        assert "skills" not in columns
        assert columns["seniority"].startswith("TEXT[]") or "ARRAY" in columns["seniority"]

        command.downgrade(alembic_config, "0005")

        columns = _preferences_columns()
        assert "skills" in columns
        assert columns["seniority"] == "TEXT"
        assert "ats_boards" not in _table_names()
    finally:
        command.downgrade(alembic_config, "base")


def _company_columns() -> dict[str, dict]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        columns = inspect(engine).get_columns("companies")
        return {column["name"]: column for column in columns}
    finally:
        engine.dispose()


def _insert_contact(
    company_id: int, url: str | None, *, sent: bool = False, sent_at: str | None = None
) -> int:
    rows = _execute_params(
        "INSERT INTO company_networking "
        "(company_id, linkedin_url, connection_request_sent, connection_request_sent_at) "
        "VALUES (:company_id, :url, :sent, CAST(:sent_at AS timestamptz)) RETURNING id",
        {"company_id": company_id, "url": url, "sent": sent, "sent_at": sent_at},
    )
    return rows[0][0]


def _execute_params(sql: str, params: dict) -> list[tuple]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        with engine.begin() as connection:
            result = connection.execute(text(sql), params)
            return [tuple(row) for row in result] if result.returns_rows else []
    finally:
        engine.dispose()


def _contacts() -> list[tuple]:
    return _execute(
        "SELECT id, company_id, linkedin_url FROM company_networking ORDER BY company_id, id"
    )


def test_contacts_searched_at_column_is_added_and_removed(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    try:
        column = _company_columns()["contacts_searched_at"]
        assert column["nullable"] is True
        assert "TIMESTAMP" in str(column["type"]) and column["type"].timezone is True

        command.downgrade(alembic_config, "0010")
        assert "contacts_searched_at" not in _company_columns()
    finally:
        command.downgrade(alembic_config, "base")


def test_linkedin_url_migration_normalizes_variants_and_keeps_the_earliest_sent_row(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "0011")
    try:
        _execute("INSERT INTO companies (id, name) VALUES (1, 'Acme'), (2, 'Globex')")
        first = _insert_contact(1, "https://www.linkedin.com/in/Ada-L/")
        later_sent = _insert_contact(
            1, "http://uk.linkedin.com/in/ada-l?trk=x", sent=True, sent_at="2026-09-02"
        )
        earliest_sent = _insert_contact(
            1, "https://LinkedIn.com/in/ada-l#about", sent=True, sent_at="2026-09-01"
        )
        _insert_contact(1, "https://de.linkedin.com/in/ada-l")
        other_company = _insert_contact(2, "https://www.linkedin.com/in/ada-l")
        # No sent rows: the lowest id is kept.
        grace_low = _insert_contact(1, "https://www.linkedin.com/in/grace/")
        _insert_contact(1, "https://fr.linkedin.com/in/grace?x=1")
        # Not a profile path: left unchanged, but exact duplicates are still merged.
        company_page = _insert_contact(1, "https://www.linkedin.com/company/Acme")
        _insert_contact(1, "https://www.linkedin.com/company/Acme")
        no_url_a = _insert_contact(1, None)
        no_url_b = _insert_contact(1, None)

        command.upgrade(alembic_config, "0012")

        # The kept row is neither the lowest id nor the first sent row inserted.
        assert first < later_sent < earliest_sent
        assert _contacts() == [
            (earliest_sent, 1, "https://www.linkedin.com/in/ada-l"),
            (grace_low, 1, "https://www.linkedin.com/in/grace"),
            (company_page, 1, "https://www.linkedin.com/company/Acme"),
            (no_url_a, 1, None),
            (no_url_b, 1, None),
            (other_company, 2, "https://www.linkedin.com/in/ada-l"),
        ]
    finally:
        command.downgrade(alembic_config, "base")


def test_linkedin_url_unique_index_rejects_duplicates_but_allows_null_urls(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    try:
        _execute("INSERT INTO companies (id, name) VALUES (1, 'Acme')")
        _insert_contact(1, "https://www.linkedin.com/in/ada")
        _insert_contact(1, None)
        _insert_contact(1, None)
        with pytest.raises(IntegrityError):
            _insert_contact(1, "https://www.linkedin.com/in/ada")
    finally:
        command.downgrade(alembic_config, "base")


def test_phase_four_migrations_round_trip(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    try:
        _execute("INSERT INTO companies (id, name) VALUES (1, 'Acme')")
        _insert_contact(1, "https://www.linkedin.com/in/ada")

        command.downgrade(alembic_config, "0010")
        command.upgrade(alembic_config, "head")

        assert _contacts()[0][2] == "https://www.linkedin.com/in/ada"
        assert "contacts_searched_at" in _company_columns()
    finally:
        command.downgrade(alembic_config, "base")
