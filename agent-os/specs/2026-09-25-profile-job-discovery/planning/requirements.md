# Spec Requirements: Phase 2 — Profile & Job Discovery

## Initial Description
Phase 2: Profile & Job Discovery from `agent-os/product/roadmap.md` (the next uncompleted phase after Phase 1: Foundation (MVP), commit `78f37f8`). Goal: enable the user to set up their profile and start discovering jobs automatically.

Deliverables as written in the roadmap:

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

## Requirements Discussion

### First Round Questions

**Q1:** Scope and splitting. This phase has four deliverables (Profile page, `fetcher.py`, `evaluator.py`, `company_lookup.py`). I assume we build it as a single spec, the same way Phase 1 was done. Is that right, or do you want two specs (Profile/Preferences, then Fetcher + Evaluator + Company Lookup)?
**Answer:** Single spec (agreed).

**Q2:** LLM configuration. Add `CAREER_NETWORKING_LLM_MODEL` (a LiteLLM model string), the standard provider API keys passed to LiteLLM, and optionally `CAREER_NETWORKING_LLM_API_BASE` for local models. All agents share one model, or can each agent use its own? Should agents check the `prompts` table for a customized prompt now, with the `{AGENT}_SYSTEM_PROMPT` constant as fallback, even though the Prompts page arrives in Phase 6?
**Answer:** Yes — add the new env vars to .env.example. All agents share one model. Check the `prompts` table for overrides now, with the constant as fallback. ALSO support OpenRouter (e.g. `openrouter/...` LiteLLM model strings + OPENROUTER_API_KEY in .env.example).

**Q3:** Resume upload and AI extraction. Keep one resume, saved as `CAREER_NETWORKING_RESUME_FOLDER/resume.{pdf|docx}`; a new upload replaces the old one. Max 10 MB, file type checked. Extract text with python-docx / pdfminer.six into `resume_text`, with the path in `resume_location`. The LLM suggests desired titles, hard skills and soft skills, which fill the form as editable suggestions and are saved only when the user clicks Save. Deleting the resume removes the file and clears `resume_location` and `resume_text`, but keeps the extracted skills and titles. Is that right? Keep or drop the generic `skills` column?
**Answer:** Proposed behavior accepted. Use `hard_skills` and `soft_skills` columns and DROP the generic `skills` column (migration needed).

**Q4:** Preference fields and EEO. Tag inputs for desired titles, hard skills and soft skills; a country dropdown (one country); an ISO 4217 currency dropdown defaulting from the country; annual whole-number salary min/max with min ≤ max; seniority from a fixed list (Intern, Entry, Mid, Senior, Staff/Principal, Lead/Manager, Director, VP+), single or multiple choice?; free-text address; gender; and EEO answers in `eeo_answers` JSONB (race/ethnicity, veteran status, disability status, work authorization, needs visa sponsorship), each with "Decline to answer". Should any fields be required before the fetcher runs?
**Answer:** Seniority is MULTIPLE choice. The fetcher must wait (skip runs) until at least desired titles and country are set. Rest of proposed field list accepted.

