# Spec Requirements: Phase 3 — Inbox & Job Details UI

## Initial Description

Source: `agent-os/product/roadmap.md`, Phase 3 (captured in `planning/raw-idea.md`, 2026-09-25). Phases 1 (Foundation) and 2 (Profile & Job Discovery) are already implemented.

**Goal:** Display discovered jobs in an actionable inbox interface.

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

## Requirements Discussion

### First Round Questions

**Q1:** I assume we build all of Phase 3 as one spec, as with Phases 1 and 2, including the new backend endpoints for reading and updating jobs, companies and contacts. Is that right, or should we split it into (a) inboxes plus Job Details and (b) the two company pages?
**Answer:** Yes, one spec (all of Phase 3 including backend endpoints).

**Q2:** I'm proposing Job Details at `/jobs/[id]` and Company Details at `/companies/[id]`; inbox lists sorted newest first by `discovered_when`; filtering, search and paging done by the backend with a "Load more" button (about 25 cards at a time); filters and search saved in the URL. Numbered pages, infinite scroll, or browser-side filtering instead?
**Answer:** Infinite scroll (instead of "Load more"). The other proposed defaults were not objected to: `/jobs/[id]`, `/companies/[id]`, newest first, server-side filtering/search/paging, filters in the URL.

**Q3:** Each card shows `overall_score` as a colored badge with a label (Strong 80+, Good 60–79, Weak below 60), and Job Details shows all four scores. Different cut-offs or display? Should unknown values show as "Not specified" or be hidden?
**Answer:** "When a value is unknown, the field should be hidden." Badge cut-offs and display not objected to (Strong >= 80 / Good 60–79 / Weak < 60; all four scores on Job Details).

**Q4:** The heart toggles `jobs.liked`; I assume an "Only liked" filter and liked jobs sorted to the top. Should this phase add "Ignore" / "Move to Recommended" actions, or leave inbox changes to the fetcher and the Apply flow?
**Answer:** "Leave inbox changes to the fetcher and the Apply flow." No Ignore/Move actions. (Liked filter and liked-first sort not objected to.)

**Q5:** Before Phase 5, Apply opens `jobs.url` in a new tab, asks "Did you apply?", and on yes moves the job to Applied and records `applied_when`. Or should Apply just link to the posting?
**Answer:** "Only marked the job as applied if it is actually applied."

**Q6:** Clicking a contact's name opens their LinkedIn profile and copies a message from a fixed template (max 300 characters) using the contact's first name, the user's first name, company and job title, asking for a mock interview; the contact is marked `connection_request_sent` with a timestamp. Do you have wording in mind? Should the message be editable before copying?
**Answer:** Message template, verbatim:

> Hello {first_name}, I came across a job posting for "{job_title}" at your current company (company_name).  Can you help me with mock interview?  If your company has a referal program, you may be able to earn the referal.  Otherwise, you may enjoy and getting to know me.  Thank you

Follow-up (2026-09-25): the user asked for the typos to be fixed and for `{first_name}` and `{job_title}` to be handled the same way as the company name. See "Connection request message" below for the final template.

The user did not answer whether the message is editable before copying. Marking the contact as `connection_request_sent` with a timestamp was not objected to.

**Q7:** Companies page: "intelligent" search as case-insensitive, typo-tolerant match on name, description and industries in the database (no AI)? Make logo URL optional in the add form? Build the people-tab link as `{linkedin_url}/people/`? Should companies be editable or deletable?
**Answer:** "Search should be case-insensitive, typo-tolerant match on name." (name only). "Companies should be editable and deletable on the companies page." Logo URL and people-tab link questions not answered; proposed defaults stand.

**Q8:** Failed evaluations show "Not scored" plus the reason on cards and a notice on Job Details. I assume no "Re-evaluate" button this phase, and Need Attention is the same card list, mostly empty until Phase 5. Correct?
**Answer:** "We should add the 'Re-evaluate' button." Need Attention behavior as proposed was not objected to.

**Q9:** Pages must work well on mobile (reusing the existing mobile menu), and heart toggles, filters and copy-to-clipboard must work from the keyboard and with screen readers, with an on-screen confirmation such as "Message copied". Correct?
**Answer:** "Make your best judgement here."

**Q10:** Proposed exclusions: networking agent and Playwright outreach (Phase 4); AI resumes/cover letters and the Apply agent (Phase 5); bulk actions; deleting jobs; re-running the fetcher from the UI; AI calls during search. Anything to add or keep in?
**Answer:** "We do not need to run the fetcher from the UI." The rest of the proposed out-of-scope list is accepted.

