"""Evaluator, company lookup and resume extractor agents with LiteLLM mocked."""

import json
from unittest.mock import MagicMock

import pytest

from src.agents.company_lookup import lookup_company
from src.agents.evaluator import JobForEvaluation, evaluate_job
from src.agents.resume_extractor import extract_resume_suggestions
from src.models import Company, Preferences
from tests.conftest import FakeLlm

JOB = JobForEvaluation(
    title="Senior Backend Engineer",
    company="Acme",
    location="Remote, United States",
    description="Build APIs in Python. 5+ years required. Full-time.",
)


@pytest.fixture
def session() -> MagicMock:
    """A session with no customised prompts."""
    mock = MagicMock()
    mock.scalar.return_value = None
    return mock


def _evaluation(**overrides: object) -> str:
    reply = {
        "overall_score": 82,
        "experience_score": 75,
        "skill_score": 90,
        "industry_exp_score": 60,
        "compensation_range": None,
        "work_arrangement": "Remote",
        "job_type_classification": "Full-time",
        "seniority_level": "principal-ish",
        "year_exp": 5,
        "visa_sponsorship": None,
        "location_city": None,
        "location_state": None,
        "location_country": "United States",
    }
    return json.dumps(reply | overrides)


def test_evaluator_returns_validated_evaluation_with_vocabulary_slugs(
    fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_llm.replies = [_evaluation()]

    evaluation = evaluate_job(session, JOB, Preferences(desired_titles=["Backend Engineer"]))

    assert evaluation.overall_score == 82
    assert evaluation.work_arrangement == "remote"
    assert evaluation.job_type_classification == "full_time"
    assert evaluation.seniority_level is None
    assert evaluation.location_country == "US"
    assert evaluation.visa_sponsorship is None


def test_evaluator_context_excludes_address_gender_and_other_eeo_answers(
    fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_llm.replies = [_evaluation()]
    preferences = Preferences(
        desired_titles=["Backend Engineer"],
        hard_skills=["Python"],
        country="US",
        address="742 Evergreen Terrace, Springfield",
        gender="non_binary",
        resume_text="Ten years building Python services.",
        eeo_answers={
            "race_ethnicity": "hispanic_or_latino",
            "veteran_status": "protected_veteran",
            "disability_status": "yes",
            "work_authorization": "authorized",
            "needs_visa_sponsorship": "no",
        },
    )

    evaluate_job(session, JOB, preferences)

    sent = fake_llm.sent_text()
    for private in (
        "Evergreen",
        "non_binary",
        "hispanic_or_latino",
        "protected_veteran",
        "disability_status",
        "race_ethnicity",
        "gender",
    ):
        assert private not in sent
    assert "needs_visa_sponsorship" in sent
    assert "authorized" in sent
    assert "Ten years building Python services." in sent


def test_company_lookup_drops_non_http_urls_and_keeps_the_given_name(
    fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_llm.replies = [
        json.dumps(
            {
                "website_url": "javascript:alert(1)",
                "linkedin_url": "https://www.linkedin.com/company/acme",
                "description": "Makes anvils.",
                "industries": ["Manufacturing", "manufacturing", " "],
                "growth_stage": None,
                "employee_estimate": "",
                "history": None,
            }
        )
    ]

    company = lookup_company(session, "ACME inc.", "We build anvils.")

    assert isinstance(company, Company)
    assert company.name == "ACME inc."
    assert company.website_url is None
    assert company.linkedin_url == "https://www.linkedin.com/company/acme"
    assert company.industries == ["Manufacturing"]
    assert company.employee_estimate is None
    session.add.assert_called_once_with(company)


def test_resume_extractor_trims_and_deduplicates_suggestions(
    fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_llm.replies = [
        json.dumps(
            {
                "desired_titles": [" Backend Engineer ", "backend engineer", "Staff Engineer"],
                "hard_skills": ["Python", "PYTHON", "  SQL"],
                "soft_skills": ["Mentoring", ""],
            }
        )
    ]

    suggestions = extract_resume_suggestions(session, "Resume text")

    assert suggestions.desired_titles == ["Backend Engineer", "Staff Engineer"]
    assert suggestions.hard_skills == ["Python", "SQL"]
    assert suggestions.soft_skills == ["Mentoring"]
