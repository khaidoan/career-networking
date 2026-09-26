"""ATS providers, posting filters and the directory sweep, with every HTTP call mocked."""

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from src.sources import ats_sweep
from src.sources.ats_sweep import directory_url, run_sweep_batch
from src.sources.boards import scan_board
from src.sources.filters import SearchCriteria, location_matches
from src.sources.providers import PROVIDERS, detect_board, get_provider
from src.sources.providers.base import BoardRef, Posting
from src.sources.state import FileFetcherState
from src.vocabularies import ATS_PROVIDERS
from tests.conftest import FakeHttp, fixture_json, fixture_text

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
BACKEND_US = SearchCriteria(desired_titles=("Backend Engineer",), country="US")


def _fetch(fake_http: FakeHttp, provider: str, board_key: str) -> list[Posting]:
    ats = get_provider(provider)
    with fake_http.client() as client:
        postings = ats.fetch_postings(ats.board_ref(board_key), client)
        if postings and (postings[0].published_at is None or not postings[0].description):
            ats.enrich(postings[0], client)
    return postings


def test_greenhouse_lever_and_ashby_boards_map_to_normalized_postings(
    fake_http: FakeHttp,
) -> None:
    fake_http.add(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        json=fixture_json("ats/greenhouse.json"),
    )
    fake_http.add("https://api.lever.co/v0/postings/globex", json=fixture_json("ats/lever.json"))
    fake_http.add(
        "https://api.ashbyhq.com/posting-api/job-board/Initech",
        json=fixture_json("ats/ashby.json"),
    )

    greenhouse = _fetch(fake_http, "greenhouse", "acme")[0]
    lever = _fetch(fake_http, "lever", "globex")
    ashby = _fetch(fake_http, "ashby", "Initech")

    assert (greenhouse.title, greenhouse.company, greenhouse.location) == (
        "Senior Backend Engineer",
        "Acme Corp",
        "Austin, Texas",
    )
    assert greenhouse.url == "https://job-boards.greenhouse.io/acme/jobs/101"
    assert greenhouse.published_at == datetime(2026, 9, 23, 14, 0, tzinfo=UTC)
    assert greenhouse.description == "Build & ship APIs in Python.\n5+ years"
    assert greenhouse.board == BoardRef(
        "greenhouse", "acme", None, "https://job-boards.greenhouse.io/acme"
    )

    assert len(lever) == 1
    assert lever[0].company == "globex"
    assert lever[0].location == "Toronto; Vancouver; CA"
    assert lever[0].published_at == datetime.fromtimestamp(1790157600, tz=UTC)
    assert lever[0].description is not None
    assert "Requirements\nSQL\nAirflow" in lever[0].description

    assert len(ashby) == 1
    assert ashby[0].url == "https://jobs.ashbyhq.com/Initech/c1d2"
    assert ashby[0].location == "Berlin · Munich · Germany · Remote"
    assert ashby[0].published_at == datetime(2026, 9, 22, 8, 30, tzinfo=UTC)
    assert ashby[0].description == "Train and ship models."


def test_workday_icims_and_bamboohr_boards_map_and_enrich_postings(fake_http: FakeHttp) -> None:
    fake_http.add(
        "https://umbrella.wd5.myworkdayjobs.com/wday/cxs/umbrella/External/jobs",
        json=fixture_json("ats/workday.json"),
        method="POST",
    )
    fake_http.add(
        "https://umbrella.wd5.myworkdayjobs.com/wday/cxs/umbrella/External"
        "/job/Remote-USA/Site-Reliability-Engineer_R123",
        json=fixture_json("ats/workday_detail.json"),
    )
    fake_http.add(
        "https://careers-hooli.icims.com/jobs/search", text=fixture_text("ats/icims_search.html")
    )
    fake_http.add(
        "https://careers-hooli.icims.com/jobs/4521/software-engineer/job",
        text=fixture_text("ats/icims_job.html"),
    )
    fake_http.add(
        "https://initrode.bamboohr.com/careers/list", json=fixture_json("ats/bamboohr_list.json")
    )
    fake_http.add(
        "https://initrode.bamboohr.com/careers/42/detail",
        json=fixture_json("ats/bamboohr_detail.json"),
    )

    workday = _fetch(fake_http, "workday", "umbrella/wd5/External")
    # A page with an entry shorter than PAGE_SIZE ends pagination (one POST); then one detail GET.
    icims = _fetch(fake_http, "icims", "hooli")
    bamboohr = _fetch(fake_http, "bamboohr", "initrode")

    assert [posting.title for posting in workday] == ["Site Reliability Engineer", "Old Engineer"]
    assert workday[0].url == (
        "https://umbrella.wd5.myworkdayjobs.com/External/job/Remote-USA/Site-Reliability-Engineer_R123"
    )
    assert workday[0].company == "Umbrella Inc."
    assert workday[0].published_at == datetime(2026, 9, 24, tzinfo=UTC)
    assert workday[0].description == "Keep production healthy.\nOn-call rotation."
    assert workday[0].location == "Remote, USA · United States of America"
    assert workday[1].published_at is None and workday[1].location == ""

    assert len(icims) == 1
    assert icims[0].title == "Software Engineer & Tools"
    assert icims[0].url == "https://careers-hooli.icims.com/jobs/4521/software-engineer/job"
    assert icims[0].location == "US-CA-Mountain View"
    assert icims[0].company == "Hooli"
    assert icims[0].published_at == datetime(2026, 9, 21, tzinfo=UTC)
    assert icims[0].description == "Build internal tools."

    assert len(bamboohr) == 1
    assert bamboohr[0].url == "https://initrode.bamboohr.com/careers/42"
    assert bamboohr[0].location == "Denver, Colorado, United States"
    assert bamboohr[0].published_at == datetime(2026, 9, 20, tzinfo=UTC)
    assert bamboohr[0].description == "Help customers succeed."


