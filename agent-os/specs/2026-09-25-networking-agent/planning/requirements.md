# Spec Requirements: Phase 4 — Networking Agent

## Initial Description

Phase 4 — Networking Agent (source: `agent-os/product/roadmap.md`, Phase 4; Phases 1-3 are already implemented).

**Goals:** Automate discovery of relevant LinkedIn contacts at target companies.

**Deliverables (as originally written in the roadmap):**

Networking Agent (`networking.py`)
- On job fetch, extract company name and skillset from posting
- Search LinkedIn for employees with matching skills
- Populate `company_networking` table
- Playwright-based LinkedIn outreach (user-triggered via UI button)

**Explicit user constraint:** "Do not auto-connect." The app must never automatically send LinkedIn connection requests. This aligns with the roadmap's Deferred / Out of Scope (v1) item "Auto-connect to LinkedIn (due to rate limiting / account risk)."

## Requirements Discussion

### First Round Questions

**Q1:** Since the app will never send anything, I propose we drop the "Playwright-based LinkedIn outreach" deliverable from Phase 4 and keep the Phase 3 click-to-connect flow (open profile, copy message, mark as sent) as the only outreach path, and update `mission.md`, `roadmap.md` and `tech-stack.md` to remove the Playwright "LinkedIn outreach" lines. Is that correct, or would you prefer (b) Playwright used only for contact discovery (reading, never connecting/messaging), or (c) Playwright opening the profile and pre-filling the note while you click Send yourself (not recommended; it is close to auto-connect and carries the same account risk)?
**Answer:** "Agree." Drop the Playwright LinkedIn outreach deliverable from Phase 4. Phase 3 click-to-connect remains the only outreach path. Remove the Playwright LinkedIn outreach rows from mission.md, roadmap.md and tech-stack.md. The roadmap's Deferred "Auto-connect" item stays.

**Q2:** I'm assuming contacts are found via web search using the existing SerpApi key (Google query like `site:linkedin.com/in "<Company>" "<skill or title>"`), reading names, titles and profile URLs from the results, with the LLM only choosing and ranking candidates; not a logged-in LinkedIn session (LinkedIn's User Agreement bans scraping/automated access, risking account restriction or ban), not LinkedIn's official APIs (no people search for individuals), and not paid people-data APIs such as Proxycurl or Apollo (would send your target list to a third party). Search results may be stale and each search uses SerpApi quota. Is web search acceptable? If `SERPAPI_API_KEY` is unset, discovery would be skipped and the existing "LinkedIn people tab" link stays as the fallback.
**Answer:** "Web search is acceptable, but is there a better way using AI?" After the trade-off was explained (provider-native web search tools for OpenAI, Anthropic and Gemini are more expensive per company, can hallucinate profile URLs, and break the LiteLLM "any model incl. Ollama" design), the user chose option (a): SerpApi Google search (`site:linkedin.com/in ...`) plus one small LLM call to select and rank candidates. There is no provider-native web search, even as a fallback. Every stored profile URL must come from an actual search result, never invented by the LLM. If SERPAPI_API_KEY is unset, discovery is unavailable; keep the existing "LinkedIn people tab" link as the fallback, and have the button explain why.

**Q3:** I propose discovery runs only for recommended jobs: automatically at the end of the daily fetch, plus a "Find contacts" button on Job Details and Company Details. Ignored jobs never trigger discovery. Should it run automatically for recommended jobs at all, or only from the button? Should liked companies get discovery even with no recommended job?
**Answer:** "Only from the button." There is NO automatic discovery during the daily fetch. "We should not run search for liked companies with no recommended job." The button appears on Job Details and Company Details. Discovery is only for companies that have at least one recommended job. How the button behaves on Company Details (and on Job Details for non-recommended jobs) under this rule is to be decided and documented (e.g. hidden or disabled with an explanation). Follow-up (2026-09-25): the user said "Allow networking after apply," so applied jobs also make a company eligible. They also asked for the button to appear on the Job Details page.

**Q4:** I propose up to 5 contacts per company per run, targeting people in the same or a close peer role to the job (for mock interviews), optionally plus one hiring manager or team lead, excluding recruiters, HR and executives, and matching on the job's key skills plus your `hard_skills`. Is that the right mix and number? Should there be a lifetime cap per company (e.g. 10) after which discovery stops?
**Answer:** "Yes." Up to 5 contacts per company per run, targeting the same or peer role (plus optionally one hiring manager or team lead), and excluding recruiters, HR and execs. Matching uses the job's skills plus the user's hard_skills. "No on the lifetime cap per company."