**Q5:** Job sources. Career-Ops mainly scans public ATS APIs from a configured company list and doesn't scrape LinkedIn/Indeed/Glassdoor. Proposed a pluggable `JobSource` interface with Greenhouse, Lever, Ashby, SmartRecruiters and Workable adapters, searching the `companies` table plus a seed list, and deferring LinkedIn, Indeed, Glassdoor, ZipRecruiter, Workday, iCIMS, Taleo, Jobvite and BambooHR. Acceptable? Career-Ops repo to reference?
**Answer:** Pull jobs from public ATS APIs but do NOT use the `companies` table as a seed list (figure out an alternative discovery approach, e.g. how Career-Ops does it). Investigate supporting LinkedIn, Indeed, Glassdoor, Workday, etc. via Google Jobs (e.g. a Google Jobs search API such as SerpApi's google_jobs engine or similar) — research feasibility and record findings/options. Career-Ops repo to reference: https://github.com/career-ops-hq/career-ops — please review it for how it discovers and scans jobs.

**Q6:** Scheduling, dedup and failures. A separate `fetcher` compose service built from the `backend/jobs` image runs `python -m src.fetcher` every 30 minutes (supercronic or a cron loop) with an overlap lock. Duplicates are caught by normalizing the URL (tracking parameters stripped) before insert, with the `jobs.url` unique constraint as a backstop. A failing job or source is logged and skipped. A job whose evaluation fails is saved with null scores. Optional "Fetch now" trigger. Evaluate each job once, or re-evaluate when preferences change?
**Answer:** Proposed behavior accepted. Each job is evaluated only ONCE (no re-evaluation on preference/resume change).

**Q7:** Scoring, inbox routing and company lookup. The evaluator is a LangGraph graph that returns Pydantic-validated JSON with scores from 0 to 100. `inbox_type = recommended` when `overall_score >= 70`, else `ignored`; should the threshold be an env var or a preference field? Fixed value sets for work_arrangement (remote/hybrid/onsite), job_type_classification (full-time/part-time/contract/internship/temporary) and seniority_level (same list as preferences). Company lookup does a case-insensitive exact name match in the DB first; otherwise `company_lookup.py` uses the LLM (no web browsing) to fill website, LinkedIn URL, description, industries, growth stage, employee estimate and history, leaving unknown fields null.
**Answer:** Threshold is a new environment variable (CAREER_NETWORKING_MATCH_THRESHOLD, default 70). Rest of proposal accepted (no objections raised).

**Q8:** Out of scope. Inbox and Job Details UI (Phase 3); networking agent (Phase 4); Prompts page (Phase 6); email notifications; a web-search tool for company lookup; multiple resume versions; re-scoring past jobs; sources that need a login. Anything to add or bring into scope?
**Answer:** No changes given — proposed out-of-scope list accepted.

### Existing Code to Reference

**Similar Features Identified:**
- Feature: Career-Ops job discovery (external, MIT license) — Repo: https://github.com/career-ops-hq/career-ops
  - `scan-ats-full.mjs` — reverse ATS sweep using the Feashliaa/job-board-aggregator company directories (to be ported to Python, with credit)
  - `discover-ats.mjs` — resolves a company to a scannable ATS board by probing public APIs (vendor order: Greenhouse, Ashby, Lever, then Workable, SmartRecruiters, Rippling and others)
  - `providers/` — one module per ATS/board (`greenhouse.mjs`, `lever.mjs`, `ashby.mjs`, `workday.mjs`, `icims.mjs`, `bamboohr.mjs`, ...); `docs/SUPPORTED_JOB_BOARDS.md` describes each
  - `templates/portals.example.yml` — title/location filter semantics
- Company directory dataset (MIT): https://github.com/Feashliaa/job-board-aggregator (`data/{greenhouse,lever,ashby,workday,icims,bamboohr}_companies.json`, updated daily)
- Phase 1 code in this repo (internal patterns to follow):
  - Profile page placeholder: `frontend/app/(app)/profile/page.tsx`
  - shadcn/ui components: `frontend/components/ui/` (button, input, label, card, badge, dropdown-menu, sheet, separator, avatar)
  - Models: `backend/jobs/src/models/preferences.py` (single-row, already has `gender`, `eeo_answers`), `job.py` (`INBOX_TYPES`, `SCORE_COLUMNS`, unique `url`), `company.py`, `prompt.py`
  - Settings: `backend/jobs/src/config.py`; errors: `backend/jobs/src/errors.py`; logging: `backend/jobs/src/logging_config.py`; auth dependency: `backend/jobs/src/auth/dependencies.py`; router: `backend/jobs/src/api/v1/router.py`
  - Migrations: `backend/jobs/alembic/versions/` (one reversible migration per change)
  - Compose: `docker-compose.yml`, `dev-docker-compose.yml`

### Follow-up Questions

**Follow-up 1:** How are jobs found without the companies table? Proposed porting Career-Ops's reverse ATS sweep (job-board-aggregator directories for Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR, refreshed every 24h) with rotating batches, plus free no-key feeds (Himalayas, Remotive, The Muse, Arbeitnow), and asked whether to include the YC/a16z seed list.
**Answer:** Reverse ATS sweep accepted (see the combined decision below). The free no-key feeds and the YC/a16z seeds were NOT confirmed and are out of scope; they are listed as possible future enhancements.

**Follow-up 2:** Google Jobs for LinkedIn/Indeed/Glassdoor/Workday coverage: an optional SerpApi `google_jobs` source enabled by `SERPAPI_API_KEY`, running once a day by default, with one query per desired title in the user's country. SerpApi or another provider (SearchApi.io, JSearch)?
**Answer:** SerpApi `google_jobs`, as proposed (see the combined decision below).

**Follow-up 3:** `python-jobspy` direct scraping: exclude, or add as an opt-in source?
**Answer:** NO python-jobspy, NO keyless scraping of Google, NO Adzuna/Jooble (for now).

**Combined job-source decision (user, verbatim intent):**
- The user must never have to add boards manually. The `companies` table is not used as a seed list.
- Hybrid discovery plus a self-populating watch list:
  1. Discovery (daily cadence):
     a. Google Jobs via SerpApi `google_jobs` engine. Optional: enabled only when `SERPAPI_API_KEY` is set; skipped silently (logged) otherwise. Runs once per day (`CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS`, default 24), one query per desired title in the user's country, a few result pages per title, sized to stay within SerpApi's free tier (250 searches/month). Jobs found here are ingested (URL = first direct apply link; fetch the full description from that link when the snippet is truncated). This is how LinkedIn/Indeed/Glassdoor/Workday listings are covered.
     b. Reverse ATS sweep (ported to Python from Career-Ops `scan-ats-full.mjs`, MIT, credited) using the Feashliaa/job-board-aggregator company directories (Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR), cached 24h. Completes one full pass per day, spread in rotating batches across the 30-minute runs. Only postings matching desired titles + country (and recent) are kept.
  2. Auto-populated `ats_boards` table (new, separate from `companies`): any ATS board (provider + slug/URL) where discovery (a or b) finds a matching posting is added automatically, including boards detected from Google Jobs apply links that point to a supported ATS.
  3. Tracking: every 30-minute fetcher run polls all boards in `ats_boards` via their public APIs (full descriptions, real ATS URLs).
  4. Pruning: boards with no matching postings for ~30 days are removed/deactivated, and re-added if discovery finds them again.
- Resilience: if the external directory disappears, tracking of already-discovered boards continues.
- Cross-source duplicates (same job via Google Jobs and ATS) are an accepted limitation in Phase 2; prefer the ATS URL where detectable.
- Env vars to add to `.env.example`: `SERPAPI_API_KEY` (optional), `CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS`, plus the LLM vars (including OpenRouter) and `CAREER_NETWORKING_MATCH_THRESHOLD`.
- Documentation: README.md must include setup instructions for obtaining and configuring `SERPAPI_API_KEY` (the coordinator is adding that section; the spec must keep it in sync).

### Research Findings (recorded at the user's request)

**Career-Ops discovery (reviewed 2026-09-25):**
- `scan.mjs` scans a user-maintained `portals.yml` company list through about 100 provider modules.
- `scan-ats-full.mjs` needs no curation. It downloads per-ATS company directories from `https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data` (cached 24h), calls each board's public JSON API, and keeps only recent postings that match the title/location filters. Postings without a publish date are skipped. It has a checkpoint so an interrupted sweep can resume.
- Directory sizes as of 2026-09-25: greenhouse about 143 KB, lever about 67 KB, ashby about 46 KB, workday about 398 KB, icims about 218 KB, bamboohr about 187 KB (several thousand companies in total), hence the rotating batches.
- Career-Ops does not scrape LinkedIn, Indeed or Glassdoor. Its docs say Glassdoor/Dice need stealth browser automation, which is out of scope on technical and ethical grounds.

**SerpApi `google_jobs`:**
- Parameters: `q`, `location`, `gl`, `hl`, `lrad`. Pagination uses `next_page_token` (the `start` parameter is gone). The `ltype` and `chips` filters are deprecated. Up to 10 results per page.
- Result fields: `title`, `company_name`, `location`, `via` (original board), `description` (may be truncated), `job_highlights`, `detected_extensions` (posted_at, schedule_type, salary), `apply_options[{title, link}]`, `job_id`, `share_link`.
- Pricing: Free 250 searches/month; Starter $25 for 1,000; Developer $75 for 5,000. Only successful searches count; cached, errored and failed ones do not.
- Budget: running every 30 minutes would be about 1,440 searches a month per title, which is why it runs daily. Example: 2 titles × 3 pages × 30 days = 180 searches/month.

**Alternatives considered and rejected:** SearchApi.io, Scrapingdog and JSearch (RapidAPI) Google Jobs APIs (SerpApi chosen); `python-jobspy` (ToS/IP-ban risk; rejected); keyless Google scraping (rejected); Adzuna/Jooble APIs (not for now).

## Visual Assets

### Files Provided:
No visual assets provided. (Bash check of `planning/visuals/` found no image or PDF files.)

### Visual Insights:
Not applicable. The Profile page should use the Phase 1 design system (warm, modern, minimalist; shadcn/ui; Tailwind; Lucide icons).

## Requirements Summary

### Functional Requirements

**Profile / Preferences page (`/profile`)**
- Resume upload (.pdf or .docx, max 10 MB, type checked by extension and content). Only one resume is kept: it is saved as `CAREER_NETWORKING_RESUME_FOLDER/resume.{pdf|docx}` and a new upload replaces the old one. Text is extracted (python-docx / pdfminer.six) into `preferences.resume_text`, and the path goes into `preferences.resume_location`.
- After upload, the LLM suggests desired titles, hard skills and soft skills. These fill the form as editable suggestions and are saved only when the user clicks Save.
- Delete resume: removes the file and clears `resume_location` and `resume_text`; extracted titles and skills are kept.
- Preference fields:
  - Desired titles, hard skills, soft skills — tag/chip inputs
  - Country — single dropdown (one country per installation)
  - Currency — ISO 4217 dropdown, defaulting from the country
  - Salary min / max — annual whole numbers, min ≤ max
  - Seniority — MULTIPLE choice from: Intern, Entry, Mid, Senior, Staff/Principal, Lead/Manager, Director, VP+
  - Address — free text
  - Gender
  - EEO answers (stored in `eeo_answers` JSONB): race/ethnicity, veteran status, disability status, work authorization, needs visa sponsorship — each with a "Decline to answer" option
- Data changes: drop `preferences.skills`; change `preferences.seniority` from single text to multiple values. Both need reversible Alembic migrations.

**LLM configuration (shared by all agents)**
- One model for every agent, set by a LiteLLM model string (e.g. `CAREER_NETWORKING_LLM_MODEL`), with an optional API base for local models.
- Supported providers include OpenAI, Anthropic, local (e.g. Ollama) and OpenRouter (`openrouter/...` model strings with `OPENROUTER_API_KEY`).
- Each agent defines a `{AGENT_NAME}_SYSTEM_PROMPT` constant. At runtime it uses the `prompts` table row for that agent when `is_customized` is true, otherwise the constant.

**Job Fetcher (`fetcher.py`)**
- Runs every 30 minutes in a dedicated compose service (same `backend/jobs` image) with an overlap lock so runs never overlap.
- Skips the run (logged) until at least desired titles and country are set.
- Sources:
  1. Google Jobs discovery via SerpApi (optional, daily; see the decision above).
  2. Reverse ATS sweep over the job-board-aggregator directories (Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR), cached 24h, one full pass per day in rotating batches across the 30-minute runs.
  3. Tracking: every run polls all active boards in the new `ats_boards` table.
- `ats_boards` table (new): provider + slug/URL, added automatically when discovery finds a matching posting (including boards detected from Google Jobs apply links). It records last-matched time and is deactivated after about 30 days without matches, then reactivated if discovery finds the board again.
- Filtering: title matches desired titles, location matches the country, posting is recent.
- Deduplication: normalize the URL (strip tracking parameters) and check before insert; the `jobs.url` unique constraint is the backstop. Prefer the ATS URL where a Google Jobs apply link points to a supported ATS.
- For each new job: company lookup (case-insensitive exact name match in DB, else the Company Lookup agent), then the evaluator, then set `inbox_type`.
- Failures: one bad job or source is logged and skipped and the run continues. A job whose evaluation fails is saved with null scores. Each job is evaluated exactly once.

**Evaluator Agent (`evaluator.py`)**
- LangGraph graph comparing the job with preferences, the resume text and skills. It returns structured JSON validated with Pydantic.
- Scores 0–100: `overall_score`, `experience_score`, `skill_score`, `industry_exp_score`.
- Extracts `compensation_range`, `work_arrangement` (remote/hybrid/onsite), `job_type_classification` (full-time/part-time/contract/internship/temporary), `seniority_level` (same list as preferences), `year_exp`, `visa_sponsorship`, and location city/state/country.
- `inbox_type = recommended` if `overall_score >= CAREER_NETWORKING_MATCH_THRESHOLD` (default 70), else `ignored`.

**Company Lookup Agent (`company_lookup.py`)**
- Given a company name and optional job description, the LLM (model knowledge only, no web browsing) fills website_url, linkedin_url, description, industries, growth_stage, employee_estimate and history. Unknown fields are left null.

**Configuration and docs**
- `.env.example` additions: LLM model/API base, provider keys including `OPENROUTER_API_KEY`, `CAREER_NETWORKING_MATCH_THRESHOLD` (default 70), `SERPAPI_API_KEY` (optional), `CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS` (default 24).
- README.md: SerpApi key setup section kept in sync with the implementation, plus LLM configuration notes.
- Credit Career-Ops and job-board-aggregator (MIT) for the ported logic and data.

### Reusability Opportunities
- Phase 1 `Preferences` single-row model, `Job`/`Company`/`Prompt` models, `config.py` Settings (add the new variables with fail-fast validation), `errors.py`, `logging_config.py`, auth dependency, `/api/v1` router.
- shadcn/ui primitives in `frontend/components/ui/` for the Profile form; `PagePlaceholder` is replaced by the real page.
- Career-Ops `scan-ats-full.mjs`, `discover-ats.mjs` and `providers/{greenhouse,lever,ashby,workday,icims,bamboohr}.mjs` as reference implementations for the Python port (API endpoints, URL detection, date handling, pagination).
- Existing compose files for adding the `fetcher` service (with the same env file and volumes as `jobs`).

### Scope Boundaries
**In Scope:**
- Profile/Preferences page with resume upload, AI extraction, delete, and all preference/EEO fields
- Migrations: drop `skills`, make seniority multi-value, create `ats_boards`
- Shared LiteLLM configuration (including OpenRouter) and prompt override lookup
- `fetcher.py` with SerpApi Google Jobs discovery, reverse ATS sweep, `ats_boards` tracking and pruning, dedup, scheduling and overlap lock
- `evaluator.py` and `company_lookup.py`
- `.env.example` and README updates (including SerpApi setup)

**Out of Scope:**
- Inbox and Job Details UI (Phase 3); jobs are only visible through the API or database in Phase 2
- Networking agent (Phase 4); Prompts page (Phase 6)
- Email notifications
- Web search/browsing tool for company lookup
- Multiple resume versions
- Re-scoring past jobs when preferences or resume change
- Sources that require a login; python-jobspy; keyless Google scraping; Adzuna/Jooble
- Using the `companies` table as a seed list; manual board entry by the user
- Cross-source duplicate detection beyond URL (accepted limitation)
- Possible future enhancements: free no-key feeds (Himalayas, Remotive, The Muse, Arbeitnow), YC/a16z portfolio seeds, additional Career-Ops providers (SmartRecruiters, Workable, Rippling, etc.)

### Technical Considerations
- Stack: FastAPI, SQLAlchemy 2.x, Alembic (reversible migrations), LangGraph, LiteLLM, Next.js App Router with TypeScript and shadcn/ui/Tailwind, pytest and Vitest.
- New Python dependencies are likely: litellm, langgraph, python-docx, pdfminer.six, an HTTP client (httpx), and a cron runner (supercronic or equivalent) in the fetcher image.
- Resume upload runs behind JWT auth. The file is stored only on the mounted volume; the original filename is never trusted for the path.
- Rate and politeness: rotate ATS batches so a full pass takes a day; set timeouts per request; SerpApi usage is budgeted to the free tier by default.
- The external directory is cached on disk (e.g. under the jobs data volume or a cache folder). If it is unreachable, the cached copy is used, and tracking of `ats_boards` continues regardless.
- All components log to `career_networking.log` in `CAREER_NETWORKING_LOG_FOLDER`.
- Single-user, privacy-first: only the job text, resume text and preferences are sent to the configured LLM provider; nothing else leaves the machine except calls to public ATS APIs and SerpApi.
