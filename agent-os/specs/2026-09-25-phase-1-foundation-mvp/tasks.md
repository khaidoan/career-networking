# Task Breakdown: Phase 1 — Foundation (MVP)

## Overview
Total Task Groups: 10
Total Tasks: 64 sub-tasks (plus 10 parent tasks)

Greenfield monorepo: Next.js frontend, FastAPI `jobs` service, PostgreSQL, nginx. Everything runs through Docker Compose on `http://localhost:8080`. No visual assets exist (`planning/visuals/` is empty), so the UI follows the written palette and layout decisions in `spec.md` under "App shell and design system".

Guiding rules for every group:
- `.env` at the repo root is the only runtime env file. Never create or reference `.env.local` anywhere except `.gitignore`.
- No social sharing features or share icons anywhere.
- Do not create `backend/users/`.
- Tests are minimal and cover only core flows (per `agent-os/standards/testing/test-writing.md`). Each group runs only its own tests.
- Build shared building blocks meant for reuse in later phases: settings module, timestamped model base, DB session dependency, auth dependency, app-shell layout, and shadcn/ui primitives.

## Task List

### Repository & Configuration

#### Task Group 1: Monorepo Scaffolding and Environment Configuration
**Dependencies:** None

- [x] 1.0 Complete repo scaffolding and env configuration
  - [x] 1.1 Create the top-level layout
    - `frontend/`, `backend/jobs/`, `nginx/`, `docker-compose.yml` (stub), `dev-docker-compose.yml` (stub), `.env.example`, `.gitignore`, `README.md` (stub)
    - Do NOT create `backend/users/`
  - [x] 1.2 Create the bind-mount folders so they work on a fresh clone
    - `backend/data/resume/`, `backend/data/jobs/`, `backend/logs/`, each with a committed `.gitkeep`
    - Make sure the `.gitignore` rules still allow the `.gitkeep` files, e.g. `backend/data/**` plus `!backend/data/**/.gitkeep`, or ignore the contents instead of the directories
  - [x] 1.3 Write `.gitignore`
    - `.env`, `.env.local`, `backend/data/`, `backend/logs/` (contents; keep `.gitkeep`)
    - Node: `node_modules/`, `.next/`, `out/`, `coverage/`, `*.tsbuildinfo`, `next-env.d.ts`
    - Python: `__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`
    - OS/editor noise: `.DS_Store`, `*.swp`
  - [x] 1.4 Write `.env.example` with placeholder values for every variable
    - Every variable from the `agent-os/product/tech-stack.md` Environment Variables table: `CAREER_NETWORKING_DATABASE_URL` (host `postgres`), `_DATABASE_DBNAME`, `_DATABASE_USERNAME`, `_DATABASE_PASSWORD`, `_USERNAME`, `_PASSWORD`, `_FIRSTNAME`, `_LASTNAME`, `_EMAIL`, `_LONG_COMMON_JOBBOARDS_PASSWORD`, `_RESUME_FOLDER=/opt/career_networking/resume`, `_JOB_DATA=/opt/career_networking/jobs`, `_LOG_FOLDER=/opt/career_networking/logs`
    - New variables: `CAREER_NETWORKING_JWT_SECRET` (placeholder plus a comment on how to generate one), `CAREER_NETWORKING_JWT_EXPIRES_MINUTES=10080`, `CAREER_NETWORKING_LOGIN_MAX_ATTEMPTS=5`, `CAREER_NETWORKING_LOGIN_WINDOW_MINUTES=15`
    - Short grouping comments; no real secrets
  - [x] 1.5 Verify scaffolding
    - `git status` shows `.gitkeep` files as tracked candidates, and a local `.env` is ignored
    - `.env.example` contains every variable listed above (compare by grepping against the tech-stack table)

**Acceptance Criteria:**
- The layout matches `spec.md` "Monorepo structure and tooling"; no `backend/users/`
- `.env` and `.env.local` are ignored; `.gitkeep` files are trackable
- `.env.example` lists all 13 tech-stack variables plus the 4 new ones, with placeholder values

