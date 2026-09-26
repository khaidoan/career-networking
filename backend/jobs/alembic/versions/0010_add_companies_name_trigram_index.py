"""add companies name trigram index

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_companies_name_trgm"


def upgrade() -> None:
    # pg_trgm backs the typo-tolerant company name search; the GIN index serves ILIKE and
    # trigram lookups on companies.name.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        INDEX_NAME,
        "companies",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="companies")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
