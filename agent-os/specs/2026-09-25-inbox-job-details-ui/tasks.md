# Task Breakdown: Phase 3 — Inbox & Job Details UI

## Overview
Total Tasks: 9 task groups, 64 sub-tasks

Source documents: `spec.md` (primary) and `planning/requirements.md`. No visual assets were provided (`planning/visuals/` does not exist). Follow the existing Phase 1 design system: Tailwind, the shadcn-style primitives in `frontend/components/ui/` and Lucide icons.

Test tooling: backend uses pytest (`backend/jobs/tests/`), frontend uses Vitest + Testing Library (`npm run test` in `frontend/`).

## Task List

### Backend: Database, Models and Services

#### Task Group 1: Trigram Migration, Shared Query Helpers and Evaluation Helper
**Dependencies:** None

- [x] 1.0 Complete the database and backend service layer
  - [x] 1.1 Write 2-8 focused tests for this layer
    - Migration `0010` upgrades and downgrades cleanly (follow `tests/test_migrations.py`)
    - Company name search helper matches a substring (`ILIKE`) and a typo (trigram word similarity), case-insensitively
    - Keyset cursor encode/decode round-trips, and a malformed cursor is rejected
    - Shared evaluation-success helper copies `JobEvaluation` fields, clears `evaluation_error`, and moves only Recommended/Ignored jobs (Applied and Need Attention keep their inbox)
  - [x] 1.2 Create Alembic migration `0010_...` in `backend/jobs/alembic/versions/`
    - `upgrade`: `CREATE EXTENSION IF NOT EXISTS pg_trgm`, then a GIN index on `companies.name` using `gin_trgm_ops`
    - `downgrade`: drop the index, then the extension
    - Schema change only, no data changes. No model column changes are needed (`Job`, `Company`, `CompanyNetworking` already have every column, relationship and cascade)
  - [x] 1.3 Add a keyset (cursor) paging helper
    - Opaque, URL-safe `next_cursor` (for example base64-encoded JSON of the sort key values)
    - Jobs sort key: `liked` desc, `discovered_when` desc, `id` desc
    - Companies sort key: `liked` desc, `lower(name)` asc, `id` asc
    - `limit` default 25, max 50. Fetch `limit + 1` rows to decide whether `next_cursor` is `null`
    - Invalid cursor maps to a 422 through the existing handlers in `errors.py`
  - [x] 1.4 Add a shared, AI-free company name search expression
    - A row matches on `name ILIKE %q%` OR `pg_trgm` word similarity above a chosen threshold
    - Escape `%` and `_` in the user's text before building the `ILIKE` pattern
    - Reused by `GET /companies?q=` and by `GET /jobs?company=` (against the joined company name)
  - [x] 1.5 Extract the fetcher's evaluation success path into a shared helper
    - Move `_evaluate`'s field-copy logic from `backend/jobs/src/fetcher.py` into one function (for example `apply_evaluation_success(job, evaluation, threshold, *, allow_inbox_move)`)
    - The fetcher keeps its current behavior (new jobs always get an inbox from `inbox_for`)
    - For re-evaluation, only move jobs whose current inbox is Recommended or Ignored, using `inbox_for` with `settings.match_threshold`
    - Keep `apply_evaluation_failure` and `describe_evaluation_error` as the shared failure path (failure stores the error and clears the scores)
    - Remove "never re-evaluated" from the fetcher comment
  - [x] 1.6 Add a `JobForEvaluation` builder for a stored job
    - Uses the job's title, company name, joined location parts (city, state, country; skip nulls) and description
  - [x] 1.7 Ensure the layer's tests pass
    - Run ONLY the tests written in 1.1, plus the existing `tests/test_fetcher.py` to confirm the extraction did not change fetcher behavior
    - Verify `alembic upgrade head` and `alembic downgrade -1` both succeed

**Acceptance Criteria:**
- The tests written in 1.1 pass, and `test_fetcher.py` still passes
- Migration `0010` is reversible and creates the trigram index
- The fetcher and Re-evaluate share one success helper and one failure helper (no copied logic)
- Search and paging helpers are ready for the routers

### Backend: API Endpoints

#### Task Group 2: Jobs, Companies and Contacts Routers
**Dependencies:** Task Group 1

