"""The networking agent with SerpApi and LiteLLM mocked; nothing reaches the network."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from src import fetcher
from src.agents.networking import (
    ContactSelection,
    clean_role_title,
    find_contacts,
    match_skills,
    parse_result_title,
)
from src.config import Settings
from src.llm import LlmOutputError
from src.models import Company, Job, Preferences
from src.services.contacts import ContactCandidate
from src.sources.serpapi import SERPAPI_SEARCH_URL, SerpApiError
from tests.conftest import FakeHttp, FakeLlm

API_KEY = "serpapi-secret-key"
COMPANY = Company(id=7, name='Acme "Rockets" Inc')
JOB = Job(
    id=3,
    company_id=7,
    title="Senior Software Engineer II",
    description="We use Python, C++ and .NET daily. Kubernetes is a plus. We write JavaScript too.",
)
PREFERENCES = Preferences(
    hard_skills=["python", "C++", ".net", "Java", "Rust"],
    address="1 Private Road",
    gender="private-gender",
)


def _result(slug: str, title: str, snippet: str = "") -> dict:
    return {"link": f"https://www.linkedin.com/in/{slug}/", "title": title, "snippet": snippet}


RESULTS = [
    _result("ada", "Ada Lovelace - Software Engineer - Acme | LinkedIn", "Python at Acme"),
    {"link": "https://www.linkedin.com/company/acme", "title": "Acme | LinkedIn"},
    {"link": "https://example.com/in/bob", "title": "Bob Smith - Engineer"},
    _result("grace", "Grace Hopper – Engineering Manager – Acme"),
    _result("alan", "Alan Turing | LinkedIn"),
    _result("nameless", " - Engineer - Acme"),
    _result("linus", "Linus T - Staff Engineer"),
    _result("margaret", "Margaret Hamilton - Team Lead"),
    _result("ken", "Ken Thompson - Software Engineer"),
    _result("dennis", "Dennis Ritchie - Engineer"),
]
# Usable profiles, in order: 0 ada, 1 grace, 2 alan, 3 linus, 4 margaret, 5 ken, 6 dennis.


@pytest.fixture
def settings(test_settings: Settings) -> Settings:
    return test_settings.model_copy(update={"serpapi_api_key": SecretStr(API_KEY)})


@pytest.fixture
def session() -> MagicMock:
    """A session with no customised prompts."""
    mock = MagicMock()
    mock.scalar.return_value = None
    return mock


def _picks(*picks: tuple[int, str]) -> str:
    return json.dumps({"contacts": [{"index": i, "category": c} for i, c in picks]})


def test_one_google_search_with_a_cleaned_role_and_quoted_company_and_no_skills(
    settings: Settings, fake_http: FakeHttp, fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, json={"organic_results": RESULTS})
    fake_llm.replies = [_picks()]

    result = find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    (request,) = fake_http.requests
    params = request.url.params
    assert params["engine"] == "google"
    assert params["num"] == "20"
    assert params["q"] == 'site:linkedin.com/in "Acme Rockets Inc" "Software Engineer"'
    assert "python" not in params["q"].lower()
    assert len(fake_llm.requests) == 1
    assert result.found == [] and result.results == 7 and result.selected == 0


def test_the_llm_sees_only_profile_results_and_safe_preferences(
    settings: Settings, fake_http: FakeHttp, fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, json={"organic_results": RESULTS})
    fake_llm.replies = [_picks((0, "peer"))]

    find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    sent = fake_llm.sent_text()
    assert "[0] Ada Lovelace - Software Engineer - Acme | LinkedIn" in sent
    assert "[6] Dennis Ritchie - Engineer" in sent
    assert "[7]" not in sent
    assert "[1] Grace Hopper" in sent
    assert "Bob Smith" not in sent
    assert "Nameless" not in sent and "] - Engineer - Acme" not in sent
    assert "Skills from the job that match the job seeker's: python, C++, .net" in sent
    assert "1 Private Road" not in sent and "private-gender" not in sent


def test_bad_indexes_are_dropped_one_manager_and_five_contacts_are_kept_in_rank_order(
    settings: Settings, fake_http: FakeHttp, fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, json={"organic_results": RESULTS})
    fake_llm.replies = [
        _picks(
            (5, "peer"),
            (99, "peer"),
            (-1, "peer"),
            (1, "manager"),
            (5, "peer"),
            (4, "manager"),
            (0, "peer"),
            (2, "Peer"),
            (3, "peer"),
            (6, "peer"),
        )
    ]

    result = find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    assert result.selected == 5
    assert result.found == [
        ContactCandidate("Ken", "Thompson", "Software Engineer", "https://www.linkedin.com/in/ken"),
        ContactCandidate(
            "Grace", "Hopper", "Engineering Manager", "https://www.linkedin.com/in/grace"
        ),
        ContactCandidate("Ada", "Lovelace", "Software Engineer", "https://www.linkedin.com/in/ada"),
        ContactCandidate("Alan", "Turing", None, "https://www.linkedin.com/in/alan"),
        ContactCandidate("Linus", "T", "Staff Engineer", "https://www.linkedin.com/in/linus"),
    ]
    # Grounding: the LLM's output model cannot carry names, titles or URLs.
    assert set(ContactSelection.model_fields) == {"contacts"}


def test_zero_search_results_succeeds_without_an_llm_call(
    settings: Settings, fake_http: FakeHttp, fake_llm: FakeLlm, session: MagicMock
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, json={"error": "Google hasn't returned any results."})

    result = find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    assert result.found == [] and result.results == 0
    assert fake_llm.requests == []


def test_search_and_llm_failures_raise_and_logs_hold_no_key_names_or_urls(
    settings: Settings,
    fake_http: FakeHttp,
    fake_llm: FakeLlm,
    session: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, status=500, json={})
    with caplog.at_level(logging.DEBUG), pytest.raises(SerpApiError):
        find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    fake_http.routes.clear()
    fake_http.add(SERPAPI_SEARCH_URL, json={"organic_results": RESULTS})
    fake_llm.replies = ["not json", "still not json"]
    with caplog.at_level(logging.DEBUG), pytest.raises(LlmOutputError):
        find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    fake_llm.replies = [_picks((0, "peer"))]
    with caplog.at_level(logging.DEBUG):
        find_contacts(session, settings, fake_http.client(), COMPANY, JOB, PREFERENCES)

    assert "company=7: 7 profile results, 1 selected" in caplog.text
    for secret in (API_KEY, "Lovelace", "linkedin.com/in/ada"):
        assert secret not in caplog.text


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Software Engineer II", "Software Engineer"),
        ("Sr. Data Scientist 3", "Data Scientist"),
        ("Staff Engineer (III)", "Engineer"),
        ("Software Engineer, Junior", "Software Engineer"),
        ("Principal Product Manager - I/O Platform", "Product Manager - I/O Platform"),
        ("Internal Tools Engineer", "Internal Tools Engineer"),
        ("Senior", "Senior"),
        ("Lead Software Engineer", "Software Engineer"),
        ("Senior Tech Lead", "Tech Lead"),
        ("Team Lead", "Team Lead"),
    ],
)
def test_role_title_cleanup_strips_only_seniority_and_level_words(
    title: str, expected: str
) -> None:
    assert clean_role_title(title) == expected


def test_skills_match_whole_words_case_insensitively_with_regex_specials_escaped() -> None:
    description = "Python, C++, C# and .NET. We like golang and Javascript. Go is fine."
    skills = ["python", "C++", "c#", ".NET", "Java", "Go", "PYTHON", "Rust"]
    assert match_skills(skills, description) == ["python", "C++", "c#", ".NET", "Go"]
    assert match_skills(skills, None) == []


def test_result_titles_split_on_the_first_separator() -> None:
    assert parse_result_title("Ada Lovelace - Engineer | Acme", "Acme") == (
        "Ada",
        "Lovelace",
        "Engineer",
    )
    assert parse_result_title("Ada Lovelace, PhD | Acme | LinkedIn", "acme") == (
        "Ada",
        "Lovelace",
        None,
    )
    assert parse_result_title("Cher", "Acme") == ("Cher", None, None)
    assert parse_result_title("LinkedIn", "Acme")[0] == ""


def test_the_fetcher_never_imports_or_calls_the_networking_agent() -> None:
    source = Path(fetcher.__file__).read_text(encoding="utf-8")
    assert "networking" not in source
    assert "find_contacts" not in source
    assert not hasattr(fetcher, "find_contacts")


def test_no_linkedin_automation_dependency_and_contact_search_is_never_scheduled() -> None:
    root = Path(fetcher.__file__).resolve().parents[1]
    manifests = (root / "pyproject.toml", root / "uv.lock")
    for manifest in manifests:
        text = manifest.read_text(encoding="utf-8").lower()
        for tool in ("playwright", "selenium", "pyppeteer"):
            assert tool not in text, f"{tool} in {manifest.name}"
    for module in (root / "src").rglob("*.py"):
        source = module.read_text(encoding="utf-8").lower()
        assert "playwright" not in source and "selenium" not in source, module
    # The only scheduled job is the fetcher, which never imports the agent (see the test above).
    schedule = [
        line
        for line in (root / "crontab").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert schedule and all(line.endswith("python -m src.fetcher") for line in schedule)
