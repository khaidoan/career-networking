"""Preferences and resume endpoints with an in-memory session and the resume extractor mocked."""

import io
import zipfile
from collections.abc import Iterator
from typing import Any

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents.resume_extractor import ResumeSuggestions
from src.config import Settings
from src.db.session import get_db
from src.llm import LlmError
from src.models import Preferences
from src.services.resume import MAX_RESUME_BYTES
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

PREFERENCES_URL = "/api/v1/preferences"
RESUME_URL = "/api/v1/preferences/resume"


class FakeSession:
    """Just enough of a SQLAlchemy session for the single ``preferences`` row."""

    def __init__(self) -> None:
        self.rows: dict[int, Preferences] = {}
        self.commits = 0

    def get(self, _model: type, row_id: int) -> Preferences | None:
        return self.rows.get(row_id)

    def add(self, row: Preferences) -> None:
        self.rows[row.id] = row

    def commit(self) -> None:
        self.commits += 1

    def scalar(self, *_args: Any) -> None:
        return None  # no customised prompts

    def close(self) -> None:
        pass


@pytest.fixture
def db() -> FakeSession:
    return FakeSession()


@pytest.fixture
def signed_in(app: FastAPI, client: TestClient, db: FakeSession) -> Iterator[TestClient]:
    def override() -> Iterator[FakeSession]:
        yield db

    app.dependency_overrides[get_db] = override
    client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    yield client


@pytest.fixture
def suggestions(monkeypatch: pytest.MonkeyPatch) -> list[ResumeSuggestions | Exception]:
    """Queue what the mocked resume extractor returns (or raises) per call."""
    queued: list[ResumeSuggestions | Exception] = []

    def fake_extract(_session: object, _resume_text: str) -> ResumeSuggestions:
        outcome = queued.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("src.api.v1.preferences.extract_resume_suggestions", fake_extract)
    return queued


