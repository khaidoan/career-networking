from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, event, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import NEVER_SET, NO_VALUE
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.company import Company

# The inboxes the user sees, and "pending": saved by the fetcher, not scored yet, never listed.
LISTED_INBOXES = ("recommended", "applied", "ignored", "need_attention")
INBOX_PENDING = "pending"
INBOX_TYPES = (*LISTED_INBOXES, INBOX_PENDING)
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
        Index("ix_jobs_inbox_type_inbox_entered_at_id", "inbox_type", "inbox_entered_at", "id"),
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
    # The evaluator's reason for the overall score; null when it gave none or scoring failed.
    score_explanation: Mapped[str | None] = mapped_column(Text)
    # Why the evaluator failed; null for jobs that were scored.
    evaluation_error: Mapped[str | None] = mapped_column(Text)

    inbox_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        default=INBOX_PENDING,
        server_default=text("'pending'"),
    )
    # When the job entered its current inbox (for Recommended, when it was scored); kept up to
    # date by the listener below, and the order every inbox is listed in.
    inbox_entered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    # The posting's location as the source gave it, for the scorer's evaluation.
    posting_location: Mapped[str | None] = mapped_column(Text)
    # When the source says the posting was published or last updated; null when it does not say.
    posted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    # Failed scoring attempts, and when the scorer may try this pending job again.
    scoring_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    next_scoring_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    liked: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    discovered_when: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    applied_when: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="jobs")


@event.listens_for(Job.inbox_type, "set")
def _stamp_inbox_change(job: Job, value: str, old_value: Any, _initiator: object) -> None:
    """Every move to another inbox (scoring, Apply) restarts ``inbox_entered_at``.

    The first value of a new job is not a move; the column default (or a given time) applies.
    """
    if old_value not in (NO_VALUE, NEVER_SET) and value != old_value:
        job.inbox_entered_at = datetime.now(UTC)