### Backend (jobs service)

#### Task Group 2: Backend Foundation (Settings, DB Session, App, Errors, Health)
**Dependencies:** Task Group 1

- [x] 2.0 Complete the jobs service foundation
  - [x] 2.1 Initialise the Python project with uv
    - `backend/jobs/pyproject.toml`: Python >= 3.11; runtime deps `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `alembic`, `psycopg` (v3, binary), `pydantic-settings`, `pyjwt` (or `python-jose`, choose one)
    - Dev deps: `pytest`, `httpx`, `ruff`
    - Ruff config for lint and format in `pyproject.toml`; pytest config (`testpaths = ["tests"]`, `pythonpath = ["src"]` or equivalent)
    - Commit `uv.lock`
  - [x] 2.2 Write 2 focused tests for the health endpoint (`backend/jobs/tests/test_health.py`)
    - `GET /api/v1/health` returns `200 {"status":"ok","database":"ok"}` when `SELECT 1` succeeds
    - Returns `503 {"status":"degraded","database":"unreachable"}` when the DB dependency raises (override the session dependency with a failing stub; no real DB needed)
  - [x] 2.3 Create the typed settings module (`backend/jobs/src/config.py`)
    - pydantic-settings `Settings` class covering every `CAREER_NETWORKING_*` variable the jobs service uses, with defaults only for `JWT_EXPIRES_MINUTES` (10080), `LOGIN_MAX_ATTEMPTS` (5) and `LOGIN_WINDOW_MINUTES` (15)
    - Required with no default: database URL, JWT secret, login username/password
    - Fail fast at startup with a clear error naming the missing variables
    - Cached accessor (e.g. `get_settings()` with `lru_cache`) so tests can override it
  - [x] 2.4 Create the DB engine/session module (`backend/jobs/src/db/session.py`)
    - One SQLAlchemy 2.x engine built from `CAREER_NETWORKING_DATABASE_URL` (`pool_pre_ping=True`)
    - `get_db()` FastAPI dependency that yields a session per request and always closes it
  - [x] 2.5 Create the FastAPI app factory (`backend/jobs/src/main.py`)
    - `create_app()` that mounts `api/v1` routers under `/api/v1`
    - Centralised exception handlers producing `{"detail": ...}` for `HTTPException`, validation errors (422) and unhandled errors (500 with a generic message, full error logged server-side)
    - Python `logging` configured to write `career_networking.log` in `CAREER_NETWORKING_LOG_FOLDER` plus stdout; never log secrets, passwords or tokens
  - [x] 2.6 Implement the health router (`backend/jobs/src/api/v1/health.py`)
    - `GET /api/v1/health`, unauthenticated, runs `SELECT 1` through the session dependency
    - Returns 200 or 503 with the exact bodies from the spec
  - [x] 2.7 Create the Dockerfile for jobs (`backend/jobs/Dockerfile`)
    - Python 3.11+ slim base, uv installs deps from the lockfile, copies `src/` and `alembic/`
    - Entrypoint or command runs `alembic upgrade head` and then `uvicorn` on `0.0.0.0:8000`
    - Add `.dockerignore` (`.venv`, caches, tests are optional)
  - [x] 2.8 Ensure foundation tests pass
    - Run ONLY the tests from 2.2 (`uv run pytest tests/test_health.py`)
    - `uv run ruff check` and `uv run ruff format --check` are clean

**Acceptance Criteria:**
- The 2 health tests pass
- The app refuses to start with a clear message when the JWT secret or login credentials are missing
- All errors use the `{"detail": ...}` shape
- Settings, session dependency and app factory are reusable building blocks under `backend/jobs/src/`

#### Task Group 3: Database Models and Alembic Migrations
**Dependencies:** Task Group 2

- [x] 3.0 Complete the database layer
  - [x] 3.1 Write 1-2 focused migration tests (`backend/jobs/tests/test_migrations.py`)
    - `alembic upgrade head` creates all five tables, then `alembic downgrade base` leaves no application tables (only `alembic_version` or nothing)
    - Optional second test: the five revisions form a single linear chain in the required order
    - These need a real PostgreSQL. Read the URL from a test env var (e.g. `CAREER_NETWORKING_TEST_DATABASE_URL`, pointing at the dev-compose Postgres on `localhost:5432`), and skip with a clear reason when it is unset
  - [x] 3.2 Create the shared declarative base (`backend/jobs/src/models/base.py`)
    - SQLAlchemy 2.x `DeclarativeBase` with a naming convention for constraints and indexes (so downgrades can drop by name)
    - Timestamp mixin: `created_at` and `updated_at` as `TIMESTAMP(timezone=True)`, NOT NULL, `server_default=func.now()`; `updated_at` also refreshes on update (`onupdate=func.now()`)
  - [x] 3.3 Create the models (one module per table under `backend/jobs/src/models/`, exported from `models/__init__.py`)
    - `Company`: `id`, `name` (NOT NULL, indexed), `website_url`, `history`, `linkedin_url`, `logo_url`, `description`, `industries` (text[]), `growth_stage`, `liked` (bool, default false, NOT NULL), `employee_estimate` (text)
    - `Preferences`: `id` with `CHECK (id = 1)`; `desired_titles`, `skills`, `hard_skills`, `soft_skills` (text[]); `country`, `currency`, `salary_min`, `salary_max` (int), `seniority`, `address`, `resume_location`, `resume_text`, `gender`, `eeo_answers` (JSONB); all nullable
    - `Job`: general columns, `company_id` FK (NOT NULL, `ON DELETE RESTRICT`), `title` NOT NULL, `url` NOT NULL UNIQUE; scores as nullable ints with `CHECK` 0-100; `inbox_type` NOT NULL, default `recommended`, with a `CHECK` limited to `recommended|applied|ignored|need_attention`; `liked` default false; `discovered_when` timestamptz; `applied_when` nullable timestamptz
    - `CompanyNetworking`: `company_id` FK (NOT NULL, `ON DELETE CASCADE`, indexed), `first_name`, `last_name`, `linkedin_url`, `title`, `connection_request_sent` (bool, default false), `connection_request_sent_at` (nullable timestamptz)
    - `Prompt`: `agent_name` (NOT NULL, UNIQUE), `system_prompt` (text, NOT NULL), `is_customized` (bool, default false)
    - Relationships: `Company.jobs`, `Company.networking_contacts` (cascade delete-orphan to match the DB cascade)
  - [x] 3.4 Set up Alembic (`backend/jobs/alembic/`, `backend/jobs/alembic.ini`)
    - `env.py` reads the URL from the settings module (never hard-coded) and sets `target_metadata` to the shared base
  - [x] 3.5 Write five reversible migrations, one per table, in this order
    - `create_companies_table` (including the index on `name`)
    - `create_preferences_table` (including the `CHECK (id = 1)`)
    - `create_jobs_table` (FK index on `company_id`, index on `inbox_type`, UNIQUE on `url`, CHECK constraints)
    - `create_company_networking_table` (FK index on `company_id`, CASCADE)
    - `create_prompts_table` (UNIQUE on `agent_name`)
    - Every `downgrade()` drops everything its `upgrade()` created, including indexes and constraints
    - No seed or data migrations
  - [x] 3.6 Verify that the models and migrations agree
    - Against a fresh DB: `alembic upgrade head`, then `alembic check` (or autogenerate a revision and confirm it is empty)
  - [x] 3.7 Ensure database layer tests pass
    - Run ONLY the tests from 3.1 against the dev Postgres
    - Manually confirm `alembic upgrade head` -> `downgrade base` -> `upgrade head` works cleanly

**Acceptance Criteria:**
- The migration tests from 3.1 pass
- Five migrations with the exact names and order from the spec; each is fully reversible
- Indexes exist on all FKs and `jobs.inbox_type`; integrity is enforced in the DB (NOT NULL, UNIQUE, CHECK, FK)
- Models match the migrations (no autogenerate drift); all tables start empty

#### Task Group 4: Authentication API and Login Rate Limiting
**Dependencies:** Task Group 2 (can run in parallel with Task Group 3)

- [x] 4.0 Complete the auth API
  - [x] 4.1 Write 4-5 focused auth tests (`backend/jobs/tests/test_auth.py`)
    - Login with the correct credentials returns 200, sets an httpOnly `cn_session` cookie, and includes `X-RateLimit-Limit` / `X-RateLimit-Remaining`
    - Login with wrong credentials returns 401 with `{"detail": "Invalid username or password"}`
    - After `LOGIN_MAX_ATTEMPTS` failures from the same IP, the next attempt returns 429 with `Retry-After`, even with correct credentials
    - `GET /api/v1/auth/me` returns 401 without a cookie, and returns `{username, first_name, last_name, initials, email}` with a valid cookie
    - Use test settings via dependency override; reset the in-memory limiter between tests; no DB needed
  - [x] 4.2 Implement JWT helpers (`backend/jobs/src/auth/tokens.py`)
    - Create: HS256, claims `sub` (username), `iat`, `exp` from `JWT_EXPIRES_MINUTES`
    - Decode: verifies signature and expiry; raises a typed error on failure
  - [x] 4.3 Implement the shared auth dependency (`backend/jobs/src/auth/dependencies.py`)
    - `get_current_user` reads the `cn_session` cookie, validates it, and returns 401 `{"detail": ...}` when it is missing or invalid
    - Document in a docstring that all future protected routers must depend on it
  - [x] 4.4 Implement the in-memory login rate limiter (`backend/jobs/src/auth/rate_limit.py`)
    - Per client IP: `X-Real-IP` header, falling back to the socket address
    - Sliding or fixed window of `LOGIN_WINDOW_MINUTES`, limit `LOGIN_MAX_ATTEMPTS`; counts failures only
    - Exposes: check (blocked? seconds until retry), record a failure, reset on success, and remaining attempts
    - Thread-safe (a lock) and swappable in tests
  - [x] 4.5 Implement the auth router (`backend/jobs/src/api/v1/auth.py`)
    - `POST /api/v1/auth/login`: Pydantic body `{username, password}`; check the limiter first (429 with a friendly message, `Retry-After` and the rate-limit headers, without checking credentials); compare both fields with `hmac.compare_digest`; on success set the cookie and reset the counter; on failure record it and return 401 with the generic message
    - Cookie `cn_session`: httpOnly, `SameSite=Lax`, `Path=/`, `Max-Age` equal to the JWT lifetime; `Secure` only when the request scheme or `X-Forwarded-Proto` is `https`
    - Every login response (200/401/429) carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`
    - `POST /api/v1/auth/logout`: clears the cookie (same name, path and attributes) and returns 204
    - `GET /api/v1/auth/me`: protected by `get_current_user`; returns identity from the env vars, with `initials` built from the first and last names
  - [x] 4.6 Make sure no secrets are logged
    - Log login success or failure with IP only; never the password, token or JWT secret
  - [x] 4.7 Ensure auth tests pass
    - Run ONLY the tests from 4.1
    - Ruff lint and format are clean

