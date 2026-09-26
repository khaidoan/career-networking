"""add companies contacts_searched_at

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # When contact search last succeeded for the company; display only, no cooldown.
    op.add_column(
        "companies",
        sa.Column("contacts_searched_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "contacts_searched_at")
