from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import Settings, get_settings
from src.main import create_app

TEST_USERNAME = "tester"
TEST_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Explicit settings that never touch the real environment or database."""
    return Settings(
        database_url="postgresql+psycopg://user:pass@db.invalid:5432/test",
        jwt_secret="test-secret-that-is-long-enough-for-hs256-signing",
        jwt_expires_minutes=60,
        login_max_attempts=3,
        login_window_minutes=15,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        firstname="Ada",
        lastname="Lovelace",
        email="ada@example.com",
        resume_folder=tmp_path / "resume",
        job_data=tmp_path / "jobs",
        log_folder=tmp_path / "logs",
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    application = create_app(test_settings)
    application.dependency_overrides[get_settings] = lambda: test_settings
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
