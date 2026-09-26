# Specification: Phase 2 — Profile & Job Discovery

## Goal
Let the user set up their profile (resume, AI-suggested skills and titles, job preferences, EEO answers) and have a scheduled fetcher find matching jobs every 30 minutes. It discovers jobs from public ATS boards and, optionally, Google Jobs, scores each new job with an LLM evaluator, and routes it to the recommended or ignored inbox.

## User Stories
- As a job seeker, I want to upload my resume and get suggested titles and skills so that I can fill in my profile quickly and edit the suggestions before saving.
- As a job seeker, I want relevant jobs to be found and scored automatically, without adding boards myself, so that my inbox fills with good matches.
- As a privacy-minded self-hoster, I want to pick my LLM provider (OpenAI, Anthropic, OpenRouter or a local model) and keep Google Jobs optional, so that I control cost and where my data goes.

## Specific Requirements

**Data model and migrations (three new reversible Alembic revisions after `0005`)**
- `0006`: drop `preferences.skills`. The downgrade re-adds it as a nullable `ARRAY(Text)`. Remove the `skills` attribute from the `Preferences` model.
- `0007`: change `preferences.seniority` from `Text` to `ARRAY(Text)`, wrapping any existing value in a one-element array. The downgrade keeps the first element.
- `0008`: create `ats_boards` with id, `provider`, `board_key` (slug or Workday tenant/instance/site), `board_url`, `company_name`, `is_active` (default true), `discovered_via` (`ats_sweep` or `google_jobs`), `last_matched_at`, `last_polled_at` and the timestamps.
- `ats_boards` constraints: UNIQUE(`provider`, `board_key`); CHECK that `provider` is one of greenhouse, lever, ashby, workday, icims, bamboohr; an index on `is_active`. Add a matching `AtsBoard` model in `src/models/`.
- Put the shared vocabularies in one backend module used by preferences, the evaluator and validation. Seniority slugs: intern, entry, mid, senior, staff_principal, lead_manager, director, vp_plus. Work arrangements: remote, hybrid, onsite. Job types: full_time, part_time, contract, internship, temporary. The frontend holds the matching labels.
- Update `tests/test_migrations.py` so it covers upgrade to head and downgrade through the new revisions.

**Preferences and resume API (`/api/v1/preferences`, JWT-protected)**
- `GET /preferences` returns the single row, or empty defaults if no row exists yet. `PUT /preferences` upserts row `id = 1` with all editable fields and returns the saved object.
- Pydantic validation on the server: salary values are whole numbers ≥ 0 and min ≤ max; country is an ISO 3166-1 alpha-2 code from an allowlist; currency is an ISO 4217 code from an allowlist; seniority values and every EEO answer come from fixed allowlists; tag lists are trimmed, de-duplicated case-insensitively and length-capped.
- `eeo_answers` keys: `race_ethnicity`, `veteran_status`, `disability_status`, `work_authorization`, `needs_visa_sponsorship`. Each has a fixed option list that includes `decline_to_answer`. `gender` also uses a fixed list with `decline_to_answer`.
- `POST /preferences/resume` (multipart, one file): allow only `.pdf` and `.docx`, checked by extension and by magic bytes (`%PDF` or a ZIP header containing `word/document.xml`); reject files over 10 MB with 413 and wrong types with 415.
- On upload, write atomically to `CAREER_NETWORKING_RESUME_FOLDER/resume.{pdf|docx}` (the client filename is never used for the path) and remove the resume with the other extension. Extract text (python-docx / pdfminer.six) into `resume_text` and store the path in `resume_location`.
- The upload response contains resume metadata plus `suggestions` {desired_titles, hard_skills, soft_skills} from the resume extractor. Suggestions are never persisted by this endpoint. If the LLM fails, the upload still succeeds with `suggestions: null` and a warning message.
- A resume with no extractable text (for example a scanned PDF) returns 422 with a clear message, and the old resume is left unchanged.
- `DELETE /preferences/resume` deletes the file and clears `resume_location` and `resume_text`, leaving titles and skills in place, then returns 204. Errors use the existing `{"detail": ...}` shape.

