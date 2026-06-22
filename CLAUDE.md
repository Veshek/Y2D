# CLAUDE.md — Clipflow

Bulk-transfer videos from Google Drive to YouTube, server-side. Browser extension
(UI) → FastAPI backend (enqueues) → Cloud Tasks (queue) → worker (does the
transfer). Full setup, deployment plan, and architecture in `README.md` — read it
before starting.

## Architecture invariants — do NOT change without asking

- **Tokens are backend-only.** Google OAuth tokens live in Redis keyed by
  `session_id`. The extension only ever receives the opaque `session_id`.
- **The queue is Cloud Tasks.** Emulator locally, managed in prod. Do not
  build a custom queue service.
- **Redis is shared state:** `session_id → tokens` AND pub/sub channel
  `progress:{transfer_id}` powering SSE. Worker publishes; backend relays.
- **The worker is private in production** (`--no-allow-unauthenticated`).
  Only Cloud Tasks calls it via OIDC token.
- **Progress is SSE** fed by Redis pub/sub. Do not switch to polling.
- **Logging is structured JSON** via `app/logging_config.py` in both backend
  and worker. Always use `get_logger(__name__)` — never `print()` or the
  stdlib logger directly. Include `transfer_id` and `status` as fields so
  Cloud Monitoring log-based metrics work.

## Repo layout

```
extension/      React + Vite MV3 popup → builds to extension/dist/
backend/        FastAPI: OAuth, Drive listing, enqueue, SSE relay
  app/
  tests/
worker/         FastAPI: consumes jobs, Drive→YouTube transfer
  app/
  tests/
terraform/      All GCP infrastructure as code
  modules/
    cloud_run/
    redis/
    queue/
    monitoring/
  environments/
    staging/
    production/
.github/
  workflows/
    ci.yml      test every push/PR
    deploy.yml  build + deploy main to Cloud Run
```

## Commands

**Local dev:**
- `docker compose up --build` — starts all 5 services
- Backend: http://localhost:8000 (`/docs` for OpenAPI)
- Worker: http://localhost:8080
- No-emulator mode: set `QUEUE_BACKEND=http` on backend

**Tests:**
- Backend: `cd backend && pip install -r requirements-test.txt && pytest`
- Worker:  `cd worker  && pip install -r requirements-test.txt && pytest`
- Extension: `cd extension && npm install && npm test`

**Extension:**
- `cd extension && npm run dev` — watch build into `extension/dist/`
- Load `extension/dist/` as unpacked extension at `chrome://extensions`

**Terraform:**
- `cd terraform && terraform init -backend-config="bucket=YOUR_TFSTATE_BUCKET"`
- `terraform workspace select staging` (or `production`)
- `terraform plan -var-file=environments/staging/terraform.tfvars`
- `terraform apply -var-file=environments/staging/terraform.tfvars`

## Conventions

**Backend/worker:**
- Python 3.12, FastAPI, async for all I/O
- Config via `pydantic-settings` in `app/config.py` — never hardcode
- Structured logging: `from .logging_config import get_logger`
- New deps go in `requirements.txt` (prod) and `requirements-test.txt` (test)
- Backend and worker are independent — small duplication is fine

**Extension:**
- TypeScript, React function components + hooks, 2-space indent
- All backend calls through `src/api.ts`, all auth through `src/auth.ts`
- No HTML `<form>` tags — use onClick/onChange handlers

**Terraform:**
- One module per GCP resource type (`cloud_run`, `redis`, `queue`, `monitoring`)
- Environments via tfvars files, not workspaces
- All secrets go in Secret Manager — never in tfvars or env files committed to git

## Security rules (immutable)

- Never log OAuth tokens or `session_id` values
- Never put tokens or secrets in URL query params
- **TODO before any real users:** encrypt tokens at rest in Redis (Fernet +
  Secret Manager key) — currently plain JSON in `backend/app/store.py` and
  `worker/app/store.py`
- **TODO before any real users:** verify Cloud Tasks OIDC token in worker —
  marked `TODO(prod)` in `worker/app/main.py`
- Lock CORS to extension origin in production (currently `*`)

## Monitoring (GCP-native)

All monitoring is defined in `terraform/modules/monitoring/main.tf`:
- **Uptime check** on backend `/healthz` every 60s
- **Log-based metrics:** `clipflow/transfer_errors` and
  `clipflow/transfer_completions` — driven by `jsonPayload.status` fields
- **Alert policies:** backend down, transfer error rate > 5/10min, worker
  5xx > 10%, Redis memory > 80%
- **Dashboard:** transfer completions, errors, backend p95 latency, Redis memory

For alerts to work, the worker must log with `status` as a structured field:
```python
log.info("transfer complete", transfer_id=tid, status="done")
log.error("transfer failed", transfer_id=tid, status="error", error=str(e))
```

## Constraints

- **YouTube quota:** ~1600 units per upload, 10k/day default = ~6 uploads/day
  until quota increase is approved. Do not design flows that assume unlimited.
- **OAuth scopes** (Drive readonly + YouTube upload) require Google app
  verification before non-test users can sign in.
- **Worker timeout:** set to 900s (15 min) in Terraform. Large videos may
  need streaming download→upload rather than temp file buffering.

## Priorities (suggested order)

1. Get the full local stack running end-to-end on a real transfer
2. Token encryption + OIDC verification (the two security TODOs)
3. Per-video title editing UI (API already accepts `title`)
4. Persist `transfer_ids` to `chrome.storage.local` so SSE reconnects on
   popup reopen (extension `App.tsx` — ~15 lines)
5. Richer content-script UI injected into drive.google.com (the differentiator)
6. YouTube quota increase request (needed before any real user volume)

## Working agreement

- One item at a time, verify end-to-end before marking done
- Changes touching an architecture invariant → ask first
- All new backend/worker code needs tests in the corresponding `tests/` dir
- All new Terraform resources go in the appropriate module
