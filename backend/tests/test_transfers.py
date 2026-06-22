"""Tests for the /transfers endpoints."""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app import store


async def test_create_transfers_requires_auth(client):
    resp = await client.post("/transfers", json={"items": [
        {"file_id": "abc", "privacy": "private"}
    ]})
    assert resp.status_code == 401


async def test_create_transfers_enqueues_and_returns_ids(authed_client, fake_redis):
    """POST /transfers should enqueue one job per item and return transfer_ids."""
    with patch("app.main.queue.enqueue_transfer", new_callable=AsyncMock) as mock_enqueue:
        resp = await authed_client.post("/transfers", json={"items": [
            {"file_id": "file-1", "privacy": "private"},
            {"file_id": "file-2", "privacy": "public", "title": "My Video"},
        ]})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["transfer_ids"]) == 2
    assert mock_enqueue.call_count == 2

    # Each transfer should be stored in Redis as "queued"
    for tid in data["transfer_ids"]:
        raw = await fake_redis.get(f"transfer:{tid}")
        record = json.loads(raw)
        assert record["status"] == "queued"


async def test_create_transfers_rejects_empty_items(authed_client):
    resp = await authed_client.post("/transfers", json={"items": []})
    assert resp.status_code == 422


async def test_get_transfer_returns_record(authed_client, fake_redis):
    """GET /transfers/{id} should return the stored record."""
    tid = "test-transfer-123"
    record = {"id": tid, "status": "uploading", "progress": 55, "file_id": "f1", "title": "T", "privacy": "private"}
    await fake_redis.set(f"transfer:{tid}", json.dumps(record))

    resp = await authed_client.get(f"/transfers/{tid}")
    assert resp.status_code == 200
    assert resp.json()["progress"] == 55
    assert resp.json()["status"] == "uploading"


async def test_get_transfer_404_for_unknown(authed_client):
    resp = await authed_client.get("/transfers/does-not-exist")
    assert resp.status_code == 404


async def test_privacy_values_accepted(authed_client):
    """All three privacy values should be accepted."""
    with patch("app.main.queue.enqueue_transfer", new_callable=AsyncMock):
        for privacy in ("private", "unlisted", "public"):
            resp = await authed_client.post("/transfers", json={"items": [
                {"file_id": "f1", "privacy": privacy}
            ]})
            assert resp.status_code == 200, f"Failed for privacy={privacy}"


async def test_invalid_privacy_rejected(authed_client):
    resp = await authed_client.post("/transfers", json={"items": [
        {"file_id": "f1", "privacy": "secret"}
    ]})
    assert resp.status_code == 422
