"""Resume extractor: suggests titles, skills, seniority and country from resume text."""

import re

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.llm import complete_structured, resolve_system_prompt
from src.tags import normalize_tags
from src.vocabularies import COUNTRIES, SENIORITY_LEVELS

AGENT_NAME = "resume_extractor"
MAX_RESUME_CHARS = 30_000

RESUME_EXTRACTOR_SYSTEM_PROMPT = """\
You read a candidate's resume and suggest profile values for a job search.

Return:
- desired_titles: 1 to 5 job titles the candidate is a strong fit for next, based on their most
  recent roles (for example "Backend Engineer", "Product Manager"). Do not include seniority or
  level words such as Senior, Junior, Lead, Staff, Principal or numerals like II and III; the
  level goes in seniority instead.
- seniority: 1 or 2 seniority levels the candidate fits next, from: intern, entry (entry level),
  mid (mid level), senior, staff_principal (staff or principal), lead_manager (lead or manager),
  director, vp_plus (VP and above).
- country: the ISO 3166-1 alpha-2 code of the country the candidate lives in, from their address
  or, failing that, their most recent job location (for example "US", "GB"). Use null when the
  resume does not make it clear.
- hard_skills: concrete technical or domain skills, tools, languages and certifications named
  or clearly demonstrated in the resume.
- soft_skills: interpersonal and working-style skills evidenced in the resume (for example
  "Stakeholder management", "Mentoring").

Use short, conventional names (1 to 4 words each). Do not invent skills that the resume does not
support. Do not include personal details such as names, contact details or addresses.
"""

# Level words removed from the start or end of suggested titles, in case the model adds them.
# "Lead" and "Mid" are left to the prompt: "Lead Generation Specialist", "Mid Market Manager".
_LEADING_LEVEL = re.compile(
    r"^(?:(?:senior|sr|junior|jr|staff|principal|mid-level|entry-level)\.?\s+)+",
    re.IGNORECASE,
)
_TRAILING_LEVEL = re.compile(r"\s+(?:i{1,3}|iv|v|level\s+\d+|l\d+)$", re.IGNORECASE)


def strip_seniority(title: str) -> str:
    """``"Senior Backend Engineer II"`` → ``"Backend Engineer"``."""
    title = " ".join(title.split())
    return _TRAILING_LEVEL.sub("", _LEADING_LEVEL.sub("", title)).strip(" ,-")


class ResumeSuggestions(BaseModel):
    desired_titles: list[str] = []
    hard_skills: list[str] = []
    soft_skills: list[str] = []
    seniority: list[str] = []
    country: str | None = None

    @field_validator("desired_titles", mode="before")
    @classmethod
    def _titles_without_seniority(cls, value: object) -> list[str]:
        titles = value if isinstance(value, list) else []
        return normalize_tags(
            strip_seniority(title) if isinstance(title, str) else title for title in titles
        )

    @field_validator("hard_skills", "soft_skills", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> list[str]:
        return normalize_tags(value if isinstance(value, list) else None)

    @field_validator("seniority", mode="before")
    @classmethod
    def _known_levels(cls, value: object) -> list[str]:
        # Unknown levels are dropped rather than failing the whole reply; kept in vocabulary order.
        levels = (
            {item for item in value if isinstance(item, str)} if isinstance(value, list) else set()
        )
        return [level for level in SENIORITY_LEVELS if level in levels]

    @field_validator("country", mode="before")
    @classmethod
    def _known_country(cls, value: object) -> str | None:
        code = value.strip().upper() if isinstance(value, str) else None
        return code if code in COUNTRIES else None


def extract_resume_suggestions(session: Session, resume_text: str) -> ResumeSuggestions:
    """Suggested titles, skills, seniority and country; raises ``LlmError`` if the model fails."""
    system_prompt = resolve_system_prompt(session, AGENT_NAME, RESUME_EXTRACTOR_SYSTEM_PROMPT)
    return complete_structured(
        system_prompt,
        f"Resume:\n{resume_text[:MAX_RESUME_CHARS]}",
        ResumeSuggestions,
        agent_name=AGENT_NAME,
    )
