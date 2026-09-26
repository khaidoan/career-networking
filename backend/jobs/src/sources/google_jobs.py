"""Optional Google Jobs discovery through SerpApi's ``google_jobs`` engine.

Enabled only when ``SERPAPI_API_KEY`` is set, and run at most once per
``CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS``. Each run sends one query per desired title and
follows ``next_page_token`` for up to ``MAX_PAGES_PER_TITLE`` pages, so SerpApi usage is at most
titles x pages searches per interval. The API key travels in the query string, so request URLs
are never logged.
"""

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin, urlsplit

from src.config import Settings
from src.sources.filters import SearchCriteria
from src.sources.html_text import html_to_text
from src.sources.providers import detect_board_ref, get_provider
from src.sources.providers.base import BoardRef, HttpClient, Posting, SourceError
from src.sources.state import FetcherState
from src.vocabularies import COUNTRIES

logger = logging.getLogger(__name__)

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
# Keep in sync with the "Google Jobs (optional)" section of the README.
MAX_PAGES_PER_TITLE = 3
SEARCH_LANGUAGE = "en"
SEARCH_TIMEOUT_SECONDS = 60.0
# Google's country codes differ from ISO 3166-1 for a few countries.
GOOGLE_COUNTRY_CODES = {"GB": "uk"}
NO_RESULTS_ERROR = "hasn't returned any results"

# A description shorter than this, or ending in an ellipsis, is treated as a truncated snippet.
MIN_FULL_DESCRIPTION_CHARS = 300
APPLY_PAGE_MAX_BYTES = 3 * 1024 * 1024
APPLY_PAGE_MAX_REDIRECTS = 3

_RELATIVE_AGE = re.compile(r"(\d+)(\+?)\s*(minute|hour|day|week|month)s?\s+ago", re.IGNORECASE)
_AGE_UNITS = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
}


@dataclass
class GoogleJobsResult:
    postings: list[Posting] = field(default_factory=list)
    # Supported ATS boards found in apply links, to track with discovered_via = google_jobs.
    boards: list[BoardRef] = field(default_factory=list)
    searches: int = 0
    failed_searches: int = 0


def is_enabled(settings: Settings) -> bool:
    return settings.serpapi_api_key is not None


def is_due(settings: Settings, state: FetcherState, now: datetime) -> bool:
    last_run = state.get_google_jobs_last_run()
    interval = timedelta(hours=settings.google_jobs_interval_hours)
    return last_run is None or now - last_run >= interval


def run_google_jobs(
    settings: Settings,
    criteria: SearchCriteria,
    client: HttpClient,
    state: FetcherState,
    now: datetime | None = None,
) -> GoogleJobsResult | None:
    """Search Google Jobs when enabled and due; ``None`` when the source was skipped."""
    now = now or datetime.now(UTC)
    if settings.serpapi_api_key is None:
        logger.info("Google Jobs skipped: no SERPAPI_API_KEY")
        return None
    if not is_due(settings, state, now):
        logger.info("Google Jobs skipped: next search is not due yet")
        return None

    result = GoogleJobsResult()
    seen_urls: set[str] = set()
    seen_boards: set[tuple[str, str]] = set()
    api_key = settings.serpapi_api_key.get_secret_value()
    for title in criteria.desired_titles:
        for raw in _search_title(api_key, title, criteria.country, client, result):
            posting = map_result(raw, now)
            if posting is None or posting.url in seen_urls:
                continue
            seen_urls.add(posting.url)
            result.postings.append(posting)
            for board in _apply_boards(raw):
                if (board.provider, board.board_key) not in seen_boards:
                    seen_boards.add((board.provider, board.board_key))
                    result.boards.append(board)

    # Only a run in which SerpApi answered counts; otherwise the next fetcher run retries.
    if result.searches:
        state.set_google_jobs_last_run(now)
    logger.info(
        "Google Jobs: %d searches (%d failed), %d postings, %d ATS boards",
        result.searches,
        result.failed_searches,
        len(result.postings),
        len(result.boards),
    )
    return result


def _search_title(
    api_key: str, title: str, country: str, client: HttpClient, result: GoogleJobsResult
) -> list[dict]:
    """Raw ``jobs_results`` for one title across up to ``MAX_PAGES_PER_TITLE`` pages."""
    params = {
        "engine": "google_jobs",
        "q": title,
        "location": serpapi_location(country),
        "gl": GOOGLE_COUNTRY_CODES.get(country, country.lower()),
        "hl": SEARCH_LANGUAGE,
        "api_key": api_key,
    }
    results: list[dict] = []
    for _page in range(MAX_PAGES_PER_TITLE):
        try:
            data = client.get_json(
                SERPAPI_SEARCH_URL, params=params, timeout=SEARCH_TIMEOUT_SECONDS
            )
        except SourceError as error:
            result.failed_searches += 1
            logger.warning("Google Jobs search failed: %s", error)
            break
        error_message = data.get("error") if isinstance(data, dict) else "unexpected response"
        if error_message and NO_RESULTS_ERROR not in str(error_message):
            result.failed_searches += 1
            logger.warning("Google Jobs search failed: %s", error_message)
            break
        result.searches += 1
        page_results = data.get("jobs_results") or []
        results.extend(item for item in page_results if isinstance(item, dict))
        next_token = (data.get("serpapi_pagination") or {}).get("next_page_token")
        if not next_token or not page_results:
            break
        params["next_page_token"] = next_token
    return results


