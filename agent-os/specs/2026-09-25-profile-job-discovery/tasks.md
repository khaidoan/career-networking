# Task Breakdown: Phase 2 — Profile & Job Discovery

## Overview
Total Task Groups: 11
Total Tasks: 82 (11 parent tasks, 71 sub-tasks)

Source documents: `spec.md` (primary) and `planning/requirements.md`. No visual assets were provided (`planning/visuals/` is empty), so the Profile page follows the Phase 1 design system (shadcn/ui, Tailwind tokens in `frontend/app/globals.css`, Lucide icons, card-based sections, no HTML tables).

Paths below are relative to the repo root. Backend paths under `backend/jobs/`, frontend paths under `frontend/`.

### Unconfirmed decisions (isolated for easy change)
The spec-writer made these decisions without explicit user confirmation. Each is implemented in exactly one clearly labelled sub-task, marked **[UNCONFIRMED: Dx]**, so it can be changed without touching the rest of the plan. Keep each one behind a single constant, function or config block in code.

| ID | Decision (as written in spec) | Isolated in |
|----|-------------------------------|-------------|
| D1 | **Confirmed.** A job whose evaluation fails is saved with null scores, `inbox_type = ignored` and the reason in `jobs.evaluation_error` (migration 0009) | Task 7.7 |
| D2 | **Confirmed.** Posting recency window of 7 days (module constant); undated postings skipped; applies to Google Jobs postings too | Task 5.3 |
| D3 | Fetcher run state (Google Jobs last-run, sweep cursor) and directory cache stored as files under `CAREER_NETWORKING_JOB_DATA/_fetcher/` | Task 5.2 |
| D4 | Address, gender and non-work-authorization EEO answers are never sent to the LLM | Task 3.3 |
| D5 | **Confirmed.** "Fetch now" is a CLI command only (no API endpoint, no UI button) | Task 8.5 |
| D6 | supercronic is the cron runner for the `fetcher` service | Task 8.2 |

## Task List

### Foundation

#### Task Group 1: Configuration, Dependencies and Shared Vocabularies
**Dependencies:** None

