"""Typo-tolerant company name search, run entirely in Postgres (no AI calls).

A name matches when it contains the search text (case-insensitive ``ILIKE``) or when the text is
close to a word in the name by ``pg_trgm`` word similarity, so "strpe" still finds "Stripe".
Used by ``GET /companies?q=`` and by ``GET /jobs?company=`` on the joined company name.
"""

from typing import Any

from sqlalchemy import ColumnElement, func, or_

# 0.5 accepts one dropped or swapped letter in short names ("strpe", "ntflix") while unrelated
# names score near 0; pg_trgm's own default (0.6) misses those typos.
WORD_SIMILARITY_THRESHOLD = 0.5
LIKE_ESCAPE = "\\"


def escape_like(text: str) -> str:
    """Escape ``%``, ``_`` and the escape character so they match literally in ``LIKE``."""
    return (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def normalize_search(text: str | None) -> str | None:
    """Trimmed search text with inner whitespace collapsed, or ``None`` when blank."""
    if text is None:
        return None
    return " ".join(text.split()) or None


def name_matches(column: ColumnElement[Any], text: str) -> ColumnElement[bool]:
    """``column`` contains ``text`` or has a word similar to it (both case-insensitive)."""
    pattern = f"%{escape_like(text)}%"
    return or_(
        column.ilike(pattern, escape=LIKE_ESCAPE),
        func.word_similarity(text, column) >= WORD_SIMILARITY_THRESHOLD,
    )
