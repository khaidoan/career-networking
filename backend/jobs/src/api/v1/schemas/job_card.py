"""The job list item; shared by the inbox list and Company Details (kept apart to avoid a cycle
between the jobs and companies schemas)."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel

from src.models import Company, Job


class JobCard(BaseModel):
    """One job with the few company fields a card shows (joined, not loaded per row)."""

    id: int
    title: str
    company_id: int
    company_name: str
    company_industries: list[str]
    company_growth_stage: str | None
    location_city: str | None
    location_state: str | None
    location_country: str | None
    work_arrangement: str | None
    job_type_classification: str | None
    seniority_level: str | None
    year_exp: int | None
    compensation_range: str | None
    visa_sponsorship: bool | None
    overall_score: int | None
    evaluation_error: str | None
    inbox_type: str
    liked: bool
    discovered_when: datetime
    applied_when: datetime | None

    @classmethod
    def card_fields(cls, job: Job, company: Company) -> dict[str, object]:
        return {
            "id": job.id,
            "title": job.title,
            "company_id": company.id,
            "company_name": company.name,
            "company_industries": company.industries or [],
            "company_growth_stage": company.growth_stage,
            "location_city": job.location_city,
            "location_state": job.location_state,
            "location_country": job.location_country,
            "work_arrangement": job.work_arrangement,
            "job_type_classification": job.job_type_classification,
            "seniority_level": job.seniority_level,
            "year_exp": job.year_exp,
            "compensation_range": job.compensation_range,
            "visa_sponsorship": job.visa_sponsorship,
            "overall_score": job.overall_score,
            "evaluation_error": job.evaluation_error,
            "inbox_type": job.inbox_type,
            "liked": job.liked,
            "discovered_when": job.discovered_when,
            "applied_when": job.applied_when,
        }

    @classmethod
    def from_model(cls, job: Job, company: Company) -> Self:
        return cls.model_validate(cls.card_fields(job, company))
