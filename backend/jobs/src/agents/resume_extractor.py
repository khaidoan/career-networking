"""Resume extractor: suggests desired titles, hard skills and soft skills from resume text."""

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.llm import complete_structured, resolve_system_prompt
from src.tags import normalize_tags

AGENT_NAME = "resume_extractor"
MAX_RESUME_CHARS = 30_000

RESUME_EXTRACTOR_SYSTEM_PROMPT = """\
You read a candidate's resume and suggest profile values for a job search.

Return:
- desired_titles: 1 to 5 job titles the candidate is a strong fit for next, based on their most
  recent roles and seniority (for example "Senior Backend Engineer").
- hard_skills: concrete technical or domain skills, tools, languages and certifications named
  or clearly demonstrated in the resume.
- soft_skills: interpersonal and working-style skills evidenced in the resume (for example
  "Stakeholder management", "Mentoring").

Use short, conventional names (1 to 4 words each). Do not invent skills that the resume does not
support. Do not include personal details such as names, contact details or addresses.
"""


class ResumeSuggestions(BaseModel):
    desired_titles: list[str] = []
    hard_skills: list[str] = []
    soft_skills: list[str] = []

    @field_validator("desired_titles", "hard_skills", "soft_skills", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> list[str]:
        return normalize_tags(value if isinstance(value, list) else None)


def extract_resume_suggestions(session: Session, resume_text: str) -> ResumeSuggestions:
    """Suggested titles and skills; raises ``LlmError`` if the model cannot be used."""
    system_prompt = resolve_system_prompt(session, AGENT_NAME, RESUME_EXTRACTOR_SYSTEM_PROMPT)
    return complete_structured(
        system_prompt,
        f"Resume:\n{resume_text[:MAX_RESUME_CHARS]}",
        ResumeSuggestions,
        agent_name=AGENT_NAME,
    )
