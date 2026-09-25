# Career Networking — Tech Stack

## Architecture

**Microservices monorepo** — all services in one repository, deployed via Docker Compose.

```
career-networking/
├── frontend/          # Next.js application
├── backend/
│   ├── jobs/          # Jobs microservice (FastAPI)
│   └── users/         # Users microservice (FastAPI)
├── agent-os/
└── docker-compose.yml
```

---

## Frontend

| Concern | Choice | Notes |
|---|---|---|
| Framework | Next.js (App Router) | React-based, SSR/SSG support |
| Language | TypeScript | Strict mode |
| Styling | Tailwind CSS | Warm, modern, minimalist design |
| Auth | JWT (httpOnly cookie) | No localStorage for JWT storage |
| HTTP Client | Axios or fetch | API calls to backend services |
| PDF Preview | react-pdf | Render PDF previews in-browser |
| Markdown Editor | react-markdown + textarea | Edit cover letter and resume |
| Social Sharing | Native Web Share API + fallbacks | X, Facebook, LinkedIn, Email |
| Icons | Lucide React | Consistent icon set |

---

## Backend

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Framework | FastAPI | Async, OpenAPI docs auto-generated |
| ORM | SQLAlchemy 2.x | Declarative models |
| Migrations | Alembic | Version-controlled DB schema |
| AI Orchestration | LangGraph | Agent graphs (prepare_job, apply, etc.) |
| LLM Abstraction | LiteLLM | Works with OpenAI, Anthropic, local models |
| Job Scraping | Career-Ops compatible scrapers | All job boards/ATS Career-Ops supports |
| Browser Automation | Playwright | LinkedIn outreach (user-triggered) |
| PDF Generation | WeasyPrint or reportlab | Convert markdown → PDF |
| Resume Parsing | python-docx + PyPDF2/pdfminer | Extract text from .docx and .pdf |
| Task Scheduling | Docker Compose + cron | Runs fetcher.py every 30 minutes |
| Logging | Python `logging` module | Central log file: `career_networking.log` |

---

## Data

| Concern | Choice | Notes |
|---|---|---|
| Database | PostgreSQL 15+ | Primary data store |
| ORM | SQLAlchemy | See above |
| Migrations | Alembic | |
| File Storage | Local filesystem (Docker volumes) | Resume, job PDFs, logs |

### Docker Volume Mappings

| Purpose | Host Path | Container Path | Env Var |
|---|---|---|---|
| Master resume | `backend/data/resume` | `/opt/career_networking/resume` | `CAREER_NETWORKING_RESUME_FOLDER` |
| Job-specific files | `backend/data/jobs` | `/opt/career_networking/jobs` | `CAREER_NETWORKING_JOB_DATA` |
| Logs | `backend/logs` | `/opt/career_networking/logs` | `CAREER_NETWORKING_LOG_FOLDER` |

---

## Infrastructure

| Concern | Choice |
|---|---|
| Containerization | Docker |
| Orchestration | Docker Compose |
| Reverse Proxy | Nginx |
| Scheduling | Cron (inside Docker Compose) |

---

## Authentication

- Single-user only — no users table in database
- Credentials stored in environment variables: `CAREER_NETWORKING_USERNAME`, `CAREER_NETWORKING_PASSWORD`
- JWT issued on login, stored in httpOnly cookie (not localStorage)
- Backend validates JWT on protected routes

---

## Environment Variables

| Variable | Description |
|---|---|
| `CAREER_NETWORKING_DATABASE_URL` | Full PostgreSQL connection URL |
| `CAREER_NETWORKING_DATABASE_DBNAME` | Database name |
| `CAREER_NETWORKING_DATABASE_USERNAME` | DB username |
| `CAREER_NETWORKING_DATABASE_PASSWORD` | DB password |
| `CAREER_NETWORKING_USERNAME` | App login username |
| `CAREER_NETWORKING_PASSWORD` | App login password |
| `CAREER_NETWORKING_FIRSTNAME` | User's first name |
| `CAREER_NETWORKING_LASTNAME` | User's last name |
| `CAREER_NETWORKING_EMAIL` | User's email (for notifications) |
| `CAREER_NETWORKING_LONG_COMMON_JOBBOARDS_PASSWORD` | Shared job board account password |
| `CAREER_NETWORKING_RESUME_FOLDER` | Path to master resume storage |
| `CAREER_NETWORKING_JOB_DATA` | Path to per-job file storage |
| `CAREER_NETWORKING_LOG_FOLDER` | Path to log file directory |

---

## Job Boards / ATS

Must support all job boards and ATS platforms currently supported by Career-Ops, including (but not limited to):

- LinkedIn Jobs
- Indeed
- Glassdoor
- ZipRecruiter
- Greenhouse
- Lever
- Workday
- iCIMS
- SmartRecruiters
- BambooHR
- Jobvite
- Taleo (Oracle)
- *(full list to be confirmed by inspecting Career-Ops source)*

---

## AI Agents

| Agent | File | Purpose |
|---|---|---|
| Job Evaluator | `backend/jobs/src/agents/evaluator.py` | Score job against user preferences/skills |
| Company Lookup | `backend/jobs/src/agents/company_lookup.py` | Populate companies table via LLM |
| Cover Letter | `backend/jobs/src/agents/cover_letter.py` | Generate tailored cover letter |
| Cover Letter Reviewer | `backend/jobs/src/agents/cover_letter_reviewer.py` | Review and improve cover letter |
| Resume | `backend/jobs/src/agents/resume.py` | Tailor resume to job posting |
| Resume Reviewer | `backend/jobs/src/agents/resume_reviewer.py` | Review and improve tailored resume |
| Prepare Job | `backend/jobs/src/agents/prepare_job.py` | LangGraph graph: orchestrates cover letter + resume pipeline |
| Apply | `backend/jobs/src/agents/apply.py` | Playwright-based job application (future) |
| Networking | `backend/jobs/src/agents/networking.py` | Find LinkedIn contacts at target companies |

Each agent defines a `{AGENT_NAME}_SYSTEM_PROMPT` constant. Prompts are stored in the `prompts` table; if not customized, the constant is used as fallback.