### Existing Code to Reference

The user gave no additional references. These candidates were found during research:

**Similar Features Identified:**
- Feature: UI primitives - Path: `frontend/components/ui/` (card, badge, button, input, select, checkbox, dropdown-menu, alert, sheet, textarea, separator)
- Feature: Profile form field components - Path: `frontend/components/profile/tag-input.tsx`, `frontend/components/profile/select-field.tsx`, `frontend/components/profile/profile-section.tsx` (industries tag input, filter selects, sectioned layout)
- Feature: Typed browser API client pattern - Path: `frontend/lib/api/preferences.ts` (same-origin `/api/v1/...`, `credentials: "include"`, typed result objects instead of throwing, shared error messages)
- Feature: Slug-to-label vocabularies - Path: `frontend/lib/profile/options.ts` and `backend/jobs/src/vocabularies.py` (seniority, work arrangement, job type)
- Feature: Backend endpoint and schema pattern - Path: `backend/jobs/src/api/v1/preferences.py`, `backend/jobs/src/api/v1/schemas/preferences.py`, `backend/jobs/src/api/v1/router.py` (routes mounted with `Depends(get_current_user)`)
- Feature: Models - Path: `backend/jobs/src/models/job.py`, `company.py`, `company_networking.py`
- Feature: Evaluator and fetcher logic for Re-evaluate - Path: `backend/jobs/src/agents/evaluator.py` (`evaluate_job`), `backend/jobs/src/fetcher.py` (`apply_evaluation_failure`, `describe_evaluation_error`, `inbox_for`, `load_preferences`)
- Feature: Placeholder pages to replace - Path: `frontend/app/(app)/inbox/*/page.tsx`, `frontend/app/(app)/companies/page.tsx`, `frontend/components/app-shell/page-placeholder.tsx`
- Feature: Navigation - Path: `frontend/lib/navigation.ts` (`isActivePath` already highlights `/companies/[id]`; `/jobs/[id]` has no sidebar entry)

### Follow-up Questions

No follow-up questions were asked. Items the user left open are recorded as defaults (below) or as open items for confirmation.

## Visual Assets

### Files Provided:
No visual assets provided. (Bash check of `planning/visuals/` found no files.)

### Visual Insights:
- None. Follow the existing Phase 1 design system ("warm, modern, minimalist", Tailwind, shadcn-style components in `frontend/components/ui/`, Lucide icons).

## Requirements Summary

### Functional Requirements

**Inbox pages (Recommended, Applied, Ignored, Need Attention)**
- Card-based list (no HTML tables) with alternating card background colors; one shared list component used by all four pages, filtered by `inbox_type`.
- Per card: title, company, industry, growth stage, location, work arrangement, job type, salary range, seniority, years of experience, match strength badge, visa sponsorship indicator.
- Any field whose value is unknown or null is hidden (not shown as "Not specified").
- Match strength: `overall_score` shown as a colored badge with a word label: Strong (>= 80), Good (60–79), Weak (< 60).
- Failed evaluations (`evaluation_error` set, no scores): a "Not scored" marker with the failure reason instead of the badge.
- Heart icon toggles `jobs.liked` (persisted via the backend).
- Filters: seniority level, work arrangement, job type classification, visa sponsorship, plus an "Only liked" filter.
- Search by company name.
- Sort: liked jobs first, then newest first by `discovered_when`.
- Filtering, search and paging are done on the server; the frontend uses infinite scroll (loads the next page as the user nears the end of the list).
- Filter and search state is kept in the URL query string so refreshing or sharing the link keeps it.
- Clicking a card or its title opens Job Details (`/jobs/[id]`).
- No actions that move jobs between inboxes (no Ignore / Move to Recommended). Inbox changes come only from the fetcher, the Re-evaluate action (see open items) and the Apply confirmation.
- Need Attention uses the same card list; it will usually be empty until Phase 5, so it needs a friendly empty state. Every inbox has an empty state, including "no results match your filters".

