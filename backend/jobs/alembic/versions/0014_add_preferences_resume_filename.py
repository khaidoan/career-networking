"""add preferences resume_filename

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The name of the file the user uploaded; display only (the file is stored as resume.<type>).
    op.add_column("preferences", sa.Column("resume_filename", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("preferences", "resume_filename")
