from typing import Any

from sqlalchemy import CheckConstraint, Integer, Text, text
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
    hard_skills: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    soft_skills: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    country: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    seniority: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    address: Mapped[str | None] = mapped_column(Text)
    resume_location: Mapped[str | None] = mapped_column(Text)
    resume_text: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    eeo_answers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
