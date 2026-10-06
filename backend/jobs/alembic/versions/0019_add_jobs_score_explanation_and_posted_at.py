"""add jobs score_explanation and posted_at

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The evaluator's reason for the overall score, shown from the Ignored inbox.
    op.add_column("jobs", sa.Column("score_explanation", sa.Text(), nullable=True))
    # The posting's published or updated time from the source, shown on job cards.
    op.add_column("jobs", sa.Column("posted_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "posted_at")
    op.drop_column("jobs", "score_explanation")
