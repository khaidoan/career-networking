"""FastAPI application factory for the jobs service.

Run with ``uvicorn --factory src.main:create_app``.
"""

import logging

from fastapi import FastAPI

from src.api.v1.router import api_router
from src.auth.rate_limit import LoginRateLimiter
from src.config import Settings, get_settings
from src.errors import register_exception_handlers
from src.logging_config import configure_logging

API_V1_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Settings load first so missing configuration stops startup immediately."""
    settings = settings or get_settings()
    configure_logging(settings.log_folder)

    # Interactive docs stay off so health and login remain the only unauthenticated routes.
    app = FastAPI(
        title="Career Networking - Jobs Service",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.login_rate_limiter = LoginRateLimiter(
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    logger.info("Jobs service initialised")
    return app
