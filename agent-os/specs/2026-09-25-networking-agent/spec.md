# Specification: Phase 4 — Networking Agent

## Goal
Add a user-triggered "Find contacts" action that runs one SerpApi Google search (`site:linkedin.com/in`) and one small LLM call to pick up to 5 relevant people at a company, then stores them in `company_networking`. The app never sends LinkedIn connection requests or messages. Phase 3 click-to-connect stays the only way to reach out.

## User Stories
- As a job seeker, I want to click "Find contacts" on a job I like or have applied to, so that I get a short list of peers and a possible hiring manager I can ask for a mock interview or referral.
- As a job seeker, I want to see clearly why contact search is unavailable (no SerpApi key, or no recommended or applied job at the company), so that I know what to do next.
- As a job seeker, I want contacts I already reached out to kept exactly as they are when I search again, so that my "Request sent" history is never lost.

## Specific Requirements

**Networking agent (`backend/jobs/src/agents/networking.py`)**
- Public entry point: find contacts for one company, given the job that supplies the role terms. It runs exactly one SerpApi search and at most one LLM selection call (plus the standard single validation retry in `run_structured`). It is never called by the fetcher or on any schedule.
- Search: SerpApi `google` engine. Query is `site:linkedin.com/in "<company name>" "<role title>"`. The role title is the job title with seniority and level words (Senior, Staff, Lead, Principal, Junior, I/II/III and similar) removed. "Lead" is removed only when another word follows it, so "Tech Lead" is kept. Request up to 20 results in one call. Keep only organic results whose link is a `linkedin.com/in/...` profile URL.
- Skills: the job's skills are the user's `hard_skills` found in the job description by case-insensitive, whole-word string matching. They are not put in the query. They go to the LLM, together with the full `hard_skills` list, as ranking signals. No extra LLM call is made to extract skills.
- LLM input: the company name, the job title, the matched skills and a numbered list of results (index, result title, snippet). Only the fields from `llm_safe_preferences` may be sent. The LLM returns a ranked list of `{index, category}`, where category is `peer` or `manager`.
- Selection rules in `NETWORKING_SYSTEM_PROMPT`: prefer people in the same or a close peer role. Allow at most one hiring manager or team lead. Exclude recruiters, HR and talent acquisition, executives (C-level, VP and above), and anyone the result shows no longer works at the company.
- The code enforces these limits after the LLM replies. Drop indexes that are out of range or duplicated. Keep at most one `manager` and at most 5 contacts in total. An empty selection is a valid result.
- Grounding: `linkedin_url`, first name, last name and title are all parsed in code from the chosen search result. The name is the result-title text before the first " - " / " – " / " | ". The title is the next segment, or null. The LLM never supplies URLs, names or titles. Results without a parseable name are skipped.
- Use `resolve_system_prompt(session, "networking", NETWORKING_SYSTEM_PROMPT)` so the prompt can be customised in the `prompts` table like other agents. No provider-native web search or tool use, so any LiteLLM model works, including local ones.

**SerpApi client and secrets**
- Reuse `Settings.serpapi_api_key`, `SERPAPI_SEARCH_URL`, the shared `HttpClient` and the error-handling pattern from `google_jobs.py`. That pattern is: `SourceError` means failure, an `error` key other than "no results" means failure, and "no results" means an empty list.
- Never log request URLs or params, because the API key travels in the query string. Log only the company id and the number of results, selected contacts, new contacts and updated contacts. Never log contact names or profile URLs.
- Put the shared SerpApi call in a small helper so the Google Jobs source and the networking agent don't each build requests separately. Changing Google Jobs behaviour is out of scope.

**LinkedIn URL normalization and deduplication**
- Add a single pure normalizer: lowercase the URL, force `https`, map `xx.linkedin.com` and `linkedin.com` to `www.linkedin.com`, and strip the query string, fragment and trailing slash. Reject anything that is not a `/in/<slug>` path.
- Match within the company by normalized URL first. If there is no URL match, fall back to a case-insensitive first-name plus last-name match against contacts at that company that have no `linkedin_url`. On a fallback match, set that contact's URL.
- When an existing contact is found again, update `title` only if the new title is non-empty and different. Never change `connection_request_sent` or `connection_request_sent_at`. Never delete contacts.
- New contacts are inserted with the normalized URL. Write within one transaction. Lock the company row (`SELECT ... FOR UPDATE`) so that two concurrent clicks cannot create duplicates. The unique index is the final safeguard.

