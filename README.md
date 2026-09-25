# Career Networking

Self-hosted job search and networking assistant: a Next.js frontend, a FastAPI `jobs` service, PostgreSQL and nginx, all run through Docker Compose on `http://localhost:8080`.

## Layout

```
frontend/              Next.js application (App Router, TypeScript strict, Tailwind, shadcn/ui)
backend/jobs/          Jobs service (FastAPI, SQLAlchemy 2, Alembic)
backend/data/          Resume and per-job files (bind-mounted, git-ignored)
backend/logs/          Log files, incl. career_networking.log (bind-mounted, git-ignored)
nginx/conf.d/          Reverse proxy configuration
docker-compose.yml     Production-style stack (built images)
dev-docker-compose.yml Development stack with hot reload
.env.example           Environment template (copy to .env)
```

## Prerequisites

- Docker Engine with the Docker Compose plugin (`docker compose`)
- To run tests and linters outside Docker: [pnpm](https://pnpm.io) with Node.js 24+ (frontend) and [uv](https://docs.astral.sh/uv/) (backend; it installs Python 3.12 if needed)

## Setup

```bash
cp .env.example .env
```

Then edit `.env` and replace every placeholder. `.env` at the repo root is the only runtime env file; it is git-ignored and both compose files read it.

- `CAREER_NETWORKING_USERNAME` / `CAREER_NETWORKING_PASSWORD` are the login credentials for the app.
- `CAREER_NETWORKING_DATABASE_DBNAME`, `_USERNAME` and `_PASSWORD` initialise the Postgres container. Keep `CAREER_NETWORKING_DATABASE_URL` in sync with them; its host must be `postgres` (the compose service name).
- `CAREER_NETWORKING_JWT_SECRET` signs the session cookie and must be at least 32 characters. Generate one with:

  ```bash
  openssl rand -hex 32
  # or
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

The jobs service refuses to start, naming the offending variables, if a required value is missing or invalid.

## Running

**Production-style stack** (built images; only nginx publishes a host port):

```bash
docker compose up --build
```

**Development stack** (Next.js hot reload, `uvicorn --reload`, Postgres also published on `localhost:5432`):

```bash
docker compose -f dev-docker-compose.yml up --build
```

Both stacks run `alembic upgrade head` when the jobs container starts, so the schema is always current. Every service has a healthcheck; `docker compose ps` shows each one as `healthy` once the stack is ready (usually within a minute; the first build takes longer).

Stop a stack with `docker compose down` (add `-f dev-docker-compose.yml` for dev). Adding `-v` also deletes the database volume.

### URLs

| URL | What |
|---|---|
| http://localhost:8080 | The app (redirects to `/login` until you sign in) |
| http://localhost:8080/health | nginx health (`200 ok`, answered by nginx itself) |
| http://localhost:8080/api/v1/health | jobs health: `200 {"status":"ok","database":"ok"}`, or `503 {"status":"degraded","database":"unreachable"}` when Postgres is down |

The frontend's own `GET /health` (`{"status":"ok"}`) is used only by its container healthcheck on port 3000.

### Routing

nginx serves everything from one origin, so the `cn_session` cookie is same-origin:

- `/api/*` goes to the jobs service (path unchanged): `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`, `GET /api/v1/health`
- `/health` is answered by nginx
- everything else goes to the Next.js frontend, including `/login` and `POST /logout` (a frontend route that expires the cookie when the API cannot, for example after the session was already rejected)

Page protection lives in `frontend/proxy.ts` (Next.js 16's name for middleware). It verifies the `cn_session` JWT and redirects to `/login?next=<path>` when there is no valid session. Failed logins are rate limited per client IP (`CAREER_NETWORKING_LOGIN_MAX_ATTEMPTS` failures per `CAREER_NETWORKING_LOGIN_WINDOW_MINUTES`); nginx sets `X-Real-IP`, so clients cannot spoof it.

## Tests, lint and format

### Frontend

```bash
cd frontend
pnpm install
pnpm test           # Vitest + React Testing Library
pnpm lint           # ESLint
pnpm typecheck      # next typegen + tsc --noEmit
pnpm format:check   # Prettier (pnpm format to fix)
pnpm build
```

### Backend (jobs)

```bash
cd backend/jobs
uv run pytest
uv run ruff check
uv run ruff format --check   # uv run ruff format to fix
```

The migration tests need a real, disposable PostgreSQL and are skipped unless `CAREER_NETWORKING_TEST_DATABASE_URL` is set. They migrate the database up to head and back down to base, so point them at the dev Postgres rather than anything holding data:

```bash
docker compose -f dev-docker-compose.yml up -d postgres
cd backend/jobs
CAREER_NETWORKING_TEST_DATABASE_URL=postgresql+psycopg://<db user>:<db password>@localhost:5432/<db name> uv run pytest
```

If the full dev stack is running, restart the jobs container afterwards (`docker compose -f dev-docker-compose.yml restart jobs`) to re-apply the migrations.

Without uv on the host, the same commands run in a throwaway container:

```bash
docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "$PWD/backend/jobs:/app" -w /app \
  -e UV_CACHE_DIR=/tmp/uv-cache -e UV_PROJECT_ENVIRONMENT=/tmp/venv \
  -e CAREER_NETWORKING_TEST_DATABASE_URL=postgresql+psycopg://<db user>:<db password>@localhost:5432/<db name> \
  ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
  sh -c "uv run pytest && uv run ruff check && uv run ruff format --check"
```

## Notes

- Data and logs are bind-mounted into the jobs container: `backend/data/resume` to `/opt/career_networking/resume`, `backend/data/jobs` to `/opt/career_networking/jobs`, `backend/logs` to `/opt/career_networking/logs`. The jobs container runs as root, so files it writes there (such as `career_networking.log`) are owned by root on the host.
- The dev stack mounts container-owned volumes over `frontend/node_modules` and `frontend/.next`. On a fresh clone Docker creates those two folders on the host as root, which then blocks `pnpm install` on the host. Run `pnpm install` in `frontend/` before the first `docker compose -f dev-docker-compose.yml up`, or fix ownership with `sudo chown -R "$(id -u):$(id -g)" frontend/node_modules frontend/.next`.
- Design tokens are defined once in `frontend/app/globals.css`. The warning colour is `#94621A` instead of the originally planned `#B7791F`, which did not meet WCAG AA contrast for text.
- Plain HTTP only; no TLS is configured. The app is meant to run on your own machine.
