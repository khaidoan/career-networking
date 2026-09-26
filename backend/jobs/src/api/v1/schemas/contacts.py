"""Response models for networking contacts (``company_networking`` rows)."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel

from src.models import CompanyNetworking
from src.services.contacts import ContactSearchAvailability


class ContactRead(BaseModel):
    id: int
    company_id: int
    name: str | None
    first_name: str | None
    last_name: str | None
    title: str | None
    linkedin_url: str | None
    connection_request_sent: bool
    connection_request_sent_at: datetime | None

    @classmethod
    def from_model(cls, contact: CompanyNetworking) -> "ContactRead":
        parts = (contact.first_name, contact.last_name)
        name = " ".join(part.strip() for part in parts if part and part.strip())
        return cls(
            id=contact.id,
            company_id=contact.company_id,
            name=name or None,
            first_name=contact.first_name,
            last_name=contact.last_name,
            title=contact.title,
            linkedin_url=contact.linkedin_url,
            connection_request_sent=contact.connection_request_sent,
            connection_request_sent_at=contact.connection_request_sent_at,
        )


class ContactSearchStatus(BaseModel):
    """Whether "Find contacts" can run; ``unavailable_reason`` is null when it can."""

    available: bool
    unavailable_reason: Literal["no_api_key", "no_eligible_job"] | None
    last_searched_at: datetime | None

    @classmethod
    def from_availability(cls, availability: ContactSearchAvailability) -> Self:
        return cls.model_validate(availability, from_attributes=True)


class ContactSearchResult(BaseModel):
    """One successful contact search: counts, the company's contacts and the new status."""

    found: int
    created: int
    updated: int
    contacts: list[ContactRead]
    contact_search: ContactSearchStatus
