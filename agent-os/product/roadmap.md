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
- [x] Scheduled run once a day via Docker Compose cron (was every 30 minutes; changed 2026-09-25)

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
- [x] Card-based job list (no HTML tables)
- [x] Alternating card background colors
- [x] Per-card: title, company, industry, growth stage, location, work arrangement, job type, salary range, seniority, years exp, match strength, visa sponsorship indicator
- [x] Jobs whose AI evaluation failed (Ignored inbox, no scores) show a "Not scored" marker with the failure reason from `jobs.evaluation_error`
- [x] Heart icon to like/unlike jobs
- [x] Filters: seniority level, work arrangement, job type classification, visa sponsorship
- [x] Search by company name

**Job Details Page**
- [x] Company name, job title, visa sponsorship, location, arrangement, type, seniority, years, scores
- [x] When evaluation failed: a notice with the failure reason (`jobs.evaluation_error`) in place of the scores
- [x] Full job description
- [x] Networking / Outreach section (contacts from company_networking)
- [x] Click name → open LinkedIn + copy connection request message to clipboard
- [x] Company details section (description, history, industries, growth stage, employee estimate)
- [x] Apply button

**Company Details Page**
- [x] Company name, description, industries, growth_stage, employee estimate, history
- [x] List of jobs from jobs table
- [x] List of contacts from company_networking table
- [x] LinkedIn company page link
- [x] LinkedIn people tab link

**Companies Page**
- [x] Sorted by liked, then alphabetically
- [x] Search box (intelligent)
- [x] Industry filter (multi-select dropdown)
- [x] Like/unlike per company
- [x] Manual add company form (all fields required except history)
- [x] Click company name → company details page

---

## Phase 4: Networking Agent

### Goals
Find relevant LinkedIn contacts at target companies when the user asks for them. The app never sends LinkedIn connection requests or messages; Phase 3 click-to-connect stays the only way to reach out.

### Deliverables

**Networking Agent (`networking.py`)**
- [x] Button-triggered only: a "Find contacts" button on Job Details and Company Details, available for companies with a recommended or applied job (never run by the fetcher or on a schedule)
- [x] One SerpApi Google search (`site:linkedin.com/in "<company>" "<role title>"`) per click, using the job title without seniority words
- [x] One LLM call picks up to 5 people from the search results (peers first, at most one hiring manager); the user's hard skills found in the posting are ranking signals
- [x] Populate `company_networking`, deduplicated by normalized LinkedIn URL; contacts already marked "Request sent" are never changed

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
