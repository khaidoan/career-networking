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

- `CAREER_NETWORKING_LLM_MODEL` picks the default AI model for every agent (see [LLM configuration](#llm-configuration)). It is required: **if you created `.env` before Phase 2, add it (and the matching provider key) now**, or the jobs and fetcher services will not start.

The jobs service refuses to start, naming the offending variables, if a required value is missing or invalid.

### LLM configuration

All AI agents (`resume_extractor`, `evaluator`, `company_lookup`, `networking`) use one default model, called through [LiteLLM](https://docs.litellm.ai/docs/providers); any of them can be given a different model. Set them in `.env`:

| Variable | Required | Meaning |
|---|---|---|
| `CAREER_NETWORKING_LLM_MODEL` | yes | Default LiteLLM model string, `<provider>/<model>` |
| `CAREER_NETWORKING_LLM_API_BASE` | no | Custom API base URL for the default model (e.g. a local Ollama server); leave empty for the provider default. Overridden agents do not use it |
| `CAREER_NETWORKING_LLM_MODEL_OVERRIDES` | no | Comma-separated `agent=model` pairs for agents that should not use the default, e.g. `company_lookup=anthropic/claude-sonnet-5`. An unknown agent name or malformed pair stops the service from starting |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` | for that provider | Set the keys that match the models in use. LiteLLM reads them from the environment; they are never logged |
| `CAREER_NETWORKING_MATCH_THRESHOLD` | no (default 70) | Jobs whose overall match score (0–100) is at least this go to the Recommended inbox; the rest go to Ignored |

Examples:

```bash
# OpenAI
CAREER_NETWORKING_LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic: Haiku for every agent except company lookup
CAREER_NETWORKING_LLM_MODEL=anthropic/claude-haiku-4-5
CAREER_NETWORKING_LLM_MODEL_OVERRIDES=company_lookup=anthropic/claude-sonnet-5
ANTHROPIC_API_KEY=sk-ant-...

# OpenRouter
CAREER_NETWORKING_LLM_MODEL=openrouter/meta-llama/llama-3.1-70b-instruct
OPENROUTER_API_KEY=sk-or-...

# Ollama running on the host (no key needed)
CAREER_NETWORKING_LLM_MODEL=ollama/llama3.1
CAREER_NETWORKING_LLM_API_BASE=http://host.docker.internal:11434
```

`host.docker.internal` resolves out of the box on Docker Desktop. On Linux, either add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `jobs` and `fetcher` services, or use the host's IP address instead (for example the Docker bridge address `http://172.17.0.1:11434`, with Ollama listening on that interface).

**What is sent to the model:** job postings, your resume text, and the information on the Profile / Preferences page. Treat every field on that page as something that may be sent to the model: the agents built so far send only part of it, but the planned resume, cover letter and apply agents will use more, including your address and application answers. If that is a privacy concern, check your model provider's data retention and training policy, or run a local model (see the Ollama example above) so nothing leaves your machine.

If the model is unreachable, a resume upload still succeeds (without suggestions), and the scorer retries a job twice (after 5 and 30 minutes) before saving it to the Ignored inbox without scores; it is not re-evaluated after that.

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

Each interval, Google Jobs is searched for every desired job title (set on the Profile page) in your preferred country, fetching up to 3 result pages per title. Each result page counts as one SerpApi search. At the default once a day that is about 30 searches per title per month for each result page, so keep titles × pages × runs within your plan (250 on the free plan) before adding titles or shortening the interval. Searches SerpApi serves from its cache, and failed searches, do not count toward the quota. [Contact search](#contact-search-optional) uses the same key and the same monthly quota.

### Contact search (optional)

Job Details (in the Networking / Outreach section) and Company Details (in the Contacts section) have a **Find contacts** button that looks for people at the company on LinkedIn who could help with a mock interview or a referral.

- **It needs `SERPAPI_API_KEY`**, the same key as [Google Jobs](#google-jobs-optional). Set it in `.env` as described there and restart the stack. Without it the button is disabled and says a SerpApi key is needed.
- **It only runs when you click.** The button is available for companies with at least one job in the Recommended or Applied inbox. The fetcher never searches for contacts, and nothing runs on a schedule.
- **Each click is one SerpApi search** (a DuckDuckGo search for `site:linkedin.com/in "<company>" <role words>`, where the role words are the job title without words such as Senior, II or 4, with hyphens as spaces; Google and Bing often ignore the LinkedIn restriction, so they are not used) plus one call to your AI model, which picks up to 5 people from the results: peers in the same or a close role first, and at most one hiring manager or team lead. There is no daily cap and no cooldown, and every click counts toward the same monthly SerpApi quota as Google Jobs (250 searches on the free plan).
- **Results come from Google and may be out of date.** Names, titles and profile links are taken from Google's search results, not from LinkedIn itself, so someone may have changed role or left the company. The page shows when the company was last searched.
- **Searching again is safe.** People already in the list are matched by their LinkedIn profile URL (or, for contacts without one, by name). Their title is updated if the search shows a newer one, but a contact you have already clicked (the app records this, without showing it) is never changed, and no contact is ever deleted.
- **The app never sends LinkedIn connection requests or messages**, and it never signs in to LinkedIn. To reach out, select a contact's name: it opens their profile in a new tab and copies a connection message for you to paste and send yourself. The People on LinkedIn link on the page is a manual fallback for browsing the company's people tab.

The AI model sees the company name, the job title, the search results (result title and snippet) and your hard skills; nothing else from your profile is sent. If SerpApi or the model fails, nothing is saved and the page shows the error; try again later.

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

The `fetcher` service (in both compose files) is built from the `backend/jobs` image and uses the same `.env` and data/log volumes. It waits until the `jobs` service is healthy (so migrations have run), then starts one run of `python -m src.fetcher` in the background every time the container starts (including restarts and `docker compose up` after a change), and runs it again once a day at the **Daily job fetch time** set on the Profile page, in the **Time zone** next to it. [supercronic](https://github.com/aptible/supercronic) calls `python -m src.fetcher --if-due` every 5 minutes (`backend/jobs/crontab`), which exits at once unless the time has come and no run has started since; a run that started in the hour before the time counts, so a restart shortly before it does not cause a second run. A changed time applies from the next check, with no restart needed. The fetcher spends no LLM tokens: it saves each new posting that passes every filter below as an unscored ("pending") job, and the separate scorer evaluates it (see **Scoring**). Each board's postings are saved as soon as that board is scanned, so scored jobs start appearing in Recommended while the run is still going.

**Preconditions:** job fetching is disabled until the Profile page has at least one desired job title, a country, a daily fetch time and a time zone saved (the time and time zone are required whenever the page is saved; the page pre-fills 06:00 and the browser's time zone). The Profile page always says whether job fetching is enabled, with the next run time or what is still missing. While it is disabled, the scheduled check never starts a run, a run started by a container restart logs `Fetcher skipped: preferences incomplete …` and exits, and the Recommended page sends you to the Profile page to finish setting up. Browsers do not send a time zone in any HTTP header, so the server cannot detect it; the page fills it in from the browser instead. If a run is still going when the next one starts, the new one logs `Fetcher skipped: another run is in progress` and exits (both exit with status 0).

**Each run, in order:**

1. **Google Jobs search** (optional, see [Google Jobs](#google-jobs-optional)): only if `SERPAPI_API_KEY` is set and the interval has passed since the last successful search (with up to an hour's grace, so a daily run is never skipped for starting a little early). Boards found in apply links are tracked right away; the postings wait for step 4.
2. **ATS sweep:** the public company directories for Greenhouse, Lever, Ashby, Workday, iCIMS and BambooHR (about 50,000 boards, from [job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator), cached for 24 hours) are all scanned in every run. If the download fails the cached copy is used; with no cache at all the sweep is skipped for that run.
3. **Tracked boards:** every board that has had a matching job is tracked in the `ats_boards` table. Boards the sweep already covered this run are not fetched again, so in practice this polls the boards found only through Google Jobs.
4. **Google Jobs postings** are ingested after the ATS sources, so a job an ATS board already gave us is not saved (and scored) twice (see below).
5. **Pruning:** boards with no matching job for 30 days are deactivated; they are reactivated if discovery finds them again.

**Filters (free, before any LLM call).** Every source, Google Jobs included, applies the same checks, and each one keeps a posting whenever it cannot tell:

- **Title:** the title contains every word of one of your desired titles, in any order, and does not contain every word of any of your **Excluded title words** entries (for example `Test`, `QA`, `Security`, or a phrase such as `Site Reliability`, which is skipped only when both words appear).
- **Seniority:** only if you picked seniority levels on the Profile page. A posting is dropped only when its title plainly names a level at least two steps from every level you picked (for example "Intern" or "VP" for a Senior search). Only unambiguous words count (intern, junior, new grad, senior, sr, principal, director, VP, chief … officer). Titles with no level word, or with an ambiguous one such as "Manager", "Lead", "Staff", "Head" or "Associate", always pass, and the evaluator judges them.
- **Country:** the location names your country, or is remote without naming another country. A bare "Remote" on an ATS board is dropped only when the board's other postings name other countries but never yours (for example a German company's "Remote" role in a US search). Google Jobs searches are already country-scoped, so a bare "Remote" there is kept.
- **Relocation and commute:** from the Profile page's **Relocation & commute** section. Remote postings always pass. An on-site or hybrid posting is dropped when every city it lists is in a state or city on your **Places I will not relocate to** list, or, when you are not willing to relocate, more than your **Maximum commute** (straight-line miles) from the city in your saved **Address**. A posting whose location names no recognisable city is kept, unless it names only states you excluded. Cities and states are matched offline against bundled GeoNames data (`backend/jobs/src/data/cities.tsv.gz`, every place of 1,000+ people; rebuild with `python scripts/build_cities.py` in `backend/jobs`). The Profile page shows the home city it found and any places it did not recognise.
- **Recency:** published in the last 24 hours. Postings with no publish date, or older than 24 hours, are never processed.

**Be specific with desired job titles.** Every posting that passes these filters is scored by the AI model, which costs tokens, so the title filter is the main control on cost. Because a posting only needs every word of a title somewhere in its own title, a broad title such as `Software Engineer` also matches *Software Development Engineer in Test* and *Technical Marketing Engineer – AI Infrastructure Software*. Prefer specific titles such as `Backend Software Engineer`, `Frontend Software Engineer` or `Fullstack Software Engineer`, and add **Excluded title words** for the kinds of roles you never want. The trade-off: a longer title also misses postings that leave one of its words out (`Backend Software Engineer` does not match *Senior Backend Engineer*), so list each wording you want, such as both `Backend Software Engineer` and `Backend Engineer`. Note that `Fullstack` and `Full Stack` are different words to the filter; add both forms if postings use both.

**Duplicates.** Postings are deduplicated by URL, ignoring tracking parameters. A Google Jobs posting whose link is not an ATS link (for example LinkedIn or Indeed) is also skipped when an ATS source already has the same job: same company (ignoring suffixes such as "Inc." or "Corp"), same title and a compatible country, found this run or in the last 30 days.

**Scoring.** The `scorer` service (both compose files, `python -m src.scorer`, logs in `backend/logs/scorer.log`) runs all the time and evaluates the pending jobs, `CAREER_NETWORKING_SCORER_CONCURRENCY` at a time (default 4; lower it if the LLM provider rate-limits you). Each scored job goes to the Recommended or Ignored inbox based on `CAREER_NETWORKING_MATCH_THRESHOLD`. Companies are saved by name when the job is found; the AI company lookup runs only when a job is recommended, so a company whose jobs are all ignored keeps just its name. Only jobs posted in the last 24 hours are scored (a job whose source gives no posting date counts from when it was found). The scorer never deletes jobs: an older pending job stays unscored and hidden until the fetcher deletes it after 7 days (see below). If the evaluator fails (for example the LLM is unreachable or returns invalid output), the job is tried again after 5 and then 30 minutes; after the third failure it is saved without scores in the Ignored inbox, with the reason in `jobs.evaluation_error`. Unscored jobs are never shown in the app. A failure in one source or job is logged and the run continues.

**Inbox order.** Every inbox lists jobs by when they arrived in it, newest first: for Recommended that is when the job was scored, for Applied when you applied. Recommended keeps growing at the bottom: when you scroll to the end it adds jobs scored since you opened the page, then older ones you have not seen yet; once you have seen everything it says so, and checks again when you scroll back to the bottom (or click **Check for new jobs**).

#### Fetch now

There is no button for this in the app. Restarting the `fetcher` container starts a run in the background; to run one in the foreground and watch it instead:

```bash
docker compose exec fetcher python -m src.fetcher
# development stack:
docker compose -f dev-docker-compose.yml exec fetcher python -m src.fetcher
```

The stack must be running. The command runs one full fetch in the foreground, prints its log lines, and ends with the `Fetcher run finished in …` summary. It follows the same rules as a scheduled run: it skips if your titles or country are not set, and it exits straight away if a scheduled run is already in progress. Google Jobs is searched only if its interval has passed.

**Logs** go to `backend/logs/fetcher.log` and to `docker compose logs fetcher` (add `-f dev-docker-compose.yml` for dev). Every completed run ends with a `Fetcher run finished in …` line counting fetched, matched, new, duplicate and failed postings per source, plus how many jobs were queued for scoring and how many old ignored jobs were deleted. The ATS sweep logs its progress every 2,000 boards. The scorer logs a line for each batch it scores.

**Ignored and pending jobs are deleted after 7 days.** Every fetcher run, including one skipped because preferences are incomplete, deletes jobs in the Ignored inbox and jobs still waiting to be scored that were discovered more than 7 days ago (`JOB_RETENTION` in `backend/jobs/src/fetcher.py`). This includes jobs whose evaluation failed. Postings are only picked up while under 24 hours old, so a deleted job does not come back. Jobs in the other inboxes are never deleted.

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
| `PUT /api/v1/preferences` | Replace all editable preferences (titles, excluded title words, skills, country, currency, salary range, seniority, relocation answers, address, gender, EEO answers, additional information, auto apply, fetch time). Invalid values return 422 |
| `POST /api/v1/preferences/resume` | Multipart upload of one `.pdf` or `.docx` file (field `file`, up to 10 MB). Saves the resume and what it suggests: titles and skills are added to the saved ones, seniority, country and currency are filled in only while empty, and the address is always replaced by the resume's (the AI's reading, or the city, state and ZIP code from the resume header when the AI gives none or is unavailable; kept when the resume has no address). Returns the resume info, the suggestions and the saved preferences. 413 if too large, 415 for other types, 422 if no text can be extracted (the previous resume is kept) |
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

- [GeoNames](https://www.geonames.org) (CC BY 4.0): the city and state data in `backend/jobs/src/data/cities.tsv.gz`, used by the relocation and commute filter.

The MIT notices are kept in the header of each ported module.
