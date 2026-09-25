"""Session JWT creation and verification (HS256)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from src.config import Settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """The token is missing required claims, has a bad signature, or has expired."""


def create_access_token(subject: str, settings: Settings) -> str:
    issued_at = datetime.now(UTC)
    claims = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify signature and expiry and return the claims, or raise ``InvalidTokenError``."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error
