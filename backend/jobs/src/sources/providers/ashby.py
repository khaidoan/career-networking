"""Ashby posting-api provider.

Ported from Career-Ops ``providers/ashby.mjs`` (https://github.com/career-ops-hq/career-ops).
Copyright (c) 2026 Santiago Fernández de Valderrama. Used under the MIT License.
"""

import re
from datetime import datetime
from urllib.parse import urlsplit

from src.sources.providers.base import (
    AtsProvider,
    BoardRef,
    HttpClient,
    Posting,
    company_for,
    parse_iso_datetime,
)

API_BASE = "https://api.ashbyhq.com/posting-api/job-board"
BOARD_HOST = "jobs.ashbyhq.com"
API_HOST = "api.ashbyhq.com"
SLUG = re.compile(r"^[A-Za-z0-9._%-]+$")
# Ashby's posting-api has a slow, size-independent response time.
BOARD_TIMEOUT_SECONDS = 45.0


class AshbyProvider(AtsProvider):
    name = "ashby"

    def board_url(self, board_key: str) -> str:
        return f"https://{BOARD_HOST}/{board_key}"

    def normalize_key(self, board_key: str) -> str:
        # Ashby board names are case-sensitive ("DeepL").
        return board_key

    def detect_board(self, url: str) -> str | None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        segments = [segment for segment in parts.path.split("/") if segment]
        slug: str | None = None
        if host == BOARD_HOST and segments:
            slug = segments[0]
        elif (
            host == API_HOST and len(segments) >= 3 and segments[:2] == ["posting-api", "job-board"]
        ):
            slug = segments[2]
        return slug if slug and SLUG.match(slug) else None

    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        data = client.get_json(
            f"{API_BASE}/{board.board_key}",
            params={"includeCompensation": "true"},
            timeout=BOARD_TIMEOUT_SECONDS,
        )
        jobs = data.get("jobs") if isinstance(data, dict) else None
        return [self._posting(job, board) for job in jobs or [] if _usable(job)]

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        # The public API has no single-posting endpoint; find the posting on its board.
        slug = self.detect_board(url)
        if not slug:
            return None
        wanted = url.split("?")[0].rstrip("/").lower()
        for posting in self.fetch_postings(self.board_ref(slug), client):
            if posting.url.split("?")[0].rstrip("/").lower() == wanted:
                return posting.description
        return None

    def _posting(self, job: dict, board: BoardRef) -> Posting:
        return Posting(
            title=job["title"].strip(),
            company=company_for(board),
            url=job["jobUrl"],
            source=self.name,
            location=_location(job),
            published_at=parse_iso_datetime(job.get("publishedAt")),
            description=(job.get("descriptionPlain") or "").strip() or None,
            board=board,
        )


def _usable(job: object) -> bool:
    return (
        isinstance(job, dict)
        and bool(job.get("jobUrl"))
        and bool(job.get("title"))
        and job.get("isListed", True) is not False
    )


def _location(job: dict) -> str:
    """Primary and secondary locations, their postal address countries and the remote flag."""
    places: list[object] = [job.get("location")]
    places.extend(_address_parts(job.get("address")))
    for secondary in job.get("secondaryLocations") or []:
        if isinstance(secondary, dict):
            places.append(secondary.get("location"))
            places.extend(_address_parts(secondary.get("address")))
    workplace = str(job.get("workplaceType") or "").strip().lower()
    # workplaceType wins when present; boards pair isRemote=true with "Hybrid" for office roles.
    remote = workplace == "remote" if workplace else job.get("isRemote") is True
    if remote:
        places.append("Remote")
    unique: list[str] = []
    for place in places:
        if isinstance(place, str) and place.strip() and place.strip() not in unique:
            unique.append(place.strip())
    return " · ".join(unique)


def _address_parts(address: object) -> list[object]:
    postal = address.get("postalAddress") if isinstance(address, dict) else None
    if not isinstance(postal, dict):
        return []
    return [
        postal.get("addressLocality"),
        postal.get("addressRegion"),
        postal.get("addressCountry"),
    ]
