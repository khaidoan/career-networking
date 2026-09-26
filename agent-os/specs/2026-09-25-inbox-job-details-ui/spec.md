# Specification: Phase 3 — Inbox & Job Details UI

## Goal
Replace the inbox and companies placeholder pages with working pages: four job inboxes, Job Details, Companies and Company Details. Add the JWT-protected jobs, companies and contacts endpoints behind them, so the user can review, like, re-evaluate and apply to discovered jobs and reach contacts at each company.

## User Stories
- As a job seeker, I want to browse my Recommended, Applied, Ignored and Need Attention jobs as filterable cards so that I can quickly decide which roles to pursue.
- As a job seeker, I want to open a job's details, apply to it and message a contact at the company in one click so that I can act on a good match right away.
- As a job seeker, I want to search, add, edit, like and delete companies so that I can keep a curated list of target employers.

## Specific Requirements

**Backend API endpoints (FastAPI, `/api/v1`, all behind `Depends(get_current_user)`)**
- New routers `jobs.py`, `companies.py` and `contacts.py` in `backend/jobs/src/api/v1/`, with Pydantic schemas in `schemas/`, registered in `router.py` the same way as `preferences.router`.
- Jobs: `GET /jobs` (list), `GET /jobs/{id}` (job plus its company and the company's contacts), `PATCH /jobs/{id}` (only `liked` is editable), `POST /jobs/{id}/apply`, `POST /jobs/{id}/re-evaluate`.
- Companies: `GET /companies` (list), `GET /companies/industries` (distinct industries, sorted), `GET /companies/{id}` (company, its jobs, its contacts and `job_count`), `POST /companies`, `PUT /companies/{id}`, `PATCH /companies/{id}` (only `liked`), `DELETE /companies/{id}`.
- Contacts: `POST /contacts/{id}/connection-request` sets `connection_request_sent = true` and sets `connection_request_sent_at` to now. Calling it again is safe and keeps the first timestamp.
- `POST /jobs/{id}/apply` sets `inbox_type = "applied"` and `applied_when = now`. It is idempotent, so a job that is already applied keeps its original `applied_when`.
- Missing ids return 404 with `{"detail": ...}`. Invalid input returns 422 through the existing handlers in `errors.py`. `DELETE /companies/{id}` returns 409 with a clear message if the company still has jobs, because of the `ON DELETE RESTRICT` rule.
- Company create and update are validated on the server. Required: name, website URL, LinkedIn URL, description, at least one industry, growth stage and employee estimate. Optional: history and logo URL. URLs must be absolute http(s). The LinkedIn URL must be on linkedin.com. Text is trimmed, and blank strings are treated as missing.
- Load list responses with joins or eager loading (no N+1 queries). Add pytest coverage only for the core flows: list/filter/search, like, apply, connection-request, company create/update/delete (including the 409), and re-evaluate with the evaluator mocked.

**Server-side filtering, search and paging**
- `GET /jobs` query params: `inbox` (required, one of `INBOX_TYPES`), `seniority`, `work_arrangement` and `job_type` (each repeatable), `visa` (`yes`/`no`), `liked` (`true`), `company` (search text), `cursor` and `limit` (default 25, max 50).
- Check filter values against `vocabularies.py` (`SENIORITY_LEVELS`, `WORK_ARRANGEMENTS`, `JOB_TYPES`). Accept URL slugs such as `need-attention` only at the frontend route level. The API uses the stored slug `need_attention`.
- Job sort order: `liked` desc, `discovered_when` desc, `id` desc. Company sort order: `liked` desc, `name` (case-insensitive) asc, `id` asc.
- Use keyset (cursor) paging with an opaque `next_cursor` in each list response (`null` on the last page), so infinite scroll never shows a row twice or skips one.
- `GET /companies` params: `q` (name search), `industry` (repeatable, matches any selected industry through array overlap), `cursor`, `limit`.
- Name search is case-insensitive and typo-tolerant, runs in the database, and makes no AI calls. A row matches on a substring match (`ILIKE`) or on `pg_trgm` word similarity. The job inbox company search uses the same logic against the joined company name.
- Add a new reversible Alembic migration (`0010_...`) that enables the `pg_trgm` extension and adds a GIN trigram index on `companies.name`.

**Re-evaluate a single job**
- `POST /jobs/{id}/re-evaluate` calls the existing `evaluate_job` synchronously with the current preferences. Build `JobForEvaluation` from the job's title, company name, joined location parts and description.
- Move the fetcher's success path (copy the `JobEvaluation` fields onto the job, then pick the inbox) into a shared helper. The fetcher and this endpoint both call that helper, together with the existing `apply_evaluation_failure` and `describe_evaluation_error`.
- On success: update the scores and extracted fields and clear `evaluation_error`. On failure: store the new `evaluation_error` and clear the scores.
- Inbox rule: only Recommended and Ignored jobs can move, using `inbox_for` with `settings.match_threshold`. Applied and Need Attention jobs keep their inbox, and only their scores change.
- The endpoint returns the updated job (200) even when the evaluation fails, and the frontend shows the resulting status. Remove "never re-evaluated" from the fetcher comment.
- UI: a "Re-evaluate" button on Job Details for every job, and on the "Not scored" marker of failed-evaluation cards. The button shows a disabled "Re-evaluating…" state and announces the success or error outcome.

**Inbox pages and job cards**
- `/inbox/recommended`, `/inbox/applied`, `/inbox/ignored` and `/inbox/need-attention` all render one shared `JobList` component with the matching `inbox` value, replacing `PagePlaceholder`.
- Cards are a semantic list (`ul`/`li` of `Card`), not tables. Card backgrounds alternate between two warm design-token colors.
- Card fields: title (links to `/jobs/[id]`), company, industry, growth stage, location (city, state and country joined), work arrangement, job type, salary range (`compensation_range`), seniority, years of experience, match strength and visa indicator. Any null or unknown value is hidden.
- Match strength is an `overall_score` badge with a word label and the number: Strong (>= 80), Good (60–79), Weak (< 60). Jobs with an `evaluation_error` show "Not scored", the reason and the Re-evaluate button instead.
- Visa indicator: true shows an icon plus "Visa sponsorship", false shows "No visa sponsorship", null is hidden.
- The heart toggle updates optimistically through `PATCH /jobs/{id}` and rolls back with an error message if the call fails. There are no Ignore or Move actions.
- Filter bar: seniority, work arrangement, job type, visa sponsorship, "Only liked" and a company search input (debounced). All filter and search state lives in the URL query string. On mobile the filters collapse into a `Sheet`.
- Infinite scroll uses an IntersectionObserver sentinel plus a focusable "Load more" fallback button. Loading, error-with-retry, empty-inbox and "no jobs match your filters" states are all included. Need Attention gets a friendly empty message.

**Job Details page (`/jobs/[id]`)**
- Header: job title, company name (links to `/companies/[id]`), heart toggle, a back link to the job's inbox, and the visa, location, arrangement, type, seniority and years fields (unknown values hidden).
- Scores section: overall, experience, skill and industry experience, each with a label. If evaluation failed, an `Alert` shows the `evaluation_error` reason in place of the scores.
- Full job description shown as plain text with line breaks kept (no raw HTML rendering), followed by the Re-evaluate button.
- Company section: description, history, industries, growth stage and employee estimate.
- Networking / Outreach section: the company's contacts with name, title and a "Request sent" indicator. The empty state explains that contacts arrive in a later phase.
- Apply flow: the Apply button opens `jobs.url` in a new tab, then shows a "Did you apply?" dialog. Only "Yes" calls `POST /jobs/{id}/apply`. "No" or dismissing the dialog changes nothing. Once applied, the page shows "Applied on {date}" plus a "View posting" link.
- A 404 (for example, an expired Ignored job deleted by the fetcher) renders a friendly "Job not found" page with a link back to the inboxes.

**Click-to-connect and the connection request message**
- Clicking a contact's name does three things in the same click: opens their `linkedin_url` in a new tab, copies the filled message to the clipboard, and calls `POST /contacts/{id}/connection-request`. There is no undo in this phase.
- The template is stored exactly as follows, as one frontend constant (typos corrected and approved by the user): `Hello {first_name}, I came across a job posting for {job_title} at your current company, {company_name}. Can you help me with a mock interview? If your company has a referral program, you may be able to earn the referral. Otherwise, you may enjoy getting to know me. Thank you!`
- All three placeholders are handled the same way: each `{...}` token is replaced by the bare value, with no surrounding quotes or parentheses. `{first_name}` is the contact's first name, `{job_title}` is the job's title, and `{company_name}` is the company's name.
- Never shorten the message: every value and the fixed text are kept in full, even if the result is longer than LinkedIn's 300-character note limit.
- The message is copied without an edit step. If the Clipboard API fails, show the message in a dialog with a select-all "Copy" fallback. A visible, screen-reader-announced "Message copied" confirmation is shown.
- Contacts without a `linkedin_url` are shown as plain text with no action. On Company Details, `{job_title}` comes from the company's most recently discovered job. If the company has no jobs, the name only opens LinkedIn and the contact is not marked as sent.
- Put the builder in a pure, unit-tested function (for example `frontend/lib/outreach/message.ts`).

**Companies page (`/companies`)**
- A card list (not a table) sorted liked first, then alphabetically. It has a like toggle, and each company name links to `/companies/[id]`. Cards show name, industries, growth stage and employee estimate when known.
- Search box (debounced, typo-tolerant name search on the server) and an industry multi-select dropdown fed by `GET /companies/industries`. Both are kept in the URL. The page uses infinite scroll like the inboxes.
- "Add company" opens a form (Sheet on mobile, dialog or sheet on desktop) with name, website URL, LinkedIn URL, logo URL (optional), description, industries (reuse `TagInput`), growth stage, employee estimate and history (optional).
- Edit uses the same form, pre-filled. The form validates on the client for fast feedback and shows the server's 422 errors next to each field.
- Delete opens a confirmation dialog warning that the company's contacts are deleted too. If `job_count > 0`, the Delete button is disabled with the explanation "Companies with jobs can't be deleted."

**Company Details page (`/companies/[id]`)**
- Name, logo (if set, with alt text), description, industries, growth stage, employee estimate and history (unknown values hidden). Includes like, edit and delete actions matching the Companies page.
- LinkedIn company page link (`linkedin_url`) and people tab link (`linkedin_url` with any trailing slash removed, then `/people/`). Both open in a new tab and appear only when `linkedin_url` is set.
- The company's jobs are shown as compact job cards linking to `/jobs/[id]`, and its contacts use the same click-to-connect behavior. Each list has an empty state.
- A 404 shows a friendly "Company not found" page. A successful delete redirects to `/companies`.

**Responsive and accessible behavior**
- Mobile-first Tailwind layout: single-column cards on small screens, wider layouts at `md`/`lg`. Reuse the existing app shell and mobile nav, and keep tap targets at least 44px.
- Heart toggles are `button`s with `aria-pressed` and labels such as "Like {job title}" or "Like {company}".
- Match strength, visa and "Not scored" never rely on color alone (text plus icon). Contrast is at least 4.5:1.
- Add a small `Dialog` primitive to `components/ui/` using the Radix Dialog the same way `sheet.tsx` does, for Apply confirmation, delete confirmation and the copy fallback. Focus is trapped while open and returned to the trigger on close.
- Add a toast / live-region announcer for "Message copied", like failures, Re-evaluate results and Apply results. Newly loaded infinite-scroll results are announced, and focus is not stolen.
- Each page has one `h1` and ordered section headings. Every filter and form control has a label.

**Open questions (proposed defaults applied until the user confirms)**
- Re-evaluate moving only Recommended and Ignored jobs, blocking delete for companies with jobs, optional logo URL, no undo for "request sent", and the job title used on Company Details all follow the defaults in `planning/requirements.md`.

## Visual Design
No visual assets were provided (`planning/visuals/` is empty). Follow the existing Phase 1 design system: warm, modern and minimalist, using Tailwind, the shadcn-style primitives in `frontend/components/ui/` and Lucide icons.

## Existing Code to Leverage

**`frontend/components/ui/*` and `frontend/components/profile/*`**
- Use `card`, `badge`, `button`, `input`, `select`, `checkbox`, `dropdown-menu`, `alert`, `sheet`, `textarea` and `separator` for all new UI. There is no need for new visual primitives other than `Dialog` and the toast.
- Reuse `tag-input.tsx` for company industries, `select-field.tsx` for filter selects, and `profile-section.tsx` as the pattern for sectioned detail layouts.

**`frontend/lib/api/preferences.ts` and `frontend/lib/auth/client.ts`**
- Model new `lib/api/jobs.ts`, `lib/api/companies.ts` and `lib/api/contacts.ts` on this: same-origin `/api/v1/...`, `credentials: "include"`, typed `{ ok: true } | Failure` results instead of throwing, and the shared session-expired, network and unexpected error messages.
- Move the shared `request` and validation-error parsing helpers into one module instead of copying them into each client.

**`frontend/lib/profile/options.ts`, `backend/jobs/src/vocabularies.py`, `frontend/lib/navigation.ts`**
- Take display labels for seniority, work arrangement and job type from `options.ts`, and validate filter values on the server against `vocabularies.py`. Keep one source of truth each.
- `isActivePath` already highlights Companies for `/companies/[id]`. `/jobs/[id]` has no sidebar entry and uses its back link instead.

**`backend/jobs/src/api/v1/preferences.py`, `schemas/preferences.py`, `router.py`, `errors.py`**
- Follow the router, `DbSession` dependency, Pydantic read/update schema, logging and `HTTPException` patterns. Errors render as `{"detail": ...}` through the central handlers.

**`backend/jobs/src/fetcher.py` and `backend/jobs/src/agents/evaluator.py`**
- Reuse `evaluate_job`, `JobForEvaluation`, `apply_evaluation_failure`, `describe_evaluation_error`, `inbox_for` and `settings.match_threshold` for Re-evaluate. Move `_evaluate`'s field-copy logic into a shared helper rather than copying it.
- The models `Job`, `Company` and `CompanyNetworking` already have every needed column, relationship and cascade (contacts are deleted with their company, jobs block deletion). Only the trigram migration changes the schema.

## Out of Scope
- Networking agent and Playwright-driven LinkedIn outreach (Phase 4).
- AI-generated resumes and cover letters, the prepare_job pipeline and the Apply agent (Phase 5).
- Manual inbox moves (Ignore / Move to Recommended) and bulk actions on jobs.
- Deleting jobs.
- Running the fetcher from the UI.
- AI or LLM calls during search.
- Editing the connection request message before copying.
- Adding, editing or deleting networking contacts manually.
- Undoing "connection request sent" and background or queued re-evaluation.
