"""Company lookup: fills a ``companies`` row from the model's own knowledge (no browsing).

The scorer calls it for companies with a recommended job, and Company Details asks for it (once)
when the user opens a company that has no profile, so no tokens are spent on other companies
whose jobs all go to the Ignored inbox. It also returns the company's official name,
which replaces a name taken from a job board's slug ("capitalone" -> "Capital One").
"""

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.llm import complete_structured, resolve_system_prompt
from src.models import Company
from src.tags import normalize_tags

AGENT_NAME = "company_lookup"
MAX_DESCRIPTION_CHARS = 6_000
MAX_NAME_CHARS = 200

COMPANY_LOOKUP_SYSTEM_PROMPT = """\
You describe a company for a job seeker, using only what you already know. You cannot browse
the web. You receive the company name and, sometimes, a job description from that company that
can help identify which company is meant.

Return:
- official_name: the company's name as it commonly writes it (for example "Capital One" for
  "capitalone"). The name you receive may be a job board's account name, lower-cased or
  hyphenated.
- website_url: the company's official website (https URL).
- linkedin_url: the company's LinkedIn page (https://www.linkedin.com/company/...).
- description: two or three sentences on what the company does.
- industries: a short list of industries (for example ["Fintech", "Payments"]).
- growth_stage: for example "Seed", "Series B", "Late-stage private", "Public", "Non-profit".
- employee_estimate: an approximate headcount range (for example "1,001-5,000").
- history: two or three sentences on when and where it was founded and notable milestones.

If you are not confident about a value, or do not recognise the company, return null for that
value. Never invent URLs.
"""


class CompanyProfile(BaseModel):
    website_url: str | None = None
    linkedin_url: str | None = None
    description: str | None = None
    industries: list[str] | None = None
    growth_stage: str | None = None
    employee_estimate: str | None = None
    history: str | None = None

    @field_validator("website_url", "linkedin_url", mode="before")
    @classmethod
    def _http_url_only(cls, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        url = value.strip()
        parts = urlsplit(url)
        return url if parts.scheme in ("http", "https") and parts.netloc else None

    @field_validator("description", "growth_stage", "employee_estimate", "history", mode="before")
    @classmethod
    def _blank_is_null(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("industries", mode="before")
    @classmethod
    def _industries(cls, value: object) -> list[str] | None:
        return normalize_tags(value if isinstance(value, list) else None) or None


class CompanyLookup(CompanyProfile):
    """The model's reply: the profile plus the official name (not a profile field, so it does not
    count towards ``is_name_only``)."""

    official_name: str | None = None

    @field_validator("official_name", mode="before")
    @classmethod
    def _one_line_name(cls, value: object) -> str | None:
        name = " ".join(value.split()) if isinstance(value, str) else ""
        return name if 0 < len(name) <= MAX_NAME_CHARS else None


# A job board's account name rather than a company name: one lower-case word, maybe hyphenated.
_SLUG_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def looks_like_slug(name: str) -> bool:
    return bool(_SLUG_NAME.match(name.strip()))


def _apply_official_name(company: Company, lookup: CompanyLookup) -> None:
    # Only a slug is replaced; a real name (even one spelled differently) is the user's or the
    # posting's and stays.
    if lookup.official_name and looks_like_slug(company.name):
        company.name = lookup.official_name


def _user_content(name: str, description: str | None) -> str:
    content = f"Company name: {name}"
    if description:
        content += f"\n\nJob description from this company:\n{description[:MAX_DESCRIPTION_CHARS]}"
    return content


def is_name_only(company: Company) -> bool:
    """True for a company saved without a profile (lookup skipped or failed)."""
    return all(getattr(company, field) is None for field in CompanyProfile.model_fields)


def enrich_company(session: Session, company: Company, description: str | None = None) -> None:
    """Fill the empty profile fields of an existing company; raises ``LlmError`` like lookup."""
    system_prompt = resolve_system_prompt(session, AGENT_NAME, COMPANY_LOOKUP_SYSTEM_PROMPT)
    lookup = complete_structured(
        system_prompt,
        _user_content(company.name, description),
        CompanyLookup,
        agent_name=AGENT_NAME,
    )
    for field in CompanyProfile.model_fields:
        value = getattr(lookup, field)
        if getattr(company, field) is None and value is not None:
            setattr(company, field, value)
    _apply_official_name(company, lookup)
    company.profile_looked_up_at = datetime.now(UTC)
    session.flush()


def needs_profile_lookup(company: Company) -> bool:
    """True for a name-only company the lookup agent has not tried yet."""
    return company.profile_looked_up_at is None and is_name_only(company)