**Database migrations (Alembic, reversible, one change each)**
- `0011`: add `companies.contacts_searched_at` (timestamptz, nullable) and add it to the `Company` model. It is set to now after every successful run (search and selection both succeeded), including runs that find no contacts. It is used only for display. There is no cooldown.
- `0012` (data): normalize existing `company_networking.linkedin_url` values and merge duplicates within each company. Keep the row with `connection_request_sent = true` and the earliest `connection_request_sent_at`, or else the lowest id. The migration carries its own copy of the normalizer rather than importing app code. Downgrade is a documented no-op.
- `0013`: unique index `uq_company_networking_company_id_linkedin_url` on `(company_id, linkedin_url)`. Declare it in the model's `__table_args__`. NULL URLs remain allowed.

**Eligibility and availability rules (enforced in the backend)**
- Contact search is available only when `SERPAPI_API_KEY` is set and the company has at least one job with `inbox_type` of `recommended` or `applied`. Eligibility is per company, not per job.
- Add a `contact_search` object to both `JobDetail` and `CompanyDetail`. It has `available` (bool), `unavailable_reason` (`"no_api_key"`, `"no_eligible_job"` or null) and `last_searched_at`. The key check comes first. The check must add no N+1 queries: use one `EXISTS` query.
- There is no daily cap and no per-company cooldown. Each click runs one search. The API does not add rate-limit headers for this endpoint.

**Find contacts endpoint**
- `POST /api/v1/companies/{id}/contacts/search` sits behind `get_current_user` and takes an optional `job_id` query parameter. It runs synchronously, like re-evaluate.
- Role terms come from `job_id` when it is given. The job must belong to the company; otherwise return 422. Without `job_id`, use the company's most recently discovered `recommended` or `applied` job.
- Errors return `{"detail": ...}` through the existing handlers:
  - 404: unknown company or job.
  - 409: company not eligible ("Contact search is available for companies with a recommended or applied job.").
  - 503: no SerpApi key ("Contact search needs a SerpApi key. See the README.").
  - 502: SerpApi or the LLM failed, with a user-friendly message. No contacts are written and `contacts_searched_at` is not changed.
- On success return 200 with `found`, `created` and `updated` counts, the company's full contact list (`ContactRead`) and the updated `contact_search` status.

**"Find contacts" button (frontend)**
- New `components/contacts/find-contacts-button.tsx` that follows the `ReEvaluateButton` pattern. While running, it shows `aria-disabled` and "Searching…", and extra clicks are ignored. The outcome is announced through `useAnnounce`, for example "Found 3 new contacts, updated 1", "No new contacts found", or the error message.
- Show it on every Job Details page in the Networking / Outreach section (with `job_id`), and on Company Details in the Contacts section (without `job_id`). On success, replace the displayed contact list and status with the response.
- When `available` is false, render the button disabled with visible explanation text linked through `aria-describedby`. The text depends on `unavailable_reason`: SerpApi key missing (mention the README), or no recommended or applied job at the company.
- When a search has run, show "Last searched X days ago" (relative time, with the full date in a `title`/`time` element). Otherwise show "Not searched yet".
- Keep the existing "People on LinkedIn" people-tab link on Company Details as the manual fallback, and add the same link to the Job Details Networking section when `company.linkedin_url` is set.
- Add `findContacts(companyId, jobId?)` to `lib/api/contacts.ts` using the shared `request` helper and typed `{ ok } | Failure` results. Extend the job and company types with `contact_search`.

**Contact list updates**
- Above a non-empty list, add one note: "Found via search, may be out of date." Click-to-connect, the message template and "Request sent" do not change.
- Change the empty-state text from "arrives in a later phase" to a prompt to use Find contacts (or the explanation why it is unavailable).
- No delete, hide, edit or manual-add controls.

