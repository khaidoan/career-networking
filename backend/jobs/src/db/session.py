"""Database engine and per-request session dependency."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings

# Keeps health checks and requests from hanging when the database host is unreachable.
CONNECT_TIMEOUT_SECONDS = 3


@lru_cache
def get_engine() -> Engine:
    """The single process-wide engine, created lazily on first use."""
    return create_engine(
        get_settings().sqlalchemy_database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding one session per request and always closing it."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
