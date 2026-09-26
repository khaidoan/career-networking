"""Shared LLM layer: structured output with one retry, and prompt resolution."""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.llm import LlmOutputError, complete_structured, resolve_system_prompt
from src.models import Prompt
from tests.conftest import FakeLlm


class Answer(BaseModel):
    value: int


def test_invalid_json_is_retried_once_with_the_error_then_raises(fake_llm: FakeLlm) -> None:
    fake_llm.replies = ["not json at all", '{"value": "not a number"}']

    with pytest.raises(LlmOutputError):
        complete_structured("You answer.", "Question?", Answer, agent_name="test")

    assert len(fake_llm.requests) == 2
    retry_messages = fake_llm.requests[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": "not json at all"}
    assert "did not contain a JSON object" in retry_messages[-1]["content"]
    assert fake_llm.requests[0]["model"] == "openai/test-model"


def test_valid_reply_after_retry_is_returned(fake_llm: FakeLlm) -> None:
    fake_llm.replies = ['{"value": "x"}', '```json\n{"value": 42}\n```']

    assert complete_structured("You answer.", "Question?", Answer).value == 42
    assert "value" in fake_llm.requests[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (
            Prompt(agent_name="evaluator", system_prompt="Custom prompt", is_customized=True),
            "Custom prompt",
        ),
        (
            Prompt(agent_name="evaluator", system_prompt="Stale copy", is_customized=False),
            "Default prompt",
        ),
        (None, "Default prompt"),
    ],
)
def test_prompt_resolution_prefers_customized_row(stored: Prompt | None, expected: str) -> None:
    session = MagicMock()
    session.scalar.return_value = stored

    assert resolve_system_prompt(session, "evaluator", "Default prompt") == expected