- [x] 2.0 Complete the API layer
  - [x] 2.1 Write 2-8 focused tests for the API endpoints (follow `tests/test_preferences_api.py`)
    - `GET /jobs` filters by inbox plus one filter and company search, returns liked-first order and a working `next_cursor`
    - `PATCH /jobs/{id}` toggles `liked`
    - `POST /jobs/{id}/apply` moves the job to Applied and a second call keeps the original `applied_when`
    - `POST /jobs/{id}/re-evaluate` with `evaluate_job` mocked: success updates scores; failure returns 200 with `evaluation_error` set and scores cleared
    - `POST /contacts/{id}/connection-request` sets the flag, and a second call keeps the first timestamp
    - `POST /companies` rejects invalid input with 422 (for example a non-linkedin.com LinkedIn URL); `PUT` updates
    - `DELETE /companies/{id}` returns 409 when the company has jobs, and 204 (contacts cascade) otherwise
  - [x] 2.2 Create Pydantic schemas in `backend/jobs/src/api/v1/schemas/`
    - `jobs.py`: `JobCard` (list item with joined company name, industries, growth stage), `JobDetail` (job + company + contacts), `JobPatch` (`liked` only), `JobList` (`items`, `next_cursor`)
    - `companies.py`: `CompanyCard`, `CompanyDetail` (company + jobs + contacts + `job_count`), `CompanyWrite` (create/update), `CompanyPatch` (`liked` only), `CompanyList`
    - `contacts.py`: `ContactRead` (name, first name, title, `linkedin_url`, `connection_request_sent`, `connection_request_sent_at`)
    - `CompanyWrite` validation: required name, website URL, LinkedIn URL, description, at least one industry, growth stage and employee estimate; optional history and logo URL; absolute http(s) URLs; LinkedIn URL host on `linkedin.com`; trim text and treat blank strings as missing
    - Reuse `backend/jobs/src/vocabularies.py` for any vocabulary-backed fields
  - [x] 2.3 Create `backend/jobs/src/api/v1/jobs.py`
    - `GET /jobs`: `inbox` required (one of `INBOX_TYPES`, stored slug `need_attention`), repeatable `seniority`, `work_arrangement`, `job_type` checked against `SENIORITY_LEVELS`, `WORK_ARRANGEMENTS`, `JOB_TYPES`; `visa` (`yes`/`no`); `liked` (`true`); `company`; `cursor`; `limit`
    - `GET /jobs/{id}`: job plus company and the company's contacts
    - `PATCH /jobs/{id}`: only `liked` is editable
    - `POST /jobs/{id}/apply`: sets `inbox_type = "applied"` and `applied_when = now`; idempotent
    - `POST /jobs/{id}/re-evaluate`: load current preferences (`load_preferences`), call `evaluate_job` synchronously, apply the shared success/failure helper, return the updated job with 200 even on evaluation failure
    - Follow the `preferences.py` patterns: `DbSession` dependency, logging, `HTTPException(404)` for missing ids
  - [x] 2.4 Create `backend/jobs/src/api/v1/companies.py`
    - `GET /companies`: `q`, repeatable `industry` (array overlap, matches any), `cursor`, `limit`
    - `GET /companies/industries`: distinct industries, sorted (declare before `/{id}`)
    - `GET /companies/{id}`: company, jobs (newest `discovered_when` first), contacts and `job_count`
    - `POST /companies` (201), `PUT /companies/{id}`, `PATCH /companies/{id}` (`liked` only)
    - `DELETE /companies/{id}`: 409 with a clear `detail` message if the company has jobs; otherwise delete (contacts cascade) and return 204
  - [x] 2.5 Create `backend/jobs/src/api/v1/contacts.py`
    - `POST /contacts/{id}/connection-request`: set `connection_request_sent = true`; set `connection_request_sent_at = now` only if it is not already set; return the contact
  - [x] 2.6 Register the three routers in `backend/jobs/src/api/v1/router.py`
    - Mount them the same way as `preferences.router`, behind `Depends(get_current_user)`
  - [x] 2.7 Avoid N+1 queries
    - Join the company for job lists; use `selectinload` for contacts and jobs on detail endpoints
    - Compute `job_count` in the query, not by loading all jobs
  - [x] 2.8 Ensure API layer tests pass
    - Run ONLY the tests written in 2.1
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The tests written in 2.1 pass
- All endpoints require a valid JWT
- Errors use `{"detail": ...}`: 404 for missing ids, 422 for invalid input, 409 for deleting a company with jobs
- Apply and connection-request are idempotent and keep their first timestamps
- List endpoints return stable keyset pages with `next_cursor`

### Frontend: Shared Primitives