**Acceptance Criteria:**
- The 4-5 auth tests pass
- Health and login are the only unauthenticated endpoints; `/auth/me` and future routers use the shared dependency
- 429 responses include `Retry-After`; all login responses include the rate-limit headers
- The cookie attributes match the spec exactly; the JWT is never returned in a response body

### Frontend

#### Task Group 5: Frontend Foundation and Design System
**Dependencies:** Task Group 1 (can run in parallel with Task Groups 2-4)

- [x] 5.0 Complete the frontend foundation
  - [x] 5.1 Scaffold Next.js in `frontend/` with pnpm
    - App Router, TypeScript `strict: true`, Tailwind CSS, `src/`-less layout under `frontend/app/` (keep `components/ui/` at `frontend/components/ui/` as the spec requires)
    - `output: "standalone"` in `next.config` for the production image
    - ESLint (Next config) and Prettier (with the Tailwind plugin), and `lint`, `format`, `test`, `typecheck` scripts
    - Vitest + React Testing Library + jsdom set up (`vitest.config.ts`, setup file with `@testing-library/jest-dom`)
  - [x] 5.2 Write 1 focused test for the health route (`frontend/app/health/route.test.ts`)
    - `GET` returns 200 with `{"status":"ok"}`
  - [x] 5.3 Define design tokens once in `frontend/app/globals.css`, mapped into the Tailwind theme
    - background `#FAF7F2`, surface `#FFFFFF`, surface-alt `#F3EDE4`, border `#E7DFD3`, text `#2B2724`, muted text `#6B625A`, accent `#B4532A` (hover `#9A4522`, foreground white), success `#5F7A61`, warning `#B7791F`, destructive `#B42318`
    - Radius `0.75rem`, soft warm shadow tokens, 8px spacing scale
    - Global accent-coloured `:focus-visible` ring; light mode only (no `dark:` variants or theme toggle)
  - [x] 5.4 Check colour contrast
    - Verify every text/background pair used (text, muted text, white on accent, white on hover accent, destructive text on background/surface) meets WCAG AA (4.5:1 for normal text); adjust the value and note it in `globals.css` if any pair fails
  - [x] 5.5 Add Inter through `next/font` in the root layout, and Lucide React
  - [x] 5.6 Add only these shadcn/ui components to `frontend/components/ui/`, restyled to the tokens
    - Button, Input, Label, Card, Badge, DropdownMenu, Avatar, Sheet, Separator
    - Default Button and Input sizes meet the 44x44px tap-target minimum on touch sizes
  - [x] 5.7 Implement the frontend health route (`frontend/app/health/route.ts`)
    - `GET` returns 200 `{"status":"ok"}`; no auth
  - [x] 5.8 Create the Dockerfile for the frontend (`frontend/Dockerfile`)
    - Multi-stage: pnpm install with the lockfile, `next build`, runtime stage runs the standalone `server.js` on port 3000 (`HOSTNAME=0.0.0.0`)
    - Add `.dockerignore` (`node_modules`, `.next`)
  - [x] 5.9 Ensure frontend foundation tests pass
    - Run ONLY the test from 5.2
    - `pnpm lint`, `pnpm typecheck` and `pnpm build` succeed

