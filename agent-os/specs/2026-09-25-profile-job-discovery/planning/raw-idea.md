# Raw Idea

**Source:** `agent-os/product/roadmap.md` — Phase 2: Profile & Job Discovery (next uncompleted phase after Phase 1: Foundation (MVP), which is complete per commit `78f37f8 Implement Phase 1 foundation (MVP)`).

**Date captured:** 2026-09-25

## Goals

Enable the user to set up their profile and start discovering jobs automatically.

## Deliverables (as written in roadmap.md)

**Profile / Settings / Preferences Page**
- Resume upload (.docx or .pdf) — stored to disk and converted to text
- AI extraction of desired title, hard skills, soft skills from resume
- All preference fields: desired titles, country, currency, salary ranges, seniority, address, gender, EEO questions
- Delete existing resume functionality

**Backend: Job Fetcher (`fetcher.py`)**
- Integration with all job boards/ATS supported by Career-Ops
- Deduplication by URL before insert
- Invoke evaluator agent per new job
- Company lookup (DB first, then AI agent)
- Set `inbox_type` based on match score (recommended vs ignored)
- Scheduled run every 30 minutes via Docker Compose cron

**Backend: Evaluator Agent (`evaluator.py`)**
- LangGraph-based evaluation of job vs. user preferences and skills
- Populate scoring columns: overall_score, experience_score, skill_score, industry_exp_score
- Extract: compensation_range, work_arrangement, job_type_classification, seniority_level, year_exp, visa_sponsorship, location fields

**Backend: Company Lookup Agent (`company_lookup.py`)**
- Given company name + optional job description, use LLM to populate companies table

## Note

This idea was selected automatically (no interactive feature description was provided by the user for this spec-init run). It represents the entirety of Phase 2 in the roadmap, mirroring how Phase 1 was implemented as a single unit in a prior commit.
