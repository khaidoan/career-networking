# Specification: Phase 1 — Foundation (MVP)

## Goal
Lay the base for Career Networking: a Docker Compose monorepo (Next.js frontend, FastAPI `jobs` service, PostgreSQL, nginx) with the full database schema, single-user JWT cookie authentication with login rate limiting, per-service health checks, and a responsive app shell built on a warm, minimalist design system.

## User Stories
- As a self-hosting job seeker, I want to copy `.env.example` to `.env` and run one Docker Compose command so that the whole app starts on `http://localhost:8080` with a ready database.
- As the single user, I want to log in with the credentials from my `.env` and have every other page protected so that my data stays private.
- As a developer, I want a separate hot-reload compose file and health endpoints on every service so that I can iterate quickly and see at a glance whether each container is healthy.

## Specific Requirements

**Monorepo structure and tooling**
- Top-level layout: `frontend/` (Next.js App Router, TypeScript strict), `backend/jobs/` (FastAPI, Python 3.11+), `nginx/` (config), `docker-compose.yml`, `dev-docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`.
- Do not create `backend/users/` in Phase 1.
- Frontend tooling: pnpm, ESLint, Prettier, Vitest with React Testing Library.
- Backend tooling: uv with `backend/jobs/pyproject.toml`, Ruff (lint and format), pytest.
- Backend code lives in `backend/jobs/src/` (to match the agent paths in tech-stack.md), with modules for config, db/session, models, auth, and `api/v1` routers. Alembic lives in `backend/jobs/alembic/`.
- The README covers setup (`cp .env.example .env`), prod and dev compose commands, health URLs, and running tests. No CI pipeline.
- Tests stay minimal and cover only core flows: login success and failure, rate limit returns 429, `/auth/me` requires a cookie, jobs health endpoint, migrations upgrade to head and downgrade to base, and middleware redirecting to `/login` when there is no valid cookie.

**Environment configuration and doc updates**
- `.env` at the repo root is the only runtime env file. Both compose files load it via `env_file: .env`. Never create or reference `.env.local` in code, compose files or docs.
- Commit `.env.example` containing every variable from the tech-stack.md table, with placeholder values, plus: `CAREER_NETWORKING_JWT_SECRET`, `CAREER_NETWORKING_JWT_EXPIRES_MINUTES` (default `10080`), `CAREER_NETWORKING_LOGIN_MAX_ATTEMPTS` (default `5`) and `CAREER_NETWORKING_LOGIN_WINDOW_MINUTES` (default `15`).
- `.gitignore` includes `.env`, `.env.local`, `backend/data/`, `backend/logs/`, plus standard Node/Python ignores. Commit `.gitkeep` files, or create the folders at startup, so bind mounts work on a fresh clone.
- The backend reads settings through one typed settings module (pydantic-settings). It fails fast at startup with a clear error if required variables are missing, e.g. the JWT secret or login credentials.
- **Doc update task:** in `agent-os/product/roadmap.md`, replace the Phase 1 bullet "`.env.local` with all required environment variables" with `.env` wording, and mention the committed `.env.example`. Before finishing, grep the repo for `.env.local` (outside `.gitignore` and this spec folder) and replace any remaining references with `.env`.
- In the same doc pass, remove "social share icons" from the roadmap's Phase 1 top-nav bullet and the "Social Sharing" row from `agent-os/product/tech-stack.md`, so the product docs match the decision to drop sharing.

