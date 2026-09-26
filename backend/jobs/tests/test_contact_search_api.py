"""Find-contacts endpoint and ``contact_search`` status, with SerpApi and LiteLLM mocked.

These need CAREER_NETWORKING_TEST_DATABASE_URL (see test_migrations.py).
"""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.api.v1.common import get_http_client
from src.config import Settings, get_settings
from src.db.session import get_db
from src.models import Company, CompanyNetworking, Job
from src.sources.serpapi import SERPAPI_SEARCH_URL
from tests.conftest import TEST_PASSWORD, TEST_USERNAME, FakeHttp, FakeLlm

API_KEY = "serpapi-secret-key"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
SENT_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
NOT_ELIGIBLE = "Contact search is available for companies with a recommended or applied job."
NO_KEY = "Contact search needs a SerpApi key. See the README."
RESULTS = {
    "organic_results": [
        {
            "link": "https://uk.linkedin.com/in/Ada-L/?trk=x",
            "title": "Ada Lovelace - Principal Engineer - Acme | LinkedIn",
            "snippet": "Engineer at Acme",
        },
        {
            "link": "https://www.linkedin.com/in/grace",
            "title": "Grace Hopper - Engineering Manager - Acme",
            "snippet": "",
        },
    ]
}
PICKS = json.dumps(
    {"contacts": [{"index": 0, "category": "peer"}, {"index": 1, "category": "manager"}]}
)


@pytest.fixture
def key_settings(test_settings: Settings) -> Settings:
    return test_settings.model_copy(update={"serpapi_api_key": SecretStr(API_KEY)})


def _sign_in(
    app: FastAPI,
    client: TestClient,
    sessions: sessionmaker[Session],
    settings: Settings,
    fake_http: FakeHttp,
) -> TestClient:
    def override_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_http_client] = fake_http.client
    client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    return client


@pytest.fixture
def api(
    app: FastAPI,
    client: TestClient,
    migrated_sessions: sessionmaker[Session],
    key_settings: Settings,
    fake_http: FakeHttp,
) -> TestClient:
    """Signed in, with a SerpApi key configured."""
    return _sign_in(app, client, migrated_sessions, key_settings, fake_http)


@pytest.fixture
def api_without_key(
    app: FastAPI,
    client: TestClient,
    migrated_sessions: sessionmaker[Session],
    test_settings: Settings,
    fake_http: FakeHttp,
) -> TestClient:
    return _sign_in(app, client, migrated_sessions, test_settings, fake_http)


def _seed(sessions: sessionmaker[Session], **inboxes: str) -> dict[str, int]:
    """Company Acme with one job per ``title=inbox``, a sent contact, and company Globex."""
    with sessions() as session, session.begin():
        acme, globex = Company(name="Acme"), Company(name="Globex")
        session.add_all([acme, globex])
        session.flush()
        ids = {"acme": acme.id, "globex": globex.id}
        for offset, (title, inbox) in enumerate(inboxes.items()):
            job = Job(
                company_id=acme.id,
                title=title,
                url=f"https://jobs.example/{title}",
                inbox_type=inbox,
                description="Python services.",
                discovered_when=NOW - timedelta(days=offset),
            )
            session.add(job)
            session.flush()
            ids[title] = job.id
        globex_job = Job(company_id=globex.id, title="Other", url="https://jobs.example/other")
        sent = CompanyNetworking(
            company_id=acme.id,
            first_name="Ada",
            last_name="Lovelace",
            title="Engineer",
            linkedin_url="https://www.linkedin.com/in/ada-l",
            connection_request_sent=True,
            connection_request_sent_at=SENT_AT,
        )
        session.add_all([globex_job, sent])
        session.flush()
        ids["globex_job"], ids["sent"] = globex_job.id, sent.id
        return ids


def _searched_at(sessions: sessionmaker[Session], company_id: int) -> Any:
    with sessions() as session:
        return session.get(Company, company_id).contacts_searched_at


