"""Google Jobs discovery through SerpApi, with SerpApi and every other HTTP call mocked."""

import ipaddress
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.config import Settings
from src.sources.filters import SearchCriteria
from src.sources.google_jobs import (
    SERPAPI_SEARCH_URL,
    is_due,
    recover_full_description,
    run_google_jobs,
)
from src.sources.state import FileFetcherState
from tests.conftest import FakeHttp, fixture_json, fixture_text

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
CRITERIA = SearchCriteria(desired_titles=("Backend Engineer",), country="US")
API_KEY = "serpapi-secret-key"


@pytest.fixture
def state(tmp_path: Path) -> FileFetcherState:
    return FileFetcherState(tmp_path / "_fetcher")


@pytest.fixture
def serpapi_settings(test_settings: Settings) -> Settings:
    return test_settings.model_copy(update={"serpapi_api_key": SecretStr(API_KEY)})


def test_without_an_api_key_the_source_is_skipped_with_one_log_line_and_no_requests(
    test_settings: Settings,
    fake_http: FakeHttp,
    state: FileFetcherState,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="src.sources.google_jobs"):
        result = run_google_jobs(test_settings, CRITERIA, fake_http.client(), state, NOW)

    assert result is None
    assert fake_http.requests == []
    assert [record.getMessage() for record in caplog.records] == [
        "Google Jobs skipped: no SERPAPI_API_KEY"
    ]


def test_nothing_is_searched_before_the_interval_has_passed(
    serpapi_settings: Settings, fake_http: FakeHttp, state: FileFetcherState
) -> None:
    state.set_google_jobs_last_run(NOW - timedelta(hours=22))

    result = run_google_jobs(serpapi_settings, CRITERIA, fake_http.client(), state, NOW)

    assert result is None
    assert fake_http.requests == []
    assert state.get_google_jobs_last_run() == NOW - timedelta(hours=22)


def test_a_daily_run_starting_slightly_early_is_still_due(
    serpapi_settings: Settings, state: FileFetcherState
) -> None:
    # Yesterday's run recorded its start a few minutes later than today's cron start.
    state.set_google_jobs_last_run(NOW - timedelta(hours=23, minutes=55))
    assert is_due(serpapi_settings, state, NOW)
    state.set_google_jobs_last_run(NOW - timedelta(hours=22, minutes=59))
    assert not is_due(serpapi_settings, state, NOW)


def test_results_prefer_ats_apply_links_return_boards_and_recover_full_descriptions(
    serpapi_settings: Settings,
    fake_http: FakeHttp,
    state: FileFetcherState,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, json=fixture_json("serpapi/google_jobs_page1.json"))
    fake_http.add(SERPAPI_SEARCH_URL, json=fixture_json("serpapi/google_jobs_page2.json"))
    fake_http.add(
        "https://api.lever.co/v0/postings/globex/7f3c2a10-aaaa-bbbb-cccc-1234567890ab",
        json=fixture_json("ats/lever.json")[0],
    )
    fake_http.add(
        "https://careers.contoso.example/jobs/9", text=fixture_text("serpapi/apply_page.html")
    )
    monkeypatch.setattr(
        "src.sources.google_jobs._resolve_addresses",
        lambda _host: [ipaddress.ip_address("93.184.216.34")],
    )
    client = fake_http.client()

    with caplog.at_level(logging.DEBUG):
        result = run_google_jobs(serpapi_settings, CRITERIA, client, state, NOW)
    assert result is not None
    searches = [request for request in fake_http.requests if request.url.host == "serpapi.com"]

    assert result.searches == 2 and result.failed_searches == 0
    assert searches[0].url.params["engine"] == "google_jobs"
    assert searches[0].url.params["q"] == "Backend Engineer"
    assert searches[0].url.params["location"] == "United States"
    assert searches[0].url.params["gl"] == "us"
    assert searches[1].url.params["next_page_token"] == "token-page-2"
    assert state.get_google_jobs_last_run() == NOW
    assert API_KEY not in caplog.text

    acme, contoso, globex = result.postings
    assert acme.url == "https://job-boards.greenhouse.io/acme/jobs/101?gh_src=google"
    assert acme.source == "google_jobs:LinkedIn"
    assert acme.published_at == NOW - timedelta(days=3)
    assert acme.board is not None and (acme.board.provider, acme.board.board_key) == (
        "greenhouse",
        "acme",
    )
    assert not acme.description_truncated
    assert contoso.url == "https://careers.contoso.example/jobs/9"
    assert contoso.source == "google_jobs:Indeed"
    assert contoso.board is None and contoso.published_at is None
    assert [(board.provider, board.board_key, board.company_name) for board in result.boards] == [
        ("greenhouse", "acme", "Acme Corp"),
        ("lever", "globex", "Globex"),
    ]

    for posting in result.postings:
        recover_full_description(posting, client)

    assert contoso.description == (
        "Backend Engineer II\nJoin Contoso to build billing APIs used by millions.\n"
        "Design idempotent payment flows\nOperate PostgreSQL at scale\n"
        "We offer a remote-first culture and a generous learning budget."
    )
    assert globex.description is not None
    assert globex.description.startswith("Own our data pipelines.")
    assert not contoso.description_truncated and not globex.description_truncated
