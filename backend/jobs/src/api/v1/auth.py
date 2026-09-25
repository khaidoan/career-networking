"""Single-user login, logout and identity endpoints (JWT in an httpOnly cookie)."""

import hmac
import logging
import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.auth.dependencies import SESSION_COOKIE_NAME, CurrentUser, get_current_user
from src.auth.rate_limit import LoginRateLimiter, get_client_ip, get_login_rate_limiter
from src.auth.tokens import create_access_token
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS_MESSAGE = "Invalid username or password"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class UserIdentity(BaseModel):
    username: str
    first_name: str
    last_name: str
    initials: str
    email: str


def _identity(settings: Settings) -> UserIdentity:
    initials = (settings.firstname[:1] + settings.lastname[:1]) or settings.username[:1]
    return UserIdentity(
        username=settings.username,
        first_name=settings.firstname,
        last_name=settings.lastname,
        initials=initials.upper(),
        email=settings.email,
    )


def _is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded_proto == "https"


def _cookie_attributes(request: Request) -> dict:
    return {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "secure": _is_https(request),
    }


def _credentials_match(credentials: LoginRequest, settings: Settings) -> bool:
    # Evaluate both comparisons so timing does not reveal which field was wrong.
    username_ok = hmac.compare_digest(credentials.username.encode(), settings.username.encode())
    password_ok = hmac.compare_digest(
        credentials.password.encode(), settings.password.get_secret_value().encode()
    )
    return username_ok and password_ok


@router.post("/login")
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[LoginRateLimiter, Depends(get_login_rate_limiter)],
) -> UserIdentity:
    """Exchange the configured credentials for a ``cn_session`` cookie."""
    client_ip = get_client_ip(request)

    def rate_limit_headers() -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(limiter.max_attempts),
            "X-RateLimit-Remaining": str(limiter.remaining_attempts(client_ip)),
        }

    retry_after = limiter.retry_after_seconds(client_ip)
    if retry_after:
        logger.warning("Login blocked by rate limit for %s", client_ip)
        minutes = math.ceil(retry_after / 60)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts, try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(retry_after), **rate_limit_headers()},
        )

    if not _credentials_match(credentials, settings):
        limiter.record_failure(client_ip)
        logger.warning("Login failed for %s", client_ip)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            INVALID_CREDENTIALS_MESSAGE,
            headers=rate_limit_headers(),
        )

    limiter.reset(client_ip)
    logger.info("Login succeeded for %s", client_ip)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_access_token(settings.username, settings),
        max_age=settings.jwt_expires_seconds,
        **_cookie_attributes(request),
    )
    response.headers.update(rate_limit_headers())
    return _identity(settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    _user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    """Clear the session cookie using the same name, path and attributes it was set with."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE_NAME, **_cookie_attributes(request))
    return response


@router.get("/me")
def me(
    _user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserIdentity:
    """Identity of the signed-in user, taken from the environment."""
    return _identity(settings)
