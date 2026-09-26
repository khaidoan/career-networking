"""Typed application settings loaded from ``CAREER_NETWORKING_*`` environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "CAREER_NETWORKING_"
MIN_JWT_SECRET_LENGTH = 32


class SettingsError(RuntimeError):
    """Raised when required environment variables are missing or invalid."""


class Settings(BaseSettings):
    """Every setting the jobs service reads. Only the tuning knobs have defaults."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore", frozen=True)

    database_url: SecretStr = Field(min_length=1)

    jwt_secret: SecretStr
    jwt_expires_minutes: int = Field(default=10080, gt=0)

    login_max_attempts: int = Field(default=5, gt=0)
    login_window_minutes: int = Field(default=15, gt=0)

    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    firstname: str
    lastname: str
    email: str

    resume_folder: Path
    job_data: Path
    log_folder: Path

    # One LiteLLM model string shared by every agent, e.g. "openai/gpt-4o-mini".
    # Provider keys (OPENAI_API_KEY, ...) are read by LiteLLM from the environment directly.
    llm_model: str = Field(min_length=1)
    llm_api_base: str | None = None

    match_threshold: int = Field(default=70, ge=0, le=100)
    google_jobs_interval_hours: int = Field(default=24, gt=0)
    serpapi_api_key: SecretStr | None = Field(default=None, validation_alias="SERPAPI_API_KEY")

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_is_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"must be at least {MIN_JWT_SECRET_LENGTH} characters")
        return value

    @field_validator("llm_api_base", "serpapi_api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # .env.example ships these as empty lines; treat "" as "not configured".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def sqlalchemy_database_url(self) -> str:
        """Database URL with the psycopg (v3) driver selected explicitly."""
        url = self.database_url.get_secret_value()
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def jwt_expires_seconds(self) -> int:
        return self.jwt_expires_minutes * 60

    @property
    def login_window_seconds(self) -> int:
        return self.login_window_minutes * 60


# Settings read from an unprefixed environment variable through a validation alias.
UNPREFIXED_VARIABLES = {"SERPAPI_API_KEY"}


def _variable_name(location: object) -> str:
    name = str(location)
    return name if name in UNPREFIXED_VARIABLES else ENV_PREFIX + name.upper()


def _describe_errors(error: ValidationError) -> str:
    missing: list[str] = []
    invalid: list[str] = []
    for item in error.errors(include_input=False):
        variable = _variable_name(item["loc"][0])
        if item["type"] == "missing":
            missing.append(variable)
        else:
            invalid.append(f"{variable} ({item['msg']})")
    parts = []
    if missing:
        parts.append("missing required environment variables: " + ", ".join(missing))
    if invalid:
        parts.append("invalid environment variables: " + ", ".join(invalid))
    return "Configuration error: " + "; ".join(parts) + ". See .env.example."


def load_settings() -> Settings:
    """Build settings from the environment, failing fast with the offending variable names."""
    try:
        return Settings()
    except ValidationError as error:
        raise SettingsError(_describe_errors(error)) from None


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; also usable as a FastAPI dependency (and overridable in tests)."""
    return load_settings()
