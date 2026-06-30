"""Tests for the worker's HTTP task handler."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_process_accepts_valid_payload(client):
    """POST /tasks/process should accept a job and return 200 immediately."""
    with patch("app.main._pool.submit") as mock_submit:
        resp = await client.post("/tasks/process", json={
            "transfer_id": "t-123",
            "session_id": "s-456",
            "file_id": "f-789",
            "title": "My Video",
            "privacy": "private",
        })
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
    mock_submit.assert_called_once()


async def test_process_defaults_privacy_to_private(client):
    """privacy field should default to private if omitted."""
    with patch("app.main._pool.submit") as mock_submit:
        resp = await client.post("/tasks/process", json={
            "transfer_id": "t-1",
            "session_id": "s-1",
            "file_id": "f-1",
        })
    assert resp.status_code == 200
    args = mock_submit.call_args[0]
    # args: (run_transfer, transfer_id, session_id, file_id, title, privacy)
    assert args[5] == "private"


async def test_process_rejects_missing_fields(client):
    resp = await client.post("/tasks/process", json={
        "session_id": "s-1",
        "file_id": "f-1",
        # missing transfer_id
    })
    assert resp.status_code == 422
