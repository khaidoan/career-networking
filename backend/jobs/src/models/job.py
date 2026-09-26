from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.company import Company

INBOX_TYPES = ("recommended", "applied", "ignored", "need_attention")
SCORE_COLUMNS = ("overall_score", "experience_score", "skill_score", "industry_exp_score")


def _score_range_check(column: str) -> CheckConstraint:
    return CheckConstraint(f"{column} >= 0 AND {column} <= 100", name=f"{column}_range")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "inbox_type IN (" + ", ".join(f"'{value}'" for value in INBOX_TYPES) + ")",
            name="inbox_type_allowed",
        ),
        *(_score_range_check(column) for column in SCORE_COLUMNS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    location_city: Mapped[str | None] = mapped_column(Text)
    location_state: Mapped[str | None] = mapped_column(Text)
    location_country: Mapped[str | None] = mapped_column(Text)
    work_arrangement: Mapped[str | None] = mapped_column(Text)
    job_type_classification: Mapped[str | None] = mapped_column(Text)
    seniority_level: Mapped[str | None] = mapped_column(Text)
    year_exp: Mapped[int | None] = mapped_column(Integer)
    compensation_range: Mapped[str | None] = mapped_column(Text)
    visa_sponsorship: Mapped[bool | None] = mapped_column()

    overall_score: Mapped[int | None] = mapped_column(Integer)
    experience_score: Mapped[int | None] = mapped_column(Integer)
    skill_score: Mapped[int | None] = mapped_column(Integer)
    industry_exp_score: Mapped[int | None] = mapped_column(Integer)
    # Why the evaluator failed; null for jobs that were scored.
    evaluation_error: Mapped[str | None] = mapped_column(Text)

    inbox_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        default="recommended",
        server_default=text("'recommended'"),
    )
    liked: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    discovered_when: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    applied_when: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="jobs")