def _pdf(text: str | None) -> bytes:
    """A minimal one-page PDF, with ``text`` drawn on it when given."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(output)
    output += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    output += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    output += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(output)


def _docx(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _upload(client: TestClient, filename: str, content: bytes) -> Any:
    return client.post(RESUME_URL, files={"file": (filename, content, "application/octet-stream")})


def test_get_requires_a_session_and_returns_empty_defaults_before_the_first_save(
    client: TestClient, signed_in: TestClient
) -> None:
    signed_in.cookies.clear()
    assert client.get(PREFERENCES_URL).status_code == 401

    signed_in.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    response = signed_in.get(PREFERENCES_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["desired_titles"] == [] and body["seniority"] == []
    assert body["country"] is None and body["resume"] is None
    assert body["eeo_answers"]["work_authorization"] is None


def test_put_upserts_row_one_with_normalised_values(signed_in: TestClient, db: FakeSession) -> None:
    payload = {
        "desired_titles": [" Backend Engineer ", "backend engineer", "Platform  Engineer"],
        "hard_skills": ["Python"],
        "country": "us",
        "currency": "USD",
        "salary_min": 120000,
        "salary_max": 150000,
        "seniority": ["senior", "staff_principal", "senior"],
        "gender": "decline_to_answer",
        "eeo_answers": {"work_authorization": "authorized", "veteran_status": "decline_to_answer"},
    }

    response = signed_in.put(PREFERENCES_URL, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["desired_titles"] == ["Backend Engineer", "Platform Engineer"]
    assert body["country"] == "US"
    assert body["seniority"] == ["senior", "staff_principal"]
    saved = db.rows[1]
    assert saved.salary_max == 150000
    assert saved.eeo_answers == {
        "veteran_status": "decline_to_answer",
        "work_authorization": "authorized",
    }
    assert signed_in.get(PREFERENCES_URL).json() == body


def test_put_rejects_invalid_values_with_field_level_detail(signed_in: TestClient) -> None:
    response = signed_in.put(
        PREFERENCES_URL,
        json={"salary_min": 200000, "salary_max": 100000, "country": "XX", "seniority": ["guru"]},
    )

    assert response.status_code == 422
    fields = {tuple(error["loc"][1:]) for error in response.json()["detail"]}
    assert ("salary_max",) in fields
    assert ("country",) in fields
    assert ("seniority", 0) in fields


@pytest.mark.parametrize("llm_fails", [False, True])
def test_upload_pdf_stores_resume_text_and_returns_unsaved_suggestions(
    signed_in: TestClient,
    db: FakeSession,
    test_settings: Settings,
    suggestions: list[ResumeSuggestions | Exception],
    llm_fails: bool,
) -> None:
    (test_settings.resume_folder).mkdir(parents=True)
    old_docx = test_settings.resume_folder / "resume.docx"
    old_docx.write_bytes(_docx("Old resume"))
    suggestions.append(
        LlmError("down")
        if llm_fails
        else ResumeSuggestions(desired_titles=["Data Engineer"], hard_skills=["SQL"])
    )

    response = _upload(signed_in, "../../My CV.PDF", _pdf("Jane Doe Data Engineer SQL"))

    assert response.status_code == 200
    body = response.json()
    assert body["resume"]["file_type"] == "pdf"
    stored = test_settings.resume_folder / "resume.pdf"
    assert stored.read_bytes().startswith(b"%PDF")
    assert not old_docx.exists()
    saved = db.rows[1]
    assert saved.resume_location == str(stored)
    assert "Data Engineer" in (saved.resume_text or "")
    assert saved.desired_titles is None
    if llm_fails:
        assert body["suggestions"] is None
        assert body["warning"]
    else:
        assert body["suggestions"]["desired_titles"] == ["Data Engineer"]
        assert body["warning"] is None


def test_upload_rejects_wrong_types_and_textless_files_keeping_the_old_resume(
    signed_in: TestClient, db: FakeSession, test_settings: Settings
) -> None:
    db.add(Preferences(id=1, resume_text="Old text"))
    test_settings.resume_folder.mkdir(parents=True)
    old_resume = test_settings.resume_folder / "resume.docx"
    old_resume.write_bytes(_docx("Old text"))

    not_really_pdf = _upload(signed_in, "resume.pdf", b"PK\x03\x04 not a pdf")
    plain_text = _upload(signed_in, "resume.txt", b"Just text")
    scanned = _upload(signed_in, "scan.pdf", _pdf(None))

    assert not_really_pdf.status_code == 415
    assert plain_text.status_code == 415
    assert scanned.status_code == 422
    assert isinstance(scanned.json()["detail"], str)
    assert old_resume.exists()
    assert not (test_settings.resume_folder / "resume.pdf").exists()
    assert db.rows[1].resume_text == "Old text"


def test_delete_resume_removes_file_and_text_but_keeps_titles_and_skills(
    signed_in: TestClient, db: FakeSession, test_settings: Settings
) -> None:
    test_settings.resume_folder.mkdir(parents=True)
    resume = test_settings.resume_folder / "resume.pdf"
    resume.write_bytes(_pdf("Text"))
    db.add(
        Preferences(
            id=1,
            resume_location=str(resume),
            resume_text="Text",
            desired_titles=["Data Engineer"],
            hard_skills=["SQL"],
        )
    )
    assert signed_in.get(PREFERENCES_URL).json()["resume"]["file_type"] == "pdf"

    response = signed_in.delete(RESUME_URL)

    assert response.status_code == 204
    assert not resume.exists()
    saved = db.rows[1]
    assert saved.resume_location is None and saved.resume_text is None
    assert saved.desired_titles == ["Data Engineer"] and saved.hard_skills == ["SQL"]


def _zip_without_word_body() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "A ZIP archive, but not a Word document")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "content",
    [_zip_without_word_body(), b"%PDF-1.4 renamed to .docx"],
    ids=["zip-without-word-document", "pdf-bytes"],
)
def test_docx_upload_needs_a_zip_containing_the_word_document_part(
    signed_in: TestClient, db: FakeSession, test_settings: Settings, content: bytes
) -> None:
    response = _upload(signed_in, "resume.docx", content)

    assert response.status_code == 415
    assert isinstance(response.json()["detail"], str)
    assert not (test_settings.resume_folder / "resume.docx").exists()
    assert 1 not in db.rows


def test_replacing_a_pdf_with_a_docx_removes_the_pdf_and_reads_the_word_text(
    signed_in: TestClient,
    db: FakeSession,
    test_settings: Settings,
    suggestions: list[ResumeSuggestions | Exception],
) -> None:
    test_settings.resume_folder.mkdir(parents=True)
    old_pdf = test_settings.resume_folder / "resume.pdf"
    old_pdf.write_bytes(_pdf("Old PDF resume"))
    db.add(Preferences(id=1, resume_location=str(old_pdf), resume_text="Old PDF resume"))
    suggestions.append(ResumeSuggestions(desired_titles=["Platform Engineer"]))

    response = _upload(signed_in, "CV final.docx", _docx("Jane Doe, Platform Engineer, Kubernetes"))

    assert response.status_code == 200
    assert response.json()["resume"]["file_type"] == "docx"
    stored = test_settings.resume_folder / "resume.docx"
    assert stored.exists() and not old_pdf.exists()
    assert sorted(path.name for path in test_settings.resume_folder.iterdir()) == ["resume.docx"]
    saved = db.rows[1]
    assert saved.resume_location == str(stored)
    assert saved.resume_text == "Jane Doe, Platform Engineer, Kubernetes"
    assert signed_in.get(PREFERENCES_URL).json()["resume"]["file_type"] == "docx"


def test_upload_over_ten_megabytes_returns_413_and_keeps_the_old_resume(
    signed_in: TestClient, db: FakeSession, test_settings: Settings
) -> None:
    test_settings.resume_folder.mkdir(parents=True)
    old_pdf = test_settings.resume_folder / "resume.pdf"
    old_pdf.write_bytes(_pdf("Old"))
    db.add(Preferences(id=1, resume_location=str(old_pdf), resume_text="Old"))
    oversized = b"%PDF-1.4\n" + b"0" * MAX_RESUME_BYTES

    response = _upload(signed_in, "resume.pdf", oversized)

    assert response.status_code == 413
    assert "10 MB" in response.json()["detail"]
    assert old_pdf.read_bytes().startswith(b"%PDF") and old_pdf.stat().st_size < 1024
    assert db.rows[1].resume_text == "Old"
    assert db.commits == 0
