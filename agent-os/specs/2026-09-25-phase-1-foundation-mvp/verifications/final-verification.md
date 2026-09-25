# Verification Report: Phase 1 — Foundation (MVP)

**Spec:** `2026-09-25-phase-1-foundation-mvp`
**Date:** 2026-09-25
**Verifier:** implementation-verifier
**Status:** ✅ Passed

---

## Executive Summary

All 74 tasks in the 10 task groups are complete, and spot checks of the code back this up. All 17 automated tests pass (10 backend and 7 frontend), and lint, format, typecheck, build and `alembic check` are all clean. Live smoke tests of the production stack confirmed healthchecks, routing, login and logout, rate limiting, route protection, empty tables after migration and secret-free logs. The dev stack also came up healthy, and uvicorn reloaded when a file changed. There are only minor deviations from the spec, all of them documented or justified (see Section 1).

---

## 1. Tasks Verification

**Status:** ✅ All Complete

### Completed Tasks
- [x] Task Group 1: Monorepo Scaffolding and Environment Configuration (1.0–1.5)
- [x] Task Group 2: Backend Foundation: Settings, DB Session, App, Errors, Health (2.0–2.8)
- [x] Task Group 3: Database Models and Alembic Migrations (3.0–3.7)
- [x] Task Group 4: Authentication API and Login Rate Limiting (4.0–4.7)
- [x] Task Group 5: Frontend Foundation and Design System (5.0–5.9)
- [x] Task Group 6: Route Protection, Login Page and Logout (6.0–6.6)
- [x] Task Group 7: App Shell and Placeholder Pages (7.0–7.7)
- [x] Task Group 8: Docker Compose, Dev Compose and nginx (8.0–8.6)
- [x] Task Group 9: README and Product Doc Updates (9.0–9.4)
- [x] Task Group 10: Test Review, Gap Analysis and Final Verification (10.0–10.5)

### Evidence from spot checks
- **Layout:** `frontend/`, `backend/jobs/{src,alembic,tests}`, `nginx/conf.d/default.conf`, both compose files, `.env.example`, `.gitignore` and `README.md` all exist. There is no `backend/users/`.
- **Git ignore rules:** `.env` is ignored, and `backend/data/**/.gitkeep` and `backend/logs/.gitkeep` can be tracked (checked with `git check-ignore`). `.env.example` contains all 13 tech-stack variables plus the 4 new ones.
- **Settings fail fast:** running Alembic without the full environment failed with `SettingsError: missing required environment variables: CAREER_NETWORKING_FIRSTNAME, ...`.
- **Schema:** five migrations `0001`–`0005` run in the required order. Upgrade → downgrade base → upgrade works cleanly, and `alembic check` reports "No new upgrade operations detected." Checked against the database:
  - FK indexes exist, plus an index on `jobs.inbox_type`.
  - UNIQUE on `jobs.url` and `prompts.agent_name`.
  - CHECK constraints: `preferences.id = 1`, `inbox_type` limited to the allowed values, scores limited to 0–100.
  - FK `ON DELETE RESTRICT` for jobs and `CASCADE` for company_networking.
  - Timestamptz `created_at`/`updated_at` columns with default `now()`.
- **Auth:**
  - Credentials are compared with `hmac.compare_digest`.
  - The `cn_session` cookie is HttpOnly, SameSite=Lax, Path=/, Max-Age=604800, and `Secure` only over https.
  - Every login response carries `X-RateLimit-*` headers, and 429 responses include `Retry-After`.
  - The JWT is never returned in a response body.
- **Frontend:**
  - Only the nine allowed shadcn/ui components are present.
  - There is no use of `localStorage`, `sessionStorage` or `document.cookie`, and no hard-coded hex colours in components.
  - The login error area uses `aria-live`.
  - There are no `dark:` variants and no share features.

### Minor deviations (accepted, not defects)
1. **`proxy.ts` instead of `middleware.ts`:** Next.js 16 renamed middleware to "proxy". The behaviour is what the spec asks for, and the README documents the rename. The matcher also leaves out `/logout`, a frontend route that expires the cookie when the API cannot. This extra public route only clears a cookie.
2. **Frontend container gets only the JWT secret:** in both compose files the frontend receives just `CAREER_NETWORKING_JWT_SECRET`, interpolated from `.env`, instead of `env_file: .env`. The spec says both compose files load `.env` through `env_file` (task 8.2 lists it for frontend). This choice is deliberate and stricter: it keeps the DB and login secrets out of the frontend container, and `.env` is still the only env file.
3. **Warning colour changed:** it is `#94621A` instead of `#B7791F`, because the original failed WCAG AA. This is explained in `globals.css` and the README, as task 5.4 requires.
4. **Logout requires a session:** `POST /api/v1/auth/logout` needs a valid session and returns 401 without one. The frontend `/logout` route covers that case.

### Incomplete or Issues
None.

---

## 2. Documentation Verification

