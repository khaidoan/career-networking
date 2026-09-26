from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.company import Company


class CompanyNetworking(TimestampMixin, Base):
    """A networking contact at a company; deleted together with its company."""

    __tablename__ = "company_networking"
    __table_args__ = (
        # One row per profile per company (migration 0013); NULL URLs remain allowed.
        Index(
            "uq_company_networking_company_id_linkedin_url",
            "company_id",
            "linkedin_url",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    connection_request_sent: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=false()
    )
    connection_request_sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="networking_contacts")
