"""Request and response models for ``/api/v1/jobs``."""

from typing import Self

from pydantic import BaseModel, ConfigDict

from src.api.v1.schemas.companies import CompanyRead
from src.api.v1.schemas.contacts import ContactRead, ContactSearchStatus
from src.api.v1.schemas.job_card import JobCard
from src.models import Company, CompanyNetworking, Job


class JobDetail(JobCard):
    """One job with its full text, all four scores, its company and the company's contacts."""

    url: str
    source: str | None
    description: str | None
    experience_score: int | None
    skill_score: int | None
    industry_exp_score: int | None
    company: CompanyRead
    contacts: list[ContactRead]
    contact_search: ContactSearchStatus

    @classmethod
    def from_model(
        cls,
        job: Job,
        company: Company,
        contacts: list[CompanyNetworking],
        contact_search: ContactSearchStatus,
    ) -> Self:
        return cls.model_validate(
            {
                **cls.card_fields(job, company),
                "url": job.url,
                "source": job.source,
                "description": job.description,
                "experience_score": job.experience_score,
                "skill_score": job.skill_score,
                "industry_exp_score": job.industry_exp_score,
                "company": CompanyRead.from_model(company),
                "contacts": [ContactRead.from_model(contact) for contact in contacts],
                "contact_search": contact_search,
            }
        )


class JobPatch(BaseModel):
    """Only ``liked`` is editable; inbox changes come from the fetcher, Apply and Re-evaluate."""

    model_config = ConfigDict(extra="forbid")

    liked: bool


class JobList(BaseModel):
    items: list[JobCard]
    next_cursor: str | None
