"""The provider interface, the normalized posting type and the shared HTTP client."""

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)
# httpx logs every request URL at INFO; SerpApi URLs carry the API key in the query string.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

USER_AGENT = "career-networking-fetcher/1.0 (self-hosted job search assistant)"
# Workday and iCIMS sit behind bot protection that turns away non-browser user agents.
BROWSER_LIKE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_CONCURRENT_REQUESTS = 24
MAX_RESPONSE_BYTES = 60 * 1024 * 1024
# Attempts per request for rate limits, gateway errors and timeouts (first try included).
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 2.0
TRANSIENT_STATUS_CODES = frozenset({429, 502, 503, 504})


class SourceError(RuntimeError):
    """A board or search could not be read; ``status_code`` is set for HTTP error responses."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class BoardRef:
    """One public job board: an ATS provider plus the board's key on that provider.

    ``board_key`` is a slug, or ``tenant/instance/site`` for Workday.
    """

    provider: str
    board_key: str
    company_name: str | None = None
    board_url: str | None = None


@dataclass
class Posting:
    """A job posting normalized across every source."""

    title: str
    company: str
    url: str
    # The provider name for ATS postings, ``google_jobs:<via>`` for Google Jobs.
    source: str
    location: str = ""
    published_at: datetime | None = None
    description: str | None = None
    board: BoardRef | None = None
    # Set when the description is a snippet worth replacing with the full text.
    description_truncated: bool = False
    extra: dict[str, Any] = field(default_factory=dict, repr=False)


class HttpClient:
    """Thread-safe ``httpx`` wrapper: identifying User-Agent, per-request timeout, a global cap
    on concurrent requests, a response size cap and one retry for transient failures."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        *,
        max_concurrency: int = MAX_CONCURRENT_REQUESTS,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        )
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._retry_backoff_seconds = retry_backoff_seconds

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        max_bytes: int = MAX_RESPONSE_BYTES,
        return_redirects: bool = False,
        **kwargs: Any,
    ) -> tuple[httpx.Response, bytes]:
        """Send a request and return the response with its body.

        Redirects are never followed; a 3xx is returned when ``return_redirects`` is set, and
        raises ``SourceError`` like every other non-2xx response otherwise.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                with self._slots:
                    response, body = self._send(method, url, max_bytes, **kwargs)
            except httpx.TimeoutException as error:
                if attempt < MAX_ATTEMPTS:
                    time.sleep(self._retry_backoff_seconds * attempt)
                    continue
                raise SourceError(f"{method} {_host(url)} timed out") from error
            except httpx.HTTPError as error:
                raise SourceError(
                    f"{method} {_host(url)} failed: {type(error).__name__}"
                ) from error
            if response.status_code in TRANSIENT_STATUS_CODES and attempt < MAX_ATTEMPTS:
                time.sleep(self._retry_backoff_seconds * attempt)
                continue
            if return_redirects and response.is_redirect:
                return response, body
            if not response.is_success:
                raise SourceError(
                    f"{method} {_host(url)} returned HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            return response, body
        raise SourceError(f"{method} {_host(url)} failed")  # pragma: no cover

    def _send(
        self, method: str, url: str, max_bytes: int, **kwargs: Any
    ) -> tuple[httpx.Response, bytes]:
        with self._client.stream(method, url, follow_redirects=False, **kwargs) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise SourceError(f"{method} {_host(url)} response is too large")
            return response, bytes(body)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        _response, body = self.request("GET", url, **kwargs)
        return _parse_json(url, body)

    def post_json(self, url: str, payload: Any, **kwargs: Any) -> Any:
        _response, body = self.request("POST", url, json=payload, **kwargs)
        return _parse_json(url, body)

    def get_text(self, url: str, **kwargs: Any) -> str:
        response, body = self.request("GET", url, **kwargs)
        return body.decode(response.encoding or "utf-8", errors="replace")


def _parse_json(url: str, body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        raise SourceError(f"{_host(url)} did not return JSON") from None


def _host(url: str) -> str:
    return urlsplit(url).hostname or "unknown host"


def create_http_client(transport: httpx.BaseTransport | None = None) -> HttpClient:
    """The client every source shares during a fetcher run (tests pass a mock transport)."""
    return HttpClient(transport)


def parse_iso_datetime(value: object) -> datetime | None:
    """An aware datetime from an ISO 8601 string (dates become UTC midnight), else ``None``."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def from_epoch_millis(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


class AtsProvider(ABC):
    """One ATS: board URLs, board detection from any link, and posting fetches."""

    name: ClassVar[str]

    @abstractmethod
    def board_url(self, board_key: str) -> str:
        """The public careers page of a board."""

    @abstractmethod
    def detect_board(self, url: str) -> str | None:
        """The board key when ``url`` is a page or API URL of this provider, else ``None``."""

    @abstractmethod
    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        """Every open posting on the board. ``since`` lets paginated providers stop early."""

    def normalize_key(self, board_key: str) -> str:
        """The canonical spelling of a board key; slugs are case-insensitive on most ATSs."""
        return board_key.lower()

    def enrich(self, posting: Posting, client: HttpClient) -> None:
        """Fill in the publish date and description when the board list does not carry them.

        Called only for postings that already passed the title and country filters. Providers
        whose board list already carries both keep this default, which changes nothing.
        """
        return None

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        """The full description of the posting at ``url`` through the provider's API."""
        return None

    def board_ref(self, board_key: str, company_name: str | None = None) -> BoardRef:
        return BoardRef(
            provider=self.name,
            board_key=board_key,
            company_name=company_name,
            board_url=self.board_url(board_key),
        )


def company_for(board: BoardRef, reported: object = None) -> str:
    """The company name reported by the posting, else the board's, else its slug or tenant."""
    if isinstance(reported, str) and reported.strip():
        return reported.strip()
    return board.company_name or board.board_key.split("/")[0]
