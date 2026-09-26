"""Networking contacts at a company (``/api/v1/contacts``)."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from src.api.v1.common import DbSession
from src.api.v1.schemas.contacts import ContactRead
from src.models import CompanyNetworking

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contacts", tags=["contacts"])

CONTACT_NOT_FOUND = "Contact not found"


@router.post("/{contact_id}/connection-request")
def mark_connection_request_sent(contact_id: int, session: DbSession) -> ContactRead:
    """Record that a connection request was sent; calling it again keeps the first timestamp."""
    contact = session.get(CompanyNetworking, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, CONTACT_NOT_FOUND)
    contact.connection_request_sent = True
    if contact.connection_request_sent_at is None:
        contact.connection_request_sent_at = datetime.now(UTC)
    session.commit()
    logger.info("Contact %d marked as connection request sent", contact_id)
    return ContactRead.from_model(contact)
