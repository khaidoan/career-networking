"""The shared SerpApi helper, with every HTTP call mocked."""

import logging

import pytest

from src.sources.serpapi import SERPAPI_SEARCH_URL, SerpApiError, serpapi_search
from tests.conftest import FakeHttp

API_KEY = "serpapi-secret-key"


def test_a_successful_search_returns_the_body_and_sends_engine_params_and_key(
    fake_http: FakeHttp,
) -> None:
    body = {"organic_results": [{"link": "https://example.com"}]}
    fake_http.add(SERPAPI_SEARCH_URL, json=body)

    data = serpapi_search(
        fake_http.client(), api_key=API_KEY, engine="google", params={"q": "hello", "num": 20}
    )

    assert data == body
    (request,) = fake_http.requests
    assert dict(request.url.params) == {
        "engine": "google",
        "q": "hello",
        "num": "20",
        "api_key": API_KEY,
    }


def test_http_failures_and_body_errors_raise_serpapi_error_but_no_results_is_empty(
    fake_http: FakeHttp,
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, status=401, json={"error": "Invalid API key."})
    fake_http.add(SERPAPI_SEARCH_URL, json={"error": "Your account has run out of searches."})
    fake_http.add(
        SERPAPI_SEARCH_URL, json={"error": "Google hasn't returned any results for this query."}
    )
    fake_http.add(SERPAPI_SEARCH_URL, json=["not", "an", "object"])
    client = fake_http.client()

    def search() -> dict:
        return serpapi_search(client, api_key=API_KEY, engine="google", params={"q": "x"})

    with pytest.raises(SerpApiError, match="HTTP 401"):
        search()
    with pytest.raises(SerpApiError, match="run out of searches"):
        search()
    assert search() == {}
    with pytest.raises(SerpApiError, match="unexpected response"):
        search()


def test_the_api_key_never_appears_in_logs_or_error_messages(
    fake_http: FakeHttp, caplog: pytest.LogCaptureFixture
) -> None:
    fake_http.add(SERPAPI_SEARCH_URL, json={"organic_results": []})
    fake_http.add(SERPAPI_SEARCH_URL, status=500, json={})
    client = fake_http.client()

    with caplog.at_level(logging.DEBUG):
        serpapi_search(client, api_key=API_KEY, engine="google", params={"q": "x"})
        with pytest.raises(SerpApiError) as failure:
            serpapi_search(client, api_key=API_KEY, engine="google", params={"q": "x"})

    assert API_KEY not in caplog.text
    assert API_KEY not in str(failure.value)
