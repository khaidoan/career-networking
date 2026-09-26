# Verification Report: Phase 2 — Profile & Job Discovery

**Spec:** `2026-09-25-profile-job-discovery`
**Date:** 2026-09-25
**Verifier:** implementation-verifier
**Status:** ⚠️ Passed with Issues

---

## Executive Summary

All 82 tasks in the 11 task groups are marked complete, and spot checks of the code back this up. Every automated check passes: 71 backend tests (none skipped, run against a throwaway PostgreSQL with the repo root mounted), 14 frontend tests, `ruff check`, `ruff format --check`, ESLint, `tsc`, Prettier and `next build`. Both compose files validate, and the jobs image builds with a checksum-verified supercronic that accepts the crontab. The status is "Passed with Issues" for four reasons: six product decisions (D1–D6) still need the user's confirmation, the Ollama-on-Linux setup is documented but not configured in compose, `upsert_boards` keeps the original `discovered_via`, and the 10 MB upload through nginx was not tested live.

---

## 1. Tasks Verification

**Status:** ✅ All Complete

### Completed Tasks
- [x] Task Group 1: Configuration, Dependencies and Shared Vocabularies (1.0–1.7)
- [x] Task Group 2: Migrations and Models (2.0–2.6)
- [x] Task Group 3: Shared LLM Layer, Prompt Resolution and Agents (3.0–3.7)
- [x] Task Group 4: Preferences and Resume API (4.0–4.6)
- [x] Task Group 5: ATS Providers, Directory Sweep and Filters (5.0–5.7)
- [x] Task Group 6: Google Jobs Discovery via SerpApi (6.0–6.4)
- [x] Task Group 7: Fetcher Orchestration, Tracking, Dedup and Ingestion (7.0–7.9)
- [x] Task Group 8: Docker, Compose, Scheduling and nginx (8.0–8.6)
- [x] Task Group 9: Profile Page (9.0–9.9)
- [x] Task Group 10: README and Credits (10.0–10.6)
- [x] Task Group 11: Test Review and Gap Analysis (11.0–11.4)

`tasks.md` has 82 `- [x]` boxes and no unchecked ones.

### Evidence from spot checks
- **Config:** `tests/test_config.py` shows that a missing `CAREER_NETWORKING_LLM_MODEL` fails fast and names the variable, out-of-range threshold and interval values are rejected, and `SERPAPI_API_KEY` is read without the prefix.
- **Migrations:** `0006`–`0008` form a single chain after `0005`. The tests confirm the `ats_boards` UNIQUE and CHECK constraints, the seniority text-to-array conversion and its downgrade, and a downgrade to the Phase 1 schema that restores `skills`.
- **LLM layer (D4):** there is a single allowlist in `backend/jobs/src/llm.py` (`LLM_SAFE_PREFERENCE_FIELDS`, `LLM_SAFE_EEO_KEYS`, `llm_safe_preferences`), and the evaluator builds its context through it. A test confirms that address, gender and the other EEO answers are left out.
- **Fetcher:** `backend/jobs/src/fetcher.py` implements the advisory lock, the precondition check, per-source isolation, URL-normalized dedup, company lookup with a fallback to a name-only company, the threshold-based inbox, `EVALUATION_FAILURE_INBOX` (D1) and pruning. D2 lives in `src/sources/filters.py` and D3 in `src/sources/state.py`.
- **Infrastructure:** both compose files define `fetcher` with `depends_on: jobs: condition: service_healthy` and pass `docker compose config -q`. nginx sets `client_max_body_size 11m;` in `location /api/`. The Dockerfile pins supercronic v0.2.49 with SHA256 checks for amd64 and arm64. On a throwaway image build, `supercronic -version` printed `v0.2.49` and `supercronic -test /app/crontab` reported "crontab is valid".
- **Frontend:** `frontend/components/profile/` contains the form, the sections, `TagInput` and `ResumeCard`. The shadcn primitives `select`, `checkbox`, `textarea` and `alert` were added. `app/(app)/profile/page.tsx` no longer uses the placeholder.
- **README:** it has sections for LLM configuration, the job fetcher, the preferences routes and credits. The stale "arrives in Phase 2" wording is gone.

### Incomplete or Issues
None of the tasks are incomplete. Minor observation: in the code, D1, D2, D3, D5 and D6 each carry an `[UNCONFIRMED: Dx]` comment, but D4 in `src/llm.py` has only a plain comment. Adding the label would make it easier to find.

---

## 2. Documentation Verification

**Status:** ⚠️ Issues Found

### Implementation Documentation
There is no `implementation/` folder for this spec. The implementation is documented in `tasks.md` (all tasks checked), `spec.md`, `planning/requirements.md` and the updated `README.md`.