def test_success_stores_contacts_keeps_sent_history_and_returns_counts_and_status(
    api: TestClient,
    migrated_sessions: sessionmaker[Session],
    fake_http: FakeHttp,
    fake_llm: FakeLlm,
) -> None:
    ids = _seed(migrated_sessions, Newest="recommended", Older="applied")
    fake_http.add(SERPAPI_SEARCH_URL, json=RESULTS)
    fake_llm.replies = [PICKS]

    response = api.post(f"/api/v1/companies/{ids['acme']}/contacts/search")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert (body["found"], body["created"], body["updated"]) == (2, 1, 1)
    assert fake_http.requests[0].url.params["q"] == 'site:linkedin.com/in "Acme" "Newest"'
    ada, grace = body["contacts"]
    assert ada["id"] == ids["sent"] and ada["title"] == "Principal Engineer"
    assert ada["connection_request_sent"] is True
    assert datetime.fromisoformat(ada["connection_request_sent_at"]) == SENT_AT
    assert grace["name"] == "Grace Hopper"
    assert grace["linkedin_url"] == "https://www.linkedin.com/in/grace"
    assert grace["connection_request_sent"] is False
    status = body["contact_search"]
    assert status["available"] is True and status["unavailable_reason"] is None
    assert status["last_searched_at"] is not None
    assert _searched_at(migrated_sessions, ids["acme"]) is not None


def test_job_id_supplies_the_role_even_for_an_ignored_job_at_an_eligible_company(
    api: TestClient,
    migrated_sessions: sessionmaker[Session],
    fake_http: FakeHttp,
    fake_llm: FakeLlm,
) -> None:
    ids = _seed(migrated_sessions, Liked="recommended", Skipped="ignored")
    fake_http.add(SERPAPI_SEARCH_URL, json={"error": "Google hasn't returned any results."})

    response = api.post(
        f"/api/v1/companies/{ids['acme']}/contacts/search", params={"job_id": ids["Skipped"]}
    )

    assert response.status_code == 200, response.json()
    assert fake_http.requests[0].url.params["q"] == 'site:linkedin.com/in "Acme" "Skipped"'
    assert (response.json()["found"], response.json()["created"]) == (0, 0)
    assert fake_llm.requests == []
    assert response.json()["contact_search"]["last_searched_at"] is not None


def test_not_eligible_unknown_ids_and_foreign_job_errors_come_in_order(
    api: TestClient, migrated_sessions: sessionmaker[Session], fake_http: FakeHttp
) -> None:
    ids = _seed(migrated_sessions, Skipped="ignored")
    url = f"/api/v1/companies/{ids['acme']}/contacts/search"

    not_eligible = api.post(url)
    assert not_eligible.status_code == 409
    assert not_eligible.json() == {"detail": NOT_ELIGIBLE}
    assert api.post(url, params={"job_id": ids["Skipped"]}).status_code == 409

    missing_company = api.post("/api/v1/companies/999999/contacts/search")
    assert missing_company.status_code == 404
    assert missing_company.json() == {"detail": "Company not found"}
    missing_job = api.post(url, params={"job_id": 999999})
    assert missing_job.status_code == 404 and missing_job.json() == {"detail": "Job not found"}

    foreign = api.post(url, params={"job_id": ids["globex_job"]})
    assert foreign.status_code == 422
    assert foreign.json()["detail"][0]["loc"] == ["query", "job_id"]
    assert fake_http.requests == []


def test_without_an_api_key_the_endpoint_is_503_before_eligibility_and_status_says_why(
    api_without_key: TestClient, migrated_sessions: sessionmaker[Session], fake_http: FakeHttp
) -> None:
    ids = _seed(migrated_sessions, Skipped="ignored")

    response = api_without_key.post(f"/api/v1/companies/{ids['acme']}/contacts/search")

    assert response.status_code == 503
    assert response.json() == {"detail": NO_KEY}
    assert fake_http.requests == []
    job_status = api_without_key.get(f"/api/v1/jobs/{ids['Skipped']}").json()["contact_search"]
    assert job_status == {
        "available": False,
        "unavailable_reason": "no_api_key",
        "last_searched_at": None,
    }


@pytest.mark.parametrize("failure", ["serpapi", "llm"])
def test_search_or_llm_failure_is_502_and_writes_nothing(
    failure: str,
    api: TestClient,
    migrated_sessions: sessionmaker[Session],
    fake_http: FakeHttp,
    fake_llm: FakeLlm,
) -> None:
    ids = _seed(migrated_sessions, Liked="recommended")
    if failure == "serpapi":
        fake_http.add(SERPAPI_SEARCH_URL, json={"error": "Your account has run out of searches."})
    else:
        fake_http.add(SERPAPI_SEARCH_URL, json=RESULTS)
        fake_llm.replies = ["not json", "still not json"]

    response = api.post(f"/api/v1/companies/{ids['acme']}/contacts/search")

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Contact search failed")
    assert API_KEY not in response.text
    assert _searched_at(migrated_sessions, ids["acme"]) is None
    with migrated_sessions() as session:
        contacts = session.scalars(select(CompanyNetworking)).all()
        assert [(contact.id, contact.title) for contact in contacts] == [(ids["sent"], "Engineer")]