**Acceptance Criteria:**
- The health route test passes; lint, typecheck and build are clean
- Tokens are defined once and used through Tailwind classes (no hard-coded hex values in components)
- Only the nine listed shadcn/ui components exist; all pairs meet WCAG AA; focus rings are visible in the accent colour

#### Task Group 6: Route Protection, Login Page and Logout
**Dependencies:** Task Groups 4 and 5

- [x] 6.0 Complete frontend authentication
  - [x] 6.1 Write 3-4 focused tests
    - Middleware: a request to a protected path with no cookie (or an invalid/expired JWT) redirects to `/login?next=<path>`
    - Middleware: a valid JWT on `/login` or `/` redirects to `/inbox/recommended`; a valid JWT on a protected path passes through
    - Login page: a 429 response shows "Too many attempts, try again in N minutes" in the `aria-live` region (mock `fetch`)
    - Optional: the `next` helper only accepts relative in-app paths (rejects `//evil.com`, `https://...`)
  - [x] 6.2 Implement `frontend/middleware.ts`
    - `matcher` excludes `/login`, `/health`, `/_next/*`, favicon, fonts and other static assets (still handle `/login` for the already-authenticated redirect, either by including it in the matcher with a branch or with a separate check)
    - Verify the `cn_session` JWT signature and expiry with `jose` (HS256) using `CAREER_NETWORKING_JWT_SECRET`
    - No session: redirect to `/login?next=<path+search>`. `/` redirects to `/inbox/recommended`
  - [x] 6.3 Implement a safe-redirect helper
    - Accept `next` only if it starts with a single `/` and is not protocol-relative; otherwise use `/inbox/recommended`
  - [x] 6.4 Build the login page (`frontend/app/login/page.tsx`)
    - Centred Card with labelled username and password inputs (`Label` + `Input`, correct `autocomplete` values), a submit Button with a loading/disabled state
    - Inline error area with `aria-live="polite"`: the generic 401 message, the 429 message (N from `Retry-After`, rounded up to minutes), and a network-error fallback
    - `fetch("/api/v1/auth/login", { method: "POST", credentials: "include" })`; on success, navigate to the safe `next` target
    - The JWT is never read by JS or stored in localStorage/sessionStorage
  - [x] 6.5 Implement the logout action
    - Calls `POST /api/v1/auth/logout` with `credentials: "include"`, then navigates to `/login` (used by the avatar menu in Task Group 7)
  - [x] 6.6 Ensure frontend auth tests pass
    - Run ONLY the tests from 6.1