- [x] 1.0 Complete configuration and shared foundation
  - [x] 1.1 Write 2-4 focused tests for the new settings
    - `Settings` fails fast with a clear message when `llm_model` is missing
    - `match_threshold` outside 0–100 and `google_jobs_interval_hours <= 0` are rejected
    - `serpapi_api_key` is read from the unprefixed `SERPAPI_API_KEY` env var and is a `SecretStr`
  - [x] 1.2 Add new fields to the frozen `Settings` in `src/config.py`
    - `llm_model` (required), `llm_api_base` (optional), `match_threshold` (int 0–100, default 70), `google_jobs_interval_hours` (> 0, default 24), `serpapi_api_key` (optional `SecretStr`, `validation_alias="SERPAPI_API_KEY"`)
    - Follow the existing `Field` constraints and `_describe_errors` fail-fast pattern
    - Do NOT add provider keys (`OPENAI_API_KEY`, etc.) to `Settings`; LiteLLM reads them from the environment
  - [x] 1.3 Update the `test_settings` fixture in `tests/conftest.py`
    - Add `llm_model="openai/test-model"` and any other required new fields so existing Phase 1 tests keep passing
  - [x] 1.4 Add runtime dependencies to `pyproject.toml` and refresh `uv.lock`
    - `litellm`, `langgraph`, `python-docx`, `pdfminer.six`, `python-multipart`
    - Move `httpx` from the `dev` group to runtime dependencies
  - [x] 1.5 Create the shared vocabularies module (e.g. `src/vocabularies.py`)
    - Seniority slugs: intern, entry, mid, senior, staff_principal, lead_manager, director, vp_plus
    - Work arrangements: remote, hybrid, onsite
    - Job types: full_time, part_time, contract, internship, temporary
    - Gender options and `eeo_answers` option lists for `race_ethnicity`, `veteran_status`, `disability_status`, `work_authorization`, `needs_visa_sponsorship` (each includes `decline_to_answer`)
    - ISO 3166-1 alpha-2 country allowlist (with display name and common aliases for location matching) and ISO 4217 currency allowlist
    - This is the single source used by preferences validation, the evaluator and the fetcher filters
  - [x] 1.6 Update `.env.example`
    - Keep the existing `SERPAPI_API_KEY` and `CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS` lines exactly as they are (do not duplicate them)
    - Add an "LLM" block: `CAREER_NETWORKING_LLM_MODEL`, `CAREER_NETWORKING_LLM_API_BASE`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` with short comments and example model strings (`openai/...`, `anthropic/...`, `openrouter/...`, `ollama/...`)
    - Add `CAREER_NETWORKING_MATCH_THRESHOLD=70`
  - [x] 1.7 Ensure foundation tests pass
    - Run ONLY the tests written in 1.1 plus the existing `tests/test_health.py` and `tests/test_auth.py` (to confirm the fixture change did not break them)

**Acceptance Criteria:**
- The tests written in 1.1 pass and Phase 1 tests still pass with the updated fixture
- The service refuses to start without `CAREER_NETWORKING_LLM_MODEL`, naming the variable
- One vocabularies module exists and is importable by other modules
- `.env.example` contains the new LLM block and threshold with no duplicated SerpApi lines

### Database Layer

#### Task Group 2: Migrations and Models
**Dependencies:** Task Group 1 (vocabularies for the `provider` list)

- [x] 2.0 Complete database layer
  - [x] 2.1 Extend `tests/test_migrations.py` with 2-4 focused tests
    - Upgrade to head creates `ats_boards` with the UNIQUE(`provider`, `board_key`) and provider CHECK constraints
    - `0007` wraps an existing `seniority` text value into a one-element array, and the downgrade keeps the first element
    - Downgrade from head back through `0006` succeeds (re-adds nullable `skills`)
  - [x] 2.2 Create `alembic/versions/0006_drop_preferences_skills.py`
    - Upgrade drops `preferences.skills`; downgrade re-adds it as nullable `ARRAY(Text)`
    - Copy the Phase 1 revision style (numbered IDs, `op.f()` names, full downgrade)
  - [x] 2.3 Create `alembic/versions/0007_preferences_seniority_array.py`
    - `Text` to `ARRAY(Text)` using `USING CASE WHEN seniority IS NULL THEN NULL ELSE ARRAY[seniority] END`
    - Downgrade converts back to `Text` keeping `seniority[1]`
  - [x] 2.4 Create `alembic/versions/0008_create_ats_boards_table.py`
    - Columns: `id`, `provider`, `board_key`, `board_url`, `company_name`, `is_active` (default true), `discovered_via` (`ats_sweep` | `google_jobs`), `last_matched_at`, `last_polled_at`, `created_at`, `updated_at`
    - UNIQUE(`provider`, `board_key`); CHECK `provider IN (greenhouse, lever, ashby, workday, icims, bamboohr)`; CHECK on `discovered_via`; index on `is_active`
  - [x] 2.5 Update models
    - Remove `skills` from `src/models/preferences.py`; change `seniority` to `Mapped[list[str] | None]` with `ARRAY(Text)`
    - Add `src/models/ats_board.py` (`AtsBoard`, reusing `Base` and `TimestampMixin`) with constants for providers and discovery sources; export it from `src/models/__init__.py`
  - [x] 2.6 Ensure database layer tests pass
    - Run ONLY `tests/test_migrations.py`
    - Verify `alembic upgrade head` and `alembic downgrade 0005` both run cleanly

**Acceptance Criteria:**
- The tests in 2.1 pass
- Three reversible revisions (`0006`–`0008`) chain after `0005`
- ORM models match the migrated schema

### LLM and Agents

#### Task Group 3: Shared LLM Layer, Prompt Resolution and Agents
**Dependencies:** Task Groups 1, 2

- [x] 3.0 Complete LLM layer and agents
  - [x] 3.1 Write 4-6 focused tests (LiteLLM mocked; e.g. `tests/test_llm.py`, `tests/test_agents.py`)
    - Structured output: invalid JSON triggers exactly one retry with the validation error appended, then raises `LlmOutputError`
    - Prompt resolution uses the `prompts` row when `is_customized` is true, else the module constant
    - Evaluator returns a validated `JobEvaluation`, with vocabulary fields outside the allowlist rejected or nulled
    - Company lookup drops non-http(s) URLs
    - The evaluator context never contains address, gender or non-work EEO answers (guards D4)
  - [x] 3.2 Create `src/llm.py`
    - One completion helper wrapping `litellm.completion` using `settings.llm_model` and optional `settings.llm_api_base`
    - Request timeout and bounded retries with exponential backoff for transient errors
    - `complete_structured(system_prompt, user_content, model_cls)`: request JSON, validate with Pydantic, retry once with the validation error, then raise `LlmOutputError`
    - Never log provider keys or full prompts containing resume text (log agent name, model, latency, outcome only)
    - `resolve_system_prompt(session, agent_name, default)` reading `prompts.system_prompt` when `is_customized`; no seeding
  - [x] 3.3 **[UNCONFIRMED: D4]** Implement the LLM preference allowlist
    - A single function (e.g. `llm_safe_preferences(prefs)` in `src/llm.py`) that returns only: desired titles, hard/soft skills, seniority, salary min/max, currency, country, `work_authorization`, `needs_visa_sponsorship`
    - All agents build context through this function only; changing the allowlist is a one-line edit
  - [x] 3.4 Create `src/agents/resume_extractor.py`
    - `RESUME_EXTRACTOR_SYSTEM_PROMPT` constant; plain function `extract_resume_suggestions(session, resume_text) -> ResumeSuggestions` (`desired_titles`, `hard_skills`, `soft_skills`)
    - Output trimmed and de-duplicated case-insensitively
  - [x] 3.5 Create `src/agents/evaluator.py`
    - `EVALUATOR_SYSTEM_PROMPT` constant; Pydantic `JobEvaluation` model: four scores (int 0–100), `compensation_range`, `work_arrangement`, `job_type_classification`, `seniority_level` (shared vocabularies or null), `year_exp` (int ≥ 0 or null), `visa_sponsorship` (bool or null), `location_city`, `location_state`, `location_country`
    - LangGraph `StateGraph` with nodes: build context → call LLM → validate
    - Prompt instructs the model to leave unstated values null
    - Plain function `evaluate_job(session, job, preferences) -> JobEvaluation` for the fetcher and tests to call/mock
  - [x] 3.6 Create `src/agents/company_lookup.py`
    - `COMPANY_LOOKUP_SYSTEM_PROMPT` constant; input: company name + optional job description; model knowledge only, no browsing
    - Returns `website_url`, `linkedin_url`, `description`, `industries`, `growth_stage`, `employee_estimate`, `history`; unknown stays null
    - Validate URLs (http/https only); plain function `lookup_company(session, name, description=None) -> Company` that inserts the `companies` row with the name exactly as given
  - [x] 3.7 Ensure LLM layer tests pass
    - Run ONLY the tests written in 3.1

**Acceptance Criteria:**
- The tests in 3.1 pass with LiteLLM fully mocked
- All three agents share one helper and one model setting
- The PII allowlist lives in exactly one place

### API Layer

#### Task Group 4: Preferences and Resume API
**Dependencies:** Task Groups 1, 2, 3 (resume extractor)

- [x] 4.0 Complete preferences API
  - [x] 4.1 Write 4-6 focused tests (e.g. `tests/test_preferences_api.py`, resume extractor mocked, DB via `dependency_overrides`)
    - `GET /api/v1/preferences` returns empty defaults when no row exists; requires auth (401 without a session)
    - `PUT` upserts row `id = 1` and returns the saved object; min > max salary returns 422 in `{"detail": ...}` shape
    - `POST /preferences/resume` with a valid PDF stores `resume.pdf`, fills `resume_text`, returns `suggestions`; LLM failure still succeeds with `suggestions: null` and a warning
    - Wrong type returns 415; a file with no extractable text returns 422 and keeps the old resume
    - `DELETE /preferences/resume` removes the file, clears `resume_location`/`resume_text`, keeps titles/skills, returns 204
  - [x] 4.2 Create Pydantic schemas (e.g. `src/api/v1/schemas/preferences.py`)
    - Read and write models for all editable fields
    - Validation: whole-number salaries ≥ 0 and min ≤ max; country and currency from the allowlists; seniority, gender and each `eeo_answers` value from the fixed lists; tag lists trimmed, de-duplicated case-insensitively and length-capped (items and list)
  - [x] 4.3 Create resume storage/extraction service (e.g. `src/services/resume.py`)
    - Check extension (`.pdf`/`.docx`) and magic bytes (`%PDF`, or ZIP header containing `word/document.xml`)
    - Enforce 10 MB limit (413) while reading the upload stream
    - Extract text with pdfminer.six / python-docx; empty text raises a 422 error before any file is replaced
    - Atomic write to `resume_folder/resume.{ext}` (temp file + `os.replace`), then remove the other extension; client filename is never used
  - [x] 4.4 Create `src/api/v1/preferences.py` router
    - `GET /preferences`, `PUT /preferences`, `POST /preferences/resume` (multipart, one file), `DELETE /preferences/resume`
    - Use `get_db`; raise `HTTPException` with user-friendly messages through the existing error handlers
    - Upload response: resume metadata (type, uploaded time) plus `suggestions` (not persisted) and an optional `warning`
  - [x] 4.5 Register the router in `src/api/v1/router.py` with `dependencies=[Depends(get_current_user)]`
  - [x] 4.6 Ensure API tests pass
    - Run ONLY the tests written in 4.1

**Acceptance Criteria:**
- The tests in 4.1 pass
- All endpoints are JWT-protected and return errors as `{"detail": ...}`
- Suggestions are never persisted by the upload endpoint

### Job Sources

#### Task Group 5: ATS Providers, Directory Sweep and Filters
**Dependencies:** Task Groups 1, 2

- [x] 5.0 Complete ATS source layer
  - [x] 5.1 Write 4-8 focused tests (e.g. `tests/test_providers.py`, fixture JSON under `tests/fixtures/ats/`, `httpx` mocked with `httpx.MockTransport`)
    - One parser test per provider (Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR) mapping fixture JSON to normalized postings (title, company, location, URL, published date, description)
    - Title/country/recency filter: keeps a matching posting, drops a wrong-country one and an undated one
    - ATS URL detection maps an apply URL to (`provider`, `board_key`)
  - [x] 5.2 **[UNCONFIRMED: D3]** Create the fetcher state store (e.g. `src/sources/state.py`)
    - Small interface: `get_google_jobs_last_run()`, `set_google_jobs_last_run()`, `get_sweep_cursor()`, `set_sweep_cursor()`, and `directory_cache_dir()`
    - File implementation under `settings.job_data / "_fetcher"`, written atomically; missing or corrupt files reset to defaults (logged)
    - All other code uses only this interface so the storage backend can be swapped (e.g. to a DB table) without other changes
  - [x] 5.3 **[CONFIRMED: D2]** Create posting filters (e.g. `src/sources/filters.py`)
    - `RECENCY_WINDOW_DAYS = 7` module constant; undated postings skipped
    - Title match: case-insensitive, all tokens of a desired title present
    - Country match: country name, ISO code or aliases from the vocabularies module, or remote with no conflicting country
  - [x] 5.4 Create the provider interface and normalized posting type (e.g. `src/sources/providers/base.py`)
    - Shared `httpx` client factory: per-request timeout, bounded concurrency (semaphore), identifying User-Agent
    - `fetch_postings(board) -> list[Posting]` and `detect_board(url) -> (provider, board_key) | None`
  - [x] 5.5 Port the six provider modules under `src/sources/providers/`
    - `greenhouse.py` (boards-api), `lever.py` (`/v0/postings`), `ashby.py` (posting-api), `workday.py` (`wday/cxs` POST with pagination), `icims.py` (search), `bamboohr.py` (careers list)
    - Follow Career-Ops endpoints, pagination, date parsing and board URL construction
    - MIT notice crediting Career-Ops in each ported module header
  - [x] 5.6 Create the directory sweep (e.g. `src/sources/ats_sweep.py`, port of `scan-ats-full.mjs`)
    - Download `{provider}_companies.json` from the Feashliaa/job-board-aggregator raw URL; cache 24h via the state store directory
    - Download failure uses the stale cache; no cache means skip the sweep (logged) without failing the run
    - Combine directories into one ordered list, scan `ceil(total / 48)` boards per run, advance the cursor via the state store
    - Return matching postings grouped by board; MIT notice crediting Career-Ops and job-board-aggregator
  - [x] 5.7 Ensure source tests pass
    - Run ONLY the tests written in 5.1

**Acceptance Criteria:**
- The tests in 5.1 pass with no real network calls
- Each provider returns normalized postings from fixture JSON
- State/cache storage and the recency window can each be changed in one file

#### Task Group 6: Google Jobs Discovery via SerpApi
**Dependencies:** Task Groups 1, 5

- [x] 6.0 Complete Google Jobs source
  - [x] 6.1 Write 2-4 focused tests (e.g. `tests/test_google_jobs.py`, SerpApi responses as fixture JSON)
    - No `SERPAPI_API_KEY` means the source is skipped with one log line and no HTTP calls
    - Not due (interval not elapsed per the state store) means no calls
    - Result mapping: ATS apply link preferred as job URL, `source = google_jobs:<via>`, and a supported-ATS board returned for upsert
  - [x] 6.2 Create `src/sources/google_jobs.py`
    - Enabled only when `settings.serpapi_api_key` is set; due only when `google_jobs_interval_hours` has passed since the last successful run (state store); record the new last-run time only on success
    - One `engine=google_jobs` query per desired title with `q`, `location` and `gl` from the country; up to 3 pages via `next_page_token` (page count as a module constant matching the README)
    - Job URL: first `apply_options` link pointing to a supported ATS (via provider `detect_board`), else first apply link
    - Boards detected from apply links are returned for upsert with `discovered_via = google_jobs`
  - [x] 6.3 Implement full-description recovery
    - When the snippet is truncated: use the provider API for supported ATS, otherwise fetch the apply page and strip HTML with the standard library `html.parser`; fall back to the snippet on failure
  - [x] 6.4 Ensure Google Jobs tests pass
    - Run ONLY the tests written in 6.1

**Acceptance Criteria:**
- The tests in 6.1 pass without network access
- SerpApi usage stays within titles × 3 pages per interval

### Fetcher

#### Task Group 7: Fetcher Orchestration, Tracking, Dedup and Ingestion
**Dependencies:** Task Groups 2, 3, 5, 6

- [x] 7.0 Complete fetcher run
  - [x] 7.1 Write 3-6 focused tests (e.g. `tests/test_fetcher.py`; sources, agents and LLM mocked)
    - One end-to-end run: a duplicate URL (differing only by tracking params) is not re-inserted; a new job gets a company from the DB by case-insensitive match; a failed company lookup creates a name-only company; score ≥ threshold goes to `recommended`, below to `ignored`
    - Evaluation failure saves the job with null scores and `inbox_type = ignored` (guards D1)
    - Incomplete preferences (no titles or no country) logs "skipped: preferences incomplete" and exits 0
    - Pruning deactivates boards whose `last_matched_at` is older than 30 days
  - [x] 7.2 Create URL normalization (e.g. `src/sources/urls.py`)
    - Lowercase scheme and host, drop fragment, strip `utm_*`, `gh_src`, `lever-source`, `source`, `ref` and similar, strip trailing slash
  - [x] 7.3 Create `src/fetcher.py` entry point (`python -m src.fetcher`)
    - Call `get_settings()` and `configure_logging(settings.log_folder)` as `create_app` does; use `get_sessionmaker()` for sessions
    - Postgres session-level `pg_try_advisory_lock` with a fixed key; if held, log and exit 0; always release in `finally`
    - Precondition check on desired titles and country
  - [x] 7.4 Implement run order with per-source isolation
    - Google Jobs (if due) → ATS sweep batch → poll all active `ats_boards` → prune
    - Each source and each job wrapped in its own try/except; failures are logged and the run continues
  - [x] 7.5 Implement board tracking and pruning
    - Upsert boards on match (`discovered_via`, `last_matched_at = now`, reactivate if inactive) using `ON CONFLICT (provider, board_key)`
    - Poll every `is_active` board with the same filters; update `last_polled_at`, and `last_matched_at` on a match
    - Prune: `is_active = false` when `last_matched_at` is older than 30 days (module constant)
  - [x] 7.6 Implement dedup and ingestion
    - Normalize URLs, check existence with one query per batch, catch `IntegrityError` on `jobs.url` as a race backstop (log and skip)
    - Company: case-insensitive exact name match, else `lookup_company`, else insert a name-only company
    - Run `evaluate_job` once; insert the job with extracted fields and scores in one transaction; `inbox_type = recommended` if `overall_score >= settings.match_threshold`, else `ignored`
    - `jobs.source` is the provider name, or `google_jobs:<via>`
  - [x] 7.7 **[CONFIRMED: D1]** Implement the evaluation-failure policy
    - A single function or constant (e.g. `EVALUATION_FAILURE_INBOX = "ignored"`) applied when `evaluate_job` raises: save with null scores, log the reason, never re-evaluate
  - [x] 7.8 Implement the end-of-run summary log
    - Per source: fetched, matched, new, duplicate, failed; plus evaluated, recommended, ignored, and duration
  - [x] 7.9 Ensure fetcher tests pass
    - Run ONLY the tests written in 7.1

**Acceptance Criteria:**
- The tests in 7.1 pass
- A failure in one source or job never aborts the run
- Concurrent runs are prevented by the advisory lock

### Infrastructure

#### Task Group 8: Docker, Compose, Scheduling and nginx
**Dependencies:** Task Groups 1, 7

- [x] 8.0 Complete infrastructure
  - [x] 8.1 Write 1-2 lightweight checks
    - A pytest that loads both compose files (YAML) and asserts the `fetcher` service exists, uses the `jobs` build, `.env`, the same volumes, and `depends_on: jobs: condition: service_healthy`
    - Manual check: `docker compose config` succeeds for both files
  - [x] 8.2 **[UNCONFIRMED: D6]** Add supercronic to `backend/jobs/Dockerfile`
    - Pinned release downloaded with its SHA checksum verified
    - Add a crontab file (e.g. `backend/jobs/crontab`) containing `*/30 * * * * python -m src.fetcher`
    - Keep the scheduler choice confined to the Dockerfile, crontab and the service `command`
  - [x] 8.3 Add the `fetcher` service to `docker-compose.yml` and `dev-docker-compose.yml`
    - Built from the `backend/jobs` image, same `env_file` and volumes (resume, jobs data, logs; dev also mounts source), `depends_on: jobs: condition: service_healthy`
    - `command` runs supercronic with the crontab
  - [x] 8.4 Update `nginx/conf.d/default.conf`
    - `client_max_body_size 11m;` inside `location /api/`
  - [x] 8.5 **[CONFIRMED: D5]** Document and verify the manual "Fetch now" path
    - Manual run: `docker compose exec fetcher python -m src.fetcher`; no API endpoint or UI button is added in this phase
  - [x] 8.6 Ensure infrastructure checks pass
    - Run ONLY the check from 8.1; build the image and confirm `supercronic -version` works in the container

**Acceptance Criteria:**
- Both compose stacks start with a `fetcher` service that waits for a healthy `jobs` service
- A 10 MB resume upload passes through nginx
- The fetcher runs every 30 minutes and can be run by hand

### Frontend

#### Task Group 9: Profile Page
**Dependencies:** Task Group 4 (API contract)

- [x] 9.0 Complete the Profile page
  - [x] 9.1 Write 2-4 focused Vitest tests (e.g. `components/profile/profile-form.test.tsx`, `fetch` mocked)
    - Loading preferences, editing a field and clicking Save sends `PUT` and shows a success confirmation
    - Uploading a resume merges suggestions into the tag inputs (de-duplicated, marked suggested) and shows the review notice
    - A 422 response shows field-level errors
    - `TagInput` adds a tag with Enter/comma and removes it with its chip button
  - [x] 9.2 Add missing shadcn/ui primitives
    - `pnpm dlx shadcn@latest add select checkbox textarea alert` (uses `components.json`)
  - [x] 9.3 Create `lib/api/preferences.ts`
    - `getPreferences`, `savePreferences`, `uploadResume`, `deleteResume` mirroring `lib/auth/client.ts`: `credentials: "include"`, typed results, network/unexpected error messages, field errors mapped from 422 `detail`
  - [x] 9.4 Create `lib/profile/options.ts` (or similar)
    - Labels for seniority, gender, EEO options, countries and currencies matching the backend slugs, plus a static country-to-currency map
  - [x] 9.5 Create `components/profile/tag-input.tsx`
    - Enter or comma adds, chips with accessible remove buttons, keyboard accessible, optional "suggested" chip style
  - [x] 9.6 Create `components/profile/resume-card.tsx`
    - Shows current resume type and upload time; Upload/Replace; Delete with a confirmation
    - Progress state during upload/extraction; blocks double submits; shows the LLM warning when `suggestions` is null
  - [x] 9.7 Create section components and `components/profile/profile-form.tsx`
    - Sections as cards: Resume, Job Preferences (titles, hard/soft skills, seniority checkbox group), Compensation (country Select setting default currency, currency Select override, salary min/max with client-side min ≤ max), Personal & EEO (address textarea, gender and EEO Selects with "Decline to answer")
    - Paused-discovery notice when desired titles or country are missing
    - Success confirmation on save; field-level error display
  - [x] 9.8 Replace `PagePlaceholder` in `app/(app)/profile/page.tsx` with the client form
    - Mobile-first layout, Phase 1 warm/minimalist tokens, Lucide icons, labelled controls, visible focus states
  - [x] 9.9 Ensure Profile tests pass
    - Run ONLY the tests written in 9.1 (`pnpm test components/profile`)

**Acceptance Criteria:**
- The tests in 9.1 pass
- All preference fields can be edited and saved; suggestions are only persisted on Save
- The form is keyboard accessible and usable on mobile widths

### Documentation

#### Task Group 10: README and Credits
**Dependencies:** Task Groups 6, 7, 8

- [x] 10.0 Complete documentation
  - [x] 10.1 Update the "Google Jobs (optional)" section in `README.md`
    - Remove the sentence "The fetcher itself arrives in Phase 2 … until then the key is not used."
    - Keep the rest in sync with the implementation (3 pages per title, default 24h interval); do not duplicate the section or the env lines
  - [x] 10.2 Add an "LLM configuration" section
    - `CAREER_NETWORKING_LLM_MODEL` examples for OpenAI, Anthropic, OpenRouter and Ollama; `CAREER_NETWORKING_LLM_API_BASE`; provider keys; `CAREER_NETWORKING_MATCH_THRESHOLD`; which data is sent to the LLM (per D4)
  - [x] 10.3 Add a "Job fetcher" section
    - Schedule (every 30 minutes), sources and board tracking/pruning, manual run command (per D5), where logs go, the preconditions (titles and country)
  - [x] 10.4 Add the new preferences endpoints under "Routing"
  - [x] 10.5 Add a "Credits" section
    - Career-Ops (MIT) and Feashliaa/job-board-aggregator (MIT)
  - [x] 10.6 Proofread
    - Commands match the compose service names; env var names match `.env.example` and `Settings`

**Acceptance Criteria:**
- README describes LLM setup, the fetcher and the new endpoints accurately
- No stale "arrives in Phase 2" wording; no duplicated SerpApi content

### Testing

#### Task Group 11: Test Review and Gap Analysis
**Dependencies:** Task Groups 1-10

- [x] 11.0 Review existing tests and fill critical gaps only
  - [x] 11.1 Review tests from Task Groups 1-9
    - Approximately 26-52 tests from 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1 and 9.1
  - [x] 11.2 Analyze coverage gaps for this feature only
    - Focus on integration points: upload → suggestions → save; fetcher → board upsert → next-run polling; Google Jobs board detection → tracking
  - [x] 11.3 Write up to 10 additional strategic tests maximum
    - Candidates: DOCX magic-byte check; replacing a PDF with a DOCX removes the old file; advisory lock held causes a clean exit; stale directory cache is used when download fails; an upload over 10 MB returns 413
    - Skip exhaustive edge cases
  - [x] 11.4 Run feature-specific tests only
    - Backend: the Phase 2 test files plus `tests/test_migrations.py` (`uv run pytest tests/test_llm.py tests/test_agents.py ...`)
    - Frontend: `pnpm test components/profile`
    - Run `uv run ruff check` and `pnpm lint` on changed code

**Acceptance Criteria:**
- All feature-specific tests pass (approximately 36-62 total)
- No more than 10 additional tests added
- No real network or LLM calls in any test

## Execution Order

1. Configuration, Dependencies and Shared Vocabularies (Task Group 1)
2. Migrations and Models (Task Group 2)
3. Shared LLM Layer and Agents (Task Group 3)
4. Preferences and Resume API (Task Group 4). Can run in parallel with Groups 5-6.
5. ATS Providers, Directory Sweep and Filters (Task Group 5)
6. Google Jobs Discovery (Task Group 6)
7. Fetcher Orchestration (Task Group 7)
8. Docker, Compose, Scheduling and nginx (Task Group 8)
9. Profile Page (Task Group 9). Can start once Group 4's API contract is fixed.
10. README and Credits (Task Group 10)
11. Test Review and Gap Analysis (Task Group 11)