def serpapi_location(country: str) -> str:
    """A location name SerpApi understands; formal ISO names ("Korea, Republic of") use an alias."""
    entry = COUNTRIES[country]
    if ("," in entry.name or "(" in entry.name) and entry.aliases:
        return entry.aliases[0]
    return entry.name


def map_result(raw: dict, now: datetime) -> Posting | None:
    """A posting from one SerpApi job result; results without an apply link are skipped."""
    title = str(raw.get("title") or "").strip()
    company = str(raw.get("company_name") or "").strip()
    links = _apply_links(raw)
    if not title or not company or not links:
        return None
    # Prefer a supported ATS link: it gives the real posting URL and a board to track.
    url, board = links[0], None
    for link in links:
        detected = detect_board_ref(link, company)
        if detected is not None:
            url, board = link, detected
            break
    description = str(raw.get("description") or "").strip() or _highlights(raw)
    via = re.sub(r"^via\s+", "", str(raw.get("via") or "").strip(), flags=re.IGNORECASE)
    extensions = raw.get("detected_extensions") or {}
    return Posting(
        title=title,
        company=company,
        url=url,
        source=f"google_jobs:{via or 'Google Jobs'}",
        location=str(raw.get("location") or "").strip(),
        published_at=parse_posted_at(extensions.get("posted_at"), now),
        description=description or None,
        board=board,
        description_truncated=is_truncated(description),
    )


def _apply_links(raw: dict) -> list[str]:
    links = []
    for option in raw.get("apply_options") or []:
        link = option.get("link") if isinstance(option, dict) else None
        if isinstance(link, str) and urlsplit(link).scheme in ("http", "https"):
            links.append(link)
    return links


def _apply_boards(raw: dict) -> list[BoardRef]:
    company = str(raw.get("company_name") or "").strip() or None
    return [board for link in _apply_links(raw) if (board := detect_board_ref(link, company))]


def _highlights(raw: dict) -> str:
    sections = []
    for highlight in raw.get("job_highlights") or []:
        if isinstance(highlight, dict):
            items = [str(item) for item in highlight.get("items") or []]
            sections.append("\n".join([str(highlight.get("title") or ""), *items]).strip())
    return "\n".join(section for section in sections if section)


def parse_posted_at(label: object, now: datetime) -> datetime | None:
    """``now`` minus a relative age such as "3 days ago"; open-ended ages ("30+") are unknown."""
    if not isinstance(label, str):
        return None
    match = _RELATIVE_AGE.search(label)
    if not match or match.group(2):
        return None
    return now - int(match.group(1)) * _AGE_UNITS[match.group(3).lower()]


def is_truncated(description: str) -> bool:
    text = description.rstrip()
    return len(text) < MIN_FULL_DESCRIPTION_CHARS or text.endswith(("…", "..."))


def recover_full_description(posting: Posting, client: HttpClient) -> None:
    """Replace a truncated snippet with the full text; on any failure the snippet stays.

    Supported ATS links use the provider's API; other links are fetched as a page and stripped.
    Call this only for postings that are about to be ingested.
    """
    if not posting.description_truncated:
        return
    try:
        if posting.board is not None:
            text = get_provider(posting.board.provider).fetch_description(posting.url, client)
        else:
            text = html_to_text(fetch_public_page(posting.url, client), skip_page_chrome=True)
    except Exception as error:
        logger.info("Full description unavailable for a %s posting: %s", posting.source, error)
        return
    if text and len(text) > len(posting.description or ""):
        posting.description = text
        posting.description_truncated = False


def fetch_public_page(url: str, client: HttpClient) -> str:
    """GET a page on the public internet, following a few redirects, each checked first."""
    for _hop in range(APPLY_PAGE_MAX_REDIRECTS + 1):
        _require_public_url(url)
        response, body = client.request(
            "GET", url, max_bytes=APPLY_PAGE_MAX_BYTES, return_redirects=True
        )
        if response.is_redirect and "location" in response.headers:
            url = urljoin(url, response.headers["location"])
            continue
        return body.decode(response.encoding or "utf-8", errors="replace")
    raise SourceError("too many redirects")


def _require_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise SourceError("not an http(s) URL")
    if not all(address.is_global for address in _resolve_addresses(parts.hostname)):
        raise SourceError("refusing to fetch a non-public address")


def _resolve_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as error:
        raise SourceError(f"cannot resolve {host}") from error
    addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses:
        raise SourceError(f"cannot resolve {host}")
    return addresses
