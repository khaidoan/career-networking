"""Jobs, companies and contacts endpoints against a disposable Postgres; the evaluator is mocked.

These need CAREER_NETWORKING_TEST_DATABASE_URL (see test_migrations.py).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.session import get_db
from src.models import Company, CompanyNetworking, Job
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
VALID_COMPANY = {
    "name": "  Initech ",
    "website_url": "https://initech.example",
    "linkedin_url": "https://www.linkedin.com/company/initech/",
    "logo_url": "",
    "description": "Software for TPS reports.",
    "industries": ["Software", " software ", "Enterprise"],
    "growth_stage": "Series B",
    "employee_estimate": "201-500",
    "history": "   ",
}


@pytest.fixture
def signed_in(
    app: FastAPI, client: TestClient, migrated_sessions: sessionmaker[Session]
) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        with migrated_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    yield client


def _company(session: Session, name: str, **values: Any) -> Company:
    company = Company(name=name, **values)
    session.add(company)
    session.flush()
    return company


def _job(session: Session, company: Company, title: str, **values: Any) -> Job:
    values.setdefault("discovered_when", NOW)
    job = Job(
        company_id=company.id,
        title=title,
        url=f"https://jobs.example/{company.name}/{title}".replace(" ", "-"),
        **values,
    )
    session.add(job)
    session.flush()
    return job


def _titles(response: Any) -> list[str]:
    assert response.status_code == 200, response.json()
    return [item["title"] for item in response.json()["items"]]


def test_list_jobs_filters_searches_orders_newest_arrival_first_and_pages_with_a_cursor(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        stripe = _company(session, "Stripe", industries=["Fintech"], growth_stage="Late-stage")
        globex = _company(session, "Globex")
        for day in range(4):
            _job(
                session,
                stripe,
                f"Stripe {day}",
                inbox_type="recommended",
                seniority_level="senior",
                inbox_entered_at=NOW - timedelta(days=day),
                liked=day == 3,
            )
        _job(session, stripe, "Stripe mid", inbox_type="recommended", seniority_level="mid")
        _job(session, globex, "Globex senior", inbox_type="recommended", seniority_level="senior")
        _job(session, stripe, "Stripe ignored", inbox_type="ignored", seniority_level="senior")

    first = signed_in.get(
        "/api/v1/jobs",
        params={"inbox": "recommended", "seniority": "senior", "company": "strpe", "limit": 3},
    )
    # Newest arrival first; liked jobs are not moved up.
    assert _titles(first) == ["Stripe 0", "Stripe 1", "Stripe 2"]
    card = first.json()["items"][0]
    assert card["company_name"] == "Stripe" and card["company_industries"] == ["Fintech"]
    assert card["company_growth_stage"] == "Late-stage" and card["liked"] is False

    cursor = first.json()["next_cursor"]
    second = signed_in.get(
        "/api/v1/jobs",
        params={
            "inbox": "recommended",
            "seniority": "senior",
            "company": "strpe",
            "limit": 3,
            "cursor": cursor,
        },
    )
    assert _titles(second) == ["Stripe 3"]
    # Recommended is a feed: its cursor never runs out, so newly scored jobs can still arrive.
    assert second.json()["next_cursor"] is not None

    liked_only = signed_in.get("/api/v1/jobs", params={"inbox": "recommended", "liked": "true"})
    assert _titles(liked_only) == ["Stripe 3"]

    bad = [
        {"inbox": "need-attention"},
        {"inbox": "pending"},
        {"inbox": "recommended", "seniority": "wizard"},
        {"inbox": "recommended", "cursor": "garbage"},
        {"inbox": "recommended", "limit": 51},
    ]
    for params in bad:
        response = signed_in.get("/api/v1/jobs", params=params)
        assert response.status_code == 422, params
        assert isinstance(response.json()["detail"], list)

    signed_in.cookies.clear()
    assert signed_in.get("/api/v1/jobs", params={"inbox": "recommended"}).status_code == 401


def test_like_apply_and_connection_request_are_saved_and_keep_first_timestamps(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        acme = _company(session, "Acme")
        job_id = _job(session, acme, "Engineer", inbox_type="recommended").id
        contact = CompanyNetworking(
            company_id=acme.id, first_name="Ada", last_name="Lovelace", title="CTO"
        )
        session.add(contact)
        session.flush()
        contact_id = contact.id

    liked = signed_in.patch(f"/api/v1/jobs/{job_id}", json={"liked": True})
    assert liked.status_code == 200 and liked.json()["liked"] is True
    assert signed_in.patch(
        f"/api/v1/jobs/{job_id}", json={"inbox_type": "applied"}
    ).status_code == (422)

    applied = signed_in.post(f"/api/v1/jobs/{job_id}/apply")
    assert applied.status_code == 200
    assert applied.json()["inbox_type"] == "applied"
    first_applied_when = applied.json()["applied_when"]
    assert first_applied_when is not None
    again = signed_in.post(f"/api/v1/jobs/{job_id}/apply")
    assert again.json()["applied_when"] == first_applied_when

    sent = signed_in.post(f"/api/v1/contacts/{contact_id}/connection-request")
    assert sent.status_code == 200
    assert sent.json()["connection_request_sent"] is True
    assert sent.json()["name"] == "Ada Lovelace"
    first_sent_at = sent.json()["connection_request_sent_at"]
    assert first_sent_at is not None
    resent = signed_in.post(f"/api/v1/contacts/{contact_id}/connection-request")
    assert resent.json()["connection_request_sent_at"] == first_sent_at

    detail = signed_in.get(f"/api/v1/jobs/{job_id}").json()
    assert detail["company"]["name"] == "Acme"
    assert [contact["id"] for contact in detail["contacts"]] == [contact_id]
    assert detail["contacts"][0]["connection_request_sent"] is True

    assert signed_in.get("/api/v1/jobs/999999").json() == {"detail": "Job not found"}
    missing = signed_in.post("/api/v1/contacts/999999/connection-request")
    assert missing.status_code == 404


def test_company_create_validates_input_and_update_replaces_fields(
    signed_in: TestClient,
) -> None:
    invalid = signed_in.post(
        "/api/v1/companies",
        json={
            **VALID_COMPANY,
            "name": "   ",
            "website_url": "initech.example",
            "linkedin_url": "https://www.notlinkedin.com/company/initech",
            "industries": [" "],
        },
    )
    assert invalid.status_code == 422
    fields = {tuple(error["loc"])[-1] for error in invalid.json()["detail"]}
    assert {"name", "website_url", "linkedin_url", "industries"} <= fields

    created = signed_in.post("/api/v1/companies", json=VALID_COMPANY)
    assert created.status_code == 201
    company = created.json()
    assert company["name"] == "Initech"
    assert company["industries"] == ["Software", "Enterprise"]
    assert company["logo_url"] is None and company["history"] is None
    assert company["job_count"] == 0 and company["jobs"] == [] and company["contacts"] == []

    updated = signed_in.put(
        f"/api/v1/companies/{company['id']}",
        json={**VALID_COMPANY, "name": "Initrode", "logo_url": "https://initrode.example/l.png"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Initrode"
    assert updated.json()["logo_url"] == "https://initrode.example/l.png"

    liked = signed_in.patch(f"/api/v1/companies/{company['id']}", json={"liked": True})
    assert liked.json()["liked"] is True
    assert signed_in.get("/api/v1/companies/industries").json() == ["Enterprise", "Software"]
    listed = signed_in.get("/api/v1/companies", params={"q": "initrod", "industry": "Software"})
    assert [item["name"] for item in listed.json()["items"]] == ["Initrode"]
    assert signed_in.put("/api/v1/companies/999999", json=VALID_COMPANY).status_code == 404


def test_delete_company_is_blocked_by_jobs_and_otherwise_removes_its_contacts(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        hiring = _company(session, "Hiring Co")
        _job(session, hiring, "Engineer", inbox_type="recommended")
        quiet = _company(session, "Quiet Co")
        session.add(CompanyNetworking(company_id=quiet.id, first_name="Grace"))
        hiring_id, quiet_id = hiring.id, quiet.id

    blocked = signed_in.delete(f"/api/v1/companies/{hiring_id}")
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "Companies with jobs can't be deleted."}
    assert signed_in.get(f"/api/v1/companies/{hiring_id}").json()["job_count"] == 1

    deleted = signed_in.delete(f"/api/v1/companies/{quiet_id}")
    assert deleted.status_code == 204
    assert signed_in.get(f"/api/v1/companies/{quiet_id}").status_code == 404
    with migrated_sessions() as session:
        assert session.scalar(select(func.count(CompanyNetworking.id))) == 0
    assert signed_in.delete(f"/api/v1/companies/{quiet_id}").status_code == 404


def _walk_pages(client: TestClient, path: str, params: dict[str, Any]) -> list[list[int]]:
    """Follow ``next_cursor`` to the end; returns the item ids of each page."""
    pages: list[list[int]] = []
    cursor: str | None = None
    while True:
        response = client.get(path, params={**params, **({"cursor": cursor} if cursor else {})})
        assert response.status_code == 200, response.json()
        pages.append([item["id"] for item in response.json()["items"]])
        cursor = response.json()["next_cursor"]
        if cursor is None or len(pages) > 20:
            return pages


def test_job_pages_with_tied_sort_keys_never_repeat_or_skip_rows(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        acme = _company(session, "Acme")
        # Every job entered the inbox at the same moment, so only the id tie-breaker keeps the
        # order stable across page boundaries.
        jobs = [
            _job(session, acme, f"Role {n}", inbox_type="ignored", inbox_entered_at=NOW)
            for n in range(7)
        ]
        ids = sorted((job.id for job in jobs), reverse=True)

    pages = _walk_pages(signed_in, "/api/v1/jobs", {"inbox": "ignored", "limit": 2})

    assert [len(page) for page in pages] == [2, 2, 2, 1]
    assert [job_id for page in pages for job_id in page] == ids


def test_recommended_feed_adds_newly_scored_jobs_at_the_bottom_then_older_ones(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        acme = _company(session, "Acme")
        for hour in range(5):
            _job(
                session,
                acme,
                f"Scored {hour}h ago",
                inbox_type="recommended",
                inbox_entered_at=NOW - timedelta(hours=hour),
            )
        pending_id = _job(session, acme, "Not scored yet", inbox_type="pending").id

    def page(cursor: str | None = None) -> tuple[list[str], str]:
        params = {"inbox": "recommended", "limit": 2, **({"cursor": cursor} if cursor else {})}
        response = signed_in.get("/api/v1/jobs", params=params)
        assert response.status_code == 200, response.json()
        return [item["title"] for item in response.json()["items"]], response.json()["next_cursor"]

    first, cursor = page()
    assert first == ["Scored 0h ago", "Scored 1h ago"]

    # Two jobs are scored while the user reads; the next page brings them first, oldest first.
    with migrated_sessions() as session, session.begin():
        for minutes in (10, 20):
            _job(
                session,
                acme,
                f"New +{minutes}m",
                inbox_type="recommended",
                inbox_entered_at=NOW + timedelta(minutes=minutes),
            )
    added, cursor = page(cursor)
    assert added == ["New +10m", "New +20m"]

    # Then the older jobs not shown yet, newest first, until they run out.
    older, cursor = page(cursor)
    assert older == ["Scored 2h ago", "Scored 3h ago"]
    last, cursor = page(cursor)
    assert last == ["Scored 4h ago"]
    caught_up, cursor = page(cursor)
    assert caught_up == [] and cursor is not None

    # Asking again later returns jobs scored in the meantime.
    with migrated_sessions() as session, session.begin():
        _job(
            session,
            acme,
            "Later",
            inbox_type="recommended",
            inbox_entered_at=NOW + timedelta(hours=1),
        )
    later, _cursor = page(cursor)
    assert later == ["Later"]

    # Jobs waiting to be scored are never shown.
    assert signed_in.get(f"/api/v1/jobs/{pending_id}").status_code == 404


def test_company_pages_with_tied_names_and_likes_never_repeat_or_skip_rows(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        # Names that tie case-insensitively, split across liked and not liked.
        names = [("acme", False), ("ACME", True), ("Acme", False), ("beta", True), ("Beta", False)]
        ids = {(name, liked): _company(session, name, liked=liked).id for name, liked in names}

    pages = _walk_pages(signed_in, "/api/v1/companies", {"limit": 2})

    ordered = [company_id for page in pages for company_id in page]
    tied_acme = sorted([ids[("acme", False)], ids[("Acme", False)]])
    assert ordered == [ids[("ACME", True)], ids[("beta", True)], *tied_acme, ids[("Beta", False)]]
    assert len(set(ordered)) == len(names)


def test_company_industry_filter_matches_any_selected_industry_and_search_is_literal(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        _company(session, "Stripe", industries=["Fintech", "Payments"])
        _company(session, "Globex", industries=["Healthcare"])
        _company(session, "Initech", industries=["Software"])
        _company(session, "100% Remote Co", industries=["Software"])

    def names(**params: Any) -> list[str]:
        response = signed_in.get("/api/v1/companies", params=params)
        assert response.status_code == 200, response.json()
        return [item["name"] for item in response.json()["items"]]

    # Repeated industry values match companies that have any one of them.
    assert names(industry=["Payments", "Healthcare"]) == ["Globex", "Stripe"]
    assert names(industry=["Payments", "Healthcare"], q="globx") == ["Globex"]
    # A typo still finds the company; "%" and "_" are matched literally, not as wildcards.
    assert names(q="Initeck") == ["Initech"]
    assert names(q="%") == ["100% Remote Co"]
    assert names(q="_") == []


def test_job_list_filters_by_visa_work_arrangement_and_job_type(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        acme = _company(session, "Acme")
        common = {"inbox_type": "recommended"}
        _job(
            session,
            acme,
            "Remote sponsor",
            visa_sponsorship=True,
            work_arrangement="remote",
            job_type_classification="full_time",
            **common,
        )
        _job(
            session,
            acme,
            "Hybrid no visa",
            visa_sponsorship=False,
            work_arrangement="hybrid",
            job_type_classification="contract",
            **common,
        )
        _job(
            session,
            acme,
            "Onsite unknown visa",
            visa_sponsorship=None,
            work_arrangement="onsite",
            job_type_classification="full_time",
            **common,
        )
        _job(
            session,
            acme,
            "Applied remote",
            visa_sponsorship=True,
            work_arrangement="remote",
            inbox_type="applied",
        )

    def titles(**params: Any) -> list[str]:
        response = signed_in.get("/api/v1/jobs", params={"inbox": "recommended", **params})
        return sorted(_titles(response))

    assert titles(visa="yes") == ["Remote sponsor"]
    assert titles(visa="no") == ["Hybrid no visa"]
    assert titles(work_arrangement=["remote", "hybrid"]) == ["Hybrid no visa", "Remote sponsor"]
    assert titles(job_type="full_time", visa="yes") == ["Remote sponsor"]
    assert titles(job_type="full_time", work_arrangement="hybrid") == []
    assert (
        signed_in.get(
            "/api/v1/jobs", params={"inbox": "recommended", "work_arrangement": "moon"}
        ).status_code
        == 422
    )


def test_job_list_filters_by_match_strength(
    signed_in: TestClient, migrated_sessions: sessionmaker[Session]
) -> None:
    with migrated_sessions() as session, session.begin():
        acme = _company(session, "Acme")
        for title, score in (
            ("Score 95", 95),
            ("Score 94", 94),
            ("Score 80", 80),
            ("Score 79", 79),
            ("Score 60", 60),
            ("Score 59", 59),
            ("Not scored", None),
        ):
            _job(session, acme, title, overall_score=score, inbox_type="ignored")

    def titles(*match: str) -> list[str]:
        response = signed_in.get("/api/v1/jobs", params={"inbox": "ignored", "match": match})
        return sorted(_titles(response))

    assert titles("excellent") == ["Score 95"]
    assert titles("strong") == ["Score 80", "Score 94"]
    assert titles("good") == ["Score 60", "Score 79"]
    assert titles("weak") == ["Score 59"]
    assert titles("not_scored") == ["Not scored"]
    assert titles("excellent", "weak") == ["Score 59", "Score 95"]
    assert len(titles()) == 7
    assert (
        signed_in.get("/api/v1/jobs", params={"inbox": "ignored", "match": "great"}).status_code
        == 422
    )
