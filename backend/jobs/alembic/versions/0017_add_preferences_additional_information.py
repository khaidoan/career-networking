"""add preferences additional_information

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Free text from the Profile page's "Other" section, used only when filling in application
    # forms (never for writing the resume or cover letter).
    op.add_column("preferences", sa.Column("additional_information", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("preferences", "additional_information")