**Profile page (`frontend/app/(app)/profile/page.tsx`)**
- Replace `PagePlaceholder` with a client-side form in sections (Resume, Job Preferences, Compensation, Personal & EEO), built from `frontend/components/profile/*` components and a `lib/api/preferences.ts` module that follows the `lib/auth/client.ts` fetch and error conventions.
- Resume card: shows the current resume (type and upload time) and offers Upload / Replace and Delete with a confirmation. While uploading and extracting, it shows a progress state and blocks double submits.
- Suggestions are merged into the tag inputs (de-duplicated) and marked as suggested until saved, with an inline notice asking the user to review and Save.
- Reusable `TagInput` for desired titles, hard skills and soft skills: Enter or comma adds a tag, each chip has a remove button, and everything is keyboard accessible.
- Country Select (single) sets the default currency from a static country-to-currency map. The user can override the currency with the ISO 4217 Select. Salary min and max are number inputs, and min ≤ max is checked on the client.
- Seniority is a multi-select checkbox group. Address is a textarea. Gender and each EEO question are Selects with "Decline to answer".
- If desired titles or country are missing, show a notice that job discovery is paused until both are set. Show field-level errors from 422 responses and a success confirmation on save.
- Add any missing shadcn/ui primitives (select, checkbox, textarea, alert) with the shadcn CLI. The layout is mobile-first and uses the Phase 1 warm, minimalist tokens and Lucide icons.