def test_job_and_company_details_report_contact_search_availability(
    api: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    ids = _seed(migrated_sessions, Skipped="ignored")
    with migrated_sessions() as session, session.begin():
        session.get(Company, ids["globex"]).contacts_searched_at = SENT_AT
        session.add(
            Job(
                company_id=ids["globex"],
                title="Applied",
                url="https://jobs.example/applied",
                inbox_type="applied",
            )
        )

    acme_job = api.get(f"/api/v1/jobs/{ids['Skipped']}").json()["contact_search"]
    assert acme_job == {
        "available": False,
        "unavailable_reason": "no_eligible_job",
        "last_searched_at": None,
    }
    acme = api.get(f"/api/v1/companies/{ids['acme']}").json()["contact_search"]
    assert acme["unavailable_reason"] == "no_eligible_job"

    globex = api.get(f"/api/v1/companies/{ids['globex']}").json()["contact_search"]
    assert globex["available"] is True and globex["unavailable_reason"] is None
    assert datetime.fromisoformat(globex["last_searched_at"]) == SENT_AT
    globex_job = api.get(f"/api/v1/jobs/{ids['globex_job']}").json()["contact_search"]
    assert globex_job["available"] is True


def test_repeat_searches_for_the_same_profiles_keep_one_row_each_and_the_sent_history(
    api: TestClient,
    migrated_sessions: sessionmaker[Session],
    fake_http: FakeHttp,
    fake_llm: FakeLlm,
) -> None:
    ids = _seed(migrated_sessions, Liked="recommended")
    # The second search returns the same two people under other URL forms of their profiles.
    fake_http.add(SERPAPI_SEARCH_URL, json=RESULTS)
    fake_http.add(
        SERPAPI_SEARCH_URL,
        json={
            "organic_results": [
                {**RESULTS["organic_results"][0], "link": "http://linkedin.com/in/ada-l#top"},
                {**RESULTS["organic_results"][1], "link": "https://DE.linkedin.com/in/Grace/"},
            ]
        },
    )
    fake_llm.replies = [PICKS, PICKS]
    url = f"/api/v1/companies/{ids['acme']}/contacts/search"

    first = api.post(url)
    second = api.post(url)

    assert first.status_code == 200 and second.status_code == 200, second.json()
    assert (second.json()["created"], second.json()["updated"]) == (0, 0)
    assert second.json()["contacts"] == first.json()["contacts"]
    with migrated_sessions() as session:
        rows = session.scalars(select(CompanyNetworking).order_by(CompanyNetworking.id)).all()
        assert [row.linkedin_url for row in rows] == [
            "https://www.linkedin.com/in/ada-l",
            "https://www.linkedin.com/in/grace",
        ]
        assert rows[0].id == ids["sent"] and rows[0].title == "Principal Engineer"
        assert (rows[0].connection_request_sent, rows[0].connection_request_sent_at) == (
            True,
            SENT_AT,
        )


def test_endpoint_logs_hold_no_api_key_contact_names_or_profile_urls(
    api: TestClient,
    migrated_sessions: sessionmaker[Session],
    fake_http: FakeHttp,
    fake_llm: FakeLlm,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = _seed(migrated_sessions, Liked="recommended")
    url = f"/api/v1/companies/{ids['acme']}/contacts/search"
    # A search outage (HTTP 503, retried once), an LLM failure, then a successful run.
    fake_http.add(SERPAPI_SEARCH_URL, status=503, json={"error": API_KEY})
    fake_http.add(SERPAPI_SEARCH_URL, status=503, json={"error": API_KEY})
    fake_http.add(SERPAPI_SEARCH_URL, json=RESULTS)
    fake_llm.replies = ["not json", "still not json", PICKS]

    with caplog.at_level(logging.DEBUG):
        assert api.post(url).status_code == 502
        assert api.post(url).status_code == 502
        assert api.post(url).status_code == 200

    company = ids["acme"]
    assert f"Contact search company={company} failed: search error" in caplog.text
    assert f"Contact search company={company} failed: LLM error" in caplog.text
    assert f"Contact search company={company} stored: 1 new, 1 updated" in caplog.text
    for secret in (API_KEY, "Lovelace", "Hopper", "linkedin.com/in", "serpapi.com/search"):
        assert secret not in caplog.text, secret
