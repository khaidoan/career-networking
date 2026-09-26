"""preferences seniority array

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "preferences",
        "seniority",
        type_=postgresql.ARRAY(sa.Text()),
        existing_type=sa.Text(),
        existing_nullable=True,
        postgresql_using="CASE WHEN seniority IS NULL THEN NULL ELSE ARRAY[seniority] END",
    )


def downgrade() -> None:
    # Only the first selected level survives the conversion back to a single value.
    op.alter_column(
        "preferences",
        "seniority",
        type_=sa.Text(),
        existing_type=postgresql.ARRAY(sa.Text()),
        existing_nullable=True,
        postgresql_using="seniority[1]",
    )
