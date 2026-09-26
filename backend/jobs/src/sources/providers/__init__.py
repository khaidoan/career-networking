"""The supported ATS providers, keyed by the ``ats_boards.provider`` value."""

from src.sources.providers.ashby import AshbyProvider
from src.sources.providers.bamboohr import BambooHrProvider
from src.sources.providers.base import AtsProvider, BoardRef
from src.sources.providers.greenhouse import GreenhouseProvider
from src.sources.providers.icims import IcimsProvider
from src.sources.providers.lever import LeverProvider
from src.sources.providers.workday import WorkdayProvider

PROVIDERS: dict[str, AtsProvider] = {
    provider.name: provider
    for provider in (
        GreenhouseProvider(),
        LeverProvider(),
        AshbyProvider(),
        WorkdayProvider(),
        IcimsProvider(),
        BambooHrProvider(),
    )
}


def get_provider(name: str) -> AtsProvider:
    return PROVIDERS[name]


def detect_board(url: str) -> tuple[str, str] | None:
    """``(provider, board_key)`` when ``url`` points at a supported ATS board or posting."""
    for provider in PROVIDERS.values():
        board_key = provider.detect_board(url)
        if board_key:
            return provider.name, board_key
    return None


def detect_board_ref(url: str, company_name: str | None = None) -> BoardRef | None:
    detected = detect_board(url)
    if detected is None:
        return None
    provider, board_key = detected
    return PROVIDERS[provider].board_ref(board_key, company_name)
