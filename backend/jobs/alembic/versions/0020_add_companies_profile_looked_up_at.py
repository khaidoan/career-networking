"""add companies profile_looked_up_at

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # When the company lookup agent last ran, so Company Details looks a company up only once.
    op.add_column(
        "companies", sa.Column("profile_looked_up_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("companies", "profile_looked_up_at")
