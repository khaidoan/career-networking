"""normalize company networking linkedin urls

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-25

Data only. Rewrites every stored contact profile URL to its normalized form and merges contacts
that then share a URL within the same company, so 0013 can add the unique index.

Within each company, rows are grouped by normalized URL. URLs that are not a ``/in/<slug>``
profile path are left unchanged, but exact duplicates of them are still merged. Each group keeps
one row: the one with ``connection_request_sent = true`` and the earliest
``connection_request_sent_at``, or else the lowest id. The other rows of the group are deleted.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A copy of src/services/linkedin_urls.py: migrations never import app code, so later changes to
# the app normalizer cannot change what this migration did.
CANONICAL_PREFIX = "https://www.linkedin.com/in/"
LINKEDIN_DOMAIN = "linkedin.com"
SUBDOMAIN_PATTERN = re.compile(r"[a-z]{2,3}")
SLUG_PATTERN = re.compile(r"[^/\s]+")


def normalize_linkedin_profile_url(url: str) -> str | None:
    text = url.strip().lower()
    if not text:
        return None
    if "://" not in text:
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc
    if host != LINKEDIN_DOMAIN:
        subdomain, dot, domain = host.partition(".")
        if not dot or domain != LINKEDIN_DOMAIN or not SUBDOMAIN_PATTERN.fullmatch(subdomain):
            return None
    segments = parts.path.rstrip("/").split("/")
    if len(segments) != 3 or segments[0] or segments[1] != "in":
        return None
    slug = segments[2]
    if not SLUG_PATTERN.fullmatch(slug):
        return None
    return f"{CANONICAL_PREFIX}{slug}"


def _keep_order(row: sa.Row) -> tuple[bool, bool, datetime | None, int]:
    """Sort key: sent rows first, then the earliest sent timestamp (NULLs last), then lowest id."""
    sent_at = row.connection_request_sent_at if row.connection_request_sent else None
    return (not row.connection_request_sent, sent_at is None, sent_at, row.id)


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, company_id, linkedin_url, connection_request_sent, "
            "connection_request_sent_at FROM company_networking "
            "WHERE linkedin_url IS NOT NULL"
        )
    ).all()

    groups: dict[tuple[int, str], list[sa.Row]] = defaultdict(list)
    for row in rows:
        url = normalize_linkedin_profile_url(row.linkedin_url) or row.linkedin_url
        groups[(row.company_id, url)].append(row)

    delete_ids: list[int] = []
    updates: list[dict[str, object]] = []
    for (_company_id, url), group in groups.items():
        kept, *duplicates = sorted(group, key=_keep_order)
        delete_ids.extend(row.id for row in duplicates)
        if kept.linkedin_url != url:
            updates.append({"id": kept.id, "url": url})

    if delete_ids:
        connection.execute(
            sa.text("DELETE FROM company_networking WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": delete_ids},
        )
    if updates:
        connection.execute(
            sa.text(
                "UPDATE company_networking SET linkedin_url = :url, updated_at = now() "
                "WHERE id = :id"
            ),
            updates,
        )


def downgrade() -> None:
    """No-op: the merged duplicates were deleted and the original URL spellings are not kept, so
    the merge cannot be undone. The normalized data stays valid for the 0011 schema."""
