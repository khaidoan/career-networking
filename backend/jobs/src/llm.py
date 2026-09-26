"""Shared LLM layer: one LiteLLM completion helper, structured output and prompt resolution.

Every agent calls the model configured by ``CAREER_NETWORKING_LLM_MODEL`` through this module.
Provider keys (``OPENAI_API_KEY`` and so on) are read by LiteLLM from the environment and are
never logged. Log lines carry only the agent name, model, latency and outcome, never prompts.
"""

import json
import logging
import os
import re
import time
from collections.abc import Callable
from functools import lru_cache
from types import ModuleType
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.models import Preferences, Prompt

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 60
# Transport attempts per completion (first try included) for transient provider errors.
MAX_TRANSIENT_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
# One extra attempt with the validation error appended, then LlmOutputError.
MAX_STRUCTURED_ATTEMPTS = 2

ModelT = TypeVar("ModelT", bound=BaseModel)
Message = dict[str, str]

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LlmError(RuntimeError):
    """The LLM could not be reached or rejected the request."""


class LlmOutputError(LlmError):
    """The LLM replied, but not with JSON matching the expected model (after one retry)."""


@lru_cache
def _litellm() -> ModuleType:
    """Import LiteLLM on first use; it is slow to import and must not fetch data on import."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    litellm.suppress_debug_info = True
    litellm.telemetry = False
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    return litellm


def _litellm_completion(**kwargs: Any) -> Any:
    return _litellm().completion(**kwargs)


def _is_transient(error: Exception) -> bool:
    litellm = _litellm()
    transient = (
        litellm.Timeout,
        litellm.APIConnectionError,
        litellm.RateLimitError,
        litellm.ServiceUnavailableError,
        litellm.InternalServerError,
        litellm.BadGatewayError,
    )
    return isinstance(error, transient)


def complete(messages: list[Message], *, agent_name: str, settings: Settings | None = None) -> str:
    """Send chat messages to the configured model and return the reply text.

    Transient provider errors are retried with exponential backoff; anything else, or running
    out of attempts, raises ``LlmError``.
    """
    settings = settings or get_settings()
    request: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "timeout": REQUEST_TIMEOUT_SECONDS,
        "response_format": {"type": "json_object"},
        # Providers that do not support a parameter (e.g. response_format) silently ignore it.
        "drop_params": True,
    }
    if settings.llm_api_base:
        request["api_base"] = settings.llm_api_base

    for attempt in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
        started = time.monotonic()
        try:
            response = _litellm_completion(**request)
        except Exception as error:
            latency_ms = int((time.monotonic() - started) * 1000)
            transient = _is_transient(error)
            logger.warning(
                "LLM call agent=%s model=%s latency_ms=%d outcome=error attempt=%d error=%s",
                agent_name,
                settings.llm_model,
                latency_ms,
                attempt,
                type(error).__name__,
            )
            if transient and attempt < MAX_TRANSIENT_ATTEMPTS:
                time.sleep(BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))
                continue
            raise LlmError(f"LLM request failed: {type(error).__name__}") from error

        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "LLM call agent=%s model=%s latency_ms=%d outcome=ok",
            agent_name,
            settings.llm_model,
            latency_ms,
        )
        return response.choices[0].message.content or ""

    raise LlmError("LLM request failed")  # pragma: no cover - loop always returns or raises


def output_instructions(model_cls: type[BaseModel]) -> str:
    """Instructions appended to every system prompt so customised prompts still yield JSON."""
    schema = json.dumps(model_cls.model_json_schema(), separators=(",", ":"))
    return (
        "Reply with a single JSON object and nothing else (no prose, no code fences). "
        "It must match this JSON Schema. Use null for any value that is not stated; "
        f"never guess.\nJSON Schema: {schema}"
    )


def build_messages(
    system_prompt: str, user_content: str, model_cls: type[BaseModel]
) -> list[Message]:
    return [
        {
            "role": "system",
            "content": f"{system_prompt.strip()}\n\n{output_instructions(model_cls)}",
        },
        {"role": "user", "content": user_content},
    ]


def parse_structured(raw_output: str, model_cls: type[ModelT]) -> ModelT:
    """Validate a raw reply against ``model_cls``; raises ``ValueError`` describing the problem."""
    text = _CODE_FENCE.sub("", raw_output.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("the reply did not contain a JSON object")
    try:
        return model_cls.model_validate_json(text[start : end + 1])
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or 'root'}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        raise ValueError(problems) from None


def retry_messages(messages: list[Message], raw_output: str, problem: str) -> list[Message]:
    """The conversation extended with the invalid reply and the validation error."""
    return [
        *messages,
        {"role": "assistant", "content": raw_output},
        {
            "role": "user",
            "content": (
                f"Your reply was not valid: {problem}. Reply again with only a JSON object "
                "that matches the schema."
            ),
        },
    ]


def complete_structured(
    system_prompt: str,
    user_content: str,
    model_cls: type[ModelT],
    *,
    agent_name: str = "unknown",
    settings: Settings | None = None,
) -> ModelT:
    """Ask for JSON, validate it with ``model_cls`` and retry once with the error appended."""
    return run_structured(
        build_messages(system_prompt, user_content, model_cls),
        model_cls,
        send=lambda messages: complete(messages, agent_name=agent_name, settings=settings),
        agent_name=agent_name,
    )


def run_structured(
    messages: list[Message],
    model_cls: type[ModelT],
    *,
    send: Callable[[list[Message]], str],
    agent_name: str,
) -> ModelT:
    """The validate-and-retry loop shared by ``complete_structured`` and graph-based agents."""
    problem = ""
    for attempt in range(1, MAX_STRUCTURED_ATTEMPTS + 1):
        raw_output = send(messages)
        try:
            return parse_structured(raw_output, model_cls)
        except ValueError as error:
            problem = str(error)
            logger.warning(
                "LLM output invalid agent=%s attempt=%d model=%s",
                agent_name,
                attempt,
                model_cls.__name__,
            )
            messages = retry_messages(messages, raw_output, problem)
    raise LlmOutputError(f"{agent_name}: invalid LLM output after retry ({problem})")


def resolve_system_prompt(session: Session, agent_name: str, default: str) -> str:
    """The user's customised prompt for ``agent_name`` if there is one, else ``default``."""
    prompt = session.scalar(select(Prompt).where(Prompt.agent_name == agent_name))
    if prompt is not None and prompt.is_customized and prompt.system_prompt.strip():
        return prompt.system_prompt
    return default


# The only preference fields any agent may send to the LLM. Address, gender and the other
# EEO answers are deliberately absent; changing what is shared is an edit to these tuples.
LLM_SAFE_PREFERENCE_FIELDS: tuple[str, ...] = (
    "desired_titles",
    "hard_skills",
    "soft_skills",
    "seniority",
    "salary_min",
    "salary_max",
    "currency",
    "country",
)
LLM_SAFE_EEO_KEYS: tuple[str, ...] = ("work_authorization", "needs_visa_sponsorship")


def llm_safe_preferences(preferences: Preferences | None) -> dict[str, Any]:
    """Job-relevant preferences only; every agent builds its LLM context through this."""
    if preferences is None:
        return {}
    safe: dict[str, Any] = {
        field: getattr(preferences, field)
        for field in LLM_SAFE_PREFERENCE_FIELDS
        if getattr(preferences, field) not in (None, [], "")
    }
    eeo_answers = preferences.eeo_answers or {}
    for key in LLM_SAFE_EEO_KEYS:
        if eeo_answers.get(key):
            safe[key] = eeo_answers[key]
    return safe
