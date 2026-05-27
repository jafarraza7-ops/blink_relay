# Blink Relay

Internal tech request intake and management tool for Blink Network. Stakeholders submit Feature and Defect requests; Product Managers and Pod Reviewers triage, approve, and track them through to Jira and JSM.

---

## Repository structure

```
Product Intake/
├── backend/backend/          # FastAPI backend (Python 3.11)
│   ├── app/
│   │   ├── api/              # Route handlers (requests, workflow, thread, files, webhook, auth)
│   │   ├── models/           # SQLAlchemy models
│   │   ├── services/         # Jira, JSM, notification, pod routing services
│   │   └── workers/          # Celery tasks
│   ├── alembic/versions/     # Database migrations
│   ├── main.py               # App entry point
│   └── .env                  # Local environment variables (not committed)
└── OneDrive_2_20-05-2026/    # React / TypeScript frontend (Vite)
    ├── src/
    │   ├── pages/            # DashboardPage, MyRequestsPage, ReviewPage, SubmitPage, etc.
    │   ├── components/       # Shared UI components
    │   ├── hooks/            # useAuth, useRequests, useThread
    │   └── lib/              # api.ts, constants.ts, types.ts
    └── .env.local            # Local frontend env variables (not committed)
```

---

## Local development

### Prerequisites

- Python 3.11
- Node.js 20+ (via nvm)
- Redis (optional — Celery runs in eager mode without it)

### Backend

```bash
cd backend/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# Run migrations and start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI is available at `http://localhost:8000/docs` in local mode.

### Frontend

```bash
cd OneDrive_2_20-05-2026
npm install

# Copy and fill in environment variables
cp .env.example .env.local

npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## Environment variables

### Backend (`backend/backend/.env`)

| Variable | Description | Default |
|---|---|---|
| `ENVIRONMENT` | `local` / `staging` / `production` | `local` |
| `DATABASE_URL` | SQLite (`sqlite+aiosqlite:///./relay.db`) locally; Postgres in prod | — |
| `REDIS_URL` | Celery broker | `redis://localhost:6379/0` |
| `SKIP_AUTH` | Bypass JWT validation (local dev only) | `false` |
| `SKIP_AUTH_AS` | Mock role when `SKIP_AUTH=true`: `admin`, `pm`, `requestor` | `admin` |
| `CELERY_TASK_ALWAYS_EAGER` | Run Celery tasks inline without a broker | `false` |
| `JIRA_MOCK` | Return fake Jira tickets without calling the API | `false` |
| `JSM_MOCK` | Return fake JSM tickets without calling Service Desk API | `false` |
| `JIRA_BASE_URL` | Atlassian base URL | `https://blinkcharging.atlassian.net` |
| `JIRA_EMAIL` | Service account email for Jira API | — |
| `JIRA_API_TOKEN` | Jira API token | — |
| `JIRA_WEBHOOK_SECRET` | Secret used to verify incoming Jira webhooks | — |
| `JIRA_PROJECT_*` | Jira project key per pod (Charger, Driver, Revenue, Data, DevOps, Denali) | `REL` |
| `JSM_SERVICE_DESK_ID` | Numeric JSM service desk ID | — |
| `JSM_REQUEST_TYPE_ID` | Numeric JSM request type ID for "Tech Request" | — |
| `EMAIL_BACKEND` | `smtp` (local/Ethereal) or `graph` (production/Microsoft Graph) | `smtp` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | SMTP credentials (Ethereal for dev) | — |
| `FRONTEND_URL` | Used in email notification links | `http://localhost:5173` |
| `AZURE_KEY_VAULT_URI` | Key Vault URI — only needed in staging/production | — |

### Frontend (`OneDrive_2_20-05-2026/.env.local`)

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000` |
| `VITE_SKIP_AUTH` | Match backend `SKIP_AUTH` for local dev | `false` |
| `VITE_AZURE_CLIENT_ID` | Azure AD app (client) ID | — |
| `VITE_AZURE_TENANT_ID` | Azure AD tenant ID | — |

---

## Key concepts

### Roles

| Role | Capabilities |
|---|---|
| `Requestor` | Submit requests, view own requests, respond to info requests |
| `PodReviewer` | View all requests, update status |
| `ProductManager` | All reviewer permissions + approve/reject, export CSV |
| `Admin` | All permissions + admin endpoints |

### Request lifecycle

```
Submitted → InReview → AwaitingInfo ↔ InfoReceived
                    ↘ Approved → InProgress → Completed → Closed
                    ↘ Rejected
```

Approval creates a Jira implementation ticket. JSM customer-facing ticket is created at submission and kept in sync throughout.

### PODs

Requests are routed to one of six engineering pods: **Charger**, **Driver**, **Revenue**, **Data**, **DevOps**, **Denali**. Pod routing can be automatic (AI-assisted) or manual.

---

## API endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/requests` | Optional | Submit a new request |
| `GET` | `/api/requests` | Reviewer+ | List all requests (filterable) |
| `GET` | `/api/requests/export` | Reviewer+ | Download all requests as CSV |
| `GET` | `/api/requests/mine` | Any | List current user's requests |
| `GET` | `/api/requests/{id}` | Public | Get a single request |
| `PATCH` | `/api/requests/{id}` | Submitter / PM | Edit request fields |
| `PATCH` | `/api/requests/{id}/status` | Reviewer+ | Update status |
| `POST` | `/api/requests/{id}/approve` | PM+ | Approve + create Jira ticket |
| `POST` | `/api/requests/{id}/reject` | PM+ | Reject with reason |
| `POST` | `/api/requests/{id}/respond` | Public | Submit info response |
| `POST` | `/api/requests/{id}/clarify` | PM+ | Ask clarifying question |
| `GET/POST` | `/api/requests/{id}/messages` | Auth | Thread messages |
| `GET/POST` | `/api/requests/{id}/files` | Auth | Attachments |
| `POST` | `/api/webhook/jira` | HMAC | Jira status change webhook |
| `POST` | `/api/admin/backfill-jsm` | Admin | Queue JSM creation for all requests missing a ticket |

---

## Jira webhook setup

The webhook endpoint (`POST /api/webhook/jira`) syncs Jira status changes back into Relay and posts updates to JSM. Jira Cloud cannot reach `localhost`, so a public URL is required:

```bash
# Install ngrok
brew install ngrok/ngrok/ngrok
ngrok http 8000
```

Register the tunnel URL in Jira: **Project Settings → Webhooks → Create** with URL `https://<tunnel>.ngrok.io/api/webhook/jira`.

---

## Backfill utilities

```bash
# Create JSM tickets for all requests that don't have one
cd backend/backend
source venv/bin/activate
python backfill_jsm_tickets.py            # create
python backfill_jsm_tickets.py --dry-run  # preview only

# Link existing Jira ↔ JSM ticket pairs
python backfill_ticket_links.py
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy (async), Alembic, Celery, Pydantic v2 |
| Database | SQLite (local), PostgreSQL (prod) |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Tailwind CSS, shadcn/ui |
| Auth | Azure Active Directory (MSAL) |
| Integrations | Jira Cloud, Jira Service Management, Microsoft Graph (email), Teams webhooks |
| Hosting | Azure App Service + Azure Storage (attachments) |