**Acceptance Criteria:**
- The 3-4 tests pass
- Every route except `/login`, `/health` and static assets requires a valid session
- Open redirects are impossible through `next`
- `CAREER_NETWORKING_JWT_SECRET` is the only auth variable the frontend reads

#### Task Group 7: App Shell and Placeholder Pages
**Dependencies:** Task Groups 5 and 6

- [x] 7.0 Complete the app shell
  - [x] 7.1 Write 2 focused tests
    - The sidebar marks the current route's link with `aria-current="page"` (mock `usePathname`)
    - The top bar renders initials from a mocked `/auth/me` response, and the avatar menu contains a Logout item
  - [x] 7.2 Create the authenticated layout (e.g. `frontend/app/(app)/layout.tsx` route group)
    - Semantic `header`, `nav`, `main`; a skip-to-content link is recommended
    - All placeholder pages live under this group; `/login` and `/health` do not
  - [x] 7.3 Build the top bar component
    - "Career Networking" links to `/inbox/recommended`
    - Avatar with initials fetched from `/api/v1/auth/me` (`credentials: "include"`), with a fallback state while loading or on error
    - DropdownMenu with a single Logout item wired to the action from 6.5
    - No share icons or sharing features of any kind
  - [x] 7.4 Build the sidebar component
    - Inbox group: Recommended, Applied, Ignored, Need Attention (`/inbox/recommended`, `/inbox/applied`, `/inbox/ignored`, `/inbox/need-attention`)
    - Then Companies `/companies`, Profile / Preferences `/profile`, Prompts `/prompts`, Interview Tips `/interview-tips`, Feedback `/feedback`
    - Lucide icons, active link highlighted plus `aria-current="page"`, Separator between groups
  - [x] 7.5 Make it responsive (mobile-first)
    - Below `md`: sidebar hidden, a hamburger Button (with an accessible label) in the top bar opens a shadcn Sheet containing the same nav; the Sheet traps focus and closes on navigation
    - At `md` and above: persistent sidebar
    - All tap targets at least 44x44px
  - [x] 7.6 Create the nine placeholder pages
    - Each shows only an `h1` and one short empty-state line (muted text)
  - [x] 7.7 Ensure app shell tests pass
    - Run ONLY the tests from 7.1
    - Manually check at 375px, 768px and 1280px widths, and with keyboard-only navigation (menu, sheet, focus rings)

