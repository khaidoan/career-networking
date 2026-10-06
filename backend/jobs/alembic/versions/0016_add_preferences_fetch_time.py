"""add preferences fetch_time and fetch_timezone

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # When the fetcher runs each day: "HH:MM" in fetch_timezone (an IANA name). Both are required
    # for job fetching; until the user saves them, fetching is disabled.
    op.add_column("preferences", sa.Column("fetch_time", sa.Text(), nullable=True))
    op.add_column("preferences", sa.Column("fetch_timezone", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("preferences", "fetch_timezone")
    op.drop_column("preferences", "fetch_time")
