"""Networking agent: finds up to five people at a company for mock interviews or referrals.

It runs only when the user clicks "Find contacts"; the fetcher and schedules never call it. One
run is exactly one SerpApi Google search (``site:linkedin.com/in``) and at most one LLM
selection call (plus the standard validation retry). The LLM only returns indexes into the
numbered search results and a category; every name, title and profile URL is parsed in code
from the chosen result, so nothing stored is invented by the model. The agent writes nothing:
the caller stores ``NetworkingResult.found`` with ``upsert_contacts``. Nothing is ever sent to
LinkedIn.
"""

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.config import Settings
from src.llm import complete_structured, llm_safe_preferences, resolve_system_prompt
from src.models import Company, Job, Preferences
from src.services.contacts import ContactCandidate
from src.services.linkedin_urls import normalize_linkedin_profile_url
from src.sources.providers.base import HttpClient
from src.sources.serpapi import SerpApiError, serpapi_search

logger = logging.getLogger(__name__)

AGENT_NAME = "networking"
SEARCH_ENGINE = "google"
SEARCH_RESULT_COUNT = 20
MAX_CONTACTS = 5
MAX_MANAGERS = 1
MAX_RESULT_TITLE_CHARS = 200
MAX_SNIPPET_CHARS = 400
CATEGORY_PEER = "peer"
CATEGORY_MANAGER = "manager"
CATEGORIES = (CATEGORY_PEER, CATEGORY_MANAGER)

NETWORKING_SYSTEM_PROMPT = """\
You help a job seeker find people at a company to ask for a mock interview or a referral.
You receive the company name, the job title they want, the skills from the job that match
theirs, their full skill list, and a numbered list of Google results for LinkedIn profiles
(index, result title, snippet).

Pick at most 5 people, best first. Selection rules:
- Prefer people in the same role as the job, or a close peer role (same discipline and level
  range). Shared skills are a good sign.
- You may pick at most one hiring manager or team lead for this kind of role.
- Exclude recruiters, HR, people operations and talent acquisition.
- Exclude executives: C-level (CEO, CTO, CFO, ...), VPs and anyone above VP.
- Exclude anyone the result shows does not work at this company now (for example "former",
  "ex-", or a different current employer).
- Only use indexes from the list. If nobody fits, return an empty list.

For each pick return its index and a category: "peer" or "manager" (hiring manager or team lead).
"""

# Seniority and level words stripped from the job title before it goes into the search query.
_SENIORITY_WORDS = (
    "senior",
    "sr",
    "staff",
    "principal",
    "junior",
    "jr",
    "intern",
    "iv",
    "iii",
    "ii",
    "i",
    "1",
    "2",
    "3",
)
# A "/" neighbour means the word is part of a term like "I/O", not a level. "Lead" is a level
# only before another word ("Lead Engineer"); at the end it is the role itself ("Tech Lead").
_SENIORITY_PATTERN = re.compile(
    r"(?<![\w/])(?:(?:" + "|".join(_SENIORITY_WORDS) + r")\.?(?![\w/])|lead(?=\s+\w))",
    re.IGNORECASE,
)
_EMPTY_BRACKETS = re.compile(r"\(\s*\)|\[\s*\]")
_EDGE_PUNCTUATION = " \t,;:-–|/()[]"
# Straight and typographic double quotes; a quote inside a quoted phrase would end it early.
_QUOTES = re.compile(r"[\"“”„]")
_RESULT_TITLE_SEPARATORS = (" - ", " – ", " | ")
_HAS_LETTER = re.compile(r"[^\W\d_]")
_NOT_A_TITLE = "linkedin"


