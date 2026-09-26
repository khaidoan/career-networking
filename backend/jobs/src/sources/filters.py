"""Title, country and recency filters applied to every ATS posting.

``RECENCY_WINDOW_DAYS`` is the posting recency window, and postings without a
publish date are skipped (``is_recent`` returns ``False``). Both rules live only in this module;
the fetcher applies ``is_recent`` to Google Jobs postings too, so no posting older than the
window is ever processed.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.models import Preferences
from src.sources.locations import countries_in, is_remote

RECENCY_WINDOW_DAYS = 7

_TOKEN = re.compile(r"[\w+#]+")


@dataclass(frozen=True)
class SearchCriteria:
    """What the user is looking for, taken from their saved preferences."""

    desired_titles: tuple[str, ...]
    country: str

    @classmethod
    def from_preferences(cls, preferences: Preferences | None) -> "SearchCriteria | None":
        """``None`` when titles or country are missing (job discovery is paused)."""
        if preferences is None or not preferences.country:
            return None
        titles = tuple(title for title in preferences.desired_titles or () if title.strip())
        if not titles:
            return None
        return cls(desired_titles=titles, country=preferences.country)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def title_matches(title: str, desired_titles: tuple[str, ...]) -> bool:
    """True when every word of at least one desired title appears in ``title``."""
    title_tokens = _tokens(title)
    for desired in desired_titles:
        desired_tokens = _tokens(desired)
        if desired_tokens and desired_tokens <= title_tokens:
            return True
    return False


def location_matches(location: str, country: str) -> bool:
    """True when the location names ``country``, or is remote without naming another country."""
    countries = countries_in(location or "")
    if countries:
        return country in countries
    return is_remote(location or "")


def recency_cutoff(now: datetime) -> datetime:
    return now - timedelta(days=RECENCY_WINDOW_DAYS)


def is_recent(published_at: datetime | None, now: datetime) -> bool:
    """Undated postings are never recent."""
    return published_at is not None and published_at >= recency_cutoff(now)


def matches_title_and_location(title: str, location: str, criteria: SearchCriteria) -> bool:
    """The cheap checks, run before any extra request is spent on a posting."""
    return title_matches(title, criteria.desired_titles) and location_matches(
        location, criteria.country
    )
