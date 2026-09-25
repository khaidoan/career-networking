# Spec Requirements: Phase 1 — Foundation (MVP)

## Initial Description
Phase 1: Foundation (MVP) from agent-os/product/roadmap.md — monorepo structure (frontend/ and backend/), Docker Compose (frontend, jobs backend, postgres, nginx), .env.local, data volume mounts, PostgreSQL schema via SQLAlchemy + Alembic (preferences, companies, jobs, company_networking, prompts tables), JWT authentication with credentials from env vars (no localStorage) and protected Next.js routes, and a frontend skeleton (top nav, left sidebar, warm modern minimalist design system).

## Requirements Discussion

### First Round Questions

**Q1:** Services and where login lives. tech-stack.md shows both `backend/jobs/` and `backend/users/`, but Phase 1 only lists these Docker services: frontend, jobs, postgres, nginx. I assume Phase 1 includes only the `jobs` FastAPI service, and the login and token-check endpoints live there (for example `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`). The `users` service would wait until later. Is that right, or should Phase 1 also create a `backend/users/` service just for auth?
**Answer:** Accept default (jobs service only hosts auth; no users service in Phase 1).

**Q2:** How login works. Username and password are compared against `CAREER_NETWORKING_USERNAME` / `CAREER_NETWORKING_PASSWORD` using a constant-time comparison. The login token is a JWT stored in an httpOnly, SameSite=Lax cookie, marked Secure when served over HTTPS. We add two new environment variables: `CAREER_NETWORKING_JWT_SECRET` and `CAREER_NETWORKING_JWT_EXPIRES_MINUTES` (default 7 days). There are no refresh tokens. Next.js middleware checks the cookie and sends anyone not logged in to `/login`. The FastAPI side also checks the token on every protected endpoint. Logging out clears the cookie. Is that right? Should we also add basic login rate limiting now, or leave it for later?
**Answer:** Accept default, AND add login rate limiting now (in scope for Phase 1).

**Q3:** Nginx routing and environment files. Nginx is the only public entry point (for example `http://localhost:8080`). It sends `/api/*` to the jobs service and everything else to Next.js, so the cookie is shared by both. Commit a `.env.example` with every variable and placeholder values; the real `.env.local` stays out of git. Or do you want `.env.local` itself committed with safe defaults? Also, do you want a separate dev setup with hot reload (such as `docker-compose.override.yml`) as well as the production-style build?
**Answer:** Do NOT create a .env.local file. Create a `.env` file instead; `.env` is used everywhere in place of `.env.local` (update references accordingly — the product docs mention .env.local). Add BOTH `.env` and `.env.local` to .gitignore. Keep the committed `.env.example` placeholder file (user did not object). Instead of docker-compose.override.yml, the dev setup is a separate file named `dev-docker-compose.yml`, with hot reload enabled for frontend and backend.

**Q4:** Database schema details. Proposed defaults:
- `preferences`: one row only (single user). Add the Phase 2 fields now (gender, EEO answers stored as JSONB). Lists such as desired titles and skills are Postgres arrays or JSONB.
- `jobs`: `id, company_id (FK), title, url (unique, used to spot duplicates), description, source, location_city/state/country, work_arrangement, job_type_classification, seniority_level, year_exp, compensation_range, visa_sponsorship, overall_score, experience_score, skill_score, industry_exp_score, inbox_type, liked, discovered_when, applied_when, created_at, updated_at`.
- `inbox_type`: allowed values `recommended | applied | ignored | need_attention`.
- `company_networking`: `connection_request_sent` is a boolean with a timestamp. Deleting a company also deletes its contacts.
- `prompts`: `agent_name` is unique. The table starts empty.
- All tables: `created_at`/`updated_at` timestamps, and each table gets its own reversible Alembic migration.

Does this match? Any columns you already know you need (e.g. `companies.employee_estimate`, which shows up in Phase 3)?
**Answer:** Accept default schema, and add `employee_estimate` to the `companies` table now.

