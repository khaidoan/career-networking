"""create ats boards table

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the allowed values at the time of this revision.
PROVIDERS = ("greenhouse", "lever", "ashby", "workday", "icims", "bamboohr")
DISCOVERY_SOURCES = ("ats_sweep", "google_jobs")


def _in_list(column: str, values: Sequence[str]) -> str:
    return f"{column} IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.create_table(
        "ats_boards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("board_key", sa.Text(), nullable=False),
        sa.Column("board_url", sa.Text(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("discovered_via", sa.Text(), nullable=False),
        sa.Column("last_matched_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            _in_list("provider", PROVIDERS), name=op.f("ck_ats_boards_provider_allowed")
        ),
        sa.CheckConstraint(
            _in_list("discovered_via", DISCOVERY_SOURCES),
            name=op.f("ck_ats_boards_discovered_via_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_boards")),
        sa.UniqueConstraint("provider", "board_key", name=op.f("uq_ats_boards_provider_board_key")),
    )
    op.create_index(op.f("ix_ats_boards_is_active"), "ats_boards", ["is_active"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ats_boards_is_active"), table_name="ats_boards")
    op.drop_table("ats_boards")
