"""Worker HTTP service.

Cloud Tasks (or the backend in `http` mode) POSTs a job to /tasks/process. We run
the transfer in a background thread so the HTTP call returns promptly; the queue
considers the task delivered, and progress flows to the client over Redis -> SSE.

In production this endpoint is a private Cloud Run service that only Cloud Tasks
can reach (via an OIDC token). Verify that token here using `expected_audience`.
"""
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from pydantic import BaseModel

from .transfer import run_transfer

app = FastAPI(title="Y2D Worker")
_pool = ThreadPoolExecutor(max_workers=4)


class TaskPayload(BaseModel):
    transfer_id: str
    session_id: str
    file_id: str
    title: str | None = None
    privacy: str = "private"


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.post("/tasks/process")
async def process(payload: TaskPayload) -> dict:
    # TODO(prod): verify the Cloud Tasks OIDC bearer token against expected_audience
    # before doing any work.
    _pool.submit(
        run_transfer,
        payload.transfer_id,
        payload.session_id,
        payload.file_id,
        payload.title,
        payload.privacy,
    )
    return {"accepted": True}