#### Task Group 3: Dialog, Announcer/Toast, API Clients and Shared Hooks
**Dependencies:** Task Group 2 (API contract). The `Dialog` and announcer can start in parallel with Task Group 2.

- [x] 3.0 Complete the shared frontend building blocks
  - [x] 3.1 Write 2-8 focused tests for the shared primitives
    - `Dialog` traps focus while open and returns focus to the trigger on close
    - Announcer renders a message in a polite live region and shows a visible toast
    - Shared `request` helper maps 401, network failure and 422 field errors to the typed `Failure` result
    - Infinite-scroll hook calls `loadMore` when the "Load more" fallback button is activated
  - [x] 3.2 Add `frontend/components/ui/dialog.tsx`
    - Wrap Radix Dialog the same way `sheet.tsx` does (title, description, close button, overlay)
    - Used for the Apply confirmation, delete confirmation and the copy fallback
  - [x] 3.3 Add a toast / live-region announcer
    - A provider mounted in the `(app)` layout plus an `useAnnounce()` hook
    - Polite live region for status and assertive for errors; toasts never take focus
    - Used for "Message copied", like failures, Re-evaluate results, Apply results and newly loaded results
  - [x] 3.4 Move shared request logic into one module (for example `frontend/lib/api/request.ts`)
    - Extract `request`, validation-error parsing, and the session-expired / network / unexpected messages from `frontend/lib/api/preferences.ts`
    - Update `preferences.ts` to use it (no behavior change)
  - [x] 3.5 Add typed API clients
    - `frontend/lib/api/jobs.ts`: `listJobs`, `getJob`, `setJobLiked`, `applyToJob`, `reEvaluateJob`
    - `frontend/lib/api/companies.ts`: `listCompanies`, `listIndustries`, `getCompany`, `createCompany`, `updateCompany`, `setCompanyLiked`, `deleteCompany`
    - `frontend/lib/api/contacts.ts`: `markConnectionRequestSent`
    - Same-origin `/api/v1/...`, `credentials: "include"`, `{ ok: true, ... } | Failure` results, distinct `notFound` and `conflict` failures
  - [x] 3.6 Add shared hooks and display helpers
    - `useInfiniteList` (cursor state, IntersectionObserver sentinel, focusable "Load more" fallback, loading/error/retry, announce "N more loaded")
    - `useUrlFilters` (read and write filter/search state in the query string; debounced search input)
    - `useOptimisticLike` (optimistic toggle, rollback and announce on failure)
    - Formatters: joined location, match strength label (Strong >= 80, Good 60–79, Weak < 60), date formatting
    - Take seniority, work arrangement and job type labels from `frontend/lib/profile/options.ts` (do not duplicate)
  - [x] 3.7 Add a shared `HeartToggle` component
    - A `button` with `aria-pressed`, label such as "Like {name}", Lucide heart icon, at least 44px tap target
  - [x] 3.8 Ensure shared primitive tests pass
    - Run ONLY the tests written in 3.1, plus the existing profile form tests affected by 3.4

**Acceptance Criteria:**
- The tests written in 3.1 pass
- `Dialog` and announcer are accessible and reusable
- API clients share one request module and never throw on API errors
- Hooks are ready for the inbox and companies pages

### Frontend: Inbox Pages

#### Task Group 4: Shared JobList, Job Cards and Filter Bar
**Dependencies:** Task Group 3

