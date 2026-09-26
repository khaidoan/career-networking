"""Request and response models for ``/api/v1/companies``.

Create and update share one validated body: text is trimmed, blank strings count as missing,
URLs must be absolute http(s) and the LinkedIn URL must be on linkedin.com.
"""

from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

from src.api.v1.schemas.contacts import ContactRead
from src.api.v1.schemas.job_card import JobCard
from src.models import Company
from src.tags import normalize_tags

MAX_NAME_LENGTH = 200
MAX_URL_LENGTH = 2000
MAX_SHORT_TEXT_LENGTH = 100
MAX_LONG_TEXT_LENGTH = 10_000
MAX_INDUSTRIES = 20
MAX_INDUSTRY_LENGTH = 100
LINKEDIN_HOST = "linkedin.com"


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _required(value: object) -> object:
    value = _blank_to_none(value)
    if value is None:
        raise ValueError("is required")
    return value


def _http_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("must be an absolute http(s) URL")
    return value


def _linkedin_url(value: str) -> str:
    host = urlsplit(_http_url(value)).hostname or ""
    if host != LINKEDIN_HOST and not host.endswith("." + LINKEDIN_HOST):
        raise ValueError("must be a linkedin.com URL")
    return value


def _industries(value: object) -> object:
    # Non-string items are left in place so validation reports them instead of dropping them.
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return normalize_tags(value)
    return value


RequiredText = Annotated[str, BeforeValidator(_required)]

Name = Annotated[RequiredText, Field(max_length=MAX_NAME_LENGTH)]
ShortText = Annotated[RequiredText, Field(max_length=MAX_SHORT_TEXT_LENGTH)]
LongText = Annotated[RequiredText, Field(max_length=MAX_LONG_TEXT_LENGTH)]
HttpUrl = Annotated[RequiredText, Field(max_length=MAX_URL_LENGTH), AfterValidator(_http_url)]
LinkedInUrl = Annotated[
    RequiredText, Field(max_length=MAX_URL_LENGTH), AfterValidator(_linkedin_url)
]
OptionalHttpUrl = Annotated[
    Annotated[str, Field(max_length=MAX_URL_LENGTH), AfterValidator(_http_url)] | None,
    BeforeValidator(_blank_to_none),
]
OptionalLongText = Annotated[
    Annotated[str, Field(max_length=MAX_LONG_TEXT_LENGTH)] | None,
    BeforeValidator(_blank_to_none),
]
Industries = Annotated[
    list[Annotated[str, Field(max_length=MAX_INDUSTRY_LENGTH)]],
    BeforeValidator(_industries),
    Field(min_length=1, max_length=MAX_INDUSTRIES),
]


class CompanyWrite(BaseModel):
    """The body of ``POST /companies`` and ``PUT /companies/{id}`` (every field is replaced)."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    website_url: HttpUrl
    linkedin_url: LinkedInUrl
    logo_url: OptionalHttpUrl = None
    description: LongText
    industries: Industries
    growth_stage: ShortText
    employee_estimate: ShortText
    history: OptionalLongText = None


class CompanyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    liked: bool


def _company_fields(company: Company, model: type[BaseModel]) -> dict[str, object]:
    """The stored company values for ``model``'s fields (``industries`` is never null)."""
    values = {name: getattr(company, name, None) for name in model.model_fields}
    values["industries"] = company.industries or []
    return values


class CompanyCard(BaseModel):
    """A company in the Companies list."""

    id: int
    name: str
    logo_url: str | None
    industries: list[str]
    growth_stage: str | None
    employee_estimate: str | None
    liked: bool

    @classmethod
    def from_model(cls, company: Company) -> Self:
        return cls.model_validate(_company_fields(company, cls))


class CompanyRead(CompanyCard):
    """Every stored company field; embedded in Job Details."""

    website_url: str | None
    linkedin_url: str | None
    description: str | None
    history: str | None


class CompanyDetail(CompanyRead):
    job_count: int
    jobs: list[JobCard]
    contacts: list[ContactRead]


class CompanyList(BaseModel):
    items: list[CompanyCard]
    next_cursor: str | None