**Docker Compose, dev compose and nginx**
- `docker-compose.yml` (production-style, built images) defines four services: `postgres` (15+, named volume `postgres_data`, no host port), `jobs` (uvicorn on 8000), `frontend` (Next.js standalone build on 3000), and `nginx` (host `8080` to container `80`). Only nginx publishes a host port.
- The Postgres container gets `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` from the `CAREER_NETWORKING_DATABASE_*` variables through compose interpolation. `CAREER_NETWORKING_DATABASE_URL` points at host `postgres`.
- `jobs` mounts `backend/data/resume` to `/opt/career_networking/resume`, `backend/data/jobs` to `/opt/career_networking/jobs`, and `backend/logs` to `/opt/career_networking/logs`. The matching env vars hold those container paths.
- `jobs` runs `alembic upgrade head` before starting uvicorn, so the schema is always current on boot.
- `dev-docker-compose.yml` is a standalone file (not an override), run with `docker compose -f dev-docker-compose.yml up`:
  - frontend runs `pnpm dev` with `./frontend` bind-mounted and a separate volume for `node_modules`
  - jobs runs `uvicorn --reload` with `./backend/jobs` bind-mounted
  - Postgres may publish 5432 for local tools
- Nginx routes `/api/` to `jobs:8000` (path kept unchanged) and all other paths to `frontend:3000`, so the auth cookie is same-origin. It forwards `Host`, `X-Real-IP`, `X-Forwarded-For` and `X-Forwarded-Proto`, and supports WebSocket upgrade headers for Next.js HMR in dev.
- Plain HTTP only. No TLS configuration.

**Health endpoints and container healthchecks**
- **jobs:** `GET /api/v1/health` is unauthenticated and runs `SELECT 1` against the database.
  - Returns `200 {"status":"ok","database":"ok"}` when the database is reachable.
  - Returns `503 {"status":"degraded","database":"unreachable"}` when it is not.
  - Reachable publicly at `http://localhost:8080/api/v1/health`.
- **frontend:** `GET /health` is a Next.js route handler (`app/health/route.ts`) that returns `200 {"status":"ok"}`. It is excluded from auth middleware. Only the compose healthcheck uses it, on the container's own port 3000, because nginx answers `/health` itself.
- **nginx:** `location = /health` is answered by nginx directly (not proxied), with `200` body `ok` and access logging off. Reachable at `http://localhost:8080/health`.
- **postgres:** no HTTP endpoint. The healthcheck runs `pg_isready -U <db user> -d <db name>`.
- Compose healthcheck commands, using only tools already present in each image:
  - jobs: a Python one-liner that fetches `http://localhost:8000/api/v1/health` with `urllib`
  - frontend: `node -e` with `fetch('http://localhost:3000/health')`
  - nginx: `wget -q --spider http://127.0.0.1/health`
- Healthcheck settings for all services: interval 10s, timeout 5s, retries 5. Start period 10s for postgres and nginx, 30s for jobs and frontend.
- Startup ordering: `jobs` depends on `postgres` being `service_healthy`, and `nginx` depends on both `jobs` and `frontend` being `service_healthy`. Both compose files use the same health definitions.

**Database foundation and migrations**
- SQLAlchemy 2.x declarative models share one base with timestamps:
  - `created_at` and `updated_at` are timezone-aware, NOT NULL, with server default `now()`.
  - `updated_at` is refreshed on update.
- Use one DB engine/session module, with the session provided per request through a FastAPI dependency.
- Write five reversible Alembic migrations, one per table, applied in this order: `create_companies_table`, `create_preferences_table`, `create_jobs_table`, `create_company_networking_table`, `create_prompts_table`.
- Every downgrade fully drops what its upgrade created, including indexes and constraints.
- Add indexes on all foreign keys and on `jobs.inbox_type`.
- Enforce integrity in the database with NOT NULL, UNIQUE, CHECK and foreign keys.
- No seed or data migrations. All tables start empty.

**Table schemas**
- `companies`:
  - `id`, `name` (NOT NULL, indexed), `website_url`, `history`, `linkedin_url`, `logo_url`, `description`
  - `industries` (text array), `growth_stage`, `liked` (bool, default false), `employee_estimate` (text, e.g. "51-200")
