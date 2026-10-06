"""separate job scoring

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_INBOXES = ("recommended", "applied", "ignored", "need_attention")
NEW_INBOXES = (*OLD_INBOXES, "pending")
INBOX_ORDER_INDEX = "ix_jobs_inbox_type_inbox_entered_at_id"
INBOX_CHECK = "ck_jobs_inbox_type_allowed"


def _inbox_check(values: tuple[str, ...]) -> str:
    return "inbox_type IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    # The fetcher saves new jobs as "pending"; the scorer moves them to Recommended or Ignored.
    op.drop_constraint(op.f(INBOX_CHECK), "jobs", type_="check")
    op.create_check_constraint(op.f(INBOX_CHECK), "jobs", _inbox_check(NEW_INBOXES))
    op.alter_column("jobs", "inbox_type", server_default=sa.text("'pending'"))
    # When the job entered its current inbox (for Recommended, when it was scored); inboxes are
    # listed newest first by it. Existing jobs use their applied or discovered time.
    op.add_column(
        "jobs",
        sa.Column(
            "inbox_entered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        "UPDATE jobs SET inbox_entered_at = CASE WHEN inbox_type = 'applied' "
        "THEN COALESCE(applied_when, discovered_when) ELSE discovered_when END"
    )
    op.create_index(INBOX_ORDER_INDEX, "jobs", ["inbox_type", "inbox_entered_at", "id"])
    # The posting's location as the source gave it; the scorer sends it to the evaluator.
    op.add_column("jobs", sa.Column("posting_location", sa.Text(), nullable=True))
    # Failed scoring attempts, and when the scorer may try a pending job again.
    op.add_column(
        "jobs",
        sa.Column("scoring_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("jobs", sa.Column("next_scoring_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    # Unscored jobs have no place in the old inboxes.
    op.execute("DELETE FROM jobs WHERE inbox_type = 'pending'")
    op.drop_column("jobs", "next_scoring_at")
    op.drop_column("jobs", "scoring_attempts")
    op.drop_column("jobs", "posting_location")
    op.drop_index(INBOX_ORDER_INDEX, table_name="jobs")
    op.drop_column("jobs", "inbox_entered_at")
    op.alter_column("jobs", "inbox_type", server_default=sa.text("'recommended'"))
    op.drop_constraint(op.f(INBOX_CHECK), "jobs", type_="check")
    op.create_check_constraint(op.f(INBOX_CHECK), "jobs", _inbox_check(OLD_INBOXES))
