# Career Networking

Self-hosted job search and networking assistant: a Next.js frontend, a FastAPI `jobs` service, PostgreSQL and nginx, all run through Docker Compose on `http://localhost:8080`.

## Layout

```
frontend/              Next.js application (App Router, TypeScript strict, Tailwind, shadcn/ui)
backend/jobs/          Jobs service (FastAPI, SQLAlchemy 2, Alembic)
backend/data/          Resume and per-job files (bind-mounted, git-ignored)
backend/logs/          Log files: career_networking.log and fetcher.log (bind-mounted, git-ignored)
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

- `CAREER_NETWORKING_LLM_MODEL` picks the AI model used by every agent (see [LLM configuration](#llm-configuration)). It is required: **if you created `.env` before Phase 2, add it (and the matching provider key) now**, or the jobs and fetcher services will not start.

The jobs service refuses to start, naming the offending variables, if a required value is missing or invalid.

### LLM configuration

All AI agents (resume extractor, job evaluator, company lookup) share one model, called through [LiteLLM](https://docs.litellm.ai/docs/providers). Set it in `.env`:

| Variable | Required | Meaning |
|---|---|---|
| `CAREER_NETWORKING_LLM_MODEL` | yes | LiteLLM model string, `<provider>/<model>` |
| `CAREER_NETWORKING_LLM_API_BASE` | no | Custom API base URL (e.g. a local Ollama server); leave empty for the provider default |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` | for that provider | Set only the key that matches the model. LiteLLM reads it from the environment; it is never logged |
| `CAREER_NETWORKING_MATCH_THRESHOLD` | no (default 70) | Jobs whose overall match score (0–100) is at least this go to the Recommended inbox; the rest go to Ignored |

Examples:

```bash
# OpenAI
CAREER_NETWORKING_LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic
CAREER_NETWORKING_LLM_MODEL=anthropic/claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...

# OpenRouter
CAREER_NETWORKING_LLM_MODEL=openrouter/meta-llama/llama-3.1-70b-instruct
OPENROUTER_API_KEY=sk-or-...

# Ollama running on the host (no key needed)
CAREER_NETWORKING_LLM_MODEL=ollama/llama3.1
CAREER_NETWORKING_LLM_API_BASE=http://host.docker.internal:11434
```

`host.docker.internal` resolves out of the box on Docker Desktop. On Linux, either add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `jobs` and `fetcher` services, or use the host's IP address instead (for example the Docker bridge address `http://172.17.0.1:11434`, with Ollama listening on that interface).

**What is sent to the model:** job postings, your resume text, and only the job-relevant preferences: desired titles, hard and soft skills, seniority, salary range, currency, country, and your work authorization and visa sponsorship answers. Your address, gender and the other EEO answers (race/ethnicity, veteran and disability status) are never sent.

If the model is unreachable, a resume upload still succeeds (without suggestions), and a job that cannot be evaluated is saved to the Ignored inbox without scores; it is not re-evaluated later.

### Google Jobs (optional)