- `preferences`: a single row, enforced by `id` with `CHECK (id = 1)`. Columns:
  - `desired_titles`, `skills`, `hard_skills`, `soft_skills` (text arrays)
  - `country`, `currency`, `salary_min`, `salary_max` (integers), `seniority`, `address`
  - `resume_location`, `resume_text`, `gender`, `eeo_answers` (JSONB)
  - All nullable.
- `jobs`, general columns:
  - `id`, `company_id` (FK to companies, NOT NULL, ON DELETE RESTRICT), `title` (NOT NULL), `url` (NOT NULL, UNIQUE, for deduplication)
  - `description`, `source`, `location_city`, `location_state`, `location_country`
  - `work_arrangement`, `job_type_classification`, `seniority_level`, `year_exp` (int), `compensation_range` (text), `visa_sponsorship` (nullable bool)
- `jobs`, scoring and status columns:
  - `overall_score`, `experience_score`, `skill_score`, `industry_exp_score` (nullable integers 0–100)
  - `inbox_type`: NOT NULL, default `recommended`, with a CHECK constraint limiting it to `recommended|applied|ignored|need_attention`
  - `liked` (bool, default false), `discovered_when` (timestamptz), `applied_when` (nullable timestamptz)
- `company_networking`:
  - `id`, `company_id` (FK, NOT NULL, ON DELETE CASCADE, indexed), `first_name`, `last_name`, `linkedin_url`, `title`
  - `connection_request_sent` (bool, default false), `connection_request_sent_at` (nullable timestamptz)
- `prompts`: `id`, `agent_name` (NOT NULL, UNIQUE), `system_prompt` (text, NOT NULL), `is_customized` (bool, default false).

**Authentication API (jobs service)**
- `POST /api/v1/auth/login`:
  - Takes a JSON body with `username` and `password`.
  - Compares both against `CAREER_NETWORKING_USERNAME` and `CAREER_NETWORKING_PASSWORD` in constant time (`hmac.compare_digest`).
  - Returns 200 and sets the cookie on success, or 401 with a generic "Invalid username or password" on failure.
- JWT: HS256, signed with `CAREER_NETWORKING_JWT_SECRET`. Claims are `sub` (the username), `iat` and `exp`, with `exp` set from `CAREER_NETWORKING_JWT_EXPIRES_MINUTES`. No refresh tokens.
- Cookie `cn_session` settings:
  - httpOnly, `SameSite=Lax`, `Path=/`, `Max-Age` equal to the JWT lifetime
  - `Secure` only when the request scheme or `X-Forwarded-Proto` is `https`
- `POST /api/v1/auth/logout` clears the cookie and returns 204.
- `GET /api/v1/auth/me` requires a valid cookie. It returns `{username, first_name, last_name, initials, email}` from env vars, so the frontend container needs no identity variables.
- A shared FastAPI dependency validates the JWT (signature and expiry) and returns 401 when the cookie is missing or invalid. All future protected routers must use it. Health and login are the only unauthenticated endpoints.
- Errors use one consistent JSON shape (`{"detail": ...}`) through centralized exception handling. Secrets and tokens are never logged.

**Login rate limiting**
- Count failed login attempts per client IP. The client IP comes from `X-Real-IP` set by nginx, falling back to the socket address.
- Keep the counts in memory inside the jobs process. This is acceptable for a single-user, single-instance app, and needs no Redis.
- After `CAREER_NETWORKING_LOGIN_MAX_ATTEMPTS` failures within `CAREER_NETWORKING_LOGIN_WINDOW_MINUTES`, return `429` with a friendly message and a `Retry-After` header, without checking the credentials.
- Every login response includes `X-RateLimit-Limit` and `X-RateLimit-Remaining`, per the API standard.
- A successful login resets that IP's counter.
- The login page shows the 429 message ("Too many attempts, try again in N minutes").