**Documentation**
- `roadmap.md` Phase 4: replace "On job fetch" with button-triggered discovery for companies with a recommended or applied job, remove the Playwright outreach bullet, and keep the Deferred "Auto-connect" item.
- `mission.md`: remove "Playwright-assisted LinkedIn connection requests". `tech-stack.md`: change the Browser Automation row's use from LinkedIn outreach to the Phase 5 Apply flow only. Playwright is not added as a backend dependency.
- README: add a "Contact search" section. It needs `SERPAPI_API_KEY`, uses one SerpApi search per click with no cap, adds to the same monthly quota as Google Jobs, and results come from Google and may be out of date.

**Tests (core flows only, external services mocked)**
- Agent: the LLM can only pick from the given results (bad or duplicate indexes are dropped), there is at most one manager and at most 5 contacts, and names, titles and URLs are parsed from the result.
- Storage: URL normalization and dedup, title update on re-find, request-sent fields preserved, and name fallback.
- Endpoint: success counts, 409 when not eligible, 503 without a key, 502 on SerpApi failure with no writes.
- Frontend: button enabled and disabled states with explanations, and the success announcement plus the list refresh.

## Visual Design
No visual assets were provided (`planning/visuals/` is empty). Follow the Phase 3 design system: `DetailSection`, `Button` variant `outline` with Lucide icons (for example `UserSearch` and `LoaderCircle`), muted helper text, 44px tap targets, and states that never rely on colour alone.

## Existing Code to Leverage

**`backend/jobs/src/sources/google_jobs.py`**
- `SERPAPI_SEARCH_URL`, `is_enabled(settings)`, the timeout constant, `NO_RESULTS_ERROR` handling and the rule that request URLs are never logged. Extract the request into a shared helper that both callers use.
- `HttpClient` from `sources/providers/base.py` for the GET with retry and size cap.

**`backend/jobs/src/agents/company_lookup.py` and `backend/jobs/src/llm.py`**
- Agent layout: `AGENT_NAME`, a `*_SYSTEM_PROMPT` constant, a Pydantic output model with `field_validator`s, and `resolve_system_prompt` followed by `complete_structured`.
- `llm_safe_preferences` for the `hard_skills` sent to the model. Raise `LlmError`/`LlmOutputError`, which the endpoint maps to 502.

**`backend/jobs/src/api/v1/contacts.py`, `jobs.py`, `schemas/contacts.py`, `schemas/jobs.py`, `schemas/companies.py`**
- `ContactRead.from_model` for the response. Keep the idempotent first-timestamp behaviour of `mark_connection_request_sent`.
- The `re_evaluate_job` synchronous-action pattern, the `DbSession`/`AppSettings` dependencies and `_load_job`-style 404s. Add `contact_search` to `JobDetail` and `CompanyDetail`.

**`frontend/components/jobs/re-evaluate-button.tsx`, `components/contacts/contact-list.tsx`, `components/ui/announcer.tsx`**
- Copy the running-state, `aria-disabled` and announce pattern for `FindContactsButton`. `ContactList` gets the "may be out of date" note and the new empty state.
- `job-details.tsx` (the `networking` DetailSection) and `company-details.tsx` (the `contacts` section and the people-tab link) are where the button and status go.

**`frontend/lib/api/request.ts`, `lib/api/contacts.ts`**
- The shared `request` helper and the typed failure messages for the new `findContacts` call.

## Out of Scope
- Sending LinkedIn connection requests or messages in any form (auto-connect stays Deferred).
- Playwright or any logged-in or automated LinkedIn access, for outreach or discovery.
- Automatic discovery during the daily fetch or on any schedule. Also out: daily caps, cooldowns and lifetime per-company caps.
- Discovery for companies without a recommended or applied job (including liked-only companies).
- Provider-native LLM web search or tool use, and extra LLM calls to extract job skills.
- Paid people-data APIs (Proxycurl, Apollo and similar).
- Finding contact emails or emailing contacts.
- AI-written per-contact messages (the Phase 3 template stays).
- Adding, editing, deleting or hiding contacts manually.
- Tracking whether a contact accepted or replied, and a Prompts editor UI.
