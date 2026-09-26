"""The one place SerpApi requests are built, shared by Google Jobs and contact search.

The API key travels in the query string, so request URLs and params are never logged here, and
callers must not log them either. ``SourceError`` messages from ``HttpClient`` carry only the
host, never the query string.
"""

from typing import Any

from src.sources.providers.base import HttpClient, SourceError

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
SEARCH_TIMEOUT_SECONDS = 60.0
# SerpApi reports an empty result page as an ``error`` containing this text; it is not a failure.
NO_RESULTS_ERROR = "hasn't returned any results"
UNEXPECTED_RESPONSE = "unexpected response"


class SerpApiError(RuntimeError):
    """A SerpApi search failed: HTTP error, timeout, non-JSON body or an ``error`` in the body."""


def serpapi_search(
    client: HttpClient, *, api_key: str, engine: str, params: dict[str, Any]
) -> dict[str, Any]:
    """One SerpApi search; the parsed JSON body, or ``{}`` when SerpApi found no results.

    Uses the shared ``HttpClient`` (retry for transient errors and response size cap). Raises
    ``SerpApiError`` for every failure; its message never contains the API key.
    """
    request_params = {"engine": engine, **params, "api_key": api_key}
    try:
        data = client.get_json(
            SERPAPI_SEARCH_URL, params=request_params, timeout=SEARCH_TIMEOUT_SECONDS
        )
    except SourceError as error:
        raise SerpApiError(str(error)) from error
    if not isinstance(data, dict):
        raise SerpApiError(UNEXPECTED_RESPONSE)
    error_message = data.get("error")
    if error_message:
        if NO_RESULTS_ERROR in str(error_message):
            return {}
        raise SerpApiError(str(error_message))
    return data