**Status:** ⚠️ Issues Found (documentation only; not a functional problem)

### Implementation Documentation
- No `implementation/` folder with per-task-group reports exists in the spec folder. The implementation is evidenced by the code, `tasks.md` and the verification screenshots.

### Verification Documentation
- `verification/screenshots/` holds 21 screenshots covering:
  - login, invalid login and rate-limited login
  - the shell at 375, 768 and 1280 px
  - skip-link and nav focus rings, the avatar menu and the mobile sheet
  - dev HMR, and final and prod stack runs
- `README.md` covers setup, JWT secret generation, both compose commands, health URLs, routing, and the test, lint and format commands, with a Docker fallback when uv is not installed. It has no CI section and does not mention sharing.
- Product docs:
  - `roadmap.md` uses `.env` / `.env.example` wording and no longer mentions social share icons.
  - The Social Sharing row has been removed from `tech-stack.md`.
  - The only `.env.local` reference left outside the spec folder is in `.gitignore`.

### Missing Documentation
- Per-task-group implementation reports (`implementation/*.md`) do not exist.

---

## 3. Roadmap Updates

**Status:** ✅ Updated

### Updated Roadmap Items
All Phase 1 deliverables in `agent-os/product/roadmap.md` are now marked `- [x]`:
- [x] Infrastructure & DevOps (monorepo, Docker Compose, `.env`/`.env.example`, data volume mounts, `.gitignore`)
- [x] Database (preferences, companies, jobs, company_networking, prompts tables; Alembic migrations)
- [x] Authentication (login page, protected routes)
- [x] Frontend Skeleton (top nav, left sidebar, design system)

### Notes
The roadmap had no checkboxes before, so the Phase 1 bullets were turned into checked items. Phases 2–6 are unchanged.

---

## 4. Test Suite Results

**Status:** ✅ All Passing

### Test Summary
- **Total Tests:** 17
- **Passing:** 17
- **Failing:** 0
- **Errors:** 0

**Backend (10 tests):** run with `uv run pytest` in `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, against a throwaway `postgres:16-alpine`, so the migration tests ran rather than being skipped.
- test_auth.py: correct login sets the cookie; wrong credentials give 401; 429 after too many failures; `/me` needs a cookie; logout returns 204 and clears the cookie; a successful login resets the counter
- test_health.py: 200 ok; 503 degraded
- test_migrations.py: upgrade to head then downgrade to base; the revision chain is linear and in order

**Frontend (7 tests):** run with `pnpm test` (Vitest).
- health route
- proxy: redirect with no session; authenticated redirects and pass-through
- safe-redirect helper
- sidebar `aria-current`
- login form 429 message
- top bar initials and Logout item

### Quality gates
- `uv run ruff check`: passed. `uv run ruff format --check`: 34 files already formatted.
- `alembic check`: no drift between the models and the migrations.
- `pnpm lint`, `pnpm typecheck`, `pnpm format:check` and `pnpm build`: all clean. The build produced 15 routes plus the proxy.

### Live stack smoke tests
- **Production (`docker compose up --build`):**
  - All 4 services were healthy, and only nginx publishes a port (8080).
  - `/health` returned 200 `ok`. `/api/v1/health` returned 200 `{"status":"ok","database":"ok"}`, and 503 `{"status":"degraded","database":"unreachable"}` while Postgres was stopped. It recovered once Postgres restarted.
  - Signed out: `/` redirected to `/login`, `/companies` redirected to `/login?next=%2Fcompanies`, and `/auth/me` returned 401.
  - Signed in: `/` and `/login?next=//evil.com` both redirected to `/inbox/recommended`, and `/companies` returned 200.
  - Logout returned 204 and expired the cookie. `/auth/me` then returned 401.
  - Five bad logins returned 401; the sixth returned 429 (`Retry-After: 900`, "Too many attempts, try again in 15 minutes."). A spoofed `X-Real-IP` header was overwritten by nginx and stayed blocked.
  - All five tables were empty and `alembic_version` was `0005`.
  - `career_networking.log` and the container logs contained no passwords, JWT secret, DB password or tokens (`eyJ`).
- **Dev (`docker compose -f dev-docker-compose.yml up --build`):**
  - All 4 services were healthy, and the app and API health checks worked through port 8080.
  - Touching a backend file made uvicorn log "WatchFiles detected changes... Reloading".
  - A raw curl check of the Next.js HMR websocket was inconclusive. The implementer's `dev-01-hmr.png` screenshot is the evidence that HMR works.
- Both stacks were torn down with `down -v`. The root-owned `career_networking.log` that the smoke test created was removed, and throwaway containers and networks were deleted.

### Failed Tests
None — all tests passing.

### Notes
- There is one non-blocking warning: Starlette says using `httpx` with `starlette.testclient` is deprecated and suggests `httpx2`. It does not affect results.
- The migration tests are skipped unless `CAREER_NETWORKING_TEST_DATABASE_URL` is set, as designed. They ran in this verification.