- [x] 4.0 Complete the four inbox pages
  - [x] 4.1 Write 2-8 focused tests for the inbox UI
    - Job card shows known fields and hides null ones; shows the match strength word label and number
    - Failed-evaluation card shows "Not scored", the reason and a Re-evaluate button instead of the badge
    - Heart toggle updates optimistically and rolls back with an announced error when the call fails
    - Changing a filter updates the URL query string and refetches from the first page
    - Empty inbox and "no jobs match your filters" states render correctly
  - [x] 4.2 Build the `JobCard` component
    - `li` containing a `Card`; title links to `/jobs/[id]`
    - Fields: company, industry, growth stage, location, work arrangement, job type, salary range (`compensation_range`), seniority, years of experience, match strength, visa indicator; hide null or unknown values
    - Match strength badge: word + number + icon, never color alone
    - Visa: true shows icon + "Visa sponsorship"; false shows "No visa sponsorship"; null hidden
    - Failed evaluation: "Not scored" + reason + Re-evaluate button (disabled "Re-evaluating…" state, announced outcome, card updates in place)
    - Heart toggle via `HeartToggle` and `PATCH /jobs/{id}`; no Ignore or Move actions
  - [x] 4.3 Build the `JobFilterBar` component
    - Seniority, work arrangement, job type (multi-select), visa sponsorship (any/yes/no), "Only liked", and a debounced company search input
    - Every control has a label; reuse `select-field.tsx`, `checkbox` and `dropdown-menu`
    - Collapses into a `Sheet` on mobile; inline at `md`+
  - [x] 4.4 Build the shared `JobList` component
    - Props: `inbox` (API slug)
    - Semantic `ul`; card backgrounds alternate between two warm design tokens
    - Uses `useInfiniteList` and `useUrlFilters`; loading, error-with-retry, empty-inbox and no-match states
    - Need Attention gets a friendly empty message
  - [x] 4.5 Replace the four placeholder pages
    - `frontend/app/(app)/inbox/recommended|applied|ignored|need-attention/page.tsx` render `JobList` with the matching `inbox` value (`need-attention` route maps to `need_attention`)
    - One `h1` per page; remove `PagePlaceholder` usage from these pages
  - [x] 4.6 Apply responsive layout
    - Single-column cards on mobile, wider layouts at `md`/`lg`; 44px tap targets; reuse the app shell and mobile nav
  - [x] 4.7 Ensure inbox UI tests pass
    - Run ONLY the tests written in 4.1

**Acceptance Criteria:**
- The tests written in 4.1 pass
- All four inboxes render server-filtered, infinitely scrolling card lists
- Filter and search state survives a refresh
- Unknown values are hidden and status indicators never rely on color alone

### Frontend: Job Details

#### Task Group 5: Job Details Page, Re-evaluate and Apply Flow
**Dependencies:** Task Groups 3 and 4 (reuses card helpers and the Re-evaluate button)

- [x] 5.0 Complete the Job Details page
  - [x] 5.1 Write 2-8 focused tests for Job Details
    - Scores section shows four labeled scores, or an `Alert` with `evaluation_error` when evaluation failed
    - Apply opens the posting, then "Yes" calls `applyToJob` and shows "Applied on {date}" with "View posting"; "No" or dismissing calls nothing
    - Description renders as plain text with line breaks kept (HTML is not rendered)
    - A 404 renders the "Job not found" page with a link back to the inboxes
  - [x] 5.2 Build the page at `frontend/app/(app)/jobs/[id]/page.tsx`
    - Header: `h1` job title, company name linking to `/companies/[id]`, heart toggle, back link to the job's inbox, and visa, location, arrangement, type, seniority and years (unknown values hidden)
    - Sectioned layout following `profile-section.tsx`, with ordered headings
  - [x] 5.3 Build the Scores section
    - Overall, experience, skill and industry experience, each with a label
    - Failed evaluation: `Alert` with the reason in place of the scores
  - [x] 5.4 Build the Description section and Re-evaluate button
    - Plain text with `whitespace-pre-line` (no `dangerouslySetInnerHTML`)
    - Re-evaluate: disabled "Re-evaluating…" state, updates the page with the returned job, announces success or the error status
  - [x] 5.5 Build the Company section
    - Description, history, industries, growth stage, employee estimate (unknown values hidden)
  - [x] 5.6 Build the Networking / Outreach section shell
    - Contacts with name, title and a "Request sent" indicator (text + icon)
    - Empty state explaining that contacts arrive in a later phase
    - Contact name action is wired in Task Group 6
  - [x] 5.7 Build the Apply flow
    - Apply button opens `jobs.url` in a new tab, then opens the "Did you apply?" `Dialog`
    - Only "Yes" calls `POST /jobs/{id}/apply`; announce the result
    - When applied: show "Applied on {date}" plus a "View posting" link
  - [x] 5.8 Handle not-found and error states
    - Friendly "Job not found" page on 404 (for example an expired Ignored job); error-with-retry otherwise
  - [x] 5.9 Ensure Job Details tests pass
    - Run ONLY the tests written in 5.1

**Acceptance Criteria:**
- The tests written in 5.1 pass
- The job is marked applied only after the user confirms "Yes"
- Re-evaluate shows progress and announces the outcome
- Missing jobs show a friendly not-found page

### Frontend: Click-to-Connect

#### Task Group 6: Connection Request Message Builder and Contact Action
**Dependencies:** Task Groups 3 and 5

