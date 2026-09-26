"""LinkedIn URL normalization and contact dedup/upsert.

The upsert tests need CAREER_NETWORKING_TEST_DATABASE_URL (see test_migrations.py).
"""

import threading
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from src.models import Company, CompanyNetworking
from src.services.contacts import ContactCandidate, UpsertResult, upsert_contacts
from src.services.linkedin_urls import normalize_linkedin_profile_url

ADA_URL = "https://www.linkedin.com/in/ada-l"
SENT_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/in/ada-l",
        "http://www.linkedin.com/in/Ada-L/",
        "https://linkedin.com/in/ada-l?trk=public_profile",
        "https://UK.LinkedIn.com/in/ada-l#experience",
        "  https://de.linkedin.com/in/ada-l/?a=1#b ",
    ],
)
def test_normalizer_maps_url_variants_to_one_canonical_profile_url(url: str) -> None:
    assert normalize_linkedin_profile_url(url) == ADA_URL


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/company/acme",
        "https://www.linkedin.com/jobs/view/123",
        "https://www.linkedin.com/pub/ada-l/1/2/3",
        "https://www.linkedin.com/in/",
        "https://www.linkedin.com/in/ada-l/details/experience",
        "https://example.com/in/ada-l",
        "https://notlinkedin.com/in/ada-l",
        "https://www.linkedin.com.evil.com/in/ada-l",
        "ftp://www.linkedin.com/in/ada-l",
        "",
    ],
)
def test_normalizer_rejects_anything_but_a_linkedin_profile_path(url: str) -> None:
    assert normalize_linkedin_profile_url(url) is None


def _seed(sessions: sessionmaker[Session], *contacts: CompanyNetworking) -> tuple[int, int]:
    """Two companies (Acme, Globex) plus the given contacts; returns their ids."""
    with sessions() as session, session.begin():
        acme, globex = Company(name="Acme"), Company(name="Globex")
        session.add_all([acme, globex])
        session.flush()
        for contact in contacts:
            contact.company_id = contact.company_id or acme.id
            session.add(contact)
        return acme.id, globex.id


def _upsert(sessions: sessionmaker[Session], company_id: int, *candidates: ContactCandidate):
    with sessions() as session, session.begin():
        return upsert_contacts(session, company_id, list(candidates))


def _contacts(sessions: sessionmaker[Session]) -> list[CompanyNetworking]:
    with sessions() as session:
        return list(session.scalars(select(CompanyNetworking).order_by(CompanyNetworking.id)))


def test_upsert_inserts_new_contacts_with_the_normalized_url_and_sets_searched_at(
    migrated_sessions: sessionmaker[Session],
) -> None:
    acme_id, _ = _seed(migrated_sessions)

    result = _upsert(
        migrated_sessions,
        acme_id,
        ContactCandidate("Ada", "Lovelace", "Engineer", "http://uk.linkedin.com/in/Ada-L/?x=1"),
    )

    assert (result.created, result.updated) == (1, 0)
    [contact] = _contacts(migrated_sessions)
    assert (contact.company_id, contact.first_name, contact.last_name, contact.title) == (
        acme_id,
        "Ada",
        "Lovelace",
        "Engineer",
    )
    assert contact.linkedin_url == ADA_URL
    assert contact.connection_request_sent is False
    with migrated_sessions() as session:
        assert session.get(Company, acme_id).contacts_searched_at is not None


def test_refound_contact_gets_a_new_title_and_keeps_request_sent_fields(
    migrated_sessions: sessionmaker[Session],
) -> None:
    acme_id, _ = _seed(
        migrated_sessions,
        CompanyNetworking(
            first_name="Ada",
            last_name="Lovelace",
            title="Engineer",
            linkedin_url=ADA_URL,
            connection_request_sent=True,
            connection_request_sent_at=SENT_AT,
        ),
    )

    renamed = _upsert(
        migrated_sessions,
        acme_id,
        ContactCandidate("Ada", "Lovelace", "Staff Engineer", "https://linkedin.com/in/ADA-L/"),
    )
    blank = _upsert(migrated_sessions, acme_id, ContactCandidate("Ada", "Lovelace", "  ", ADA_URL))
    same = _upsert(
        migrated_sessions, acme_id, ContactCandidate("Ada", "Lovelace", "Staff Engineer", ADA_URL)
    )

    assert (renamed.created, renamed.updated) == (0, 1)
    assert (blank.created, blank.updated) == (0, 0)
    assert (same.created, same.updated) == (0, 0)
    [contact] = _contacts(migrated_sessions)
    assert contact.title == "Staff Engineer"
    assert contact.connection_request_sent is True
    assert contact.connection_request_sent_at == SENT_AT