class ContactPick(BaseModel):
    """One chosen search result: its index in the numbered list and why it was chosen."""

    index: int
    category: Literal["peer", "manager"]

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ContactSelection(BaseModel):
    """The LLM's ranked picks; it never supplies names, titles or URLs."""

    contacts: list[ContactPick] = []

    @field_validator("contacts", mode="before")
    @classmethod
    def _drop_malformed_picks(cls, value: object) -> object:
        """Keep only picks with an integer index and a known category; null means none."""
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        picks = []
        for item in value:
            if not isinstance(item, dict):
                continue
            index, category = item.get("index"), item.get("category")
            if isinstance(index, bool) or not isinstance(index, int):
                continue
            if not isinstance(category, str) or category.strip().lower() not in CATEGORIES:
                continue
            picks.append(item)
        return picks


@dataclass(frozen=True)
class SearchResult:
    """A LinkedIn profile result that can become a contact."""

    result_title: str
    snippet: str
    candidate: ContactCandidate


@dataclass
class NetworkingResult:
    """What one run found; ``found`` is ready for ``upsert_contacts``."""

    found: list[ContactCandidate] = field(default_factory=list)
    # Organic results that were usable LinkedIn profiles, and how many the LLM kept.
    results: int = 0
    selected: int = 0


def clean_role_title(title: str) -> str:
    """The job title without seniority and level words ("Senior Engineer II" -> "Engineer")."""
    cleaned = _SENIORITY_PATTERN.sub(" ", title)
    cleaned = _EMPTY_BRACKETS.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split()).strip(_EDGE_PUNCTUATION)
    cleaned = " ".join(cleaned.split())
    return cleaned or " ".join(title.split())


def _phrase(text: str) -> str:
    """Text safe to put inside a quoted Google phrase: quotes removed, whitespace collapsed."""
    return " ".join(_QUOTES.sub(" ", text).split())


def build_query(company_name: str, job_title: str) -> str:
    """``site:linkedin.com/in "<company>" "<role>"``; skills are deliberately not included."""
    role = clean_role_title(job_title)
    return f'site:linkedin.com/in "{_phrase(company_name)}" "{_phrase(role)}"'


def match_skills(hard_skills: Iterable[str], description: str | None) -> list[str]:
    """The skills found in the description as case-insensitive whole words, in skill order.

    Skills are escaped, so ``C++``, ``C#`` and ``.NET`` match literally; "whole word" means no
    letter, digit or underscore directly before or after the skill.
    """
    if not description:
        return []
    matched: list[str] = []
    seen: set[str] = set()
    for skill in hard_skills:
        name = skill.strip() if isinstance(skill, str) else ""
        if not name or name.casefold() in seen:
            continue
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", description, re.IGNORECASE):
            matched.append(name)
            seen.add(name.casefold())
    return matched


def parse_result_title(result_title: str, company_name: str) -> tuple[str, str | None, str | None]:
    """``(first_name, last_name, title)`` from "Name - Title - Company | LinkedIn".

    The name is the text before the first separator (" - ", " – " or " | "); the title is the
    next segment, or ``None`` when there is none or it is just "LinkedIn" or the company name.
    Returns an empty first name when no name can be parsed.
    """
    # The leading space lets a title that starts with a separator parse as "no name".
    text = " " + " ".join(result_title.split())
    name, rest = _split_first(text)
    title = _split_first(rest)[0] if rest is not None else None
    if title is not None and title.casefold() in (_NOT_A_TITLE, company_name.strip().casefold()):
        title = None
    # Drop credentials after a comma ("Ada Lovelace, PhD").
    name = name.split(",")[0].strip()
    if not _HAS_LETTER.search(name) or name.casefold() == _NOT_A_TITLE:
        return "", None, title
    first, _, last = name.partition(" ")
    return first, last.strip() or None, title or None


def _split_first(text: str) -> tuple[str, str | None]:
    """The text before the earliest separator and the text after it (``None`` without one)."""
    positions = [
        (position, separator)
        for separator in _RESULT_TITLE_SEPARATORS
        if (position := text.find(separator)) != -1
    ]
    if not positions:
        return text.strip(), None
    position, separator = min(positions)
    return text[:position].strip(), text[position + len(separator) :].strip()