- [x] 6.0 Complete click-to-connect
  - [x] 6.1 Write 2-8 focused unit tests for `frontend/lib/outreach/message.ts` and the contact action
    - All three placeholders replaced by bare values (no quotes or parentheses), exact expected string
    - Very long job title and company name: every value is kept in full, even when the message is longer than 300 characters (nothing is shortened)
    - Contact action: clicking the name opens LinkedIn, copies the message and calls `markConnectionRequestSent`; when the Clipboard API fails, the copy-fallback dialog opens
  - [x] 6.2 Add the message builder `frontend/lib/outreach/message.ts`
    - One exported constant holding the template exactly: `Hello {first_name}, I came across a job posting for {job_title} at your current company, {company_name}. Can you help me with a mock interview? If your company has a referral program, you may be able to earn the referral. Otherwise, you may enjoy getting to know me. Thank you!`
    - Pure function, for example `buildConnectionMessage({ firstName, jobTitle, companyName }) => string`
    - Replace each token with the bare, trimmed value
    - Never shorten or truncate any value or the fixed text, whatever the resulting length
    - Export the template as a constant so tests can assert against it
  - [x] 6.3 Build the `ContactList` / `ContactItem` components
    - Contacts with a `linkedin_url`: the name is a button-like link that, in the same click, opens the profile in a new tab (inside the user gesture, so popups are not blocked), copies the message and calls `POST /contacts/{id}/connection-request`
    - Contacts without a `linkedin_url`: plain text, no action
    - "Request sent" indicator updates after the call succeeds; no undo
    - Visible and announced "Message copied" confirmation
  - [x] 6.4 Add the Clipboard fallback
    - If `navigator.clipboard.writeText` fails, show the message in a `Dialog` with a read-only text area (select-all on focus) and a "Copy" button
  - [x] 6.5 Support the Company Details context
    - Accept an optional job title: on Company Details it comes from the company's most recently discovered job
    - If the company has no jobs: the name only opens LinkedIn, nothing is copied and the contact is not marked as sent
  - [x] 6.6 Wire `ContactList` into the Job Details Networking / Outreach section
  - [x] 6.7 Ensure click-to-connect tests pass
    - Run ONLY the tests written in 6.1

**Acceptance Criteria:**
- The tests written in 6.1 pass
- The template text matches the spec exactly and placeholders are bare values
- Filled messages are never shortened: every value and the fixed text are kept in full
- One click opens LinkedIn, copies the message and marks the request as sent, with an accessible confirmation

### Frontend: Companies and Company Details

#### Task Group 7: Companies Page, Company Form and Company Details Page
**Dependencies:** Task Groups 3 and 6 (reuses `ContactList`) and Task Group 4 (compact job card)

- [x] 7.0 Complete the Companies and Company Details pages
  - [x] 7.1 Write 2-8 focused tests for the company UI
    - Companies page search and industry filter update the URL and refetch
    - Company form shows client-side required-field errors, and shows server 422 errors next to the matching fields
    - Delete is disabled with "Companies with jobs can't be deleted." when `job_count > 0`; otherwise confirming deletes and redirects to `/companies` (from Company Details)
    - Company Details shows LinkedIn company and people-tab links only when `linkedin_url` is set, with the trailing slash handled (`.../people/`)
  - [x] 7.2 Build the `CompanyCard` component
    - Name linking to `/companies/[id]`, industries, growth stage and employee estimate when known, heart toggle
  - [x] 7.3 Build the Companies page at `frontend/app/(app)/companies/page.tsx`
    - Replace `PagePlaceholder`; semantic card list sorted liked first, then alphabetically (server order)
    - Debounced search box and an industry multi-select dropdown fed by `GET /companies/industries`; both in the URL
    - Infinite scroll with `useInfiniteList`; loading, error-with-retry, empty and no-match states
    - "Add company" button
  - [x] 7.4 Build the `CompanyForm` component (add and edit)
    - Fields: name, website URL, LinkedIn URL, logo URL (optional), description, industries (reuse `tag-input.tsx`), growth stage, employee estimate, history (optional)
    - `Sheet` on mobile, `Dialog` or `Sheet` on desktop; every control labeled
    - Client-side validation mirroring the server rules; map server 422 errors to fields
    - Edit opens the same form pre-filled
  - [x] 7.5 Build the delete confirmation
    - `Dialog` warning that the company's contacts are deleted too
    - Disabled Delete with the explanation when `job_count > 0`; handle a 409 from the server with the same message
  - [x] 7.6 Build the Company Details page at `frontend/app/(app)/companies/[id]/page.tsx`
    - `h1` name, logo with alt text (if set), description, industries, growth stage, employee estimate, history (unknown values hidden)
    - Like, edit and delete actions matching the Companies page; delete redirects to `/companies`
    - LinkedIn company link and people-tab link (`linkedin_url` without trailing slash + `/people/`), both new tab, only when set
    - Jobs section: compact job cards linking to `/jobs/[id]`, with an empty state
    - Contacts section: `ContactList` with the most recent job's title, with an empty state
    - Friendly "Company not found" page on 404
  - [x] 7.7 Apply responsive layout
    - Single-column cards on mobile, wider at `md`/`lg`; 44px tap targets; `isActivePath` keeps Companies highlighted
  - [x] 7.8 Ensure company UI tests pass
    - Run ONLY the tests written in 7.1