**Job Details page (`/jobs/[id]`)**
- Company name (links to `/companies/[id]`), job title, visa sponsorship, location, work arrangement, job type, seniority, years of experience; unknown fields hidden.
- All four scores: overall, experience, skill, industry experience.
- When evaluation failed: a notice with the `evaluation_error` reason in place of the scores.
- Heart like/unlike toggle.
- Full job description.
- Re-evaluate button (see below).
- Networking / Outreach section listing the company's `company_networking` contacts (name, title, "request sent" indicator). A friendly empty state is needed, since contacts are populated in Phase 4.
- Clicking a contact's name: opens their LinkedIn profile in a new tab, copies the connection request message to the clipboard, shows an accessible confirmation (for example a "Message copied" toast), and marks the contact `connection_request_sent = true` with `connection_request_sent_at` set.
- Company details section: description, history, industries, growth stage, employee estimate.
- Apply button: opens the posting (`jobs.url`) in a new tab, then asks "Did you apply?". Only on "Yes" is the job moved to the Applied inbox with `applied_when` set; "No" or dismissing leaves the job unchanged. The user quote was "Only marked the job as applied if it is actually applied."

**Connection request message**
- Final template (typos corrected at the user's request, 2026-09-25):
  `Hello {first_name}, I came across a job posting for {job_title} at your current company, {company_name}. Can you help me with a mock interview? If your company has a referral program, you may be able to earn the referral. Otherwise, you may enjoy getting to know me. Thank you!`
- `{first_name}` is the contact's first name, `{job_title}` is the job's title, and `{company_name}` is the company's name. The user asked for all three placeholders to be handled the same way: each is replaced by the bare value, with no quotes or parentheses.
- Default (user did not answer the editability question): the message is copied on click without an edit step. A future phase may add editing.

**Re-evaluate**
- A "Re-evaluate" button runs the existing evaluator (`evaluate_job`) again for one job against the current preferences.
- Default scope: shown on Job Details for every job, and on the "Not scored" marker of failed-evaluation cards.
- On success: update the scores and extracted fields, and clear `evaluation_error`. On failure: store the new `evaluation_error` (same handling as the fetcher's `apply_evaluation_failure`).
- Shows a loading state while running, and a success or error message when done.

**Company Details page (`/companies/[id]`)**
- Company name, description, industries, growth stage, employee estimate, history (unknown fields hidden).
- List of the company's jobs (linking to `/jobs/[id]`, reusing the job card or a compact variant).
- List of the company's contacts from `company_networking` (same click-to-connect behavior as Job Details).
- LinkedIn company page link (`linkedin_url`) and LinkedIn people tab link (`{linkedin_url}/people/`), each shown only when `linkedin_url` is set.
- Like/unlike, edit and delete available here as well as on the Companies page.

**Companies page (`/companies`)**
- Sorted by liked first, then alphabetically by name.
- Search: case-insensitive, typo-tolerant match on company **name only**, done in the database (no AI calls).
- Industry filter: multi-select dropdown built from the industries present in the database.
- Like/unlike per company.
- Add company form. Required: name, website URL, LinkedIn URL, description, industries, growth stage, employee estimate. Optional: history and (default) logo URL.
- Edit company (same fields and validation as the add form).
- Delete company, with a confirmation dialog.
- Clicking a company name opens `/companies/[id]`.
- Infinite scroll and filters in the URL, consistent with the inbox pages.

**Backend (new FastAPI endpoints under `/api/v1`, all protected by JWT)**
- Jobs: list with inbox, filter, search, liked-only and paging parameters; get one job with company and contacts; toggle liked; mark as applied; re-evaluate.
- Companies: list with search, industry filter and paging; list distinct industries; get one company with jobs and contacts; create; update; delete; toggle liked.
- Contacts: mark connection request sent (sets the flag and timestamp).
- Validation on the server for all create and update input (required fields, URL format, allowed vocabulary values).

**Responsive and accessibility (user deferred to best judgement)**
- All pages work on mobile, tablet and desktop, reusing the existing app shell and mobile nav. Cards stack in a single column on small screens; the filter bar collapses (for example into a sheet) on mobile.
- Heart toggles are real buttons with `aria-pressed` and labels such as "Like {job title}".
- Filters, search, dialogs and click-to-connect are fully keyboard operable with visible focus.
- The "Message copied", Re-evaluate and Apply outcomes are announced through a live region or toast.
- Match strength and visa indicators do not rely on color alone (word labels and icons with text).
- Infinite scroll stays keyboard-reachable (for example a sentinel plus a focusable fallback "Load more" control) and announces new results.

### Reusability Opportunities
- `frontend/components/ui/*` primitives (card, badge, button, input, select, checkbox, dropdown-menu, alert, sheet, textarea).
- `frontend/components/profile/tag-input.tsx` for industries in the company form; `select-field.tsx` for filters.
- `frontend/lib/api/preferences.ts` as the model for new `lib/api/jobs.ts` and `lib/api/companies.ts` clients.
- `frontend/lib/profile/options.ts` for display labels of seniority, work arrangement and job type (single source; do not duplicate).
- `backend/jobs/src/vocabularies.py` for server-side validation of filter values.
- `backend/jobs/src/api/v1/preferences.py` and `schemas/preferences.py` for endpoint, schema and error patterns.
- `backend/jobs/src/fetcher.py` (`apply_evaluation_failure`, `describe_evaluation_error`, `inbox_for`, `load_preferences`) and `agents/evaluator.py` (`evaluate_job`) for Re-evaluate. Shared logic should be extracted rather than duplicated.

### Scope Boundaries
**In Scope:**
- Four inbox pages, Job Details, Company Details and Companies pages (frontend).
- All backend endpoints those pages need (jobs, companies, contacts).
- Like/unlike for jobs and companies.
- Apply button with "Did you apply?" confirmation (links to the posting only).
- Click-to-connect: open LinkedIn, copy the message, mark the request as sent.
- Re-evaluate button for a single job.
- Company add, edit and delete.
- Infinite scroll, server-side filtering, search and paging, filter state in the URL.
- Responsive layout and accessibility as described.

**Out of Scope:**
- Networking agent and Playwright-driven LinkedIn outreach (Phase 4).
- AI-generated resumes and cover letters, the prepare_job pipeline and the Apply agent (Phase 5).
- Manual inbox moves (Ignore / Move to Recommended).
- Bulk actions on jobs.
- Deleting jobs.
- Running the fetcher from the UI.
- AI or LLM calls during search.
- Editing the connection request message before copying (default; could be added later).
- Adding, editing or deleting networking contacts manually (not requested).

### Technical Considerations
- Stack: Next.js App Router + TypeScript (strict) + Tailwind + Lucide on the frontend; FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL on the backend. The JWT is an httpOnly cookie; the frontend calls the same-origin `/api/v1/*` proxied by nginx.
- Typo-tolerant name search will likely need the PostgreSQL `pg_trgm` extension and a trigram index on `companies.name` (new Alembic migration). The same approach may apply to inbox "search by company name".
- Infinite scroll needs stable paging. Keyset (cursor) paging on (liked, discovered_when, id) for jobs and (liked, name, id) for companies is preferable to offsets.
- `jobs.company_id` uses `ON DELETE RESTRICT`, so a company with jobs cannot be deleted as-is (see open items). Deleting a company already cascades to its `company_networking` contacts.
- Re-evaluate calls an LLM synchronously and may take several seconds; it needs a loading state and must respect existing LLM timeouts and error handling (`backend/jobs/src/llm.py`).
- The fetcher deletes expired Ignored jobs (`delete_expired_ignored_jobs`), so Job Details must handle a job that no longer exists (404 → friendly "not found" page).
- `CAREER_NETWORKING_FIRSTNAME` is available but not required by the user's template as written.
- Follow `agent-os/standards/*` (API conventions, migrations, validation, error handling, accessibility, responsive design, test writing).

### Open Items for Confirmation (defaults applied unless the user says otherwise)
1. **Message placeholder (resolved):** the user asked for `{first_name}`, `{job_title}` and `{company_name}` to be handled the same way, each replaced by the bare value (no quotes or parentheses).
2. **Message typos (resolved):** the user asked for the typos to be fixed. See the final template under "Connection request message".
3. **LinkedIn 300-character limit (resolved):** the user said "We do not want to shorten anything." The filled message is always copied in full, even if it is longer than 300 characters (the fixed text is 240 characters).
4. **Re-evaluate and inbox changes:** the user said inbox changes should come from the fetcher and Apply flow. Proposed default: Re-evaluate may move a job only between Recommended and Ignored, using the same match-threshold rule as the fetcher (`inbox_for`). Jobs in Applied or Need Attention keep their inbox; only their scores update.
5. **Deleting companies that have jobs:** the database blocks deleting a company that still has jobs. Proposed default: disable delete (with an explanation) when the company has jobs; allow it otherwise, with contacts deleted along with it.
6. **Logo URL:** default is optional in the add/edit form (not answered by the user).
7. **Marking contacts:** clicking a name marks the contact as request sent right away. Proposed default: no undo in this phase.