**Shared LLM layer and prompts (`src/llm.py`)**
- One LiteLLM completion helper used by every agent. It reads `CAREER_NETWORKING_LLM_MODEL` (required, for example `openai/gpt-4o-mini`, `anthropic/...`, `openrouter/...`, `ollama/...`) and optionally `CAREER_NETWORKING_LLM_API_BASE`, and applies a request timeout and bounded retries with exponential backoff.
- LiteLLM reads provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`) straight from the environment. They are never logged and are not part of `Settings`.
- Structured output: ask for JSON, validate it with a Pydantic model, and retry once with the validation error appended before raising a specific `LlmOutputError`.
- Prompt resolution: use `prompts.system_prompt` for the agent's `agent_name` when `is_customized` is true; otherwise use the module constant (`EVALUATOR_SYSTEM_PROMPT`, `COMPANY_LOOKUP_SYSTEM_PROMPT`, `RESUME_EXTRACTOR_SYSTEM_PROMPT`). No rows are seeded.
- The resume extractor (`src/agents/resume_extractor.py`) returns desired titles, hard skills and soft skills from `resume_text`.
- Privacy: prompts carry only job text, resume text and job-relevant preferences (titles, skills, seniority, salary, country, work authorization, needs sponsorship). Address, gender and the other EEO answers are never sent.

**Fetcher run orchestration and scheduling (`src/fetcher.py`, `python -m src.fetcher`)**
- Add a new `fetcher` compose service (in both compose files) built from the `backend/jobs` image. It uses the same `.env` and volumes, `depends_on: jobs: service_healthy` so migrations have run, and runs supercronic with a crontab of `*/30 * * * * python -m src.fetcher`.
- Overlap lock: a Postgres session-level advisory lock (`pg_try_advisory_lock`). If the lock is already held, the run logs and exits. The same command can be run by hand for an on-demand fetch (`docker compose exec fetcher python -m src.fetcher`).
- Precondition: if desired titles or country are missing, log "skipped: preferences incomplete" and exit 0.
- Run order: Google Jobs discovery (if due), then the ATS sweep batch, then polling of every active tracked board, then pruning. Each source and each job has its own try/except, so a failure is logged and skipped and the run continues.
- Store run state (Google Jobs last-run time and the sweep rotation cursor) and the directory cache under `CAREER_NETWORKING_JOB_DATA/_fetcher/`. Losing these files only resets the rotation.
- At the end of each run, log a summary: counts per source (fetched, matched, new, duplicate, failed), jobs evaluated, recommended and ignored, and the duration. All logs go to `career_networking.log` through `configure_logging`.

**Reverse ATS sweep (Python port of Career-Ops `scan-ats-full.mjs`)**
- Download the company directories `{greenhouse,lever,ashby,workday,icims,bamboohr}_companies.json` from `https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data` and cache them on disk for 24 hours. If the download fails, use the stale cache; if there is no cache at all, skip the sweep and keep tracking.
- Rotation: combine all directories into one ordered list and scan `ceil(total / 48)` boards per run, advancing the cursor, so a full pass finishes about once a day.
- Use one provider module per ATS under `src/sources/providers/`, each calling the board's public JSON API with `httpx` (per-request timeout, bounded concurrency, identifying User-Agent). Follow the Career-Ops endpoints: Greenhouse boards-api, Lever `/v0/postings`, Ashby posting-api, Workday `wday/cxs` POST, iCIMS search, BambooHR careers list.
- Keep a posting only if its title matches a desired title (case-insensitive, all title tokens present), its location matches the preferred country (country name, ISO code or common aliases, or remote with no conflicting country), and it was published within a recency window (module constant, 7 days). Undated postings are skipped.
- Any board with at least one matching posting is upserted into `ats_boards` (`discovered_via = ats_sweep`, `last_matched_at = now`, reactivated if it was inactive), and its matching postings go to ingestion.

**Google Jobs discovery via SerpApi (optional)**
- Enabled only when `SERPAPI_API_KEY` is set. Otherwise log "Google Jobs skipped: no SERPAPI_API_KEY" once per run.
- Runs only when `CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS` (default 24) has passed since the last successful run.
- For each desired title, send one `engine=google_jobs` query with `q = title`, `location` and `gl` from the country, fetching up to 3 pages through `next_page_token`. This stays within the 250 searches/month free tier for 2 titles, as the README describes.
- Job URL: the first `apply_options` link that points to a supported ATS; otherwise the first apply link. When an apply link points to a supported ATS, add or reactivate that board in `ats_boards` (`discovered_via = google_jobs`).
- If the snippet description is truncated, get the full text from the ATS API (supported ATS) or by fetching the apply page and stripping HTML with the standard library. If that fails, fall back to the snippet.
- Set `jobs.source` to `google_jobs:<via>` (for example `google_jobs:LinkedIn`). ATS-sourced jobs use the provider name.

**Board tracking, deduplication and ingestion**
- Every run polls all `is_active` boards in `ats_boards`, applies the same title, country and recency filters, and updates `last_polled_at`. When there is a match it also updates `last_matched_at`.
- Pruning: set `is_active = false` on boards whose `last_matched_at` is more than 30 days old. Discovery reactivates them later. Tracking continues even when the directory or SerpApi is unavailable.
- URL normalization before the dedup check: lowercase the scheme and host, drop the fragment, strip tracking parameters (`utm_*`, `gh_src`, `lever-source`, `source`, `ref` and similar) and the trailing slash. Check existence with one query per batch; the `jobs.url` unique constraint catches races (IntegrityError is logged and skipped).
- For each new job: find the company with a case-insensitive exact name match. If there is none, call the company lookup agent. If lookup fails, insert a company with only its name, because `jobs.company_id` is NOT NULL.
- Then run the evaluator once and insert the job with its extracted fields and scores in one transaction. `inbox_type` is `recommended` if `overall_score >= CAREER_NETWORKING_MATCH_THRESHOLD`, otherwise `ignored`.
- If evaluation fails, save the job with null scores and `inbox_type = ignored` and log the reason. Jobs are never re-evaluated.

**Evaluator and Company Lookup agents (`src/agents/evaluator.py`, `src/agents/company_lookup.py`)**
- The evaluator is a small LangGraph `StateGraph`: build context (job, preferences, resume text, skills), call the LLM, then validate. It returns a Pydantic `JobEvaluation`.
- `JobEvaluation` fields: `overall_score`, `experience_score`, `skill_score`, `industry_exp_score` (integers from 0 to 100); `compensation_range`; `work_arrangement`, `job_type_classification` and `seniority_level` (from the shared vocabularies or null); `year_exp` (integer ≥ 0 or null); `visa_sponsorship` (bool or null); `location_city`, `location_state`, `location_country`.
- Values not stated in the posting stay null rather than being guessed. Each agent exposes a plain function the fetcher can call and tests can mock.
- Company lookup takes a company name and an optional job description and uses model knowledge only (no web browsing). It returns `website_url`, `linkedin_url`, `description`, `industries`, `growth_stage`, `employee_estimate` and `history`; unknown fields stay null.
- Company lookup validates URLs (http/https only) and inserts the `companies` row with the name as given by the source.

**Configuration, dependencies and documentation**
- Add to `Settings` in `config.py`, with fail-fast validation:
  - `llm_model` (required)
  - `llm_api_base` (optional)
  - `match_threshold` (0–100, default 70)
  - `google_jobs_interval_hours` (> 0, default 24)
  - `serpapi_api_key` (optional `SecretStr`, read from the unprefixed `SERPAPI_API_KEY` through a validation alias)
- Update the `test_settings` fixture in `conftest.py` to match.
- `.env.example`: keep the existing `SERPAPI_API_KEY` and `CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS` lines as they are. Add an "LLM" block (`CAREER_NETWORKING_LLM_MODEL`, `CAREER_NETWORKING_LLM_API_BASE`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`) and `CAREER_NETWORKING_MATCH_THRESHOLD=70`.
- Runtime dependencies: `litellm`, `langgraph`, `python-docx`, `pdfminer.six`, `python-multipart` (required by FastAPI for uploads) and `httpx` (moved from the dev group to runtime). Add supercronic to the Dockerfile as a pinned release with its checksum verified.
- nginx: set `client_max_body_size 11m` on `location /api/`. The default 1 MB limit would block 10 MB resumes.
- README:
  - Remove the "fetcher itself arrives in Phase 2 … key is not used" sentence from "Google Jobs (optional)" and keep the rest of that section in sync with the implemented page count and interval.
  - Add sections for LLM configuration, the fetcher service (schedule, manual run, logs) and the new preferences endpoints under Routing.
  - Add a Credits section for Career-Ops (MIT) and Feashliaa/job-board-aggregator (MIT). Keep the MIT notice in the header of each ported module.
