"""The single user's preferences and resume (``/api/v1/preferences``)."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from src.agents.resume_extractor import ResumeSuggestions, extract_resume_suggestions
from src.api.v1.schemas.preferences import (
    MAX_TAGS,
    EeoAnswers,
    JobFetchingStatus,
    PreferencesRead,
    PreferencesUpdate,
    RelocationCheck,
    ResumeInfo,
    ResumeUploadResponse,
)
from src.config import Settings, get_settings
from src.db.session import get_db
from src.models import Preferences
from src.schedule import missing_for_fetching, next_scheduled_time
from src.services import resume as resume_service
from src.sources.locations import countries_in
from src.sources.places import RESUME_HEADER_LINES, address_from_resume, home_place
from src.sources.relocation import parse_excluded_places
from src.tags import normalize_tags
from src.vocabularies import COUNTRY_CURRENCIES, EEO_QUESTION_KEYS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])

PREFERENCES_ROW_ID = 1
SUGGESTED_TAG_FIELDS = ("desired_titles", "hard_skills", "soft_skills")
# Where the resume header's city is looked up when no country is saved or named.
DEFAULT_ADDRESS_COUNTRY = "US"
SUGGESTIONS_UNAVAILABLE_WARNING = (
    "Your resume was saved, but suggestions could not be generated right now. "
    "You can fill in your titles and skills by hand."
)

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _load(session: Session) -> Preferences | None:
    return session.get(Preferences, PREFERENCES_ROW_ID)


def _load_or_create(session: Session) -> Preferences:
    preferences = _load(session)
    if preferences is None:
        preferences = Preferences(id=PREFERENCES_ROW_ID)
        session.add(preferences)
    return preferences


def _resume_info(preferences: Preferences | None) -> ResumeInfo | None:
    stored = resume_service.stored_resume(preferences.resume_location if preferences else None)
    if stored is None:
        return None
    # Resumes uploaded before the name was kept fall back to the stored file's name.
    file_name = (preferences.resume_filename if preferences else None) or stored.path.name
    return ResumeInfo(
        file_type=stored.file_type, file_name=file_name, uploaded_at=stored.uploaded_at
    )


def _job_fetching(preferences: Preferences | None) -> JobFetchingStatus:
    missing = missing_for_fetching(preferences)
    next_run_at = None
    if not missing and preferences and preferences.fetch_time and preferences.fetch_timezone:
        next_run_at = next_scheduled_time(
            datetime.now(UTC), preferences.fetch_time, preferences.fetch_timezone
        )
    return JobFetchingStatus(enabled=not missing, missing=missing, next_run_at=next_run_at)


def _to_read(preferences: Preferences | None) -> PreferencesRead:
    if preferences is None:
        return PreferencesRead(job_fetching=_job_fetching(None))
    eeo_answers = {
        key: value
        for key, value in (preferences.eeo_answers or {}).items()
        if key in EEO_QUESTION_KEYS
    }
    return PreferencesRead(
        desired_titles=preferences.desired_titles or [],
        excluded_title_words=preferences.excluded_title_words or [],
        hard_skills=preferences.hard_skills or [],
        soft_skills=preferences.soft_skills or [],
        country=preferences.country,
        currency=preferences.currency,
        salary_min=preferences.salary_min,
        salary_max=preferences.salary_max,
        seniority=preferences.seniority or [],
        address=preferences.address,
        gender=preferences.gender,
        willing_to_relocate=preferences.willing_to_relocate,
        excluded_relocation_places=preferences.excluded_relocation_places or [],
        max_commute_miles=preferences.max_commute_miles,
        eeo_answers=EeoAnswers.model_validate(eeo_answers),
        additional_information=preferences.additional_information,
        auto_apply=bool(preferences.auto_apply),
        fetch_time=preferences.fetch_time,
        fetch_timezone=preferences.fetch_timezone,
        resume=_resume_info(preferences),
        job_fetching=_job_fetching(preferences),
        relocation_check=_relocation_check(preferences),
    )


def _relocation_check(preferences: Preferences) -> RelocationCheck:
    if not preferences.country:
        return RelocationCheck()
    home = home_place(preferences.address, preferences.country)
    excluded = parse_excluded_places(
        preferences.excluded_relocation_places or (), preferences.country
    )
    return RelocationCheck(
        home=home.label if home else None, unrecognized_places=list(excluded.unrecognized)
    )


@router.get("")
def get_preferences(session: DbSession) -> PreferencesRead:
    """The saved preferences, or empty defaults before the first save."""
    return _to_read(_load(session))


@router.put("")
def update_preferences(update: PreferencesUpdate, session: DbSession) -> PreferencesRead:
    """Replace every editable preference (row ``id = 1`` is created on first save)."""
    preferences = _load_or_create(session)
    values = update.model_dump(exclude={"eeo_answers"})
    for field, value in values.items():
        setattr(preferences, field, value)
    preferences.eeo_answers = update.eeo_answers.model_dump(exclude_none=True)
    session.commit()
    logger.info("Preferences saved")
    return _to_read(preferences)


@router.post("/resume")
def upload_resume(
    session: DbSession,
    settings: AppSettings,
    file: Annotated[UploadFile, File(description="The resume as .pdf or .docx, up to 10 MB")],
) -> ResumeUploadResponse:
    """Store the resume, extract its text and save what it suggests.

    Suggested titles and skills are added after the saved ones (case-insensitive duplicates are
    skipped). Seniority, country and currency are filled in only while they are empty, so a
    choice the user made is never overwritten. The address is always replaced by the resume's:
    the model's, or when it gives none (or fails) the city, state and ZIP code read from the
    resume header without it; a resume with no address keeps the saved one. The suggestions are
    returned so the client can show which ones were added.
    """
    try:
        content = resume_service.read_limited(file.file)
        file_type = resume_service.detect_file_type(file.filename, content)
        resume_text = resume_service.extract_text(file_type, content)
        stored = resume_service.store_resume(settings.resume_folder, file_type, content)
    except resume_service.ResumeError as error:
        logger.info("Resume upload rejected status=%d", error.status_code)
        raise HTTPException(error.status_code, error.message) from None
    finally:
        file.file.close()

    preferences = _load_or_create(session)
    preferences.resume_location = str(stored.path)
    file_name = resume_service.display_filename(file.filename, file_type)
    preferences.resume_filename = file_name
    preferences.resume_text = resume_text
    session.commit()
    logger.info("Resume uploaded type=%s", file_type)

    suggestions, warning = _suggestions(session, resume_text)
    if suggestions is not None:
        _add_suggestions(preferences, suggestions)
    if suggestions is None or not suggestions.address:
        _fill_address_from_header(preferences, resume_text)
    session.commit()
    return ResumeUploadResponse(
        resume=ResumeInfo(
            file_type=stored.file_type,
            file_name=file_name,
            uploaded_at=stored.uploaded_at,
        ),
        suggestions=suggestions,
        warning=warning,
        preferences=_to_read(preferences),
    )


def _add_suggestions(preferences: Preferences, suggestions: ResumeSuggestions) -> None:
    for field in SUGGESTED_TAG_FIELDS:
        saved = getattr(preferences, field) or []
        merged = normalize_tags([*saved, *getattr(suggestions, field)])
        # Saved tags come first, so only suggestions are dropped at the limit.
        setattr(preferences, field, merged[:MAX_TAGS])
    if not preferences.seniority and suggestions.seniority:
        preferences.seniority = suggestions.seniority
    if not preferences.country and suggestions.country:
        preferences.country = suggestions.country
    if not preferences.currency and preferences.country:
        preferences.currency = COUNTRY_CURRENCIES.get(preferences.country)
    if suggestions.address:
        preferences.address = suggestions.address


def _fill_address_from_header(preferences: Preferences, resume_text: str) -> None:
    """Set the address to "City, ST 12345" from the resume header, without the model.

    Replaces any saved address, independent of the relocation answers; kept when the header
    names no city. Cities are looked up in the saved country, else in a country the header
    names, else in the United States.
    """
    country = preferences.country or _header_country(resume_text) or DEFAULT_ADDRESS_COUNTRY
    address = address_from_resume(resume_text, country)
    if address:
        preferences.address = address
        logger.info("Address filled in from the resume header")


def _header_country(resume_text: str) -> str | None:
    """The one country the resume header names, if it names exactly one."""
    header = "\n".join(resume_text.splitlines()[:RESUME_HEADER_LINES])
    named = countries_in(header)
    return next(iter(named)) if len(named) == 1 else None


def _suggestions(session: Session, resume_text: str) -> tuple[ResumeSuggestions | None, str | None]:
    # The upload already succeeded; a model outage only costs the suggestions.
    try:
        return extract_resume_suggestions(session, resume_text), None
    except Exception as error:
        logger.warning("Resume suggestions unavailable: %s", type(error).__name__)
        return None, SUGGESTIONS_UNAVAILABLE_WARNING


@router.delete("/resume", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(session: DbSession, settings: AppSettings) -> Response:
    """Delete the resume file and its text; titles and skills are kept."""
    resume_service.delete_resume(settings.resume_folder)
    preferences = _load(session)
    if preferences is not None:
        preferences.resume_location = None
        preferences.resume_filename = None
        preferences.resume_text = None
        session.commit()
    logger.info("Resume deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
