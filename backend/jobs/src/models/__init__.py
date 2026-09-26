"""All ORM models; importing this package registers every table on ``Base.metadata``."""

from src.models.ats_board import (
    DISCOVERED_VIA_ATS_SWEEP,
    DISCOVERED_VIA_GOOGLE_JOBS,
    PROVIDERS,
    AtsBoard,
)
from src.models.base import Base, TimestampMixin
from src.models.company import Company
from src.models.company_networking import CompanyNetworking
from src.models.job import INBOX_TYPES, Job
from src.models.preferences import Preferences
from src.models.prompt import Prompt

__all__ = [
    "DISCOVERED_VIA_ATS_SWEEP",
    "DISCOVERED_VIA_GOOGLE_JOBS",
    "INBOX_TYPES",
    "PROVIDERS",
    "AtsBoard",
    "Base",
    "Company",
    "CompanyNetworking",
    "Job",
    "Preferences",
    "Prompt",
    "TimestampMixin",
]