def test_name_fallback_sets_the_url_only_on_a_same_company_contact_without_one(
    migrated_sessions: sessionmaker[Session],
) -> None:
    acme_id, globex_id = _seed(migrated_sessions)
    with migrated_sessions() as session, session.begin():
        session.add_all(
            [
                CompanyNetworking(company_id=globex_id, first_name="Grace", last_name="Hopper"),
                CompanyNetworking(
                    company_id=acme_id,
                    first_name="Grace",
                    last_name="Hopper",
                    linkedin_url="https://www.linkedin.com/in/grace-other",
                ),
                CompanyNetworking(
                    company_id=acme_id,
                    first_name="grace",
                    last_name="HOPPER",
                    connection_request_sent=True,
                    connection_request_sent_at=SENT_AT,
                ),
            ]
        )

    result = _upsert(
        migrated_sessions,
        acme_id,
        ContactCandidate("Grace", "Hopper", None, "https://www.linkedin.com/in/grace-h"),
    )

    assert (result.created, result.updated) == (0, 1)
    globex_contact, other_url, matched = _contacts(migrated_sessions)
    assert matched.linkedin_url == "https://www.linkedin.com/in/grace-h"
    assert (matched.connection_request_sent, matched.connection_request_sent_at) == (
        True,
        SENT_AT,
    )
    assert globex_contact.linkedin_url is None
    assert other_url.linkedin_url == "https://www.linkedin.com/in/grace-other"


def test_upsert_counts_created_and_updated_and_never_deletes(
    migrated_sessions: sessionmaker[Session],
) -> None:
    acme_id, _ = _seed(
        migrated_sessions,
        CompanyNetworking(
            first_name="Ada", last_name="Lovelace", title="Engineer", linkedin_url=ADA_URL
        ),
        CompanyNetworking(
            first_name="Alan", last_name="Turing", linkedin_url="https://www.linkedin.com/in/alan"
        ),
    )

    result = _upsert(
        migrated_sessions,
        acme_id,
        ContactCandidate("Ada", "Lovelace", "Manager", ADA_URL),
        ContactCandidate("Linus", "T", "Engineer", "https://www.linkedin.com/in/linus"),
        # The same new profile twice in one run is stored once.
        ContactCandidate("Linus", "T", "Engineer", "https://fr.linkedin.com/in/linus/"),
        ContactCandidate("Bad", "Url", None, "https://www.linkedin.com/company/acme"),
    )

    assert (result.created, result.updated) == (1, 1)
    with migrated_sessions() as session:
        assert session.scalar(select(func.count()).select_from(CompanyNetworking)) == 3


def test_a_concurrent_search_waits_for_the_company_lock_and_updates_instead_of_duplicating(
    migrated_sessions: sessionmaker[Session],
) -> None:
    acme_id, _ = _seed(migrated_sessions)
    outcome: dict[str, object] = {}

    def second_click() -> None:
        try:
            with migrated_sessions() as session, session.begin():
                # Fail instead of hanging the suite if the lock is never released.
                session.execute(text("SET LOCAL lock_timeout = '10s'"))
                outcome["result"] = upsert_contacts(
                    session,
                    acme_id,
                    [
                        ContactCandidate(
                            "Ada", "Lovelace", "Staff Engineer", "http://uk.linkedin.com/in/Ada-L/"
                        )
                    ],
                )
        except Exception as error:  # Reported by the assertion below.
            outcome["error"] = error

    with migrated_sessions() as first, first.begin():
        created = upsert_contacts(
            first, acme_id, [ContactCandidate("Ada", "Lovelace", "Engineer", ADA_URL)]
        )
        thread = threading.Thread(target=second_click)
        thread.start()
        thread.join(timeout=1.0)
        # Still waiting on SELECT ... FOR UPDATE of the company row held by this transaction.
        assert thread.is_alive() and not outcome
    thread.join(timeout=15.0)

    assert not thread.is_alive()
    assert "error" not in outcome, outcome.get("error")
    assert created == UpsertResult(created=1, updated=0)
    assert outcome["result"] == UpsertResult(created=0, updated=1)
    [contact] = _contacts(migrated_sessions)
    assert (contact.linkedin_url, contact.title) == (ADA_URL, "Staff Engineer")
