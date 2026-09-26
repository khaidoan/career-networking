"""Title, seniority, country and recency filters applied to every posting before the LLM.

These checks are free; only postings that pass them reach the evaluator, so they are where token
spend is controlled. Every rule errs on the side of keeping a posting: when a check cannot tell,
the evaluator decides.

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
from src.vocabularies import SENIORITY_LEVELS

RECENCY_WINDOW_DAYS = 7

_TOKEN = re.compile(r"[\w+#]+")

# Title words that name one seniority level unambiguously. Ambiguous words ("manager", "lead",
# "staff", "head", "associate") are deliberately absent: "Product Manager" is often an
# individual contributor and "Staff Accountant" is often entry level.
SENIORITY_MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("intern", re.compile(r"\b(intern|interns|internship|co-?op|werkstudent)\b")),
    ("entry", re.compile(r"\b(junior|jr|new grad|new graduate|graduate|entry[- ]level)\b")),
    ("senior", re.compile(r"\b(senior|sr)\b")),
    ("staff_principal", re.compile(r"\bprincipal\b")),
    ("director", re.compile(r"\bdirector\b")),
    (
        "vp_plus",
        re.compile(
            r"\b(vice president|vp|svp|evp|avp|cto|cio|cfo|ceo|coo|cpo|chief \w+ officer)\b"
        ),
    ),
)
# A title level this many steps (or fewer) from a selected level is kept, so adjacent levels
# (Senior vs Staff/Principal, Lead/Manager vs Director) are never dropped.
SENIORITY_TOLERANCE = 1


@dataclass(frozen=True)
class SearchCriteria:
    """What the user is looking for, taken from their saved preferences."""

    desired_titles: tuple[str, ...]
    country: str
    # Selected seniority levels; empty means no seniority filtering.
    seniority: tuple[str, ...] = ()

    @classmethod
    def from_preferences(cls, preferences: Preferences | None) -> "SearchCriteria | None":
        """``None`` when titles or country are missing (job discovery is paused)."""
        if preferences is None or not preferences.country:
            return None
        titles = tuple(title for title in preferences.desired_titles or () if title.strip())
        if not titles:
            return None
        seniority = tuple(
            level for level in preferences.seniority or () if level in SENIORITY_LEVELS
        )
        return cls(desired_titles=titles, country=preferences.country, seniority=seniority)


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


def title_seniority_levels(title: str) -> set[str]:
    """The seniority levels a title names unambiguously (empty when it names none)."""
    text = title.casefold()
    return {level for level, pattern in SENIORITY_MARKERS if pattern.search(text)}


def seniority_matches(title: str, seniority: tuple[str, ...]) -> bool:
    """False only when the title clearly names a level far from every selected one."""
    levels = title_seniority_levels(title)
    if not seniority or not levels:
        return True
    selected = [SENIORITY_LEVELS.index(level) for level in seniority]
    return any(
        abs(SENIORITY_LEVELS.index(level) - wanted) <= SENIORITY_TOLERANCE
        for level in levels
        for wanted in selected
    )


def names_country(location: str, country: str) -> bool:
    return country in countries_in(location or "")


def location_matches(location: str, country: str, *, allow_bare_remote: bool = True) -> bool:
    """True when the location names ``country``, or is remote without naming another country.

    ``allow_bare_remote=False`` rejects a remote posting that names no country at all; see
    ``bare_remote_allowed`` for when a board's bare "Remote" postings are trusted.
    """
    countries = countries_in(location or "")
    if countries:
        return country in countries
    return allow_bare_remote and is_remote(location or "")


def bare_remote_allowed(locations: list[str], country: str) -> bool:
    """Whether a board's remote postings that name no country are likely open to ``country``.

    Trusted when another posting on the board names ``country``, or when no posting names any
    country (nothing to go on, so keep them). Rejected only when the board's postings name other
    countries but never this one, e.g. a German company's "Remote" role for a US search.
    """
    named = [countries_in(location or "") for location in locations]
    if not any(named):
        return True
    return any(country in countries for countries in named)


def recency_cutoff(now: datetime) -> datetime:
    return now - timedelta(days=RECENCY_WINDOW_DAYS)


def is_recent(published_at: datetime | None, now: datetime) -> bool:
    """Undated postings are never recent."""
    return published_at is not None and published_at >= recency_cutoff(now)


def matches_title_and_location(title: str, location: str, criteria: SearchCriteria) -> bool:
    """The cheap checks, run before any extra request is spent on a posting."""
    return (
        title_matches(title, criteria.desired_titles)
        and seniority_matches(title, criteria.seniority)
        and location_matches(location, criteria.country)
    )
