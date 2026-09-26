"""The single user's preferences and resume (``/api/v1/preferences``)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from src.agents.resume_extractor import ResumeSuggestions, extract_resume_suggestions
from src.api.v1.schemas.preferences import (
    EeoAnswers,
    PreferencesRead,
    PreferencesUpdate,
    ResumeInfo,
    ResumeUploadResponse,
)
from src.config import Settings, get_settings
from src.db.session import get_db
from src.models import Preferences
from src.services import resume as resume_service
from src.vocabularies import EEO_QUESTION_KEYS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])

PREFERENCES_ROW_ID = 1
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
    return ResumeInfo(file_type=stored.file_type, uploaded_at=stored.uploaded_at)


def _to_read(preferences: Preferences | None) -> PreferencesRead:
    if preferences is None:
        return PreferencesRead()
    eeo_answers = {
        key: value
        for key, value in (preferences.eeo_answers or {}).items()
        if key in EEO_QUESTION_KEYS
    }
    return PreferencesRead(
        desired_titles=preferences.desired_titles or [],
        hard_skills=preferences.hard_skills or [],
        soft_skills=preferences.soft_skills or [],
        country=preferences.country,
        currency=preferences.currency,
        salary_min=preferences.salary_min,
        salary_max=preferences.salary_max,
        seniority=preferences.seniority or [],
        address=preferences.address,
        gender=preferences.gender,
        eeo_answers=EeoAnswers.model_validate(eeo_answers),
        resume=_resume_info(preferences),
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
    """Store the resume, extract its text and return (unsaved) title and skill suggestions."""
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
    preferences.resume_text = resume_text
    session.commit()
    logger.info("Resume uploaded type=%s", file_type)

    suggestions, warning = _suggestions(session, resume_text)
    return ResumeUploadResponse(
        resume=ResumeInfo(file_type=stored.file_type, uploaded_at=stored.uploaded_at),
        suggestions=suggestions,
        warning=warning,
    )


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
        preferences.resume_text = None
        session.commit()
    logger.info("Resume deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
