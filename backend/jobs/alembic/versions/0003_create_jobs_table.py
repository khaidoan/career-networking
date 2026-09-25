"""create jobs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCORE_COLUMNS = ("overall_score", "experience_score", "skill_score", "industry_exp_score")


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("location_city", sa.Text(), nullable=True),
        sa.Column("location_state", sa.Text(), nullable=True),
        sa.Column("location_country", sa.Text(), nullable=True),
        sa.Column("work_arrangement", sa.Text(), nullable=True),
        sa.Column("job_type_classification", sa.Text(), nullable=True),
        sa.Column("seniority_level", sa.Text(), nullable=True),
        sa.Column("year_exp", sa.Integer(), nullable=True),
        sa.Column("compensation_range", sa.Text(), nullable=True),
        sa.Column("visa_sponsorship", sa.Boolean(), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("experience_score", sa.Integer(), nullable=True),
        sa.Column("skill_score", sa.Integer(), nullable=True),
        sa.Column("industry_exp_score", sa.Integer(), nullable=True),
        sa.Column("inbox_type", sa.Text(), server_default=sa.text("'recommended'"), nullable=False),
        sa.Column("liked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "discovered_when",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("applied_when", sa.TIMESTAMP(timezone=True), nullable=True),
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
            "inbox_type IN ('recommended', 'applied', 'ignored', 'need_attention')",
            name=op.f("ck_jobs_inbox_type_allowed"),
        ),
        *(
            sa.CheckConstraint(
                f"{column} >= 0 AND {column} <= 100", name=op.f(f"ck_jobs_{column}_range")
            )
            for column in SCORE_COLUMNS
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_jobs_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("url", name=op.f("uq_jobs_url")),
    )
    op.create_index(op.f("ix_jobs_company_id"), "jobs", ["company_id"])
    op.create_index(op.f("ix_jobs_inbox_type"), "jobs", ["inbox_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_inbox_type"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_company_id"), table_name="jobs")
    op.drop_table("jobs")