The job fetcher can search Google Jobs, which surfaces listings from LinkedIn, Indeed, Glassdoor, Workday and other boards, through [SerpApi](https://serpapi.com). This source is optional: without a key it is skipped and the fetcher still pulls jobs from public ATS boards (Greenhouse, Lever, Ashby and others).

1. Sign up at https://serpapi.com/users/sign_up. The free plan includes 250 searches per month.
2. Copy your private API key from https://serpapi.com/manage-api-key.
3. Add it to `.env`:

   ```bash
   SERPAPI_API_KEY=your-serpapi-key
   # How often Google Jobs is searched, in hours (default 24)
   CAREER_NETWORKING_GOOGLE_JOBS_INTERVAL_HOURS=24
   ```

4. Restart the stack so the services pick up the new values.

Each interval, Google Jobs is searched for every desired job title (set on the Profile page) in your preferred country, fetching up to 3 result pages per title. Each result page counts as one SerpApi search. At the default once a day that is about 30 searches per title per month for each result page, so keep titles × pages × runs within your plan (250 on the free plan) before adding titles or shortening the interval. Searches SerpApi serves from its cache, and failed searches, do not count toward the quota.

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

### Job fetcher

The `fetcher` service (in both compose files) is built from the `backend/jobs` image and uses the same `.env` and data/log volumes. It waits until the `jobs` service is healthy (so migrations have run), then runs `python -m src.fetcher` once a day at 06:00 UTC through [supercronic](https://github.com/aptible/supercronic); the schedule is in `backend/jobs/crontab`. A run takes roughly 30–90 minutes, almost all of it the ATS sweep's HTTP requests; it spends no LLM tokens until a posting has passed every filter below.

**Preconditions:** the fetcher does nothing until the Profile page has at least one desired job title and a country saved. Until then each run logs `Fetcher skipped: preferences incomplete …` and exits, and the Profile page shows that discovery is paused. If a run is still going when the next one starts, the new one logs `Fetcher skipped: another run is in progress` and exits (both exit with status 0).

**Each run, in order:**

1. **Google Jobs search** (optional, see [Google Jobs](#google-jobs-optional)): only if `SERPAPI_API_KEY` is set and the interval has passed since the last successful search (with up to an hour's grace, so a daily run is never skipped for starting a little early). Boards found in apply links are tracked right away; the postings wait for step 4.
2. **ATS sweep:** the public company directories for Greenhouse, Lever, Ashby, Workday, iCIMS and BambooHR (about 50,000 boards, from [job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator), cached for 24 hours) are all scanned in every run. If the download fails the cached copy is used; with no cache at all the sweep is skipped for that run.
3. **Tracked boards:** every board that has had a matching job is tracked in the `ats_boards` table. Boards the sweep already covered this run are not fetched again, so in practice this polls the boards found only through Google Jobs.
4. **Google Jobs postings** are ingested after the ATS sources, so a job an ATS board already gave us is not evaluated twice (see below).
5. **Pruning:** boards with no matching job for 30 days are deactivated; they are reactivated if discovery finds them again.

**Filters (free, before any LLM call).** Every source, Google Jobs included, applies the same checks, and each one keeps a posting whenever it cannot tell:

- **Title:** the title contains every word of one of your desired titles.
- **Seniority:** only if you picked seniority levels on the Profile page. A posting is dropped only when its title plainly names a level at least two steps from every level you picked (for example "Intern" or "VP" for a Senior search). Only unambiguous words count (intern, junior, new grad, senior, sr, principal, director, VP, chief … officer). Titles with no level word, or with an ambiguous one such as "Manager", "Lead", "Staff", "Head" or "Associate", always pass, and the evaluator judges them.
- **Country:** the location names your country, or is remote without naming another country. A bare "Remote" on an ATS board is dropped only when the board's other postings name other countries but never yours (for example a German company's "Remote" role in a US search). Google Jobs searches are already country-scoped, so a bare "Remote" there is kept.
- **Recency:** published in the last 7 days. Postings with no publish date, or older than 7 days, are never processed.

**Duplicates.** Postings are deduplicated by URL, ignoring tracking parameters. A Google Jobs posting whose link is not an ATS link (for example LinkedIn or Indeed) is also skipped when an ATS source already has the same job: same company (ignoring suffixes such as "Inc." or "Corp"), same title and a compatible country, found this run or in the last 30 days.

**Scoring.** Each new job is scored by the evaluator and goes to the Recommended or Ignored inbox based on `CAREER_NETWORKING_MATCH_THRESHOLD`. The company is then matched by name; the AI company lookup runs only for recommended jobs, so a company whose jobs are all ignored is saved by name only (and filled in later if one of its jobs is recommended). If the evaluator fails (for example the LLM is unreachable or returns invalid output), the job is saved without scores in the Ignored inbox, with the reason in `jobs.evaluation_error`, and it is not evaluated again. A failure in one source or job is logged and the run continues.

#### Fetch now

There is no button for this in the app. To run the fetcher immediately instead of waiting for tomorrow's run:

```bash
docker compose exec fetcher python -m src.fetcher
# development stack:
docker compose -f dev-docker-compose.yml exec fetcher python -m src.fetcher
```

The stack must be running. The command runs one full fetch in the foreground, prints its log lines, and ends with the `Fetcher run finished in …` summary. It follows the same rules as a scheduled run: it skips if your titles or country are not set, and it exits straight away if a scheduled run is already in progress. Google Jobs is searched only if its interval has passed.

**Logs** go to `backend/logs/fetcher.log` and to `docker compose logs fetcher` (add `-f dev-docker-compose.yml` for dev). Every completed run ends with a `Fetcher run finished in …` line counting fetched, matched, new, duplicate and failed postings per source, plus how many jobs were evaluated, recommended and ignored, and how many old ignored jobs were deleted.

**Ignored jobs are deleted after 7 days.** Every run, including one skipped because preferences are incomplete, deletes jobs in the Ignored inbox that were discovered more than 7 days ago (`IGNORED_JOB_RETENTION` in `backend/jobs/src/fetcher.py`). This includes jobs whose evaluation failed. Postings are only picked up while under 7 days old, so a deleted job does not come back. Jobs in the other inboxes are never deleted.

Run state (the Google Jobs last-run time and the sweep position) and the directory cache live in `backend/data/jobs/_fetcher/`. Deleting that folder is safe: it only restarts the sweep rotation and makes Google Jobs due on the next run.

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

- `/api/*` goes to the jobs service (path unchanged): `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`, `GET /api/v1/health`, and the preferences endpoints below. nginx accepts request bodies up to 11 MB on `/api/` so 10 MB resumes fit.
- `/health` is answered by nginx
- everything else goes to the Next.js frontend, including `/login` and `POST /logout` (a frontend route that expires the cookie when the API cannot, for example after the session was already rejected)

Preferences endpoints (all require a valid session; errors use `{"detail": ...}`):

| Method and path | What |
|---|---|
| `GET /api/v1/preferences` | The saved preferences, or empty defaults before the first save; includes `resume` (`file_type`, `uploaded_at`) or `null` |
| `PUT /api/v1/preferences` | Replace all editable preferences (titles, skills, country, currency, salary range, seniority, address, gender, EEO answers). Invalid values return 422 |
| `POST /api/v1/preferences/resume` | Multipart upload of one `.pdf` or `.docx` file (field `file`, up to 10 MB). Returns the resume info plus suggested titles and skills, which are not saved until a `PUT`. 413 if too large, 415 for other types, 422 if no text can be extracted (the previous resume is kept) |
| `DELETE /api/v1/preferences/resume` | Delete the resume file and its extracted text (titles and skills are kept); 204 |

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

The fetcher's database tests (`tests/test_fetcher.py`) need the same variable. `tests/test_compose.py` checks the compose files at the repo root, so it is skipped when only `backend/jobs` is available (as in the throwaway container below); to run it there, mount the repo root and set the working directory to `backend/jobs` (`-v "$PWD:/repo" -w /repo/backend/jobs`).

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
- Log files rotate at midnight UTC and are kept for 3 days: the API writes `career_networking.log` and the fetcher writes `fetcher.log`, each with up to two dated backups (for example `fetcher.log.2026-09-24`). Older backups are deleted automatically, both at rotation and each time a process starts (`LOG_RETENTION_DAYS` in `backend/jobs/src/logging_config.py`).
- The dev stack mounts container-owned volumes over `frontend/node_modules` and `frontend/.next`. On a fresh clone Docker creates those two folders on the host as root, which then blocks `pnpm install` on the host. Run `pnpm install` in `frontend/` before the first `docker compose -f dev-docker-compose.yml up`, or fix ownership with `sudo chown -R "$(id -u):$(id -g)" frontend/node_modules frontend/.next`.
- Design tokens are defined once in `frontend/app/globals.css`. The warning colour is `#94621A` instead of the originally planned `#B7791F`, which did not meet WCAG AA contrast for text.
- Plain HTTP only; no TLS is configured. The app is meant to run on your own machine.

## Credits

- [Career-Ops](https://github.com/career-ops-hq/career-ops) (MIT License): the ATS provider modules in `backend/jobs/src/sources/providers/` and the directory sweep in `backend/jobs/src/sources/ats_sweep.py` are Python ports of its provider scanners and `scan-ats-full.mjs`.
- [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator) by Riley Dorrington: the company directories used by the ATS sweep. The project's code is MIT licensed, but these datasets (its `data/` folder) are licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): free for personal, non-commercial use with attribution. Commercial use needs the author's permission. The fetcher downloads them at run time; they are not included in this repository.

The MIT notices are kept in the header of each ported module.
