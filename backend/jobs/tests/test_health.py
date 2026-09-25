from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.db.session import get_db


def _override_db(app: FastAPI, session: MagicMock) -> None:
    def fake_db():
        yield session

    app.dependency_overrides[get_db] = fake_db


def test_health_reports_ok_when_database_answers(app: FastAPI, client: TestClient) -> None:
    _override_db(app, MagicMock())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_degraded_when_database_is_unreachable(
    app: FastAPI, client: TestClient
) -> None:
    session = MagicMock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("connection refused"))
    _override_db(app, session)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unreachable"}