**Q5:** Frontend skeleton and pages. The left sidebar links to placeholder pages: Inbox (Recommended, Applied, Ignored, Need Attention), Companies, Profile / Preferences, Prompts, Interview Tips, Feedback. The top bar shows the app name (linking to the Recommended inbox), share icons for X, Facebook, LinkedIn and Email sharing the project's GitHub URL, and an avatar with initials from `CAREER_NETWORKING_FIRSTNAME`/`LASTNAME` with a small menu holding Logout. On narrow screens the sidebar collapses into a hamburger menu. Is that right, and what is the GitHub repo URL to share?
**Answer:** Do NOT implement any social sharing functionality and do not show any share icons in the UI (remove them from the top bar; the GitHub share URL question is moot). Rest of the skeleton default accepted.

**Q6:** Design system. Tailwind with custom colour values (cream/off-white backgrounds, warm neutral text, one terracotta or amber accent), Inter font, rounded corners, soft shadows, Lucide icons, WCAG AA contrast, light mode only. Build our own basic components (Button, Input, Card, Badge) or use shadcn/ui? Any existing brand colours or logo?
**Answer:** No brand colours or logo exist — use best judgement for palette, typography, and the shadcn/ui vs. custom components choice. Record the decision and rationale.

**Q7:** Tooling and tests. Frontend: pnpm, ESLint and Prettier, Vitest and React Testing Library. Backend: uv with `pyproject.toml`, Ruff, pytest. No CI in Phase 1. Tests cover only key flows: login succeeds or fails, protected routes redirect, migrations run up and down. Okay, or prefer npm/Poetry, or add CI (Bitbucket Pipelines)?
**Answer:** Accept default (pnpm, ESLint/Prettier, Vitest+RTL; uv, Ruff, pytest; no CI).

**Q8:** Out of scope. Phase 1 does not include: job fetching or the cron container; AI agents or LiteLLM setup; seed data; real content on any page beyond the skeleton; the `users` microservice; password reset; HTTPS certificates (nginx serves plain HTTP on localhost). Anything else to exclude, or bring into scope (e.g. a `/health` endpoint per service, placeholder cron service)?
**Answer:** Accept default out-of-scope list, but ADD a `/health` endpoint for each service (in scope).

### Existing Code to Reference

No similar existing features identified for reference. The repository is greenfield (no application code) and the user provided no external projects or templates to borrow from.

### Follow-up Questions

None asked.

## Visual Assets

### Files Provided:
No visual assets provided. (Bash check of `planning/visuals/` found no image or PDF files.)

### Visual Insights:
Not applicable. The design direction comes from the written decisions below.

## Requirements Summary

### Functional Requirements

**Monorepo and infrastructure**
- Monorepo layout: `frontend/` (Next.js App Router, TypeScript strict) and `backend/jobs/` (FastAPI, Python 3.11+). No `backend/users/` service in Phase 1.
- `docker-compose.yml` (production-style build) with services: `frontend`, `jobs`, `postgres` (15+), `nginx`.
- `dev-docker-compose.yml`: a separate, standalone dev compose file (not an override file) with hot reload for both frontend (Next.js dev server) and backend (uvicorn `--reload`), using source-code bind mounts.
- Nginx is the single public entry point (e.g. `http://localhost:8080`): `/api/*` goes to the `jobs` service and everything else goes to the Next.js frontend, so the auth cookie is same-origin.
- Environment configuration:
  - Use a `.env` file (NOT `.env.local`) everywhere. Compose files, docs and code must reference `.env`.
  - Commit a `.env.example` listing every required variable with placeholder values.
  - Add both `.env` and `.env.local` to `.gitignore`.
  - Update existing product docs that mention `.env.local` (agent-os/product/roadmap.md, and any others) to say `.env`.
  - New variables in addition to those in tech-stack.md: `CAREER_NETWORKING_JWT_SECRET`, `CAREER_NETWORKING_JWT_EXPIRES_MINUTES` (default 10080 = 7 days), plus any login-rate-limit settings.
