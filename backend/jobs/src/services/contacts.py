"""Storing contacts found by contact search: dedup and upsert into ``company_networking``.

A candidate matches an existing contact at the same company by normalized LinkedIn URL first,
then by case-insensitive first + last name among that company's contacts with no URL (which then
get the URL). A re-found contact only gets a newer non-empty title; its request-sent fields are
never touched and no contact is ever deleted, so "Request sent" history survives every search.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from src.config import Settings
from src.models import Company, CompanyNetworking, Job
from src.services.linkedin_urls import normalize_linkedin_profile_url

# Contact search is offered for companies with at least one job in one of these inboxes.
ELIGIBLE_INBOXES = ("recommended", "applied")
UNAVAILABLE_NO_API_KEY = "no_api_key"
UNAVAILABLE_NO_ELIGIBLE_JOB = "no_eligible_job"


@dataclass(frozen=True)
class ContactCandidate:
    """A person parsed from a search result; ``linkedin_url`` is normalized again on write."""

    first_name: str
    last_name: str | None
    title: str | None
    linkedin_url: str


@dataclass(frozen=True)
class UpsertResult:
    created: int
    updated: int


@dataclass(frozen=True)
class ContactSearchAvailability:
    """Whether "Find contacts" can run for a company, and when it last ran successfully."""

    available: bool
    unavailable_reason: str | None
    last_searched_at: datetime | None


class CompanyNotFoundError(LookupError):
    """The company to store contacts for does not exist."""


def has_eligible_job(session: Session, company_id: int) -> bool:
    """One ``EXISTS`` query: does the company have a recommended or applied job?"""
    eligible = exists().where(Job.company_id == company_id, Job.inbox_type.in_(ELIGIBLE_INBOXES))
    return bool(session.scalar(select(eligible)))


def latest_eligible_job(session: Session, company_id: int) -> Job | None:
    """The company's most recently discovered recommended or applied job."""
    return session.scalars(
        select(Job)
        .where(Job.company_id == company_id, Job.inbox_type.in_(ELIGIBLE_INBOXES))
        .order_by(Job.discovered_when.desc(), Job.id.desc())
        .limit(1)
    ).first()


def contact_search_availability(
    session: Session, settings: Settings, company: Company
) -> ContactSearchAvailability:
    """Available only with a SerpApi key (checked first, no query) and an eligible job."""
    if settings.serpapi_api_key is None:
        reason: str | None = UNAVAILABLE_NO_API_KEY
    elif not has_eligible_job(session, company.id):
        reason = UNAVAILABLE_NO_ELIGIBLE_JOB
    else:
        reason = None
    return ContactSearchAvailability(
        available=reason is None,
        unavailable_reason=reason,
        last_searched_at=company.contacts_searched_at,
    )


def _name_key(first_name: str | None, last_name: str | None) -> tuple[str, str] | None:
    first = " ".join((first_name or "").split()).casefold()
    last = " ".join((last_name or "").split()).casefold()
    return (first, last) if first else None


def _clean_title(title: str | None) -> str | None:
    """The title with whitespace collapsed, or ``None`` when blank."""
    if title is None:
        return None
    return " ".join(title.split()) or None


def upsert_contacts(
    session: Session,
    company_id: int,
    candidates: list[ContactCandidate],
    *,
    now: datetime | None = None,
) -> UpsertResult:
    """Insert new contacts, update re-found ones and set ``companies.contacts_searched_at``.

    Locks the company row (``SELECT ... FOR UPDATE``) before matching, so concurrent searches for
    the same company run one after the other; the unique index is the final safeguard. Writes in
    the caller's transaction and only flushes, so the caller commits (or rolls back) both the
    contacts and the timestamp together. Candidates whose URL fails normalization are skipped.
    """
    company = session.scalars(
        select(Company).where(Company.id == company_id).with_for_update()
    ).one_or_none()
    if company is None:
        raise CompanyNotFoundError(f"company {company_id} not found")

    contacts = session.scalars(
        select(CompanyNetworking)
        .where(CompanyNetworking.company_id == company_id)
        .order_by(CompanyNetworking.id)
    ).all()
    by_url = {contact.linkedin_url: contact for contact in contacts if contact.linkedin_url}
    without_url = [contact for contact in contacts if contact.linkedin_url is None]

    created: list[CompanyNetworking] = []
    updated: set[int] = set()
    for candidate in candidates:
        url = normalize_linkedin_profile_url(candidate.linkedin_url)
        if url is None:
            continue
        title = _clean_title(candidate.title)
        contact = by_url.get(url)
        if contact is None:
            contact = _take_name_match(without_url, candidate)
            if contact is not None:
                contact.linkedin_url = url
                by_url[url] = contact
                updated.add(contact.id)
        if contact is None:
            contact = CompanyNetworking(
                company_id=company_id,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                title=title,
                linkedin_url=url,
            )
            session.add(contact)
            created.append(contact)
            by_url[url] = contact
            continue
        if title is not None and title != contact.title:
            contact.title = title
            if contact not in created:
                updated.add(contact.id)

    company.contacts_searched_at = now or datetime.now(UTC)
    session.flush()
    return UpsertResult(created=len(created), updated=len(updated))


def _take_name_match(
    without_url: list[CompanyNetworking], candidate: ContactCandidate
) -> CompanyNetworking | None:
    """Remove and return the first no-URL contact with the candidate's first + last name."""
    key = _name_key(candidate.first_name, candidate.last_name)
    if key is None:
        return None
    for index, contact in enumerate(without_url):
        if _name_key(contact.first_name, contact.last_name) == key:
            return without_url.pop(index)
    return None