### Verification Documentation
- `verification/screenshots/`: 8 UI screenshots (empty profile, uploading, merged suggestions, country select, client validation error, saved, delete confirmation, mobile layout)

### Missing Documentation
- Per-task-group implementation reports (`implementation/*.md`) were not written. Phase 1 did not write them either, so this is consistent with the project's workflow.

---

## 3. Roadmap Updates

**Status:** ✅ Updated

### Updated Roadmap Items
In `agent-os/product/roadmap.md`, Phase 2: Profile & Job Discovery, all 14 bullets were changed to `- [x]`:
- [x] Profile page: resume upload (.docx/.pdf), AI extraction, all preference fields, resume deletion
- [x] Job fetcher: Career-Ops ATS integrations (Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR), URL dedup, evaluator per new job, company lookup (DB first, then the agent), inbox_type by score, a 30-minute schedule in compose
- [x] Evaluator agent (LangGraph): four scores plus the extracted fields
- [x] Company lookup agent

### Notes
Before this update, the Phase 2 bullets were plain list items with no checkboxes. They now follow the same `- [x]` format as Phase 1.

---

## 4. Test Suite Results

**Status:** ✅ All Passing

### Test Summary
- **Total Tests:** 85 (71 backend + 14 frontend)
- **Passing:** 85
- **Failing:** 0
- **Errors:** 0
- **Skipped:** 0

Backend (`backend/jobs`, `uv run pytest`, run in `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` with the repo root mounted and `CAREER_NETWORKING_TEST_DATABASE_URL` pointing to a throwaway `postgres:16-alpine` on port 55432): **71 passed in 5.11s**. The throwaway container was stopped afterwards. Per file:
- `test_agents` 4
- `test_auth` 6
- `test_compose` 2
- `test_config` 6
- `test_fetcher` 7
- `test_google_jobs` 3
- `test_health` 2
- `test_llm` 5
- `test_migrations` 5
- `test_preferences_api` 11
- `test_providers` 20

Other checks:
- `ruff check`: all checks passed
- `ruff format --check`: 76 files already formatted

Frontend (`frontend/`): `pnpm test` gave **8 files, 14 tests passed**, of which 7 are Profile tests (6 in `profile-form.test.tsx`, 1 in `tag-input.test.tsx`). `pnpm lint`, `pnpm typecheck`, `pnpm format:check` and `pnpm build` all exited 0.

### Failed Tests
None. All tests pass.

### Notes
- Every LLM, SerpApi and ATS call in the tests is mocked. The "HTTP 404" warnings in the sweep test output come from its mock transport.
- Nothing touched the dev database or any running stack.

---

## 5. Known Issues and Open Items

1. **Unconfirmed decisions D1–D6.** The spec writer made these decisions without the user's confirmation. Each one is kept in a single place, so it is easy to change:
   - D1: a failed evaluation is saved as `ignored` with null scores (`fetcher.py`, `EVALUATION_FAILURE_INBOX`).
   - D2: a 7-day recency window, and undated postings are skipped (`sources/filters.py`).
   - D3: fetcher state is stored as files under `JOB_DATA/_fetcher/` (`sources/state.py`).
   - D4: an LLM allowlist that excludes address, gender and non-work EEO answers (`llm.py`).
   - D5: "Fetch now" is a CLI command only (`docker compose exec fetcher python -m src.fetcher`).
   - D6: supercronic is the scheduler (Dockerfile, crontab, service `command`).

   **The user should review and confirm these.**
2. **Ollama on Linux.** `.env.example` and the README use `http://host.docker.internal:11434`, but neither compose file sets `extra_hosts: ["host.docker.internal:host-gateway"]` on `jobs` or `fetcher`. The README (line 76) explains the workaround, which is to add `extra_hosts` or use the bridge IP. As shipped, an Ollama setup on Linux will fail to resolve the host until the user makes that change. Consider adding `extra_hosts` to both services in both compose files. It is harmless on Docker Desktop.
3. **`upsert_boards` keeps the original `discovered_via`.** On conflict it updates `last_matched_at` and `is_active`, but leaves `discovered_via` as the first source that found the board. This is deliberate and documented in the docstring. It means a board first found by the sweep and later also found via Google Jobs still shows `ats_sweep`. This fits "how it was discovered", but if the user wants the most recent source instead, it needs a decision.
4. **The 10 MB upload through nginx was not tested live.** `client_max_body_size 11m;` is set, and the backend 413 limit is covered by `test_upload_over_ten_megabytes_returns_413_and_keeps_the_old_resume`. No real upload close to 10 MB went through the running nginx stack. The acceptance criterion "A 10 MB resume upload passes through nginx" is met by configuration only. A manual smoke test is recommended.
5. **Not tested live:** a real fetcher run against live ATS APIs, SerpApi and an LLM provider. All of these are covered only by mocked tests.