def test_board_scan_keeps_matching_postings_and_drops_wrong_country_undated_and_stale(
    fake_http: FakeHttp,
) -> None:
    fake_http.add(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        json=fixture_json("ats/greenhouse.json"),
    )
    board = get_provider("greenhouse").board_ref("acme")

    with fake_http.client() as client:
        scan = scan_board(board, BACKEND_US, client, NOW)

    assert scan.fetched == 6
    # Kept: Austin, Texas (US state name) and a plain "Remote" posting with no other country.
    # Dropped: London, UK (wrong country), undated, published 55 days ago, and a designer role.
    assert [posting.url.rsplit("/", 1)[1] for posting in scan.matches] == ["101", "106"]


@pytest.mark.parametrize(
    ("location", "country", "expected"),
    [
        ("Toronto, ON", "CA", True),
        ("San Francisco, CA", "US", True),
        ("Remote - Canada", "US", False),
        ("Remote (EMEA)", "US", False),
        ("Berlin, Germany", "DE", True),
        ("New Jersey", "JE", False),
    ],
)
def test_location_matching_handles_states_provinces_and_regions(
    location: str, country: str, expected: bool
) -> None:
    assert location_matches(location, country) is expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://job-boards.greenhouse.io/Acme/jobs/123?gh_src=abc", ("greenhouse", "acme")),
        ("https://boards.greenhouse.io/embed/job_app?for=acme&token=123", ("greenhouse", "acme")),
        ("https://jobs.lever.co/globex/7f3c2a10/apply", ("lever", "globex")),
        ("https://jobs.ashbyhq.com/Initech/c1d2/application", ("ashby", "Initech")),
        (
            "https://Umbrella.wd5.myworkdayjobs.com/en-US/External/job/Remote/SRE_R1",
            ("workday", "umbrella/wd5/External"),
        ),
        (
            "https://careers-hooli.icims.com/jobs/4521/software-engineer/job",
            ("icims", "careers-hooli"),
        ),
        ("https://initrode.bamboohr.com/careers/42", ("bamboohr", "initrode")),
        ("https://www.linkedin.com/jobs/view/123", None),
        ("https://www.bamboohr.com/careers", None),
    ],
)
def test_detect_board_maps_apply_urls_to_provider_and_board_key(
    url: str, expected: tuple[str, str] | None
) -> None:
    assert tuple(PROVIDERS) == ATS_PROVIDERS
    assert detect_board(url) == expected


def test_sweep_uses_stale_directory_cache_rotates_batches_and_skips_without_any_cache(
    fake_http: FakeHttp, tmp_path: os.PathLike[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Production scans everything once a day; a multi-run pass exercises the rotation cursor.
    monkeypatch.setattr(ats_sweep, "RUNS_PER_FULL_PASS", 48)
    state = FileFetcherState(tmp_path / "_fetcher")
    cache = state.directory_cache_dir() / "greenhouse_companies.json"
    cache.write_text(json.dumps([f"company{number}" for number in range(96)] + ["bad slug!"]))
    two_days_ago = (NOW - timedelta(days=2)).timestamp()
    os.utime(cache, (two_days_ago, two_days_ago))
    fake_http.add(directory_url("lever"), json=["globex"])
    fake_http.add(
        "https://boards-api.greenhouse.io/v1/boards/company1/jobs",
        json=fixture_json("ats/greenhouse.json"),
    )

    with fake_http.client() as client:
        first = run_sweep_batch(BACKEND_US, client, state, NOW)
        second = run_sweep_batch(BACKEND_US, client, state, NOW)

    # 96 greenhouse boards (stale cache; download failed) + 1 lever board, interleaved.
    # ceil(97 / 48) = 3 boards per run: greenhouse company0, lever globex, greenhouse company1.
    assert first.boards_scanned == 3
    assert state.get_sweep_cursor() == 6  # advanced by 3 on each of the two runs
    assert [scan.board.board_key for scan in first.matched_boards] == ["company1"]
    assert len(first.matched_boards[0].matches) == 2
    assert first.boards_failed == 2  # company0 and globex have no mocked board API
    assert second.boards_scanned == 3 and second.matched_boards == []
    assert json.loads(cache.read_text())[0] == "company0"  # stale cache kept, not overwritten

    empty_state = FileFetcherState(tmp_path / "empty")
    with FakeHttp().client() as offline:
        skipped = run_sweep_batch(BACKEND_US, offline, empty_state, NOW)
    assert skipped.skipped and empty_state.get_sweep_cursor() == 0


def test_state_store_resets_corrupt_files_to_defaults(tmp_path: os.PathLike[str]) -> None:
    state = FileFetcherState(tmp_path / "_fetcher")
    state.set_sweep_cursor(12)
    state.set_google_jobs_last_run(NOW)
    assert (state.get_sweep_cursor(), state.get_google_jobs_last_run()) == (12, NOW)

    (tmp_path / "_fetcher" / "state.json").write_text("{not json")

    assert state.get_sweep_cursor() == 0
    assert state.get_google_jobs_last_run() is None
