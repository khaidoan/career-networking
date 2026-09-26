# Task Breakdown: Phase 4 — Networking Agent

## Overview
Total Tasks: 8 task groups, 48 tasks (including the x.0 parent tasks)

> **Hard constraint (applies to every group):** The app never sends LinkedIn connection requests or messages, in any form. There is no Playwright, no logged-in LinkedIn session and no LinkedIn automation of any kind, for outreach or discovery. Playwright must not be added as a backend dependency. Phase 3 click-to-connect (open profile, copy message, mark as sent) stays the only outreach path. Discovery is button-triggered only: it is never wired into `fetcher.py` or any schedule.

Test locations: backend pytest in `backend/jobs/tests/`, frontend Vitest tests co-located as `*.test.tsx` / `*.test.ts` in `frontend/`. All external services (SerpApi, LiteLLM) are mocked. Migration tests run against the disposable PostgreSQL named by `CAREER_NETWORKING_TEST_DATABASE_URL`, as `tests/test_migrations.py` already does.

## Task List

### Database Layer

#### Task Group 1: Migrations 0011–0013 and Model Updates
**Dependencies:** Task Group 2 (the normalizer's rules must be settled first; 0012 carries its own copy)

- [x] 1.0 Complete database layer
  - [x] 1.1 Write 3-6 focused migration tests in `backend/jobs/tests/test_migrations.py`
    - Extend `EXPECTED_REVISION_ORDER` with `add_companies_contacts_searched_at`, `normalize_company_networking_linkedin_urls`, `add_company_networking_linkedin_url_unique_index`
    - 0011: `companies.contacts_searched_at` exists (timestamptz, nullable) after upgrade and is gone after downgrade to 0010
    - 0012: seed rows at 0011 with mixed-case, `http`, `xx.linkedin.com`, query string, fragment and trailing-slash variants of the same profile in one company; after upgrade the URLs are normalized and duplicates merged
    - 0012 merge rule: the kept row is the one with `connection_request_sent = true` and the earliest `connection_request_sent_at`; with no sent rows, the lowest id is kept; the same URL at two different companies is NOT merged
    - 0013: inserting a duplicate `(company_id, linkedin_url)` raises `IntegrityError`; two rows with NULL `linkedin_url` in the same company are allowed
    - Round trip: upgrade head, downgrade to 0010, upgrade head succeeds (0012 downgrade is a no-op)
  - [x] 1.2 Create `0011_add_companies_contacts_searched_at.py`
    - Add nullable `contacts_searched_at` `TIMESTAMP(timezone=True)`; downgrade drops the column
    - Add `contacts_searched_at: Mapped[datetime | None]` to `src/models/company.py`
  - [x] 1.3 Create `0012_normalize_company_networking_linkedin_urls.py` (data only, irreversible)
    - Carries its own copy of the normalizer (do not import `src.` app code), identical in rules to Task 2.2
    - Normalize every non-NULL `linkedin_url`; within each `company_id`, group by normalized URL and keep one row per the merge rule in 1.1; delete the other rows of the group
    - Existing URLs that fail normalization (not a `/in/<slug>` path) are not covered by the spec. Recommended default: leave them unchanged but still merge exact duplicates of them within a company, so 0013 cannot fail. Confirm before implementing
    - Run in the migration's transaction; use bound parameters only
    - `downgrade()` is a documented no-op (docstring explains the merge cannot be undone)
  - [x] 1.4 Create `0013_add_company_networking_linkedin_url_unique_index.py`
    - Unique index `uq_company_networking_company_id_linkedin_url` on `(company_id, linkedin_url)`; downgrade drops it
    - Declare the same index in `CompanyNetworking.__table_args__` so model metadata and migrations match
  - [x] 1.5 Ensure database layer tests pass
    - Run ONLY the tests written in 1.1 (`pytest backend/jobs/tests/test_migrations.py -k "contacts_searched_at or linkedin_url or round_trip"` or equivalent)
    - Do NOT run the entire test suite

**Acceptance Criteria:**
- The tests written in 1.1 pass against real PostgreSQL
- Each migration is one focused change; 0011 and 0013 are reversible; 0012 is data-only with a documented no-op downgrade
- No duplicate `(company_id, linkedin_url)` rows survive 0012, and no row with `connection_request_sent = true` is lost in favour of an unsent duplicate
- Model and migrations agree (`contacts_searched_at` on `Company`, unique index in `__table_args__`)

### Backend Shared Services

#### Task Group 2: LinkedIn URL Normalizer and Contact Dedup/Upsert Service
**Dependencies:** None (the upsert service's DB tests need Task Group 1 applied; write the pure normalizer first)

- [x] 2.0 Complete normalization and dedup services
  - [x] 2.1 Write 4-8 focused tests (e.g. `backend/jobs/tests/test_contact_storage.py`)
    - Normalizer: lowercases, forces `https`, maps `linkedin.com` and `xx.linkedin.com` to `www.linkedin.com`, strips query, fragment and trailing slash; rejects `/company/...`, `/jobs/...`, `/pub/...` and non-LinkedIn hosts (returns `None`)
    - Upsert: a new result is inserted with the normalized URL
    - Upsert: a re-found contact (URL differs only by normalization) gets its `title` updated when the new title is non-empty and different, and is left alone when the new title is empty
    - Upsert: `connection_request_sent` and `connection_request_sent_at` are never changed on a re-found contact
    - Upsert: name fallback matches a same-company contact with no `linkedin_url` case-insensitively on first + last name and sets its URL; it does not match contacts at another company or contacts that already have a URL
    - Upsert returns correct `created` / `updated` counts and never deletes rows
  - [x] 2.2 Add the pure normalizer (e.g. `src/services/linkedin_urls.py`: `normalize_linkedin_profile_url(url: str) -> str | None`)
    - No I/O, no DB; the single source of truth used by the agent and the upsert service (0012 keeps its own copy)
  - [x] 2.3 Add the contact upsert service (e.g. `src/services/contacts.py`)
    - Input: company id plus a list of parsed candidates (`first_name`, `last_name`, `title`, normalized `linkedin_url`); output: `created`, `updated` counts
    - Lock the company row with `SELECT ... FOR UPDATE` before matching, so two concurrent clicks cannot create duplicates; the unique index from 0013 is the final safeguard
    - Match by normalized URL first, then by case-insensitive first + last name among the company's contacts with no URL
    - Write in the caller's single transaction; the service also sets `companies.contacts_searched_at = now()` so both writes commit together
    - Never touch request-sent fields; never delete
  - [x] 2.4 Ensure service tests pass
    - Run ONLY the tests written in 2.1

**Acceptance Criteria:**
- The tests written in 2.1 pass
- One normalizer function is used everywhere in app code
- Re-finding a contact never loses "Request sent" history
- Upsert and `contacts_searched_at` update happen in one transaction under a company row lock

#### Task Group 3: Shared SerpApi Helper and Google Jobs Refactor
**Dependencies:** None (can run in parallel with Task Group 2)

- [x] 3.0 Complete shared SerpApi helper
  - [x] 3.1 Write 2-4 focused tests for the helper (e.g. in `backend/jobs/tests/test_serpapi.py`)
    - A successful response returns the parsed JSON body
    - `SourceError` from `HttpClient` surfaces as a failure the caller can map (e.g. a `SerpApiError`)
    - A body `error` equal to the "no results" message returns an empty result; any other `error` is a failure
    - The API key never appears in log output (use `caplog` and assert the key string is absent)
  - [x] 3.2 Create the helper (e.g. `src/sources/serpapi.py`)
    - Move `SERPAPI_SEARCH_URL`, `NO_RESULTS_ERROR` and the timeout constant here; `google_jobs.py` imports them (keep the names importable from `google_jobs` if tests reference them)
    - One function that takes the API key, engine and params, uses the shared `HttpClient` (retry and size cap), and applies the `SourceError` / `error` / "no results" rules
    - Never logs request URLs or params
  - [x] 3.3 Refactor `google_jobs.py` to call the helper, with NO behaviour change
    - Same query params, paging via `next_page_token`, `MAX_PAGES_PER_TITLE`, failure counting, `last_run` update rule and log lines
  - [x] 3.4 Ensure helper tests and the Google Jobs regression tests pass
    - Run ONLY the tests from 3.1 plus the existing `backend/jobs/tests/test_google_jobs.py` (unchanged) as the behaviour guard
    - Do NOT modify existing Google Jobs test assertions to make them pass

**Acceptance Criteria:**
- The tests written in 3.1 pass and `test_google_jobs.py` passes without edits to its assertions
- Google Jobs and the networking agent build SerpApi requests through one helper
- No request URL, params or API key is ever logged

### Networking Agent

#### Task Group 4: `networking.py` Agent (one search + one LLM call, URL-grounded)
**Dependencies:** Task Groups 2 and 3

- [x] 4.0 Complete the networking agent
  - [x] 4.1 Write 4-8 focused tests in `backend/jobs/tests/test_agents.py` (or a new `test_networking_agent.py`), with SerpApi and the LLM mocked
    - Exactly one SerpApi request is made, with engine `google`, query `site:linkedin.com/in "<company>" "<role title>"` and 20 results requested; the role title has seniority/level words stripped (e.g. "Senior Software Engineer II" -> "Software Engineer")
    - Non-`linkedin.com/in/` organic results are dropped before the LLM sees the numbered list
    - Out-of-range and duplicate indexes from the LLM are dropped; at most one `manager` and at most 5 contacts are kept
    - Name, title and URL come from the chosen search result (split on the first " - " / " – " / " | "; title is the next segment or `None`); results with no parseable name are skipped; the LLM output model has no URL, name or title fields
    - Matched skills are the user's `hard_skills` found as case-insensitive whole words in the job description, and they are not in the search query
    - An empty LLM selection is a valid success; zero search results succeeds without calling the LLM (see Spec Gaps)
  - [x] 4.2 Create `backend/jobs/src/agents/networking.py` following `company_lookup.py`
    - `AGENT_NAME = "networking"`, `NETWORKING_SYSTEM_PROMPT` constant with the selection rules: prefer same or close peer role; at most one hiring manager or team lead; exclude recruiters, HR and talent acquisition, executives (C-level, VP and above) and anyone no longer at the company
    - Pydantic output model: ranked list of `{index: int, category: "peer" | "manager"}` with `field_validator`s
    - Prompt via `resolve_system_prompt(session, "networking", NETWORKING_SYSTEM_PROMPT)`, then `complete_structured` (standard single validation retry only)
    - LLM input: company name, job title, matched skills, the `hard_skills` list obtained through `llm_safe_preferences` only, and the numbered results (index, result title, snippet)
    - No provider-native web search or tool use, so any LiteLLM model works, including local ones
  - [x] 4.3 Implement role-title cleanup and skill matching as small pure functions
    - Seniority/level word list: Senior, Sr, Staff, Lead (only when followed by another word, so "Tech Lead" is kept), Principal, Junior, Jr, Intern, and roman/number levels I/II/III/IV and 1/2/3
    - Whole-word, case-insensitive match of `hard_skills` in the job description (escape regex specials such as `C++`, `C#`, `.NET`)
  - [x] 4.4 Enforce limits in code after the LLM replies
    - Drop out-of-range and duplicate indexes, keep the first `manager` only, cap at 5, preserve LLM rank order
    - Parse and normalize each chosen result's URL with the Task 2.2 normalizer; skip results that fail normalization or name parsing
  - [x] 4.5 Define the public entry point and error surface
    - e.g. `find_contacts(session, settings, client, company, job) -> NetworkingResult` with `found` candidates and search/selection counts
    - SerpApi failure raises a specific error; `LlmError` / `LlmOutputError` propagate; nothing is written by the agent itself
    - Log only company id and counts (results, selected, new, updated); never names, profile URLs or request URLs
    - Confirm `fetcher.py` does not import or call the agent
  - [x] 4.6 Ensure agent tests pass
    - Run ONLY the tests written in 4.1

**Acceptance Criteria:**
- The tests written in 4.1 pass
- One SerpApi search and at most one LLM selection call (plus the standard validation retry) per run
- Every stored URL, name and title comes from a real search result; the LLM only returns indexes and categories
- Only `llm_safe_preferences` fields reach the LLM
- No LinkedIn automation, no Playwright, no scheduling hooks

### API Layer

#### Task Group 5: Find-Contacts Endpoint and `contact_search` Status
**Dependencies:** Task Groups 1, 2 and 4

- [x] 5.0 Complete API layer
  - [x] 5.1 Write 4-8 focused API tests (e.g. `backend/jobs/tests/test_contact_search_api.py`), with the agent's SerpApi and LLM calls mocked
    - Success: 200 with `found`, `created`, `updated`, the full `ContactRead` list and an updated `contact_search` (with `last_searched_at` set); an existing sent contact keeps its request-sent fields
    - 409 with the exact message when the company has no `recommended` or `applied` job
    - 503 with the exact message when `SERPAPI_API_KEY` is unset (key check comes before eligibility)
    - 502 on SerpApi failure (and on LLM failure): no contacts written and `contacts_searched_at` unchanged
    - 422 when `job_id` belongs to another company; 404 for unknown company or job
    - `JobDetail` and `CompanyDetail` both include `contact_search` with the right `available` / `unavailable_reason`
  - [x] 5.2 Add the eligibility/status helper (e.g. in `src/services/contacts.py`)
    - Returns `available`, `unavailable_reason` (`"no_api_key"` first, then `"no_eligible_job"`, else `null`) and `last_searched_at`
    - One `EXISTS` query for `jobs.inbox_type IN ('recommended', 'applied')` per company; no N+1
  - [x] 5.3 Add schemas
    - `ContactSearchStatus` (`available`, `unavailable_reason`, `last_searched_at`) and `ContactSearchResult` (`found`, `created`, `updated`, `contacts: list[ContactRead]`, `contact_search`) in `schemas/contacts.py`
    - Add `contact_search` to `JobDetail` (`schemas/jobs.py`) and `CompanyDetail` (`schemas/companies.py`) and populate it in the existing detail endpoints
  - [x] 5.4 Add `POST /api/v1/companies/{id}/contacts/search` (behind `get_current_user`, optional `job_id` query param)
    - Follow the synchronous `re_evaluate_job` pattern with `DbSession` / `AppSettings`
    - Order: 404 company -> 404 job / 422 job not at company -> 503 no key -> 409 not eligible -> run agent -> upsert
    - Without `job_id`, use the company's most recently discovered `recommended` or `applied` job
    - Map SerpApi errors and `LlmError` / `LlmOutputError` to 502 with a user-friendly message through the existing handlers; roll back so no writes happen
    - No rate-limit headers, no cap, no cooldown (documented exception to the API rate-limit standard)
    - Return contacts sorted by id, consistent with Company Details
  - [x] 5.5 Ensure API tests pass
    - Run ONLY the tests written in 5.1

**Acceptance Criteria:**
- The tests written in 5.1 pass
- Eligibility is enforced in the backend with the exact error codes and messages from the spec
- Failed runs write nothing; successful runs (including empty ones) set `contacts_searched_at`
- `contact_search` status adds a single `EXISTS` query per detail request

### Frontend

#### Task Group 6: API Client, "Find contacts" Button and Contact List Changes
**Dependencies:** Task Group 5 (API contract)

- [x] 6.0 Complete frontend changes
  - [x] 6.1 Write 3-7 focused Vitest tests
    - `components/contacts/find-contacts-button.test.tsx`: enabled when `available`; disabled with `aria-disabled` and the right explanation (linked by `aria-describedby`) for `no_api_key` (mentions the README) and `no_eligible_job`
    - Clicking shows "Searching…", ignores extra clicks, and announces "Found 3 new contacts, updated 1" / "No new contacts found" / the error message via `useAnnounce`
    - `job-details.test.tsx` or `company-details.test.tsx`: on success the displayed contact list and "Last searched …" status are replaced with the response
    - `contact-list.test.tsx`: the "Found via search, may be out of date." note shows above a non-empty list; the new empty-state text prompts to use Find contacts
  - [x] 6.2 Extend the API client and types
    - `findContacts(companyId, jobId?)` in `lib/api/contacts.ts` using the shared `request` helper and typed `{ ok } | Failure` results with friendly messages for 409 / 503 / 502
    - Add `ContactSearchStatus` and `contact_search` to the job and company detail types (`lib/api/jobs.ts`, `lib/api/companies.ts`)
  - [x] 6.3 Create `components/contacts/find-contacts-button.tsx` following `ReEvaluateButton`
    - `Button` variant `outline`, Lucide `UserSearch` / `LoaderCircle`, 44px tap target
    - Running state: `aria-disabled`, "Searching…", repeat clicks ignored; disabled states never rely on colour alone
    - Visible, muted explanation text for unavailable states, linked via `aria-describedby`
    - "Last searched X days ago" in a `<time>` with the full date in `title`, or "Not searched yet"; add a small relative-time helper (e.g. in `lib/jobs/format.ts`), since none exists
  - [x] 6.4 Wire the button into Job Details (`components/jobs/job-details.tsx`, `networking` DetailSection)
    - Pass `job_id`; on success replace the contact list and status
    - Add the "People on LinkedIn" people-tab link when `company.linkedin_url` is set (manual fallback, opens in a new tab)
  - [x] 6.5 Wire the button into Company Details (`components/companies/company-details.tsx`, contacts section)
    - No `job_id`; keep the existing people-tab link
  - [x] 6.6 Update `components/contacts/contact-list.tsx`
    - One "Found via search, may be out of date." note above a non-empty list
    - Empty state: replace "arrives in a later phase" with a prompt to use Find contacts, or the unavailable explanation
    - Click-to-connect, message template and "Request sent" unchanged; no delete, hide, edit or add controls
    - No UI element sends anything to LinkedIn
  - [x] 6.7 Ensure frontend tests pass
    - Run ONLY the tests from 6.1 (e.g. `npx vitest run components/contacts components/jobs/job-details.test.tsx components/companies/company-details.test.tsx`)

**Acceptance Criteria:**
- The tests written in 6.1 pass
- Button behaves identically on both pages, with accessible disabled explanations and live-region announcements
- Contact list and status refresh from the response without a page reload
- Mobile-first layout holds on small screens; follows the Phase 3 design system (no visuals were provided; `planning/visuals/` is empty)

### Documentation

#### Task Group 7: Product Docs and README
**Dependencies:** None (can run any time; best after Task Group 5 so README matches the final behaviour)

- [x] 7.0 Complete documentation updates
  - [x] 7.1 `agent-os/product/roadmap.md` Phase 4
    - Replace "On job fetch" with button-triggered discovery for companies with a recommended or applied job
    - Remove the "Playwright-based LinkedIn outreach" bullet; keep the Deferred "Auto-connect to LinkedIn" item
  - [x] 7.2 `agent-os/product/mission.md`: remove "Playwright-assisted LinkedIn connection requests"
  - [x] 7.3 `agent-os/product/tech-stack.md`: Browser Automation row is for the Phase 5 Apply flow only; Playwright is not a backend dependency
  - [x] 7.4 `README.md`: add a "Contact search" section
    - Needs `SERPAPI_API_KEY`; one SerpApi search per click, no cap; shares the monthly quota with Google Jobs; results come from Google and may be out of date; the app never sends connection requests or messages
    - Make sure the in-app 503 message ("See the README.") points somewhere real
  - [x] 7.5 Verify no remaining doc references claim LinkedIn outreach automation (`grep -ri "playwright" agent-os/product README.md`)

**Acceptance Criteria:**
- No doc describes Playwright or automated LinkedIn outreach
- README explains the key requirement, quota use and staleness of contact search

### Testing

#### Task Group 8: Test Review and Gap Analysis
**Dependencies:** Task Groups 1-7

- [x] 8.0 Review existing tests and fill critical gaps only
  - [x] 8.1 Review tests from Task Groups 1-6 (approximately 20-45 tests)
  - [x] 8.2 Analyze gaps for THIS feature only; likely candidates:
    - End-to-end: seed a sent contact, run the endpoint with a mocked SerpApi result for the same profile under a different URL form, assert one row, updated title, request-sent fields intact
    - Concurrency safeguard: a second upsert of the same URL does not raise and does not duplicate (unique index plus lock)
    - Logging: a full endpoint run logs no API key, profile URL or contact name (`caplog`)
    - Only `llm_safe_preferences` fields appear in the LLM messages
    - Grep-style guard: `fetcher.py` never references the networking agent, and no backend dependency on Playwright
    - Frontend: Company Details button calls `findContacts` without `job_id`
  - [x] 8.3 Write up to 10 additional strategic tests maximum to fill the critical gaps found
  - [x] 8.4 Run feature-specific tests only
    - Tests from 1.1, 2.1, 3.1, 4.1, 5.1, 6.1 and 8.3, plus unchanged `test_google_jobs.py`
    - Do NOT run the entire application suite

**Acceptance Criteria:**
- All feature-specific tests pass
- No more than 10 tests added in this group
- Hard constraint (no sending, no automation, button-only) is covered by at least one test or guard

## Execution Order

1. Shared services: URL normalizer first (Task Group 2.2), then Task Group 3 (SerpApi helper) in parallel
2. Database layer (Task Group 1), using the settled normalizer rules for 0012
3. Contact upsert service (rest of Task Group 2)
4. Networking agent (Task Group 4)
5. API layer (Task Group 5)
6. Frontend (Task Group 6)
7. Documentation (Task Group 7)
8. Test review and gap analysis (Task Group 8)