- Tests (core flows only, with external calls mocked):
  - preferences GET/PUT
  - resume upload and delete
  - migrations
  - one fetcher run covering dedup, company lookup fallback and inbox routing
  - provider parsers against fixture JSON
  - a Vitest test for the Profile form's save and upload flow

## Visual Design
No visual assets were provided. The Profile page follows the Phase 1 design system (shadcn/ui, Tailwind tokens in `globals.css`, Lucide icons, card-based sections, no HTML tables).

## Existing Code to Leverage

**Settings, logging and errors (`backend/jobs/src/config.py`, `logging_config.py`, `errors.py`)**
- Add the new variables to the frozen `Settings` class, following the existing `Field` constraints and `_describe_errors` fail-fast messages.
- The fetcher entry point calls `get_settings()` and `configure_logging(settings.log_folder)` just as `create_app` does.
- API errors go through the centralized `{"detail": ...}` handlers; raise `HTTPException` with user-friendly messages.

**Models and migrations (`src/models/*.py`, `alembic/versions/0002`–`0005`)**
- Reuse `Base` (naming convention), `TimestampMixin`, `Preferences` (single row, `CHECK id = 1`), `Job` (`INBOX_TYPES`, `SCORE_COLUMNS`, unique `url`), `Company` and `Prompt`.
- Copy the revision file style (numbered IDs, `op.f()` constraint names, a full downgrade) for 0006–0008.

**API plumbing (`src/api/v1/router.py`, `src/auth/dependencies.py`, `src/db/session.py`)**
- Add a `preferences` router to `api_router`, protected with `dependencies=[Depends(get_current_user)]`.
- Use `get_db` for request sessions and `get_sessionmaker()` for the fetcher's own sessions.
- Use the `conftest.py` `app`/`client` fixtures with `dependency_overrides` for tests.

**Frontend shell and primitives (`frontend/components/ui/*`, `lib/auth/client.ts`, `components/app-shell/*`)**
- Reuse button, input, label, card, badge and separator; add select, checkbox, textarea and alert through `components.json`.
- Mirror `client.ts` for the preferences API: `credentials: "include"`, typed results, and network or unexpected error messages.
- The page sits in the `(app)` layout, which is already protected by `proxy.ts` and already linked in the sidebar.

**Career-Ops reference (MIT), in the scratchpad clone**
- `scan-ats-full.mjs`: directory URLs, 24h cache, recency cutoff, skipping undated postings, per-ATS board URL construction.
- `providers/{greenhouse,lever,ashby,workday,icims,bamboohr}.mjs`: API endpoints, pagination, date parsing and URL detection, which is reused to recognize ATS links in Google Jobs apply options.
- `discover-ats.mjs`: patterns for mapping an apply URL to a (provider, board_key).

## Out of Scope
- Inbox and Job Details UI (Phase 3); in Phase 2, jobs are visible only through the database and logs.
- Networking agent (Phase 4) and the Prompts page (Phase 6); no prompt seeding or editing UI.
- Email notifications and a "Fetch now" button in the UI (manual runs use the CLI command only).
- Web search or browsing tools for company lookup.
- Multiple resume versions, resume download or preview.
- Re-scoring existing jobs when preferences or the resume change.
- Sources that need a login, python-jobspy, keyless Google scraping, and the Adzuna/Jooble APIs.
- Using the `companies` table as a seed list, or letting the user enter boards by hand.
- Cross-source duplicate detection beyond normalized URL.
- Free no-key feeds (Himalayas, Remotive, The Muse, Arbeitnow), YC/a16z seeds, and other Career-Ops providers (SmartRecruiters, Workable, Rippling and others).
