"""Lever ``/v0/postings`` provider.

Ported from Career-Ops ``providers/lever.mjs`` (https://github.com/career-ops-hq/career-ops).
Copyright (c) 2026 Santiago Fernández de Valderrama. Used under the MIT License.
"""

import re
from datetime import datetime
from urllib.parse import urlsplit

from src.sources.html_text import html_to_text
from src.sources.providers.base import (
    AtsProvider,
    BoardRef,
    HttpClient,
    Posting,
    company_for,
    from_epoch_millis,
)

API_BASE = "https://api.lever.co/v0/postings"
BOARD_HOST = "jobs.lever.co"
API_HOST = "api.lever.co"
SLUG = re.compile(r"^[A-Za-z0-9._-]+$")
# The whole board, descriptions included, arrives in one response; large boards are slow.
BOARD_TIMEOUT_SECONDS = 45.0


class LeverProvider(AtsProvider):
    name = "lever"

    def board_url(self, board_key: str) -> str:
        return f"https://{BOARD_HOST}/{board_key}"

    def detect_board(self, url: str) -> str | None:
        segments, host = _segments(url)
        slug: str | None = None
        if host == BOARD_HOST and segments:
            slug = segments[0]
        elif host == API_HOST and len(segments) >= 3 and segments[:2] == ["v0", "postings"]:
            slug = segments[2]
        return self.normalize_key(slug) if slug and SLUG.match(slug) else None

    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        data = client.get_json(
            f"{API_BASE}/{board.board_key}", params={"mode": "json"}, timeout=BOARD_TIMEOUT_SECONDS
        )
        if not isinstance(data, list):
            return []
        return [self._posting(job, board) for job in data if _usable(job)]

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        slug = self.detect_board(url)
        segments, _host = _segments(url)
        if not slug or len(segments) < 2:
            return None
        data = client.get_json(f"{API_BASE}/{slug}/{segments[1]}", params={"mode": "json"})
        return _description(data) if isinstance(data, dict) else None

    def _posting(self, job: dict, board: BoardRef) -> Posting:
        return Posting(
            title=job["text"].strip(),
            company=company_for(board),
            url=job["hostedUrl"],
            source=self.name,
            location=_location(job),
            published_at=from_epoch_millis(job.get("createdAt")),
            description=_description(job) or None,
            board=board,
        )


def _segments(url: str) -> tuple[list[str], str]:
    parts = urlsplit(url)
    return [segment for segment in parts.path.split("/") if segment], (parts.hostname or "").lower()


def _usable(job: object) -> bool:
    return isinstance(job, dict) and bool(job.get("hostedUrl")) and bool(job.get("text"))


def _location(job: dict) -> str:
    """Primary location, every other location, the country code and the remote flag."""
    categories = job.get("categories") or {}
    places = [categories.get("location"), *(categories.get("allLocations") or [])]
    if isinstance(job.get("country"), str):
        places.append(job["country"])
    if str(job.get("workplaceType", "")).lower() == "remote":
        places.append("Remote")
    unique: list[str] = []
    for place in places:
        if isinstance(place, str) and place.strip() and place.strip() not in unique:
            unique.append(place.strip())
    return "; ".join(unique)


def _description(job: dict) -> str:
    sections = [job.get("descriptionPlain") or ""]
    for item in job.get("lists") or []:
        if isinstance(item, dict):
            sections.append(f"{item.get('text', '')}\n{html_to_text(item.get('content'))}")
    sections.append(job.get("additionalPlain") or "")
    return "\n\n".join(section.strip() for section in sections if section and section.strip())
