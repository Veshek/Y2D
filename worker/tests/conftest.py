"""Shared fixtures for worker tests."""
import json
import pytest
import fakeredis
from unittest.mock import patch

import app.store as store_module


@pytest.fixture(autouse=True)
def fake_redis():
    """Replace worker's Redis client with an in-process fake."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    with patch.object(store_module, "_client", fake):
        yield fake


@pytest.fixture
def seeded_session(fake_redis):
    """Pre-seed a valid session with fake credentials."""
    session_id = "worker-test-session"
    fake_redis.set(
        f"session:{session_id}",
        json.dumps({
            "credentials": {
                "token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "fake-client-id",
                "client_secret": "fake-client-secret",
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            },
            "email": "test@example.com",
        }),
        ex=86400,
    )
    return session_id
