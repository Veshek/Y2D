"""Y2D backend API.

Responsibilities:
  * Run the Google OAuth dance server-side and hand the extension a session_id.
  * Accept transfer requests and enqueue one job per video.
  * Stream per-transfer progress to the extension over SSE (fed by the worker
    via Redis pub/sub).

Note: Drive file listing is intentionally absent. The browser extension's
content script reads file IDs directly from the drive.google.com DOM, so
no Drive list API call (or scope) is needed for selection.
"""
import secrets
from urllib.parse import urlencode

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as redis

from . import auth, queue, store
from .config import get_settings
from .models import CreateTransfersRequest

settings = get_settings()
app = FastAPI(title="Y2D API")

# The extension's popup is a chrome-extension:// origin. Allowing all origins keeps
# local dev simple; lock this down to your extension id for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pubsub_redis = redis.from_url(settings.redis_url, decode_responses=True)


@app.on_event("startup")
async def _startup() -> None:
    queue.ensure_queue()


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


# --- Auth -------------------------------------------------------------------
@app.get("/auth/login")
async def login(ext_redirect: str):
    """Kick off OAuth. `ext_redirect` is the extension's chromiumapp.org URL that
    chrome.identity.launchWebAuthFlow is watching for."""
    state = secrets.token_urlsafe(24)
    await store.save_oauth_state(state, ext_redirect)
    return RedirectResponse(auth.build_authorization_url(state))


@app.get("/auth/callback")
async def callback(code: str, state: str):
    ext_redirect = await store.pop_oauth_state(state)
    if not ext_redirect:
        raise HTTPException(400, "Invalid or expired OAuth state")

    creds = auth.exchange_code(code)

    # Identify the user (nice for the UI; not required).
    email = None
    try:
        c = Credentials(**{k: creds[k] for k in
                           ("token", "refresh_token", "token_uri",
                            "client_id", "client_secret", "scopes")})
        info = build("oauth2", "v2", credentials=c).userinfo().get().execute()
        email = info.get("email")
    except Exception:
        pass

    session_id = secrets.token_urlsafe(32)
    await store.save_session(session_id, {"credentials": creds, "email": email})

    # Hand the session_id back to the extension via URL fragment (not logged by
    # servers, and read client-side by launchWebAuthFlow).
    sep = "&" if "?" in ext_redirect else "#"
    return RedirectResponse(f"{ext_redirect}{sep}{urlencode({'session_id': session_id})}")


async def _require_session(x_session_id: str | None) -> dict:
    if not x_session_id:
        raise HTTPException(401, "Missing X-Session-Id")
    session = await store.get_session(x_session_id)
    if not session:
        raise HTTPException(401, "Unknown or expired session")
    return session


def _credentials_from_session(session: dict) -> Credentials:
    c = session["credentials"]
    return Credentials(**{k: c[k] for k in
                          ("token", "refresh_token", "token_uri",
                           "client_id", "client_secret", "scopes")})


@app.get("/me")
async def me(x_session_id: str | None = Header(default=None)):
    session = await _require_session(x_session_id)
    return {"email": session.get("email")}


# --- Transfers --------------------------------------------------------------
@app.post("/transfers")
async def create_transfers(
    body: CreateTransfersRequest,
    x_session_id: str | None = Header(default=None),
):
    await _require_session(x_session_id)
    created = []
    for item in body.items:
        transfer_id = secrets.token_urlsafe(16)
        record = {
            "id": transfer_id,
            "file_id": item.file_id,
            "title": item.title or "",
            "privacy": item.privacy.value,
            "status": "queued",
            "progress": 0,
        }
        await store.set_transfer(transfer_id, record)
        await queue.enqueue_transfer({
            "transfer_id": transfer_id,
            "session_id": x_session_id,
            "file_id": item.file_id,
            "title": item.title,
            "privacy": item.privacy.value,
        })
        created.append(transfer_id)
    return {"transfer_ids": created}


@app.get("/transfers/{transfer_id}")
async def get_transfer(transfer_id: str):
    record = await store.get_transfer(transfer_id)
    if not record:
        raise HTTPException(404, "Unknown transfer")
    return record


@app.get("/transfers/{transfer_id}/events")
async def transfer_events(transfer_id: str, request: Request):
    """SSE stream of progress events for one transfer. The worker publishes to the
    Redis channel `progress:{transfer_id}`; we relay each message to the client."""
    channel = f"progress:{transfer_id}"

    async def event_generator():
        # Send the current snapshot immediately so late subscribers aren't blank.
        snapshot = await store.get_transfer(transfer_id)
        if snapshot:
            yield {"event": "progress", "data": __import__("json").dumps(snapshot)}

        pubsub = _pubsub_redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message.get("type") != "message":
                    continue
                yield {"event": "progress", "data": message["data"]}
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return EventSourceResponse(event_generator())
