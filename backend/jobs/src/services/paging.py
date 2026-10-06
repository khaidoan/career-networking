"""Keyset (cursor) paging for the list endpoints.

A cursor is the sort key of the last row on a page, as URL-safe base64 JSON. The next page is
every row that sorts after it, so rows never repeat or get skipped while the user scrolls, even
when rows are added in between. Every sort key ends with the primary key, so it is unique.
"""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Row, Select, and_, false, literal, or_
from sqlalchemy.orm import Session

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 50
MAX_CURSOR_LENGTH = 1000


class InvalidCursorError(ValueError):
    """The cursor was not produced by this API (or was tampered with)."""


@dataclass(frozen=True)
class SortKey:
    """One ordering column: the SQL expression, its direction and how to decode its value."""

    expression: ColumnElement[Any]
    descending: bool
    decode: Callable[[object], object]

    def order_by(self) -> ColumnElement[Any]:
        return self.expression.desc() if self.descending else self.expression.asc()


def as_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise InvalidCursorError("expected a boolean")
    return value


def as_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidCursorError("expected an integer")
    return value


def as_str(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidCursorError("expected a string")
    return value


def as_datetime(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(as_str(value))
    except ValueError:
        raise InvalidCursorError("expected an ISO 8601 timestamp") from None
    if parsed.tzinfo is None:
        raise InvalidCursorError("expected a timezone-aware timestamp")
    return parsed


def _json_value(value: object) -> object:
    return value.isoformat() if isinstance(value, datetime) else value


def _dump(payload: object) -> str:
    text = json.dumps(payload, separators=(",", ":"))
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _load(cursor: str) -> object:
    if len(cursor) > MAX_CURSOR_LENGTH:
        raise InvalidCursorError("cursor is too long")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (UnicodeError, binascii.Error, ValueError):
        raise InvalidCursorError("cursor is not valid") from None


def _plain(values: Sequence[object]) -> list[object]:
    return [_json_value(value) for value in values]


def _decode_values(values: object, keys: Sequence[SortKey]) -> list[object]:
    if not isinstance(values, list) or len(values) != len(keys):
        raise InvalidCursorError("cursor is not valid")
    return [key.decode(value) for key, value in zip(keys, values, strict=True)]


def encode_cursor(values: Sequence[object]) -> str:
    return _dump(_plain(values))


def decode_cursor(cursor: str, keys: Sequence[SortKey]) -> list[object]:
    """The sort key values in ``cursor``; raises ``InvalidCursorError`` for anything malformed."""
    return _decode_values(_load(cursor), keys)


def after_cursor(keys: Sequence[SortKey], values: Sequence[object]) -> ColumnElement[bool]:
    """Rows that sort strictly after ``values`` in the order given by ``keys``.

    Expands to ``k1 > v1 OR (k1 = v1 AND (k2 > v2 OR (k2 = v2 AND ...)))``, with ``<`` for
    descending keys, so mixed directions work.
    """
    condition: ColumnElement[bool] = false()
    for key, raw_value in reversed(list(zip(keys, values, strict=True))):
        # A bound literal, because SQLAlchemy refuses ``<``/``>`` against a bare True/False.
        value = literal(raw_value, type_=key.expression.type)
        beyond = key.expression < value if key.descending else key.expression > value
        condition = or_(beyond, and_(key.expression == value, condition))
    return condition


def keyset_page(
    session: Session,
    statement: Select[Any],
    keys: Sequence[SortKey],
    *,
    cursor: str | None,
    limit: int,
    sort_values: Callable[[Row[Any]], Sequence[object]],
) -> tuple[list[Row[Any]], str | None]:
    """One page of ``statement`` in ``keys`` order after ``cursor``, and the next page's cursor.

    Fetches ``limit + 1`` rows so the last page returns ``None`` without a count query.
    """
    if cursor is not None:
        statement = statement.where(after_cursor(keys, decode_cursor(cursor, keys)))
    statement = statement.order_by(*(key.order_by() for key in keys)).limit(limit + 1)
    rows = list(session.execute(statement).all())
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, encode_cursor(sort_values(page[-1]))


def feed_page(
    session: Session,
    statement: Select[Any],
    newest_first: Sequence[SortKey],
    *,
    cursor: str | None,
    limit: int,
    sort_values: Callable[[Row[Any]], Sequence[object]],
) -> tuple[list[Row[Any]], str]:
    """One page of a feed that grows at the bottom; the cursor never runs out.

    The first page is the newest rows. Each later page is, first, rows added since the newest
    row shown so far (oldest of those first, so they read in order at the bottom), and once there
    are none, the next older rows not shown yet. When both are used up the page is empty but the
    cursor stays valid, so asking again later returns rows added in the meantime.

    ``newest_first`` must be all-descending keys ending with the primary key. The cursor holds
    the newest row shown (``None`` before any) and the last older row shown (``None`` once the
    oldest has been shown).
    """
    oldest_first = [SortKey(key.expression, False, key.decode) for key in newest_first]
    if cursor is None:
        rows, older = keyset_page(
            session, statement, newest_first, cursor=None, limit=limit, sort_values=sort_values
        )
        newest = list(sort_values(rows[0])) if rows else None
        return rows, _encode_feed_cursor(newest, _decode_plain(older, newest_first))

    newest, older = _decode_feed_cursor(cursor, newest_first)
    added = statement
    if newest is not None:
        added = added.where(after_cursor(oldest_first, newest))
    rows = list(
        session.execute(
            added.order_by(*(key.order_by() for key in oldest_first)).limit(limit)
        ).all()
    )
    if rows:
        return rows, _encode_feed_cursor(list(sort_values(rows[-1])), older)
    if older is None:
        return [], cursor
    rows, next_older = keyset_page(
        session,
        statement,
        newest_first,
        cursor=encode_cursor(older),
        limit=limit,
        sort_values=sort_values,
    )
    return rows, _encode_feed_cursor(newest, _decode_plain(next_older, newest_first))


def _decode_plain(cursor: str | None, keys: Sequence[SortKey]) -> list[object] | None:
    return None if cursor is None else decode_cursor(cursor, keys)


def _encode_feed_cursor(newest: Sequence[object] | None, older: Sequence[object] | None) -> str:
    return _dump([None if part is None else _plain(part) for part in (newest, older)])


def _decode_feed_cursor(
    cursor: str, keys: Sequence[SortKey]
) -> tuple[list[object] | None, list[object] | None]:
    parts = _load(cursor)
    if not isinstance(parts, list) or len(parts) != 2:
        raise InvalidCursorError("cursor is not valid")
    newest, older = (None if part is None else _decode_values(part, keys) for part in parts)
    return newest, older
