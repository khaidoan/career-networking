# Career Networking — Roadmap

## Phase 1: Foundation (MVP)

### Goals
Establish the project structure, database schema, authentication, and core UI skeleton.

### Deliverables

**Infrastructure & DevOps**
- [x] Monorepo structure: `frontend/` and `backend/` folders
- [x] Docker Compose setup with services: frontend, jobs (backend), postgres, nginx
- [x] `.env` at the repo root with all required environment variables (the only runtime env file, loaded by both compose files), created from the committed `.env.example` template
- [x] Data volume mounts: `backend/data/resume`, `backend/data/jobs`, `backend/logs`
- [x] `.gitignore` entries for data and log folders

**Database (PostgreSQL + SQLAlchemy + Alembic)**
- [x] `preferences` table (desired titles, country, currency, salary, seniority, address, skills, resume location, resume text, hard_skills, soft_skills)
- [x] `companies` table (id, name, website_url, history, linkedin_url, logo_url, description, industries, growth_stage, liked)
- [x] `jobs` table (all columns including scoring, inbox_type, source, location, applied_when, discovered_when)
- [x] `company_networking` table (company_id, first_name, last_name, linkedin_url, title, connection_request_sent)
- [x] `prompts` table (agent name, system prompt, is_customized)
- [x] Alembic migrations for all tables

**Authentication**
- [x] Login page (JWT, credentials from env vars, no localStorage)
- [x] Protected routes in Next.js

**Frontend Skeleton (Next.js + React)**
- [x] Top navigation bar (app name link, user avatar with initials)
- [x] Left sidebar navigation (all pages linked)
- [x] Warm, modern, minimalist design system

---

## Phase 2: Profile & Job Discovery

### Goals
Enable the user to set up their profile and start discovering jobs automatically.

### Deliverables

**Profile / Settings / Preferences Page**
- [x] Resume upload (.docx or .pdf) — stored to disk and converted to text
- [x] AI extraction of desired title, hard skills, soft skills from resume
- [x] All preference fields: desired titles, country, currency, salary ranges, seniority, address, gender, EEO questions
- [x] Delete existing resume functionality

**Backend: Job Fetcher (`fetcher.py`)**
- [x] Integration with all job boards/ATS supported by Career-Ops
- [x] Deduplication by URL before insert
- [x] Invoke evaluator agent per new job
- [x] Company lookup (DB first, then AI agent)
- [x] Set `inbox_type` based on match score (recommended vs ignored)
- [x] Scheduled run every 30 minutes via Docker Compose cron

**Backend: Evaluator Agent (`evaluator.py`)**
- [x] LangGraph-based evaluation of job vs. user preferences and skills
- [x] Populate scoring columns: overall_score, experience_score, skill_score, industry_exp_score
- [x] Extract: compensation_range, work_arrangement, job_type_classification, seniority_level, year_exp, visa_sponsorship, location fields

**Backend: Company Lookup Agent (`company_lookup.py`)**
- [x] Given company name + optional job description, use LLM to populate companies table

---

## Phase 3: Inbox & Job Details UI

### Goals
Display discovered jobs in an actionable inbox interface.

### Deliverables

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

---

## Phase 4: Networking Agent

### Goals
Automate discovery of relevant LinkedIn contacts at target companies.

### Deliverables

**Networking Agent (`networking.py`)**
- On job fetch, extract company name and skillset from posting
- Search LinkedIn for employees with matching skills
- Populate `company_networking` table
- Playwright-based LinkedIn outreach (user-triggered via UI button)

---

## Phase 5: Apply Flow (Manual with AI Assist)

### Goals
Help the user prepare tailored application materials and apply manually or semi-automatically.

### Deliverables

**Prepare Job Agent (`prepare_job.py`) — LangGraph graph**
- Fetch preferences
- Cover letter agent → Cover letter reviewer agent → Resume agent → Resume reviewer agent (chain)
- Output: markdown cover letter and tailored resume
- Preview: convert markdown to PDF, save to `CAREER_NETWORKING_JOB_DATA/{job_id}/`
- File naming: `{FirstName}{LastName}_{CoverLetter|Resume}.pdf`

**Apply Flow UI**
- "Apply" button on job card and job details page
- Markdown editor for cover letter and resume (user can edit)
- Preview button → renders PDF previews in-browser
- Submit button → triggers apply agent
- Post-apply: download links for submitted resume and cover letter

**Apply Agent (`apply.py`) — stub**
- Playwright-based form filling
- Use tailored PDFs from job folder
- Unknown question handling: email user + set inbox_type to `need_attention`

---

## Phase 6: Prompts Customization & Polish

### Goals
Allow prompt customization and finalize all secondary pages.

### Deliverables

**Prompts Page**
- Display all agent prompts (text areas)
- Customization indicator icon per prompt
- Reset-to-default icon per prompt
- Save customized prompts to DB

**Interview Tips Page**
- Static/curated content: common interview tips, questions to ask

**Feedback Page**
- GitHub repository URL
- Encouragement to file issues / PRs

**Logging**
- All backend Python files log to `career_networking.log` in `CAREER_NETWORKING_LOG_FOLDER`
- Centralized logging configuration

---

## Deferred / Out of Scope (v1)

- Recruiter-initiated contact
- Multi-user support
- SaaS hosting
- Auto-connect to LinkedIn (due to rate limiting / account risk)
- Auto-apply (ATS bypass)
- Message center
- Multiple country support per installation (use separate installations)