**Acceptance Criteria:**
- The 2 tests pass
- All nine routes render inside the shared shell; `/` lands on Recommended
- The mobile Sheet works with keyboard and focus trapping; no share icons anywhere
- The layout and components are reusable for later phases

### Infrastructure

#### Task Group 8: Docker Compose, Dev Compose and nginx
**Dependencies:** Task Groups 2, 3, 5 (Dockerfiles, migrations and health routes exist)

- [x] 8.0 Complete container wiring
  - [x] 8.1 Write the nginx config (`nginx/nginx.conf` or `nginx/conf.d/default.conf`)
    - `listen 80`; `location = /health { access_log off; return 200 "ok"; }` (text/plain)
    - `location /api/` -> `proxy_pass http://jobs:8000;` (no trailing slash, so the path is kept)
    - `location /` -> `proxy_pass http://frontend:3000;`
    - Forward `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`; WebSocket upgrade headers (`Upgrade`, `Connection` via a `map`) for Next.js HMR
    - Plain HTTP only; no TLS
  - [x] 8.2 Write `docker-compose.yml` (production-style, built images)
    - `postgres` (15+ image, named volume `postgres_data`, no host port; `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` interpolated from the `CAREER_NETWORKING_DATABASE_*` variables)
    - `jobs` (build `backend/jobs`, `env_file: .env`, bind mounts `./backend/data/resume:/opt/career_networking/resume`, `./backend/data/jobs:/opt/career_networking/jobs`, `./backend/logs:/opt/career_networking/logs`; runs migrations then uvicorn on 8000)
    - `frontend` (build `frontend`, `env_file: .env`, standalone server on 3000)
    - `nginx` (official image, config mounted read-only, `8080:80`), the only service with a host port
  - [x] 8.3 Add healthchecks and startup ordering (identical in both compose files)
    - postgres: `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}`
    - jobs: `python -c` with `urllib.request.urlopen('http://localhost:8000/api/v1/health')`
    - frontend: `node -e` with `fetch('http://localhost:3000/health')` exiting non-zero on failure
    - nginx: `wget -q --spider http://127.0.0.1/health`
    - All: interval 10s, timeout 5s, retries 5; start period 10s for postgres and nginx, 30s for jobs and frontend
    - `jobs` depends on `postgres: service_healthy`; `nginx` depends on `jobs` and `frontend` being `service_healthy`
  - [x] 8.4 Write `dev-docker-compose.yml` (standalone, not an override)
    - frontend: `pnpm dev` (bound to `0.0.0.0:3000`), `./frontend` bind-mounted, a separate named volume for `/app/node_modules`
    - jobs: `alembic upgrade head` then `uvicorn --reload`, `./backend/jobs` bind-mounted (keep the container venv out of the bind mount), same data/log mounts
    - postgres: may publish `5432:5432` for local tools and the migration tests
    - Same `env_file: .env`, healthchecks, and dependency ordering as production
  - [x] 8.5 Smoke-test the production stack
    - `cp .env.example .env` (fill in values), `docker compose up --build`: all four containers reach `healthy`
    - `curl -i http://localhost:8080/health` -> 200 `ok`; `curl -i http://localhost:8080/api/v1/health` -> 200 `{"status":"ok","database":"ok"}`
    - Stop postgres: the jobs health returns 503 `degraded`
    - Browser: `/` redirects to `/login`; log in; the shell loads; logout returns to `/login`; the cookie is same-origin and httpOnly
    - Six bad logins -> 429 shown on the login page (confirms `X-Real-IP` forwarding)
  - [x] 8.6 Smoke-test the dev stack
    - `docker compose -f dev-docker-compose.yml up`: editing a page hot-reloads through `http://localhost:8080` (HMR websocket works); editing a Python file reloads uvicorn

