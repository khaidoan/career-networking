"""add preferences auto_apply

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Whether the user allows applying to jobs automatically; off unless they turn it on.
    op.add_column(
        "preferences",
        sa.Column("auto_apply", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("preferences", "auto_apply")
