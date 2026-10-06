"""add preferences excluded_title_words

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Title words that make the fetcher skip a posting before it is saved and scored.
    op.add_column(
        "preferences",
        sa.Column("excluded_title_words", postgresql.ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("preferences", "excluded_title_words")
