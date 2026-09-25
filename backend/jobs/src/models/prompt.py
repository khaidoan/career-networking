from sqlalchemy import Text, false
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Prompt(TimestampMixin, Base):
    """A customisable system prompt for one AI agent."""

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_customized: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=false()
    )
