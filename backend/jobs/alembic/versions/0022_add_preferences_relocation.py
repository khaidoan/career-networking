"""add preferences relocation

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Used by the fetcher's relocation filter and when filling in application forms.
    op.add_column("preferences", sa.Column("willing_to_relocate", sa.Boolean(), nullable=True))
    op.add_column(
        "preferences",
        sa.Column("excluded_relocation_places", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column("preferences", sa.Column("max_commute_miles", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("preferences", "max_commute_miles")
    op.drop_column("preferences", "excluded_relocation_places")
    op.drop_column("preferences", "willing_to_relocate")
