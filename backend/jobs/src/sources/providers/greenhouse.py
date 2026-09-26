"""Greenhouse boards-api provider.

Ported from Career-Ops ``providers/greenhouse.mjs``
(https://github.com/career-ops-hq/career-ops).
Copyright (c) 2026 Santiago Fernández de Valderrama. Used under the MIT License.
"""

import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from src.sources.html_text import html_to_text
from src.sources.providers.base import (
    AtsProvider,
    BoardRef,
    HttpClient,
    Posting,
    company_for,
    parse_iso_datetime,
)

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
BOARD_HOSTS = frozenset(
    {
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "job-boards.eu.greenhouse.io",
        "boards.eu.greenhouse.io",
    }
)
API_HOSTS = frozenset({"boards-api.greenhouse.io", "api.greenhouse.io"})
SLUG = re.compile(r"^[A-Za-z0-9._-]+$")
JOB_ID = re.compile(r"/jobs/(\d+)")


class GreenhouseProvider(AtsProvider):
    name = "greenhouse"

    def board_url(self, board_key: str) -> str:
        return f"https://job-boards.greenhouse.io/{board_key}"

    def detect_board(self, url: str) -> str | None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        segments = [segment for segment in parts.path.split("/") if segment]
        slug: str | None = None
        if host in BOARD_HOSTS and segments:
            if segments[0] == "embed":
                # Embedded boards: boards.greenhouse.io/embed/job_app?for=<slug>&token=<id>
                slug = parse_qs(parts.query).get("for", [None])[0]
            else:
                slug = segments[0]
        elif host in API_HOSTS and len(segments) >= 3 and segments[1] == "boards":
            slug = segments[2]
        return self.normalize_key(slug) if slug and SLUG.match(slug) else None

    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        # content=true embeds every posting's body, so one request covers the whole board.
        data = client.get_json(f"{API_BASE}/{board.board_key}/jobs", params={"content": "true"})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        return [self._posting(job, board) for job in jobs or [] if _usable(job)]

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        slug = self.detect_board(url)
        job_id = _job_id(url)
        if not slug or not job_id:
            return None
        data = client.get_json(f"{API_BASE}/{slug}/jobs/{job_id}")
        return html_to_text(data.get("content")) if isinstance(data, dict) else None

    def _posting(self, job: dict, board: BoardRef) -> Posting:
        location = job.get("location") or {}
        return Posting(
            title=job["title"].strip(),
            company=company_for(board, job.get("company_name")),
            url=job["absolute_url"],
            source=self.name,
            location=(location.get("name") or "") if isinstance(location, dict) else "",
            published_at=parse_iso_datetime(job.get("first_published")),
            description=html_to_text(job.get("content")) or None,
            board=board,
        )


def _usable(job: object) -> bool:
    return isinstance(job, dict) and bool(job.get("absolute_url")) and bool(job.get("title"))


def _job_id(url: str) -> str | None:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    token = (query.get("token") or query.get("gh_jid") or [None])[0]
    if token and token.isdigit():
        return token
    match = JOB_ID.search(parts.path)
    return match.group(1) if match else None
