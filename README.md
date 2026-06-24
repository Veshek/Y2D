# Y2D

Bulk-transfer videos from Google Drive to YouTube — server-side, so users never
download-then-reupload large files. A browser extension is the UI; a FastAPI
backend enqueues jobs; a worker does the actual Drive → YouTube transfer.

## Architecture

```
┌─────────────┐   HTTPS    ┌──────────┐  enqueue   ┌─────────────┐  push   ┌────────┐
│  extension  │ ─────────► │ backend  │ ─────────► │ Cloud Tasks │ ──────► │ worker │
│ (React/MV3) │            │(FastAPI) │            │ (the queue) │         │(FastAPI)│
└─────────────┘            └────┬─────┘            └─────────────┘         └───┬────┘
       ▲                        │                                              │
       │   SSE progress         │            Redis (tokens + pub/sub)          │
       └────────────────────────┴──────────────────────────────────────────────┘
                                            Drive ⇣        ⇡ YouTube
```

- **extension/** — React + Vite MV3 popup. Runs OAuth via `chrome.identity`, lists
  Drive videos, lets you pick privacy (private / unlisted / public), and shows live
  per-video progress over SSE.
- **backend/** — FastAPI. Owns the OAuth flow (tokens never reach the extension —
  it only gets an opaque `session_id`), lists Drive videos, enqueues one job per
  video, and relays worker progress to the extension via SSE.
- **worker/** — FastAPI. Receives pushed jobs, downloads from Drive, resumable-
  uploads to YouTube, and publishes progress to Redis.
- **Cloud Tasks** is the queue. You don't write it — it's managed in production and
  an emulator container locally. Same code path both ways.
- **Redis** is shared state: the `session_id → tokens` map (the worker needs the
  tokens too) and the pub/sub channel that powers SSE across services.

## Local development

1. **Create a Google OAuth client** (Google Cloud console → APIs & Services →
   Credentials → Create OAuth client → type **Web application**):
   - Authorized redirect URI: `http://localhost:8000/auth/callback`
   - Enable the **Google Drive API** and **YouTube Data API v3** for the project.
2. `cp .env.example .env` and paste in your client id/secret.
3. `docker compose up --build`
   - backend → http://localhost:8000 (docs at `/docs`)
   - worker → http://localhost:8080
   - extension builds into `extension/dist/`
4. **Load the extension:** Chrome → `chrome://extensions` → enable *Developer mode*
   → *Load unpacked* → select `extension/dist`. Copy the extension id Chrome
   assigns; its OAuth redirect is `https://<id>.chromiumapp.org/`, handled
   automatically by `chrome.identity`.

> Don't want the emulator? Set `QUEUE_BACKEND=http` on the backend and it POSTs jobs
> straight to the worker — no queue infra, but no retries either.

## Deployment (Google Cloud)

This is the plan I'd recommend for the target you described:

| Piece          | Service                          | Why |
|----------------|----------------------------------|-----|
| backend        | **Cloud Run** (public)           | Scales to zero; the extension calls it directly. |
| worker         | **Cloud Run** (private)          | Only Cloud Tasks should reach it. |
| queue          | **Cloud Tasks** (managed)        | Replaces the emulator; gives retries + backoff. |
| shared state   | **Memorystore (Redis)**          | Token store + SSE pub/sub. |
| images         | **Artifact Registry**            | Where CI pushes container images. |
| secrets        | **Secret Manager**               | OAuth client secret, Redis auth. |
| CI/CD          | **GitHub Actions**               | Build → push → deploy on merge to `main`. |

A few specifics worth knowing up front:

- **Worker auth.** The worker is deployed `--no-allow-unauthenticated`. Cloud Tasks
  calls it with an **OIDC token** minted by a dedicated service account (set
  `WORKER_INVOKER_SA` on the backend, and grant that SA `roles/run.invoker` on the
  worker). The worker should verify the token's audience before doing work — there's
  a `TODO(prod)` marking exactly where.
- **No JSON keys in CI.** `deploy.yml` uses **Workload Identity Federation**: GitHub
  exchanges its OIDC token for short-lived GCP credentials. You set up a workload
  identity pool + provider once, then fill in the repo variables listed at the top
  of `deploy.yml`.
- **Terminology note:** GitHub *is* your version control (the Git repo). GitHub
  *Actions* is the CI/CD that builds and ships on each push. The two workflows here
  are `ci.yml` (validate every push/PR) and `deploy.yml` (ship `main`).

## SECURITY — read before going past local

- **Tokens at rest.** Right now sessions/tokens are stored in Redis as plain JSON.
  Before production, encrypt them (e.g. Fernet with a key from Secret Manager) or
  store refresh tokens in Secret Manager and keep only short-lived state in Redis.
- **CORS.** The backend currently allows all origins for dev. Lock it to your
  extension id (`chrome-extension://<id>`) in production.
- **YouTube quota.** A video upload costs ~1600 units against the default 10,000/day
  YouTube Data API quota — i.e. only a handful of uploads/day until you request a
  quota increase. Plan the launch around that.
- **OAuth verification.** The Drive + YouTube scopes are "sensitive/restricted," so
  Google requires app verification before you can serve users outside your test list.

## Next steps

- The extension UI here is a minimal popup that exercises the whole pipeline. The
  product vision is a richer UI injected into drive.google.com via a content script
  with per-video title editing — that's the natural next build.
- Add token encryption and OIDC verification (the two `TODO`s) before any real users.