**Acceptance Criteria:**
- Both stacks start with one command and all services report `healthy`
- Only nginx publishes a port in production; `/api/` and everything else are routed correctly with the path unchanged
- Migrations run on jobs boot; data and log folders are bind-mounted to the paths from tech-stack.md
- Hot reload works for both frontend and backend in dev

### Documentation

#### Task Group 9: README and Product Doc Updates
**Dependencies:** Task Group 8

- [x] 9.0 Complete the documentation updates
  - [x] 9.1 Write `README.md`
    - Prerequisites (Docker, Docker Compose; pnpm and uv for running tests locally)
    - Setup: `cp .env.example .env`, and how to generate `CAREER_NETWORKING_JWT_SECRET`
    - Commands: `docker compose up --build` (prod) and `docker compose -f dev-docker-compose.yml up` (dev)
    - URLs: app `http://localhost:8080`, `http://localhost:8080/health`, `http://localhost:8080/api/v1/health`
    - Running tests: `cd backend/jobs && uv run pytest` (with the test DB env var for migration tests), `cd frontend && pnpm test`; lint/format commands
    - No CI section; no sharing mentions
  - [x] 9.2 Update `agent-os/product/roadmap.md`
    - Replace the Phase 1 bullet "`.env.local` with all required environment variables" with `.env` wording and mention the committed `.env.example`
    - Remove "social share icons" from the Phase 1 top-nav bullet
  - [x] 9.3 Update `agent-os/product/tech-stack.md`
    - Remove the "Social Sharing" row from the Frontend table
  - [x] 9.4 Sweep for stale references
    - `grep -rn "\.env\.local" .` excluding `.git`, `node_modules`, `.gitignore` and this spec folder; replace every remaining hit with `.env`
    - Grep for "share"/"Social Sharing" in product docs and app code to confirm nothing remains for Phase 1

