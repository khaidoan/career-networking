"""Shared authentication dependency for protected routes."""

import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from src.auth.tokens import InvalidTokenError, decode_access_token
from src.config import Settings, get_settings

SESSION_COOKIE_NAME = "cn_session"
NOT_AUTHENTICATED_MESSAGE = "Not authenticated"


@dataclass(frozen=True)
class CurrentUser:
    username: str


def get_current_user(
    settings: Annotated[Settings, Depends(get_settings)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> CurrentUser:
    """Validate the ``cn_session`` JWT cookie and return the signed-in user.

    Every protected router must depend on this, e.g.
    ``APIRouter(dependencies=[Depends(get_current_user)])`` or a ``CurrentUser`` parameter.
    Only the health and login endpoints are public. Missing, invalid or expired sessions
    produce ``401 {"detail": "Not authenticated"}``.
    """
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED_MESSAGE)
    try:
        claims = decode_access_token(session_token, settings)
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED_MESSAGE) from None

    subject = str(claims["sub"])
    # Tokens issued for a previously configured username are no longer valid.
    if not hmac.compare_digest(subject.encode(), settings.username.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED_MESSAGE)
    return CurrentUser(username=subject)
