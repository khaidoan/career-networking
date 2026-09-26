"""Normalisation for free-text tag lists (titles, skills, industries)."""

from collections.abc import Iterable


def normalize_tags(values: Iterable[object] | None) -> list[str]:
    """Trim each tag, drop blanks and non-strings, and de-duplicate case-insensitively.

    The first spelling of a tag wins and the original order is kept.
    """
    seen: set[str] = set()
    tags: list[str] = []
    for value in values or ():
        if not isinstance(value, str):
            continue
        tag = " ".join(value.split())
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            tags.append(tag)
    return tags
