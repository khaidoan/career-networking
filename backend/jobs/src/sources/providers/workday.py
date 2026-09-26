"""Workday ``wday/cxs`` provider (paginated POST search).

Ported from Career-Ops ``providers/workday.mjs`` (https://github.com/career-ops-hq/career-ops).
Copyright (c) 2026 Santiago Fernández de Valderrama. Used under the MIT License.
"""

import re
import time
from datetime import UTC, datetime, timedelta

from src.sources.html_text import html_to_text
from src.sources.providers.base import (
    BROWSER_LIKE_USER_AGENT,
    AtsProvider,
    BoardRef,
    HttpClient,
    Posting,
    company_for,
    parse_iso_datetime,
)

PAGE_SIZE = 20
MAX_PAGES = 50
INTER_PAGE_DELAY_SECONDS = 0.25
# A page whose newest-to-oldest listing is past the window by this margin ends pagination.
EARLY_STOP_MARGIN = timedelta(days=2)

# https://{tenant}.{instance}.myworkdayjobs.com/wday/cxs/{tenant}/{site}[/jobs|/job/...]
CXS_URL = re.compile(
    r"^https?://([\w-]+)\.(wd[\w-]*)\.myworkdayjobs\.com/wday/cxs/([\w-]+)/([^/?#]+)",
    re.IGNORECASE,
)
# https://{tenant}.{instance}.myworkdayjobs.com[/{locale}]/{site}[/...]
CAREERS_URL = re.compile(
    r"^https?://([\w-]+)\.(wd[\w-]*)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)",
    re.IGNORECASE,
)
PART = re.compile(r"^[A-Za-z0-9._-]+$")
POSTED_DAYS_AGO = re.compile(r"posted\s+(\d+)(\+?)\s*day", re.IGNORECASE)
MULTI_LOCATION_PLACEHOLDER = re.compile(r"^\s*\d+\s+locations?\s*$", re.IGNORECASE)


class WorkdayProvider(AtsProvider):
    name = "workday"

    def board_url(self, board_key: str) -> str:
        tenant, instance, site = board_key.split("/")
        return f"{_origin(tenant, instance)}/{site}"

    def normalize_key(self, board_key: str) -> str:
        # Host parts are case-insensitive; the site path is not.
        tenant, instance, site = board_key.split("/")
        return f"{tenant.lower()}/{instance.lower()}/{site}"

    def detect_board(self, url: str) -> str | None:
        match = CXS_URL.match(url)
        if match:
            _host, instance, tenant, site = match.groups()
        else:
            match = CAREERS_URL.match(url)
            if not match:
                return None
            tenant, instance, site = match.groups()
        if site.lower() == "wday" or not all(PART.match(part) for part in (tenant, instance, site)):
            return None
        return self.normalize_key(f"{tenant}/{instance}/{site}")

    def fetch_postings(
        self, board: BoardRef, client: HttpClient, *, since: datetime | None = None
    ) -> list[Posting]:
        tenant, instance, site = board.board_key.split("/")
        origin = _origin(tenant, instance)
        api_url = f"{origin}/wday/cxs/{tenant}/{site}/jobs"
        headers = {
            "User-Agent": BROWSER_LIKE_USER_AGENT,
            "Accept": "application/json",
            "Origin": origin,
            "Referer": f"{origin}/{site}/",
        }
        now = datetime.now(UTC)
        postings: list[Posting] = []
        total: int | None = None
        for page in range(MAX_PAGES):
            if page:
                time.sleep(INTER_PAGE_DELAY_SECONDS)
            payload = {
                "limit": PAGE_SIZE,
                "offset": page * PAGE_SIZE,
                "searchText": "",
                "appliedFacets": {},
            }
            data = client.post_json(api_url, payload, headers=headers)
            if not isinstance(data, dict):
                break
            # Workday reports the total on the first page only.
            if total is None and isinstance(data.get("total"), int):
                total = data["total"]
            page_postings = [
                self._posting(job, board, origin, site, now)
                for job in data.get("jobPostings") or []
                if _usable(job)
            ]
            postings.extend(page_postings)
            if len(data.get("jobPostings") or []) < PAGE_SIZE:
                break
            if total is not None and (page + 1) * PAGE_SIZE >= total:
                break
            if since is not None and _page_is_past(page_postings, since):
                break
        return postings

    def enrich(self, posting: Posting, client: HttpClient) -> None:
        detail = self._detail(posting.url, client)
        info = detail.get("jobPostingInfo") if isinstance(detail, dict) else None
        if not isinstance(info, dict):
            return
        posting.description = html_to_text(info.get("jobDescription")) or posting.description
        posting.published_at = parse_iso_datetime(info.get("startDate")) or posting.published_at
        places = [info.get("location"), *(info.get("additionalLocations") or [])]
        country = info.get("country")
        if isinstance(country, dict):
            places.append(country.get("descriptor"))
        location = " · ".join(
            dict.fromkeys(p.strip() for p in places if isinstance(p, str) and p.strip())
        )
        if location:
            posting.location = location
            posting.extra.pop("location_pending", None)
        organization = detail.get("hiringOrganization")
        if isinstance(organization, dict) and posting.board and not posting.board.company_name:
            posting.company = company_for(posting.board, organization.get("name"))

    def fetch_description(self, url: str, client: HttpClient) -> str | None:
        detail = self._detail(url, client)
        info = detail.get("jobPostingInfo") if isinstance(detail, dict) else None
        return html_to_text(info.get("jobDescription")) if isinstance(info, dict) else None

    def _detail(self, url: str, client: HttpClient) -> object:
        """The posting's detail document: its ``externalPath`` under the CXS base URL."""
        board_key = self.detect_board(url)
        if not board_key:
            return None
        tenant, instance, site = board_key.split("/")
        origin = _origin(tenant, instance)
        marker = f"/{site}/"
        path_start = url.find(marker)
        if path_start == -1:
            return None
        external_path = url[path_start + len(marker) - 1 :].split("?")[0]
        return client.get_json(
            f"{origin}/wday/cxs/{tenant}/{site}{external_path}",
            headers={"User-Agent": BROWSER_LIKE_USER_AGENT, "Accept": "application/json"},
        )

    def _posting(
        self, job: dict, board: BoardRef, origin: str, site: str, now: datetime
    ) -> Posting:
        location = job.get("locationsText") or _location_from_path(job["externalPath"])
        posting = Posting(
            title=job["title"].strip(),
            company=company_for(board),
            url=f"{origin}/{site}{job['externalPath']}",
            source=self.name,
            location="" if MULTI_LOCATION_PLACEHOLDER.match(location) else location,
            published_at=parse_posted_on(job.get("postedOn"), now),
            board=board,
        )
        if MULTI_LOCATION_PLACEHOLDER.match(location):
            # "3 Locations": the real places are only in the detail document.
            posting.extra["location_pending"] = True
        return posting


def _origin(tenant: str, instance: str) -> str:
    return f"https://{tenant}.{instance}.myworkdayjobs.com"


def _usable(job: object) -> bool:
    return (
        isinstance(job, dict)
        and isinstance(job.get("externalPath"), str)
        and job["externalPath"].startswith("/")
        and bool(str(job.get("title") or "").strip())
    )


def parse_posted_on(label: object, now: datetime) -> datetime | None:
    """Workday only gives relative labels such as "Posted 5 Days Ago"; "30+ Days" is undated."""
    if not isinstance(label, str):
        return None
    lowered = label.lower()
    if "posted today" in lowered:
        return now
    if "posted yesterday" in lowered:
        return now - timedelta(days=1)
    match = POSTED_DAYS_AGO.search(label)
    if not match or match.group(2) == "+":
        return None
    return now - timedelta(days=int(match.group(1)))


def _location_from_path(external_path: str) -> str:
    # externalPath looks like /job/{Location-Slug}/{title-slug}_{requisition}
    match = re.search(r"/job/([^/]+)/", external_path)
    return match.group(1).replace("-", " ") if match else ""


def _page_is_past(page_postings: list[Posting], since: datetime) -> bool:
    dated = [posting.published_at for posting in page_postings if posting.published_at]
    return bool(dated) and min(dated) < since - EARLY_STOP_MARGIN
