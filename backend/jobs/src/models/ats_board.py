from datetime import datetime

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base, TimestampMixin
from src.vocabularies import ATS_PROVIDERS, BOARD_DISCOVERY_SOURCES

PROVIDERS = ATS_PROVIDERS
DISCOVERED_VIA_ATS_SWEEP, DISCOVERED_VIA_GOOGLE_JOBS = BOARD_DISCOVERY_SOURCES


def _allowed_values_check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IN (" + ", ".join(f"'{value}'" for value in values) + ")", name=name
    )


class AtsBoard(TimestampMixin, Base):
    """A public ATS job board found by discovery and polled on every fetcher run."""

    __tablename__ = "ats_boards"
    __table_args__ = (
        UniqueConstraint("provider", "board_key", name="uq_ats_boards_provider_board_key"),
        _allowed_values_check("provider", PROVIDERS, "provider_allowed"),
        _allowed_values_check("discovered_via", BOARD_DISCOVERY_SOURCES, "discovered_via_allowed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    # A board slug, or "tenant/instance/site" for Workday.
    board_key: Mapped[str] = mapped_column(Text, nullable=False)
    board_url: Mapped[str | None] = mapped_column(Text)
    company_name: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        nullable=False, index=True, default=True, server_default=true()
    )
    discovered_via: Mapped[str] = mapped_column(Text, nullable=False)
    last_matched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_polled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