**Acceptance Criteria:**
- The tests written in 7.1 pass
- Users can search, filter, add, edit, like and delete companies
- Companies with jobs cannot be deleted, and the reason is explained
- Company Details reuses click-to-connect and handles 404

### Accessibility and Polish

#### Task Group 8: Cross-Page Accessibility and Responsive Pass
**Dependencies:** Task Groups 4-7

- [x] 8.0 Complete the accessibility and responsive review
  - [x] 8.1 Verify heading structure: one `h1` per page and ordered section headings on all six new pages
  - [x] 8.2 Verify keyboard access: filters, heart toggles, dialogs, click-to-connect and the "Load more" fallback work with the keyboard and show visible focus
  - [x] 8.3 Verify announcements: "Message copied", like failures, Re-evaluate and Apply results and newly loaded results are announced without stealing focus
  - [x] 8.4 Verify color use: match strength, visa and "Not scored" use text plus icon, and contrast is at least 4.5:1 on both alternating card backgrounds
  - [x] 8.5 Verify layouts at mobile (320-768px), tablet (768-1024px) and desktop (1024px+), including the filter `Sheet` and the company form `Sheet`
  - [x] 8.6 Run `npm run lint`, `npm run typecheck` and `npm run format:check` in `frontend/`, and the backend linter, and fix any issues

**Acceptance Criteria:**
- All checks in 8.1-8.5 pass
- Lint, type-check and formatting are clean

### Testing

#### Task Group 9: Test Review and Gap Analysis
**Dependencies:** Task Groups 1-8

- [x] 9.0 Review existing tests and fill critical gaps only
  - [x] 9.1 Review the tests from Task Groups 1-7
    - Backend: tests from 1.1 and 2.1
    - Frontend: tests from 3.1, 4.1, 5.1, 6.1 and 7.1
    - Total existing tests: approximately 14-56
  - [x] 9.2 Analyze coverage gaps for THIS feature only
    - Check that the spec's required pytest flows are covered: list/filter/search, like, apply, connection-request, company create/update/delete (including the 409) and re-evaluate with the evaluator mocked
    - Check that the message builder is covered (bare placeholder values, nothing shortened for long values)
    - Check paging correctness across pages (no duplicates or skipped rows when sort keys tie)
    - Prioritize end-to-end workflows over unit gaps
  - [x] 9.3 Write up to 10 additional strategic tests maximum
    - Candidates: keyset paging across two pages with tied `liked`/`discovered_when` values; Re-evaluate keeps an Applied job in Applied; `GET /companies?industry=` array overlap; companies typo search through the API; click-to-connect on Company Details with no jobs does not mark the contact
    - Skip non-critical edge cases, performance and exhaustive accessibility tests
  - [x] 9.4 Run feature-specific tests only
    - Run the tests from 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1 and 9.3, plus `tests/test_fetcher.py` and `tests/test_migrations.py`
    - Do NOT run the entire application test suite
    - Verify the critical workflows pass

**Acceptance Criteria:**
- All feature-specific tests pass
- Critical user workflows for this feature are covered
- No more than 10 additional tests are added in this group
- Testing stays focused on this spec's requirements

## Execution Order

Recommended implementation sequence:
1. Backend: Database, Models and Services (Task Group 1)
2. Backend: API Endpoints (Task Group 2)
3. Frontend: Shared Primitives (Task Group 3). `Dialog` and the announcer can start alongside Task Group 2
4. Frontend: Inbox Pages (Task Group 4)
5. Frontend: Job Details (Task Group 5)
6. Frontend: Click-to-Connect (Task Group 6). The pure message builder (6.2) has no dependencies and can be built at any time
7. Frontend: Companies and Company Details (Task Group 7)
8. Accessibility and Polish (Task Group 8)
9. Test Review and Gap Analysis (Task Group 9)
