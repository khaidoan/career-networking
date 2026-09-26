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
