from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Integer, Text, false, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Preferences(TimestampMixin, Base):
    """The single user's preferences; ``CHECK (id = 1)`` keeps it to one row."""

    __tablename__ = "preferences"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False, default=1, server_default=text("1")
    )
    desired_titles: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    # A posting whose title contains every word of one of these is skipped by the fetcher.
    excluded_title_words: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    hard_skills: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    soft_skills: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    country: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    seniority: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    address: Mapped[str | None] = mapped_column(Text)
    resume_location: Mapped[str | None] = mapped_column(Text)
    resume_filename: Mapped[str | None] = mapped_column(Text)
    resume_text: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    eeo_answers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    auto_apply: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Daily fetcher time as "HH:MM" in fetch_timezone (an IANA name); fetching needs both.
    fetch_time: Mapped[str | None] = mapped_column(Text)
    fetch_timezone: Mapped[str | None] = mapped_column(Text)
    # The user's long-form resume plus application facts; for the apply process and the cover
    # letter and resume writers.
    additional_information: Mapped[str | None] = mapped_column(Text)