**Frontend route protection and login page**
- `middleware.ts` runs on every route except `/login`, `/health`, `/_next/*`, and static assets such as favicon and fonts.
- The middleware verifies the `cn_session` JWT signature and expiry with `jose`, using `CAREER_NETWORKING_JWT_SECRET` (the only auth variable passed to the frontend container).
- Visitors without a valid session are redirected to `/login?next=<path>`. After login, the user returns to `next` only if it is a relative in-app path; otherwise they go to `/inbox/recommended`.
- `/` redirects to `/inbox/recommended`. Visiting `/login` while already authenticated also redirects there.
- The login page is a centered Card with labelled username and password inputs, a submit button with a loading state, and an inline error area announced through `aria-live`.
- Login and logout call the same-origin `/api/v1/auth/*` endpoints with `fetch` and `credentials: "include"`. The JWT is never read by JS or stored in localStorage or sessionStorage.
- Logout, from the avatar menu, calls the logout endpoint and then navigates to `/login`.

**App shell and design system**
- Authenticated pages share one layout: a top bar, a left sidebar and a `main` content region, built with semantic `header`, `nav` and `main` elements.
- Top bar:
  - The app name "Career Networking" links to `/inbox/recommended`.
  - A shadcn Avatar shows initials from `/auth/me`, with a DropdownMenu containing Logout.
  - No share icons or sharing features of any kind.
- Sidebar links go to placeholder pages:
  - Inbox group: Recommended `/inbox/recommended`, Applied `/inbox/applied`, Ignored `/inbox/ignored`, Need Attention `/inbox/need-attention`
  - `/companies`, `/profile` (Profile / Preferences), `/prompts`, `/interview-tips`, `/feedback`
  - The active link is highlighted and gets `aria-current="page"`.
- Each placeholder page shows only an `h1` and a short empty-state line.
- Responsive, mobile-first:
  - Below the `md` breakpoint, the sidebar is hidden behind a hamburger button that opens a shadcn Sheet with focus trapping.
  - Tap targets are at least 44x44px.
- Design system:
  - Use shadcn/ui with only these components: Button, Input, Label, Card, Badge, DropdownMenu, Avatar, Sheet and Separator. Add them to `frontend/components/ui/` and restyle them to the palette.
  - Use Lucide icons.
  - Use Inter through `next/font`.
  - Light mode only.
- Tokens are defined once, as CSS variables in `globals.css` mapped into the Tailwind theme:
  - background `#FAF7F2`, surface `#FFFFFF`, surface-alt `#F3EDE4`, border `#E7DFD3`
  - text `#2B2724`, muted text `#6B625A`
  - accent `#B4532A` (hover `#9A4522`, white text on accent)
  - success `#5F7A61`, warning `#B7791F`, destructive `#B42318`
  - radius `0.75rem`, soft warm shadows, 8px spacing scale
- All text and background pairs must meet WCAG AA contrast, and all interactive elements need visible focus rings in the accent colour.

## Visual Design
No visual assets were provided (`planning/visuals/` is empty). The UI follows the written palette, typography and layout decisions under "App shell and design system".

## Existing Code to Leverage

**None: the repository is greenfield**
- There is no application code, and no external templates or projects were supplied as references.
- `agent-os/product/tech-stack.md` is the source of truth for the environment variable names, Docker volume mappings and the `backend/jobs/src/agents/` layout, and must be followed exactly.
- The modules built here are meant to be reused in later phases and should be written as shared building blocks: the timestamped model base, DB session dependency, settings module, auth dependency, app-shell layout and shadcn/ui primitives.

## Out of Scope
- Social sharing features and share icons of any kind
- The `backend/users/` microservice or any users table
- Job fetching, the cron container and scheduling
- AI agents, LangGraph and LiteLLM setup
- Seed data, including default prompts
- Real page content beyond placeholders (inbox cards, profile form, companies list, etc.)
- Password reset, refresh tokens and multi-user support
- HTTPS/TLS certificates in nginx
- CI pipelines
- Dark mode
