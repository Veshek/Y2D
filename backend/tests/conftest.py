"""Shared pytest fixtures for backend tests."""
import pytest
import fakeredis.aioredis
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
import app.store as store_module


@pytest.fixture(autouse=True)
def fake_redis():
    """Replace the real Redis client with an in-process fake for every test."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch.object(store_module, "_client", fake):
        yield fake


@pytest.fixture
async def client():
    """HTTPX async test client wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def valid_session_id():
    return "test-session-id-abc123"


@pytest.fixture
async def authed_client(client, fake_redis, valid_session_id):
    """Client with a pre-seeded session in fake Redis."""
    import json
    session_data = {
        "credentials": {
            "token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake-client-id",
            "client_secret": "fake-client-secret",
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        },
        "email": "test@example.com",
    }
    await fake_redis.set(
        f"session:{valid_session_id}",
        json.dumps(session_data),
        ex=86400,
    )
    client.headers["X-Session-Id"] = valid_session_id
    return client
