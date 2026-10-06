"""Request and response models for ``/api/v1/preferences``.

Every fixed value (country, currency, seniority, gender, EEO answers) is checked against the
shared vocabularies so the database only ever holds known slugs and codes.
"""

from collections.abc import Callable, Collection
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)

from src.agents.resume_extractor import ResumeSuggestions
from src.schedule import FETCH_TIME_PATTERN, FetchingRequirement, is_valid_timezone
from src.tags import normalize_tags
from src.vocabularies import (
    COUNTRIES,
    CURRENCIES,
    EEO_ANSWER_OPTIONS,
    GENDER_OPTIONS,
    SENIORITY_LEVELS,
)

MAX_TAGS = 50
MAX_TAG_LENGTH = 100
MAX_ADDRESS_LENGTH = 1000
MAX_ADDITIONAL_INFORMATION_LENGTH = 20_000
# Salaries are stored in a 32-bit integer column.
MAX_SALARY = 2_000_000_000

ResumeFileType = Literal["pdf", "docx"]


def _one_of(options: Collection[str]) -> Callable[[str], str]:
    def check(value: str) -> str:
        if value not in options:
            raise ValueError("is not one of the allowed options")
        return value

    return check


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _code_or_none(value: object) -> object:
    value = _blank_to_none(value)
    return value.upper() if isinstance(value, str) else value


def _normalized_tags(value: object) -> object:
    # Non-string items are left in place so validation reports them instead of dropping them.
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return normalize_tags(value)
    return value


def _unique(value: object) -> object:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(dict.fromkeys(item.strip() for item in value))
    return value


TagList = Annotated[
    list[Annotated[str, Field(max_length=MAX_TAG_LENGTH)]],
    BeforeValidator(_normalized_tags),
    Field(max_length=MAX_TAGS),
]
CountryCode = Annotated[str, AfterValidator(_one_of(COUNTRIES))]
CurrencyCode = Annotated[str, AfterValidator(_one_of(CURRENCIES))]
SeniorityList = Annotated[
    list[Annotated[str, AfterValidator(_one_of(SENIORITY_LEVELS))]],
    BeforeValidator(_unique),
    Field(max_length=len(SENIORITY_LEVELS)),
]
Salary = Annotated[int, Field(ge=0, le=MAX_SALARY)]


def _answer(question: str) -> AfterValidator:
    return AfterValidator(_one_of(EEO_ANSWER_OPTIONS[question]))


def _timezone(value: str) -> str:
    if not is_valid_timezone(value):
        raise ValueError("is not a known time zone")
    return value


FetchTime = Annotated[str, Field(pattern=FETCH_TIME_PATTERN.pattern)]
TimeZoneName = Annotated[str, Field(max_length=64), AfterValidator(_timezone)]
GenderSlug = Annotated[str, AfterValidator(_one_of(GENDER_OPTIONS))]
RaceEthnicity = Annotated[str, _answer("race_ethnicity")]
VeteranStatus = Annotated[str, _answer("veteran_status")]
DisabilityStatus = Annotated[str, _answer("disability_status")]
WorkAuthorization = Annotated[str, _answer("work_authorization")]
NeedsVisaSponsorship = Annotated[str, _answer("needs_visa_sponsorship")]


class EeoAnswers(BaseModel):
    """Voluntary self-identification answers; each value comes from a fixed option list."""

    model_config = ConfigDict(extra="forbid")

    race_ethnicity: RaceEthnicity | None = None
    veteran_status: VeteranStatus | None = None
    disability_status: DisabilityStatus | None = None
    work_authorization: WorkAuthorization | None = None
    needs_visa_sponsorship: NeedsVisaSponsorship | None = None


class PreferencesFields(BaseModel):
    """Every editable preference; ``PUT`` replaces all of them at once."""

    desired_titles: TagList = []
    excluded_title_words: TagList = []
    hard_skills: TagList = []
    soft_skills: TagList = []
    country: Annotated[CountryCode | None, BeforeValidator(_code_or_none)] = None
    currency: Annotated[CurrencyCode | None, BeforeValidator(_code_or_none)] = None
    salary_min: Salary | None = None
    salary_max: Salary | None = None
    seniority: SeniorityList = []
    address: Annotated[
        Annotated[str, Field(max_length=MAX_ADDRESS_LENGTH)] | None, BeforeValidator(_blank_to_none)
    ] = None
    gender: Annotated[GenderSlug | None, BeforeValidator(_blank_to_none)] = None
    eeo_answers: EeoAnswers = EeoAnswers()
    additional_information: Annotated[
        Annotated[str, Field(max_length=MAX_ADDITIONAL_INFORMATION_LENGTH)] | None,
        BeforeValidator(_blank_to_none),
    ] = None
    auto_apply: bool = False
    # Daily fetcher time as "HH:MM" in ``fetch_timezone``; ``None`` until saved, and job
    # fetching stays disabled until both are set.
    fetch_time: FetchTime | None = None
    fetch_timezone: TimeZoneName | None = None


class PreferencesUpdate(PreferencesFields):
    model_config = ConfigDict(extra="forbid")

    # Required on every save, so a saved profile always has a fetch schedule.
    fetch_time: FetchTime
    fetch_timezone: TimeZoneName

    @field_validator("salary_max")
    @classmethod
    def _max_not_below_min(cls, salary_max: int | None, info: ValidationInfo) -> int | None:
        salary_min = info.data.get("salary_min")
        if salary_max is not None and salary_min is not None and salary_min > salary_max:
            raise ValueError("must be greater than or equal to the minimum salary")
        return salary_max


class ResumeInfo(BaseModel):
    file_type: ResumeFileType
    file_name: str
    uploaded_at: datetime


class JobFetchingStatus(BaseModel):
    """Whether the fetcher will run, and if not, which saved values it still needs."""

    enabled: bool
    missing: list[FetchingRequirement]
    # The next daily run, when enabled (a container restart also starts one).
    next_run_at: datetime | None


class PreferencesRead(PreferencesFields):
    resume: ResumeInfo | None = None
    job_fetching: JobFetchingStatus


class ResumeUploadResponse(BaseModel):
    """The suggestions returned here have already been added to the saved preferences."""

    resume: ResumeInfo
    suggestions: ResumeSuggestions | None
    warning: str | None = None
    # Everything saved after the upload, suggestions included.
    preferences: PreferencesRead