**Q5:** I propose deduplicating on the normalized LinkedIn profile URL within a company (lowercase, strip query string and trailing slash, map `xx.linkedin.com` to `www.linkedin.com`), with name + company as a fallback when there is no URL, via a new migration adding a unique index on `(company_id, linkedin_url)`. Existing contacts are never overwritten, so `connection_request_sent` and its timestamp are preserved. Is that right, and should an existing contact's title be updated when newer data is found?
**Answer:** "Yes." Dedup by normalized LinkedIn URL within a company, using a new migration with a unique index on (company_id, linkedin_url) and a name+company fallback. Never overwrite existing contacts. Keep connection_request_sent and its timestamp. The user said "Yes" to updating the title when newer data is found: update the title of an existing contact, but never touch its request-sent fields.

**Q6:** To stay in line with the recent token cuts, I propose: at most 1 SerpApi search plus 1 small LLM call per company per run; a company is skipped if searched in the last 14 days (new "last searched at" field); a daily cap of about 20 companies across automatic runs (env var such as `CAREER_NETWORKING_NETWORKING_DAILY_LIMIT`); the button ignores the daily cap and the 14-day cooldown but still searches only one company. Do these limits look reasonable? Should the button bypass them?
**Answer:** "Yes." Limits: max 1 SerpApi search plus 1 small LLM call per company per run; a 14-day per-company cooldown via a new last-searched timestamp; a daily cap via env var. Button bypasses the cap and cooldown. Coordinator note: since discovery is now button-only, the daily cap and cooldown as approved would never apply to anything, because the button bypasses both. Resolve sensibly and list as an open item. Suggested default: keep the per-company last-searched timestamp for display ("last searched X days ago"), with no cooldown or daily cap, and make the button one search per click.

**Q7:** I propose the agent reuses the skills the evaluator already extracts from the posting instead of a separate LLM call; `NETWORKING_SYSTEM_PROMPT` stored in the `prompts` table like other agents; contacts shown with name, title and a "found via search, may be out of date" note, with existing click-to-connect unchanged. Should you be able to delete or hide an irrelevant contact (delete endpoint and button)?
**Answer:** "We do not need to delete or hide contact." No delete/hide endpoint or UI. Keep the "found via search, may be out of date" note. Keep NETWORKING_SYSTEM_PROMPT in the prompts table. Reuse the evaluator's extracted skills rather than making an extra LLM call.

**Q8:** Out of scope: any sending of connection requests or messages; logged-in LinkedIn scraping; paid people-data APIs; emailing contacts or finding their email addresses; AI-written personal messages per contact (Phase 3 template stays); adding contacts by hand; tracking whether a contact accepted or replied. Anything missing, or anything you want included?
**Answer:** Not answered. The proposed out-of-scope list is accepted.

### Existing Code to Reference

The user added no references; the following candidates were identified during research and are recorded for the spec-writer.

**Similar Features Identified:**
- Feature: SerpApi client (Google Jobs) - Path: `backend/jobs/src/sources/google_jobs.py`
  - Backend logic to reference: SerpApi request pattern, optional-key handling (`SERPAPI_API_KEY` via `Settings.serpapi_api_key`), rule that request URLs are never logged because the key travels in the query string.
- Feature: Company lookup agent - Path: `backend/jobs/src/agents/company_lookup.py`
  - Backend logic to reference: agent structure, `*_SYSTEM_PROMPT` constant, structured LLM output.
- Feature: LLM helpers - Path: `backend/jobs/src/llm.py`
  - Backend logic to reference: `run_structured`, `complete_structured`, `resolve_system_prompt` (prompts table fallback), `llm_safe_preferences`.
- Feature: Job fetcher - Path: `backend/jobs/src/fetcher.py`
  - Backend logic to reference: recommended-only token spending, `find_or_create_company`, `company_key` normalization, advisory lock pattern. (Discovery must NOT be wired into the fetch.)
- Feature: Contacts API - Path: `backend/jobs/src/api/v1/contacts.py`, `backend/jobs/src/api/v1/schemas/contacts.py`
  - Backend logic to reference: `ContactRead` schema, mark-connection-request-sent endpoint (must keep first timestamp).
