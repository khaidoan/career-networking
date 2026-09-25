"""Migration tests against a real PostgreSQL named by CAREER_NETWORKING_TEST_DATABASE_URL.

The database must be disposable: the tests migrate it up to head and back down to base.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from src.config import get_settings

TEST_DATABASE_URL = os.environ.get("CAREER_NETWORKING_TEST_DATABASE_URL")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
APP_TABLES = {"companies", "preferences", "jobs", "company_networking", "prompts"}
EXPECTED_REVISION_ORDER = [
    "create_companies_table",
    "create_preferences_table",
    "create_jobs_table",
    "create_company_networking_table",
    "create_prompts_table",
]


@pytest.fixture
def alembic_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Config]:
    if not TEST_DATABASE_URL:
        pytest.skip("CAREER_NETWORKING_TEST_DATABASE_URL is not set; needs a disposable Postgres")

    # env.py reads the URL through the settings module, so provide a complete test environment.
    test_env = {
        "DATABASE_URL": TEST_DATABASE_URL,
        "JWT_SECRET": "migration-test-secret-that-is-long-enough",
        "USERNAME": "tester",
        "PASSWORD": "tester-password",
        "FIRSTNAME": "Ada",
        "LASTNAME": "Lovelace",
        "EMAIL": "ada@example.com",
        "RESUME_FOLDER": str(tmp_path / "resume"),
        "JOB_DATA": str(tmp_path / "jobs"),
        "LOG_FOLDER": str(tmp_path / "logs"),
    }
    for name, value in test_env.items():
        monkeypatch.setenv(f"CAREER_NETWORKING_{name}", value)
    get_settings.cache_clear()
    yield Config(str(ALEMBIC_INI))
    get_settings.cache_clear()


def _table_names() -> set[str]:
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        return set(inspect(engine).get_table_names())
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
