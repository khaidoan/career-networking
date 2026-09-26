"""Response models for networking contacts (``company_networking`` rows)."""

from datetime import datetime

from pydantic import BaseModel

from src.models import CompanyNetworking


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
