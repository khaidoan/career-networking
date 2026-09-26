"""Company lookup: fills a new ``companies`` row from the model's own knowledge (no browsing)."""

from urllib.parse import urlsplit

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.llm import complete_structured, resolve_system_prompt
from src.models import Company
from src.tags import normalize_tags

AGENT_NAME = "company_lookup"
MAX_DESCRIPTION_CHARS = 6_000

COMPANY_LOOKUP_SYSTEM_PROMPT = """\
You describe a company for a job seeker, using only what you already know. You cannot browse
the web. You receive the company name and, sometimes, a job description from that company that
can help identify which company is meant.

Return:
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


def _user_content(name: str, description: str | None) -> str:
    content = f"Company name: {name}"
    if description:
        content += f"\n\nJob description from this company:\n{description[:MAX_DESCRIPTION_CHARS]}"
    return content


def lookup_company(session: Session, name: str, description: str | None = None) -> Company:
    """Insert (and flush) a company named exactly ``name``, enriched by the LLM.

    Raises ``LlmError`` if the model cannot be used; the caller then inserts a name-only company.
    The caller owns the transaction.
    """
    system_prompt = resolve_system_prompt(session, AGENT_NAME, COMPANY_LOOKUP_SYSTEM_PROMPT)
    profile = complete_structured(
        system_prompt, _user_content(name, description), CompanyProfile, agent_name=AGENT_NAME
    )
    company = Company(name=name, **profile.model_dump())
    session.add(company)
    session.flush()
    return company
