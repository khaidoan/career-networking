"""BambooHR careers-list provider.

The list endpoint has no dates or descriptions; ``enrich`` reads both from the posting's detail
endpoint, only for postings that passed the filters.

Ported from Career-Ops ``providers/bamboohr.mjs`` (https://github.com/career-ops-hq/career-ops).
Copyright (c) 2026 Santiago Fernández de Valderrama. Used under the MIT License.
"""

import re
from datetime import datetime
from urllib.parse import quote, urlsplit

from src.sources.html_text import html_to_text
from src.sources.providers.base import (
    AtsProvider,
    BoardRef,
    HttpClient,
    Posting,
    company_for,
    parse_iso_datetime,
)

HOST = re.compile(r"^([a-z0-9][a-z0-9-]*)\.bamboohr\.com$")
RESERVED_LABELS = frozenset({"www", "api", "help", "marketplace"})
POSTING_PATH = re.compile(r"^/careers/([^/]+)")


class BambooHrProvider(AtsProvider):
    name = "bamboohr"

    def board_url(self, board_key: str) -> str:
        return f"{_origin(board_key)}/careers"

    def detect_board(self, url: str) -> str | None:
        match = HOST.match((urlsplit(url).hostname or "").lower())
        if not match or match.group(1) in RESERVED_LABELS:
            return None
        return match.group(1)

    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        # Redirects are not followed: a tenant that redirects has no public careers list.
        data = client.get_json(f"{_origin(board.board_key)}/careers/list")
        rows = data.get("result") if isinstance(data, dict) else None
        postings = []
        for row in rows or []:
            if (
                isinstance(row, dict)
                and row.get("jobOpeningName")
                and str(row.get("id", "")).strip()
            ):
                postings.append(self._posting(row, board))
        return postings

    def enrich(self, posting: Posting, client: HttpClient) -> None:
        opening = self._opening(posting.url, client)
        if opening is None:
            return
        posting.published_at = parse_iso_datetime(opening.get("datePosted")) or posting.published_at
        posting.description = html_to_text(opening.get("description")) or posting.description

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        opening = self._opening(url, client)
        return html_to_text(opening.get("description")) if opening else None

    def _opening(self, url: str, client: HttpClient) -> dict | None:
        board_key = self.detect_board(url)
        match = POSTING_PATH.match(urlsplit(url).path)
        if not board_key or not match:
            return None
        data = client.get_json(f"{_origin(board_key)}/careers/{match.group(1)}/detail")
        result = data.get("result") if isinstance(data, dict) else None
        opening = result.get("jobOpening") if isinstance(result, dict) else None
        return opening if isinstance(opening, dict) else None

    def _posting(self, row: dict, board: BoardRef) -> Posting:
        location = row.get("location") if isinstance(row.get("location"), dict) else {}
        ats_location = row.get("atsLocation") if isinstance(row.get("atsLocation"), dict) else {}
        places = [
            location.get("city"),
            location.get("state"),
            ats_location.get("country"),
            "Remote" if row.get("isRemote") else None,
        ]
        return Posting(
            title=str(row["jobOpeningName"]).strip(),
            company=company_for(board),
            url=f"{_origin(board.board_key)}/careers/{quote(str(row['id']).strip(), safe='')}",
            source=self.name,
            location=", ".join(
                dict.fromkeys(p.strip() for p in places if isinstance(p, str) and p.strip())
            ),
            board=board,
        )


def _origin(board_key: str) -> str:
    return f"https://{board_key}.bamboohr.com"