**Acceptance Criteria:**
- The README lets a new user go from clone to a running app with the two documented commands
- The only `.env.local` references left are in `.gitignore` and this spec folder
- The roadmap and tech-stack docs no longer mention social sharing for Phase 1

### Verification

#### Task Group 10: Test Review, Gap Analysis and Final Verification
**Dependencies:** Task Groups 1-9

- [x] 10.0 Review the feature tests and verify the full feature
  - [x] 10.1 Review the tests from Task Groups 2-7
    - Backend: health (2.2), migrations (3.1), auth and rate limit (4.1)
    - Frontend: health route (5.2), middleware and login (6.1), shell (7.1)
    - About 13-17 tests in total
  - [x] 10.2 Check coverage against the spec's required core flows only
    - Login success and failure, 429 rate limit, `/auth/me` needs a cookie, jobs health, migrations upgrade/downgrade, middleware redirect to `/login`
    - Confirm each is covered; do not assess anything beyond this spec
  - [x] 10.3 Add at most 5 more tests, only if a required core flow is missing
    - Likely candidates if absent: logout returns 204 and clears the cookie; a successful login resets the IP counter
    - Skip edge cases, performance and exhaustive accessibility testing
  - [x] 10.4 Run the feature tests and quality gates
    - `cd backend/jobs && uv run pytest` (with the dev Postgres up for the migration tests), `uv run ruff check`, `uv run ruff format --check`
    - `cd frontend && pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`
  - [x] 10.5 Final checks against the spec
    - Repeat the production smoke test from 8.5 on a fresh clone (removes the `postgres_data` volume first): all healthy, login/logout works, tables are empty after migrations
    - Confirm the out-of-scope items are absent: no `backend/users/`, no share icons, no seed data, no cron container, no TLS config, no CI files, no dark mode
    - Confirm no secrets or tokens appear in `backend/logs/career_networking.log` after a login cycle

**Acceptance Criteria:**
- All feature tests pass (about 13-22 in total), with no more than 5 added in this group
- Every core flow listed in the spec's testing requirement is covered
- Lint, format, typecheck and build are clean for both services
- A fresh clone reaches a working, healthy stack with `cp .env.example .env` plus one compose command

## Execution Order

Recommended sequence (groups on the same line can run in parallel):
1. Monorepo scaffolding and env configuration (Task Group 1)
2. Backend foundation (Task Group 2) | Frontend foundation and design system (Task Group 5)
3. Database models and migrations (Task Group 3) | Auth API and rate limiting (Task Group 4)
4. Route protection, login page and logout (Task Group 6)
5. App shell and placeholder pages (Task Group 7)
6. Docker Compose, dev compose and nginx (Task Group 8)
7. README and product doc updates (Task Group 9)
8. Test review, gap analysis and final verification (Task Group 10)

Note: the migration tests (3.1) need a running PostgreSQL. The simplest option is to bring up only the dev Postgres early (`docker compose -f dev-docker-compose.yml up postgres`), so a minimal Postgres service in `dev-docker-compose.yml` may be drafted during Task Group 3 and finished in Task Group 8.