- Feature: Model - Path: `backend/jobs/src/models/company_networking.py`, `backend/jobs/src/models/company.py`, `backend/jobs/src/models/job.py`
- Feature: Phase 3 UI - Path: `agent-os/specs/2026-09-25-inbox-job-details-ui/` (Networking / Outreach section, click-to-connect, Company Details contacts list, "LinkedIn people tab" link)
  - Components to potentially reuse: Re-evaluate button pattern (loading state, success/error message, live-region announcement); contact list and toast; typed API client pattern in `frontend/lib/api/preferences.ts`.

### Follow-up Questions

No further follow-up questions were sent to the user; the coordinator asked for sensible defaults on the remaining points, which are listed under Open Items below.

## Visual Assets

### Files Provided:

No visual assets provided. (Bash check of `planning/visuals/` found no files.)

## Requirements Summary

### Functional Requirements

**Hard constraint:** The app never sends LinkedIn connection requests or messages on the user's behalf, in any form (no Playwright, no API, no background job). The Phase 3 click-to-connect flow (open profile in new tab, copy message, mark as sent) remains the only outreach path.

**Networking agent (`backend/jobs/src/agents/networking.py`)**
- Triggered only by a user-clicked "Find contacts" button. No automatic discovery during the daily fetch or any other schedule.
- Eligible only for companies with at least one recommended or applied job (`inbox_type IN ('recommended', 'applied')`). The user said: "Allow networking after apply."
- Per click, one company: exactly 1 SerpApi Google search (`site:linkedin.com/in` query built from the company name plus role/skill terms) and 1 small LLM call that selects and ranks candidates from the search results.
- Selects up to 5 contacts per run: people in the same or a peer role to the job, optionally plus one hiring manager or team lead. Excludes recruiters, HR/talent acquisition and executives.
- Matching signals: the job's skills plus the user's `hard_skills` (see Open Item 2 on where the job's skills come from).
- Every stored `linkedin_url` must come verbatim (before normalization) from an actual search result. The LLM may only reference results it was given (e.g. by index); any URL not present in the results is rejected. Names and titles likewise come from the search result data.
- No provider-native LLM web search, even as a fallback. Works with any LiteLLM model, including local ones.
- System prompt constant `NETWORKING_SYSTEM_PROMPT`, stored in and resolved through the `prompts` table like the other agents.

**Deduplication and storage**
- Normalize LinkedIn profile URLs: lowercase, strip query string and fragment, strip trailing slash, map country subdomains (`xx.linkedin.com`) to `www.linkedin.com`.
- New Alembic migration: unique index on `(company_id, linkedin_url)`. Existing rows need their URLs normalized (and any duplicates resolved) before the index is created.
- Fallback match on first name + last name within the company when a result has no usable URL.
- Existing contacts are never replaced or deleted. When an existing contact is found again, its `title` is updated if newer data differs; `connection_request_sent` and `connection_request_sent_at` are never touched.
- New per-company "last searched at" timestamp (e.g. on `companies`), set on each discovery run and shown in the UI ("Last searched X days ago").

**Limits (default; see Open Item 1)**
- One search per click. No cooldown and no daily cap, since discovery is button-only.
- While a search is running, the button is disabled to prevent duplicate clicks.

**UI: "Find contacts" button**
- Appears on every Job Details page, in the Networking / Outreach section; the user explicitly asked for it there. It also appears on Company Details, in the contacts list.
- Enabled when `SERPAPI_API_KEY` is set and the company has at least one recommended or applied job.
- When the company has no recommended or applied job (on Company Details, or on Job Details for an ignored or need-attention job whose company has none), the button is shown disabled with a visible explanation, e.g. "Contact search is available for companies with a recommended or applied job."
- When `SERPAPI_API_KEY` is unset: the button is shown disabled with an explanation that contact search needs a SerpApi key (pointing to the README), and the existing "LinkedIn people tab" link stays as the fallback.
- Role and skill terms: on Job Details, from that job; on Company Details, from the company's most recently discovered recommended or applied job.
- Follows the Phase 3 Re-evaluate pattern: loading state, then a success message (e.g. "Found 3 new contacts, updated 1") or error message, announced via a live region/toast; the contact list refreshes.
- Contacts found through search show name, title and a "Found via search, may be out of date" note. Click-to-connect is unchanged.
- The backend enforces the same eligibility rules (a recommended or applied job, key configured) and returns clear errors, not just the UI.

**Documentation updates**
- Remove the Playwright LinkedIn outreach rows/lines from `agent-os/product/mission.md`, `agent-os/product/roadmap.md` (Phase 4 deliverable) and `agent-os/product/tech-stack.md` (Browser Automation row's LinkedIn outreach use).
- Update the Phase 4 roadmap text to reflect button-triggered discovery (not "on job fetch").
- Keep the roadmap's Deferred "Auto-connect to LinkedIn" item.
- README: document that contact search requires `SERPAPI_API_KEY` and uses one SerpApi search per click.

### Reusability Opportunities
- SerpApi request, key handling and no-URL-logging rule from `backend/jobs/src/sources/google_jobs.py`.
- Agent structure and structured-output helpers from `company_lookup.py` and `llm.py` (`run_structured`, `resolve_system_prompt`).
- `company_key` normalization in `fetcher.py` for consistent company matching.
- Contacts API/schema in `backend/jobs/src/api/v1/contacts.py` and `schemas/contacts.py`.
- Phase 3 frontend: Re-evaluate button pattern, contact list, toast/live region, typed API client pattern (`frontend/lib/api/preferences.ts`).

### Scope Boundaries

**In Scope:**
- `networking.py` agent: SerpApi search + one LLM selection/ranking call, URL-grounded results.
- Button-triggered discovery endpoint and "Find contacts" button on Job Details and Company Details, with disabled states and explanations.
- Eligibility rule: company must have at least one recommended or applied job.
- Migration: unique `(company_id, linkedin_url)` index, normalization of existing URLs, per-company last-searched timestamp.
- Dedup, title updates, preservation of request-sent fields.
- `NETWORKING_SYSTEM_PROMPT` in the prompts table.
- "Found via search, may be out of date" note and "Last searched X days ago" display.
- Removing Playwright LinkedIn outreach from mission, roadmap and tech-stack docs; README update.

**Out of Scope:**
- Any sending of connection requests or messages (auto-connect stays Deferred).
- Playwright for LinkedIn in any form (outreach or discovery); logged-in LinkedIn scraping.
- Automatic discovery during the daily fetch or on any schedule.
- Discovery for companies without a recommended or applied job (including liked-only companies).
- Provider-native LLM web search tools.
- Paid people-data APIs (Proxycurl, Apollo, etc.).
- Emailing contacts or finding their email addresses.
- AI-written personal messages per contact (the Phase 3 template stays).
- Adding, editing, deleting or hiding contacts manually.
- Tracking whether a contact accepted or replied.
- Lifetime cap on contacts per company.

### Technical Considerations
- Playwright is not currently a backend dependency and must not be added for this phase.
- `SERPAPI_API_KEY` is already optional in `Settings`; discovery availability depends on it. Search URLs contain the key and must never be logged.
- `company_networking` currently has no unique constraint; the migration must normalize and dedupe existing rows before adding the index.
- Frontend needs to know whether discovery is available (key set, company eligible) so it can render the disabled states. This could come from existing company/job responses or a small status field.
- LiteLLM "any model incl. local" design must hold: the LLM call only selects from supplied results and needs no tool use.
- The Phase 3 connection-request endpoint keeps the first timestamp on repeat calls; discovery must not change that behavior.
- Follow the standards in `agent-os/standards/` (API, migrations, models, accessibility, error handling, testing). Disabled buttons need accessible explanations, e.g. via `aria-describedby`.

### Open Items and Defaults Chosen

1. **Cooldown and daily cap (default chosen):** The approved answers asked for a 14-day cooldown and a daily cap, with the button bypassing both. Since discovery is now button-only, neither would ever apply. Default: no cooldown and no daily cap; one search per click; keep the per-company last-searched timestamp for display only. No new daily-limit env var. Confirm with the user.
2. **Source of the job's skills (default chosen):** The user asked to reuse the evaluator's extracted skills to avoid an extra LLM call, but the evaluator only stores `skill_score`; it does not save the job's skills anywhere. Default: no extra LLM call. Search terms come from the job title and company name. For skill matching, use the user's `hard_skills` that appear in the job description (plain string match, no tokens), passed to the single selection/ranking LLM call. Alternative for the user to confirm or reject: extend the evaluator's structured output with a `key_skills` list stored on `jobs`. That adds a few output tokens to every evaluation, and existing jobs would have no value.
3. **Eligible jobs (resolved):** the user said "Allow networking after apply." Jobs in both the Recommended and Applied inboxes make a company eligible. The user also asked that the "Find contacts" button appear on the Job Details page.
4. **Button on ineligible pages (default chosen):** Shown disabled with a visible explanation rather than hidden, so the user understands why it is unavailable.
