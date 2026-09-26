import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import Settings, get_settings
from src.main import create_app
from src.sources.providers.base import HttpClient

TEST_USERNAME = "tester"
TEST_PASSWORD = "correct-horse-battery-staple"
TEST_DATABASE_URL = os.environ.get("CAREER_NETWORKING_TEST_DATABASE_URL")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


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
        llm_model="openai/test-model",
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


@pytest.fixture
def alembic_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Config]:
    """Alembic config for the disposable Postgres in CAREER_NETWORKING_TEST_DATABASE_URL."""
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
        "LLM_MODEL": "openai/test-model",
    }
    for name, value in test_env.items():
        monkeypatch.setenv(f"CAREER_NETWORKING_{name}", value)
    get_settings.cache_clear()
    yield Config(str(ALEMBIC_INI))
    get_settings.cache_clear()


@pytest.fixture
def migrated_sessions(alembic_config: Config) -> Iterator[sessionmaker[Session]]:
    """Sessions on the disposable Postgres migrated to head; downgraded to base afterwards."""
    command.upgrade(alembic_config, "head")
    engine = create_engine(get_settings().sqlalchemy_database_url)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        command.downgrade(alembic_config, "base")


class FakeLlm:
    """Stands in for ``litellm.completion``: returns queued replies and records every request."""

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.requests: list[dict[str, Any]] = []

    def __call__(self, **request: Any) -> SimpleNamespace:
        self.requests.append(request)
        content = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    def sent_text(self) -> str:
        """Every message content sent to the model, joined for privacy assertions."""
        return "\n".join(
            message["content"] for request in self.requests for message in request["messages"]
        )


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch, test_settings: Settings) -> FakeLlm:
    fake = FakeLlm()
    monkeypatch.setattr("src.llm._litellm_completion", fake)
    monkeypatch.setattr("src.llm.get_settings", lambda: test_settings)
    return fake


class FakeHttp:
    """Routes ``httpx`` requests to canned responses by URL (query ignored) and records them.

    Adding the same URL again queues another response; the last one repeats. Unknown URLs answer
    404, so no test can reach the real network.
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], list[httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def add(
        self,
        url: str,
        *,
        json: Any = None,
        text: str | None = None,
        status: int = 200,
        method: str = "GET",
    ) -> None:
        if text is not None:
            response = httpx.Response(status, text=text)
        else:
            response = httpx.Response(status, json=json)
        self.routes.setdefault((method, url), []).append(response)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, str(request.url.copy_with(query=None)))
        queued = self.routes.get(key)
        if not queued:
            return httpx.Response(404, json={"error": "not found"})
        response = queued.pop(0) if len(queued) > 1 else queued[0]
        return httpx.Response(
            response.status_code, content=response.content, headers=response.headers
        )

    def client(self) -> HttpClient:
        return HttpClient(httpx.MockTransport(self.handler), retry_backoff_seconds=0)

    def urls(self) -> list[str]:
        return [str(request.url) for request in self.requests]


@pytest.fixture
def fake_http() -> FakeHttp:
    return FakeHttp()


FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(relative_path: str) -> str:
    return (FIXTURES / relative_path).read_text(encoding="utf-8")


def fixture_json(relative_path: str) -> Any:
    return json.loads(fixture_text(relative_path))
