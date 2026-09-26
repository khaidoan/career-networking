"""iCIMS provider: the public hosted-portal search pages (HTML).

List pages carry title, location and URL but no date; ``enrich`` reads the publish date and
description from the posting page's JSON-LD, only for postings that passed the filters.

Ported from Career-Ops ``providers/icims.mjs`` and the iCIMS host handling in
``scan-ats-full.mjs`` (https://github.com/career-ops-hq/career-ops).
Copyright (c) 2026 Santiago Fernández de Valderrama. Used under the MIT License.
"""

import html
import json
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

from src.sources.html_text import html_to_text
from src.sources.providers.base import (
    BROWSER_LIKE_USER_AGENT,
    AtsProvider,
    BoardRef,
    HttpClient,
    Posting,
    SourceError,
    company_for,
    parse_iso_datetime,
)

HOST_SUFFIX = ".icims.com"
MAX_PAGES = 30
INTER_PAGE_DELAY_SECONDS = 0.25
HEADERS = {"User-Agent": BROWSER_LIKE_USER_AGENT}
LABEL = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_CARD_HREF = re.compile(r'href="([^"]*/jobs/\d+/[^"/]+/job[^"]*)"')
_CARD_TITLE = re.compile(r"<h3\b[^>]*>\s*([\s\S]*?)</h3>")
_CARD_LOCATION = re.compile(
    r"<span\b[^>]*class=[\"'][^\"']*(?<![\w-])field-label(?![\w-])[^\"']*[\"'][^>]*>\s*Location"
    r"\s*</span>\s*<span\b[^>]*>\s*([\s\S]*?)</span>"
)
_JSON_LD = re.compile(
    r"<script\b[^>]*(?<![\w-])type=[\"']application/ld\+json[\"'][^>]*>([\s\S]*?)</script>",
    re.IGNORECASE,
)
_TAGS = re.compile(r"<[^>]+>")


class PortalNotFoundError(SourceError):
    """The first search page of a portal host answered 404: no board on that host."""


class IcimsProvider(AtsProvider):
    name = "icims"

    def board_url(self, board_key: str) -> str:
        return f"https://{host_candidates(board_key)[0]}/jobs/search?ss=1"

    def detect_board(self, url: str) -> str | None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host.endswith(HOST_SUFFIX):
            return None
        label = host.removesuffix(HOST_SUFFIX)
        return label if LABEL.match(label) and label != "www" else None

    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        # The directory stores some tenants bare ("acme") and some as the full portal label
        # ("careers-acme"); a first-page 404 means "try the other host shape".
        not_found: PortalNotFoundError | None = None
        for host in host_candidates(board.board_key):
            try:
                return self._fetch_portal(f"https://{host}", board, client)
            except PortalNotFoundError as error:
                not_found = error
        raise not_found or SourceError(f"icims: no host for {board.board_key}")

    def enrich(self, posting: Posting, client: HttpClient) -> None:
        nodes = _json_ld_nodes(client.get_text(_iframe_url(posting.url), headers=HEADERS))
        job = _job_posting(nodes)
        if job is None:
            return
        posting.published_at = parse_iso_datetime(job.get("datePosted")) or posting.published_at
        posting.description = html_to_text(job.get("description")) or posting.description
        if not posting.location.strip():
            posting.location = _json_ld_location(job)
        organization = job.get("hiringOrganization")
        if isinstance(organization, dict) and posting.board and not posting.board.company_name:
            posting.company = company_for(posting.board, organization.get("name"))

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        job = _job_posting(_json_ld_nodes(client.get_text(_iframe_url(url), headers=HEADERS)))
        return html_to_text(job.get("description")) if job else None

    def _fetch_portal(self, origin: str, board: BoardRef, client: HttpClient) -> list[Posting]:
        postings: list[Posting] = []
        previous_first_url: str | None = None
        for page in range(MAX_PAGES):
            if page:
                time.sleep(INTER_PAGE_DELAY_SECONDS)
            url = f"{origin}/jobs/search?ss=1&pr={page}&in_iframe=1"
            try:
                page_html = client.get_text(url, headers=HEADERS)
            except SourceError as error:
                if page == 0 and error.status_code == 404:
                    raise PortalNotFoundError(str(error), status_code=404) from error
                raise
            page_postings = parse_search_page(page_html, origin, board)
            # Some tenants repeat the last page for out-of-range page numbers.
            if not page_postings or page_postings[0].url == previous_first_url:
                break
            previous_first_url = page_postings[0].url
            postings.extend(page_postings)
        return postings


def host_candidates(slug: str) -> list[str]:
    """Portal hosts for a directory slug, likeliest first."""
    label = slug.lower().lstrip("-")
    as_is = f"{label}{HOST_SUFFIX}"
    prefixed = f"careers-{label}{HOST_SUFFIX}"
    if label.startswith("careers-"):
        return [as_is]
    return [as_is, prefixed] if "careers" in label else [prefixed, as_is]


def parse_search_page(page_html: str, origin: str, board: BoardRef) -> list[Posting]:
    """Postings from one search results page (``iCIMS_JobCardItem`` cards)."""
    postings: list[Posting] = []
    for card in page_html.split("iCIMS_JobCardItem")[1:]:
        href = _CARD_HREF.search(card)
        title = _CARD_TITLE.search(card)
        if not href or not title:
            continue
        link = urlsplit(urljoin(origin + "/", html.unescape(href.group(1))))
        if f"{link.scheme}://{link.netloc}" != origin:
            continue
        location = _CARD_LOCATION.search(card)
        title_text = _clean(title.group(1))
        if not title_text:
            continue
        postings.append(
            Posting(
                title=title_text,
                company=company_for(board),
                url=f"{origin}{link.path}",
                source=IcimsProvider.name,
                location=_clean(location.group(1)) if location else "",
                board=board,
            )
        )
    return postings


def _clean(fragment: str) -> str:
    return " ".join(html.unescape(_TAGS.sub(" ", fragment)).split())


def _iframe_url(url: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}in_iframe=1"


def _json_ld_nodes(page_html: str) -> list[Any]:
    nodes: list[Any] = []
    for raw in _JSON_LD.findall(page_html):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, list):
            nodes.extend(data)
        elif isinstance(data, dict) and isinstance(data.get("@graph"), list):
            nodes.extend(data["@graph"])
        else:
            nodes.append(data)
    return nodes


def _job_posting(nodes: list[Any]) -> dict | None:
    for node in nodes:
        if isinstance(node, dict):
            kind = node.get("@type")
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                return node
    return None


def _json_ld_location(job: dict) -> str:
    places = job.get("jobLocation")
    for place in places if isinstance(places, list) else [places]:
        address = place.get("address") if isinstance(place, dict) else None
        if not isinstance(address, dict):
            continue
        parts = [
            str(address.get(key) or "").strip()
            for key in ("addressLocality", "addressRegion", "addressCountry")
        ]
        parts = [part for part in parts if part and part.upper() != "UNAVAILABLE"]
        if parts:
            return ", ".join(parts)
    return ""
