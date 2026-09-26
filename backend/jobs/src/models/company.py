from typing import TYPE_CHECKING

from sqlalchemy import Index, Text, false
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.company_networking import CompanyNetworking
    from src.models.job import Job


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        # Trigram index for the typo-tolerant name search (migration 0010 enables pg_trgm).
        Index(
            "ix_companies_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    history: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    industries: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    growth_stage: Mapped[str | None] = mapped_column(Text)
    liked: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    employee_estimate: Mapped[str | None] = mapped_column(Text)

    # Jobs block company deletion (ON DELETE RESTRICT); let the database enforce it.
    jobs: Mapped[list["Job"]] = relationship(back_populates="company", passive_deletes="all")
    networking_contacts: Mapped[list["CompanyNetworking"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )
