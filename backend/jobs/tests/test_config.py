"""Fail-fast validation of the Phase 2 settings (LLM, threshold, Google Jobs)."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from src.config import ENV_PREFIX, Settings, SettingsError, load_settings


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    """A complete, valid environment; each test removes or breaks one variable."""
    values = {
        "DATABASE_URL": "postgresql+psycopg://user:pass@db.invalid:5432/test",
        "JWT_SECRET": "test-secret-that-is-long-enough-for-hs256-signing",
        "USERNAME": "tester",
        "PASSWORD": "tester-password",
        "FIRSTNAME": "Ada",
        "LASTNAME": "Lovelace",
        "EMAIL": "ada@example.com",
        "RESUME_FOLDER": str(tmp_path / "resume"),
        "JOB_DATA": str(tmp_path / "jobs"),
        "LOG_FOLDER": str(tmp_path / "logs"),
        "LLM_MODEL": "openai/gpt-4o-mini",
    }
    for name, value in values.items():
        monkeypatch.setenv(ENV_PREFIX + name, value)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    for name in ("LLM_API_BASE", "MATCH_THRESHOLD", "GOOGLE_JOBS_INTERVAL_HOURS"):
        monkeypatch.delenv(ENV_PREFIX + name, raising=False)
    return monkeypatch


def test_missing_llm_model_fails_fast_naming_the_variable(base_env: pytest.MonkeyPatch) -> None:
    base_env.delenv("CAREER_NETWORKING_LLM_MODEL")

    with pytest.raises(SettingsError, match="CAREER_NETWORKING_LLM_MODEL"):
        load_settings()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CAREER_NETWORKING_MATCH_THRESHOLD", "101"),
        ("CAREER_NETWORKING_MATCH_THRESHOLD", "-1"),
        ("CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS", "0"),
    ],
)
def test_out_of_range_tuning_values_are_rejected(
    base_env: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    base_env.setenv(variable, value)

    with pytest.raises(SettingsError, match=variable):
        load_settings()


def test_defaults_and_unprefixed_serpapi_key(base_env: pytest.MonkeyPatch) -> None:
    base_env.setenv("SERPAPI_API_KEY", "serp-secret")

    settings = load_settings()

    assert settings.match_threshold == 70
    assert settings.google_jobs_interval_hours == 24
    assert settings.llm_api_base is None
    assert isinstance(settings.serpapi_api_key, SecretStr)
    assert settings.serpapi_api_key.get_secret_value() == "serp-secret"
    assert "serp-secret" not in repr(settings)


def test_blank_serpapi_key_means_google_jobs_is_disabled(base_env: pytest.MonkeyPatch) -> None:
    base_env.setenv("SERPAPI_API_KEY", "")
    base_env.setenv("CAREER_NETWORKING_SERPAPI_API_KEY", "prefixed-is-ignored")

    settings: Settings = load_settings()

    assert settings.serpapi_api_key is None