- Data volume mounts: `backend/data/resume` -> `/opt/career_networking/resume`, `backend/data/jobs` -> `/opt/career_networking/jobs`, `backend/logs` -> `/opt/career_networking/logs` (env vars `CAREER_NETWORKING_RESUME_FOLDER`, `CAREER_NETWORKING_JOB_DATA`, `CAREER_NETWORKING_LOG_FOLDER`). Add the data and log folders to `.gitignore`.
- `/health` endpoint for each service:
  - jobs: e.g. `GET /api/v1/health`, which ideally includes a DB connectivity check
  - frontend: e.g. `/api/health` route handler or equivalent
  - nginx: a simple health location
  - postgres: health via a compose `healthcheck` (`pg_isready`)
  - Compose healthchecks should use these.

**Database (SQLAlchemy 2.x + Alembic)**
- All tables have `created_at` / `updated_at` timestamps. Each table gets its own reversible Alembic migration (upgrade and downgrade).
- `preferences`: single row (single user). Fields: desired titles, country, currency, salary (range), seniority, address, skills, resume location, resume text, hard_skills, soft_skills, plus the Phase 2 fields gender and EEO answers (JSONB). List-type fields stored as Postgres arrays or JSONB.
- `companies`: id, name, website_url, history, linkedin_url, logo_url, description, industries, growth_stage, liked, **employee_estimate** (added now per user).
- `jobs`: id, company_id (FK -> companies), title, url (unique; used for deduplication), description, source, location_city, location_state, location_country, work_arrangement, job_type_classification, seniority_level, year_exp, compensation_range, visa_sponsorship, overall_score, experience_score, skill_score, industry_exp_score, inbox_type, liked, discovered_when, applied_when, created_at, updated_at.
- `inbox_type` allowed values: `recommended`, `applied`, `ignored`, `need_attention`.
- `company_networking`: company_id (FK, cascade delete when the company is deleted), first_name, last_name, linkedin_url, title, connection_request_sent (boolean) plus a timestamp for when it was sent.
- `prompts`: agent_name (unique), system_prompt, is_customized. The table starts empty (no seed data).

**Authentication**
- Login page at `/login`. Credentials are checked against `CAREER_NETWORKING_USERNAME` / `CAREER_NETWORKING_PASSWORD` using constant-time comparison. There is no users table.
- Jobs service endpoints: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
- JWT signed with `CAREER_NETWORKING_JWT_SECRET`, expiry from `CAREER_NETWORKING_JWT_EXPIRES_MINUTES` (default 7 days), no refresh tokens.
- JWT stored in an httpOnly, SameSite=Lax cookie, marked Secure when served over HTTPS. The JWT is never stored in localStorage.
- Logout clears the cookie.
- Next.js middleware protects all routes except `/login` (and health/static assets), redirecting unauthenticated users to `/login`. FastAPI validates the JWT on every protected endpoint.
- **Login rate limiting is in scope for Phase 1**: throttle repeated failed login attempts (e.g. per client IP) and return HTTP 429 when the limit is exceeded.

**Frontend skeleton**
- Top navigation bar:
  - app name, linking to the Recommended inbox
  - user avatar with initials derived from `CAREER_NETWORKING_FIRSTNAME` / `CAREER_NETWORKING_LASTNAME`, with a small dropdown menu containing Logout
  - **no social share icons and no sharing functionality**
- Left sidebar linking to placeholder pages: Inbox — Recommended, Applied, Ignored, Need Attention; Companies; Profile / Preferences; Prompts; Interview Tips; Feedback.
- Responsive: on narrow screens the sidebar collapses behind a hamburger menu.
- Placeholder pages contain only a page heading or empty state (no real content).

