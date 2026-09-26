"""Evaluator: scores a job against the user's preferences and resume, and extracts job facts.

A small LangGraph ``StateGraph``: build context -> call LLM -> validate, looping back to the LLM
once with the validation error before giving up with ``LlmOutputError``.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.llm import (
    MAX_STRUCTURED_ATTEMPTS,
    LlmOutputError,
    Message,
    build_messages,
    complete,
    llm_safe_preferences,
    parse_structured,
    resolve_system_prompt,
    retry_messages,
)
from src.models import Preferences
from src.vocabularies import (
    COUNTRIES,
    JOB_TYPES,
    SENIORITY_LEVELS,
    WORK_ARRANGEMENTS,
    slug_or_none,
)

AGENT_NAME = "evaluator"
MAX_DESCRIPTION_CHARS = 20_000
MAX_RESUME_CHARS = 20_000

EVALUATOR_SYSTEM_PROMPT = f"""\
You evaluate how well one job posting fits one candidate, and extract facts from the posting.

You receive the posting (title, company, location, description), the candidate's job
preferences and, when available, their resume text.

Scores are whole numbers from 0 (no fit) to 100 (perfect fit):
- experience_score: how well the candidate's years and kind of experience match what the job
  asks for.
- skill_score: overlap between the job's required and preferred skills and the candidate's hard
  and soft skills and resume.
- industry_exp_score: how closely the candidate's industry and domain background matches the
  company's industry and the role's domain.
- overall_score: your overall judgement of fit, also weighing title and seniority alignment,
  location and country, work authorization and sponsorship needs, and salary expectations.
  A job the candidate clearly cannot take (for example it needs sponsorship the company does
  not offer) must score low.

Extract from the posting only; do not use the candidate's data for these fields:
- compensation_range: the pay range as written (for example "$150,000 - $180,000 per year").
- work_arrangement: one of {", ".join(WORK_ARRANGEMENTS)}.
- job_type_classification: one of {", ".join(JOB_TYPES)}.
- seniority_level: one of {", ".join(SENIORITY_LEVELS)}.
- year_exp: the minimum years of experience required, as a whole number.
- visa_sponsorship: true if the posting says it sponsors visas, false if it says it does not.
- location_city, location_state, location_country (ISO 3166-1 alpha-2 code, for example "US").

If the posting does not state a value, return null for it. Do not guess.
"""

Score = Annotated[int, Field(ge=0, le=100)]


class JobEvaluation(BaseModel):
    overall_score: Score
    experience_score: Score
    skill_score: Score
    industry_exp_score: Score
    compensation_range: str | None = None
    work_arrangement: str | None = None
    job_type_classification: str | None = None
    seniority_level: str | None = None
    year_exp: int | None = Field(default=None, ge=0)
    visa_sponsorship: bool | None = None
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None

    @field_validator("work_arrangement", mode="before")
    @classmethod
    def _work_arrangement(cls, value: object) -> str | None:
        return slug_or_none(value, WORK_ARRANGEMENTS)

    @field_validator("job_type_classification", mode="before")
    @classmethod
    def _job_type(cls, value: object) -> str | None:
        return slug_or_none(value, JOB_TYPES)

    @field_validator("seniority_level", mode="before")
    @classmethod
    def _seniority(cls, value: object) -> str | None:
        return slug_or_none(value, SENIORITY_LEVELS)

    @field_validator(
        "compensation_range", "location_city", "location_state", "location_country", mode="before"
    )
    @classmethod
    def _blank_is_null(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("location_country")
    @classmethod
    def _country_code(cls, value: str | None) -> str | None:
        """Prefer the ISO code; a recognised country name is converted, anything else kept."""
        if value is None or value.upper() in COUNTRIES:
            return value.upper() if value else None
        lowered = value.lower()
        for country in COUNTRIES.values():
            if lowered in country.match_terms:
                return country.code
        return value


@dataclass(frozen=True)
class JobForEvaluation:
    """The posting fields the evaluator reads; built by the fetcher from a source posting."""

    title: str
    company: str
    location: str | None = None
    description: str | None = None


class EvaluatorState(TypedDict, total=False):
    system_prompt: str
    job: JobForEvaluation
    preferences: Preferences | None
    messages: list[Message]
    raw_output: str
    attempts: int
    problem: str | None
    evaluation: JobEvaluation | None


def build_context(job: JobForEvaluation, preferences: Preferences | None) -> str:
    """The user message: job text, LLM-safe preferences and resume text only."""
    candidate: dict[str, Any] = {"preferences": llm_safe_preferences(preferences)}
    resume_text = preferences.resume_text if preferences is not None else None
    sections = [
        "Job posting:",
        json.dumps(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": (job.description or "")[:MAX_DESCRIPTION_CHARS],
            },
            ensure_ascii=False,
        ),
        "Candidate:",
        json.dumps(candidate, ensure_ascii=False),
    ]
    if resume_text:
        sections += ["Candidate resume:", resume_text[:MAX_RESUME_CHARS]]
    return "\n".join(sections)


def _build_context_node(state: EvaluatorState) -> EvaluatorState:
    user_content = build_context(state["job"], state.get("preferences"))
    return {
        "messages": build_messages(state["system_prompt"], user_content, JobEvaluation),
        "attempts": 0,
    }


def _call_llm_node(state: EvaluatorState) -> EvaluatorState:
    raw_output = complete(state["messages"], agent_name=AGENT_NAME)
    return {"raw_output": raw_output, "attempts": state["attempts"] + 1}


def _validate_node(state: EvaluatorState) -> EvaluatorState:
    try:
        return {"evaluation": parse_structured(state["raw_output"], JobEvaluation), "problem": None}
    except ValueError as error:
        problem = str(error)
        return {
            "evaluation": None,
            "problem": problem,
            "messages": retry_messages(state["messages"], state["raw_output"], problem),
        }


def _after_validate(state: EvaluatorState) -> str:
    if state.get("evaluation") is not None or state["attempts"] >= MAX_STRUCTURED_ATTEMPTS:
        return END
    return "call_llm"


@lru_cache
def evaluator_graph() -> Any:
    graph = StateGraph(EvaluatorState)
    graph.add_node("build_context", _build_context_node)
    graph.add_node("call_llm", _call_llm_node)
    graph.add_node("validate", _validate_node)
    graph.add_edge(START, "build_context")
    graph.add_edge("build_context", "call_llm")
    graph.add_edge("call_llm", "validate")
    graph.add_conditional_edges("validate", _after_validate, ["call_llm", END])
    return graph.compile()


def evaluate_job(
    session: Session, job: JobForEvaluation, preferences: Preferences | None
) -> JobEvaluation:
    """Score and classify one job; raises ``LlmError`` (or ``LlmOutputError``) on failure."""
    system_prompt = resolve_system_prompt(session, AGENT_NAME, EVALUATOR_SYSTEM_PROMPT)
    final_state = evaluator_graph().invoke(
        {"system_prompt": system_prompt, "job": job, "preferences": preferences}
    )
    evaluation = final_state.get("evaluation")
    if evaluation is None:
        raise LlmOutputError(
            f"{AGENT_NAME}: invalid LLM output after retry ({final_state.get('problem')})"
        )
    return evaluation
