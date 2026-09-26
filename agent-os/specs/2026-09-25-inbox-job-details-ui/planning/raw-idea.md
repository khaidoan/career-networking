# Raw Idea

**Source:** `agent-os/product/roadmap.md` — Phase 3: Inbox & Job Details UI (next uncompleted phase after Phase 1: Foundation (MVP) and Phase 2: Profile & Job Discovery, both complete per commits `78f37f8 Implement Phase 1 foundation (MVP)` and `b75c1e9 Implement Phase 2: profile and job discovery`).

**Date captured:** 2026-09-25

## Goals

Display discovered jobs in an actionable inbox interface.

## Deliverables (as written in roadmap.md)

**Inbox Pages (Recommended, Applied, Ignored, Need Attention)**
- Card-based job list (no HTML tables)
- Alternating card background colors
- Per-card: title, company, industry, growth stage, location, work arrangement, job type, salary range, seniority, years exp, match strength, visa sponsorship indicator
- Jobs whose AI evaluation failed (Ignored inbox, no scores) show a "Not scored" marker with the failure reason from `jobs.evaluation_error`
- Heart icon to like/unlike jobs
- Filters: seniority level, work arrangement, job type classification, visa sponsorship
- Search by company name

**Job Details Page**
- Company name, job title, visa sponsorship, location, arrangement, type, seniority, years, scores
- When evaluation failed: a notice with the failure reason (`jobs.evaluation_error`) in place of the scores
- Full job description
- Networking / Outreach section (contacts from company_networking)
- Click name → open LinkedIn + copy connection request message to clipboard
- Company details section (description, history, industries, growth stage, employee estimate)
- Apply button

**Company Details Page**
- Company name, description, industries, growth_stage, employee estimate, history
- List of jobs from jobs table
- List of contacts from company_networking table
- LinkedIn company page link
- LinkedIn people tab link

**Companies Page**
- Sorted by liked, then alphabetically
- Search box (intelligent)
- Industry filter (multi-select dropdown)
- Like/unlike per company
- Manual add company form (all fields required except history)
- Click company name → company details page

## Note

This idea was selected automatically (no interactive feature description was provided by the user for this spec-init run). It represents the entirety of Phase 3 in the roadmap, mirroring how Phases 1 and 2 were each implemented as a single unit in prior commits.