**Design system (decided by agent per user's delegation; no brand colours or logo exist)**
- **Component approach: shadcn/ui.** Rationale:
  - It is Tailwind-native, so it matches the chosen styling stack with no extra styling layer.
  - Components are copied into the repo (`frontend/components/ui/`) rather than installed as a dependency, so they can be fully restyled to the warm palette.
  - It is built on Radix primitives, which provide keyboard navigation, focus management and ARIA out of the box. This fits the accessibility standards for the avatar dropdown and the mobile sidebar sheet.
  - It uses Lucide icons by default, matching tech-stack.md.
  - Only the components needed for Phase 1 are added: Button, Input, Label, Card, Badge, DropdownMenu, Avatar, Sheet (mobile sidebar), Separator.
- **Palette** (defined as CSS variables / Tailwind theme tokens; light mode only):
  - Background: warm cream `#FAF7F2`
  - Surface / cards: `#FFFFFF`, with an alternate warm sand surface `#F3EDE4` (supports alternating card backgrounds in Phase 3)
  - Border: `#E7DFD3`
  - Primary text: warm charcoal `#2B2724`; muted text: `#6B625A`
  - Accent / primary: terracotta `#B4532A` (hover `#9A4522`), with white text on accent
  - Supporting: sage success `#5F7A61`, amber warning `#B7791F`, brick destructive `#B42318`
  - All text/background pairs must meet WCAG AA contrast; the implementer verifies the final values.
- **Typography**: Inter (via `next/font`) for UI text. Rationale: highly legible, neutral, modern, and gets its warmth from the palette. Optional: a soft serif (Fraunces) for the app wordmark only; this is a judgement call left to the implementer and is not required.
- **Shape and elevation**: base radius about 0.75rem (rounded-xl cards), soft low-opacity warm shadows, generous whitespace, 8px spacing scale.
- **Icons**: Lucide React.
- Design tokens are documented in one place (Tailwind config / globals.css) per the CSS standards.

### Reusability Opportunities
- No existing code in the repo (greenfield) and no external references provided.
- Components built in Phase 1 are the foundation for later phases:
  - app shell (top bar and sidebar)
  - shadcn/ui primitives
  - auth dependency / middleware
  - SQLAlchemy base model with timestamps
  - DB session handling
  - settings/config module that reads `.env`

### Scope Boundaries
**In Scope:**
- Monorepo structure (`frontend/`, `backend/jobs/`)
- `docker-compose.yml` and `dev-docker-compose.yml` (hot reload), nginx reverse proxy
- `.env.example` (committed); `.env` used everywhere; `.env` and `.env.local` gitignored; doc references to `.env.local` updated to `.env`
- Data/log volume mounts and their `.gitignore` entries
- SQLAlchemy models and reversible Alembic migrations for preferences, companies (including employee_estimate), jobs, company_networking, prompts
- JWT cookie auth in the jobs service, Next.js middleware route protection, login page, logout
- Login rate limiting
- `/health` endpoint for each service, plus compose healthchecks
- Frontend app shell: top bar (app name, avatar with Logout), responsive left sidebar, placeholder pages
- Design system tokens and shadcn/ui base components
- Tooling: pnpm, ESLint, Prettier, Vitest + React Testing Library; uv (`pyproject.toml`), Ruff, pytest
- Minimal tests for key flows: login success/failure, rate limit, protected route redirect, migrations upgrade/downgrade

**Out of Scope:**
- Social sharing functionality and share icons (removed entirely)
- `backend/users/` microservice
- Job fetching, the cron container, and scheduling
- AI agents, LangGraph and LiteLLM setup
- Seed data (including default prompts)
- Real page content beyond the skeleton/placeholders
- Password reset
- HTTPS/TLS certificates (plain HTTP on localhost; the user may add TLS in front)
- CI pipelines
- Dark mode
- Refresh tokens

### Technical Considerations
- Frontend: Next.js App Router, TypeScript strict, Tailwind CSS, shadcn/ui, Lucide React, pnpm.
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.x (declarative), Alembic, uv, Ruff, pytest.
- Database: PostgreSQL 15+.
- API follows the standards: versioned under `/api/v1`, plural resource nouns, correct status codes (401 unauthenticated, 429 rate limited). Rate-limit headers should be included on the login endpoint, per the API standard.
- Migrations follow the standards: reversible, small and focused (one per table), descriptively named.
- Single-user system: no users table. Credentials and identity (first/last name, email) come from environment variables.
- The frontend needs the user's initials. They can come from `GET /api/v1/auth/me` (backend reads the FIRSTNAME/LASTNAME env vars), so the frontend container doesn't need those variables.
- Testing follows the testing standard: minimal, core-flow-only tests, with external dependencies mocked where appropriate.
