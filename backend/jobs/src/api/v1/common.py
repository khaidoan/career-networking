"""Dependencies and helpers shared by the jobs, companies and contacts routers."""

from collections.abc import Callable, Collection, Sequence
from typing import Annotated, Any

from fastapi import Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Row, Select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.db.session import get_db
from src.services.paging import (
    DEFAULT_PAGE_SIZE,
    MAX_CURSOR_LENGTH,
    MAX_PAGE_SIZE,
    InvalidCursorError,
    SortKey,
    keyset_page,
)

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
PageLimit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
PageCursor = Annotated[str | None, Query(max_length=MAX_CURSOR_LENGTH)]
PAGE_SIZE = DEFAULT_PAGE_SIZE
INVALID_CURSOR_MESSAGE = "Value error, is not a valid cursor; start again from the first page"


def one_of(options: Collection[str]) -> Callable[[str], str]:
    """A validator accepting only the given slugs."""

    def check(value: str) -> str:
        if value not in options:
            raise ValueError("is not one of the allowed options")
        return value

    return check


def fetch_page(
    session: Session,
    statement: Select[Any],
    keys: Sequence[SortKey],
    *,
    cursor: str | None,
    limit: int,
    sort_values: Callable[[Row[Any]], Sequence[object]],
) -> tuple[list[Row[Any]], str | None]:
    """``keyset_page`` with a malformed cursor reported as a 422 on the ``cursor`` parameter."""
    try:
        return keyset_page(
            session, statement, keys, cursor=cursor, limit=limit, sort_values=sort_values
        )
    except InvalidCursorError:
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("query", "cursor"), "msg": INVALID_CURSOR_MESSAGE}]
        ) from None
