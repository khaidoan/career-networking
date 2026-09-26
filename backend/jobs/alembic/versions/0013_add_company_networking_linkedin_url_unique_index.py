"""add company networking linkedin url unique index

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_company_networking_company_id_linkedin_url"


def upgrade() -> None:
    # One row per profile per company; NULL URLs stay allowed (NULLs are distinct in Postgres).
    op.create_index(INDEX_NAME, "company_networking", ["company_id", "linkedin_url"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="company_networking")