def profile_results(data: dict, company_name: str) -> list[SearchResult]:
    """Organic results that are LinkedIn ``/in/`` profiles with a parseable name, deduplicated."""
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for raw in data.get("organic_results") or []:
        if not isinstance(raw, dict):
            continue
        link, result_title = raw.get("link"), raw.get("title")
        if not isinstance(link, str) or not isinstance(result_title, str):
            continue
        url = normalize_linkedin_profile_url(link)
        if url is None or url in seen_urls:
            continue
        first_name, last_name, title = parse_result_title(result_title, company_name)
        if not first_name:
            continue
        seen_urls.add(url)
        snippet = raw.get("snippet")
        results.append(
            SearchResult(
                result_title=result_title.strip()[:MAX_RESULT_TITLE_CHARS],
                snippet=(snippet.strip() if isinstance(snippet, str) else "")[:MAX_SNIPPET_CHARS],
                candidate=ContactCandidate(
                    first_name=first_name, last_name=last_name, title=title, linkedin_url=url
                ),
            )
        )
    return results


def enforce_limits(picks: list[ContactPick], result_count: int) -> list[ContactPick]:
    """Drop out-of-range and repeated indexes, keep the first manager only, cap at five."""
    kept: list[ContactPick] = []
    seen: set[int] = set()
    managers = 0
    for pick in picks:
        if not 0 <= pick.index < result_count or pick.index in seen:
            continue
        if pick.category == CATEGORY_MANAGER:
            if managers >= MAX_MANAGERS:
                continue
            managers += 1
        seen.add(pick.index)
        kept.append(pick)
        if len(kept) == MAX_CONTACTS:
            break
    return kept


def _user_content(
    company: Company,
    job: Job,
    matched_skills: list[str],
    hard_skills: list[str],
    results: list[SearchResult],
) -> str:
    lines = [
        f"Company: {company.name}",
        f"Job title: {job.title}",
        f"Skills from the job that match the job seeker's: {', '.join(matched_skills) or 'none'}",
        f"Job seeker's skills: {', '.join(hard_skills) or 'not given'}",
        "",
        "Search results:",
    ]
    for index, result in enumerate(results):
        lines.append(f"[{index}] {result.result_title}")
        if result.snippet:
            lines.append(f"    {result.snippet}")
    return "\n".join(lines)


def find_contacts(
    session: Session,
    settings: Settings,
    client: HttpClient,
    company: Company,
    job: Job,
    preferences: Preferences | None,
) -> NetworkingResult:
    """Search for people at ``company`` in ``job``'s role and let the LLM pick up to five.

    Raises ``SerpApiError`` when the search fails (or no key is configured) and lets
    ``LlmError`` / ``LlmOutputError`` propagate. Zero usable search results is a success that
    skips the LLM call. Writes nothing; logs only the company id and counts.
    """
    if settings.serpapi_api_key is None:
        raise SerpApiError("SERPAPI_API_KEY is not set")
    data = serpapi_search(
        client,
        api_key=settings.serpapi_api_key.get_secret_value(),
        engine=SEARCH_ENGINE,
        params={"q": build_query(company.name, job.title), "num": SEARCH_RESULT_COUNT},
    )
    results = profile_results(data, company.name)
    outcome = NetworkingResult(results=len(results))
    if results:
        hard_skills = list(llm_safe_preferences(preferences).get("hard_skills") or [])
        system_prompt = resolve_system_prompt(session, AGENT_NAME, NETWORKING_SYSTEM_PROMPT)
        selection = complete_structured(
            system_prompt,
            _user_content(
                company, job, match_skills(hard_skills, job.description), hard_skills, results
            ),
            ContactSelection,
            agent_name=AGENT_NAME,
            settings=settings,
        )
        picks = enforce_limits(selection.contacts, len(results))
        outcome.found = [results[pick.index].candidate for pick in picks]
        outcome.selected = len(picks)
    logger.info(
        "Contact search company=%d: %d profile results, %d selected",
        company.id,
        outcome.results,
        outcome.selected,
    )
    return outcome
