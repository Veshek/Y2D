"""Tests for the OAuth flow endpoints."""
import pytest
from unittest.mock import patch, MagicMock

from app import store


async def test_login_redirects_to_google(client):
    """GET /auth/login should redirect to a Google accounts URL."""
    with patch("app.main.auth.build_authorization_url", return_value="https://accounts.google.com/fake"):
        resp = await client.get(
            "/auth/login",
            params={"ext_redirect": "https://abc123.chromiumapp.org/"},
            follow_redirects=False,
        )
    assert resp.status_code == 307
    assert "accounts.google.com" in resp.headers["location"]


async def test_login_saves_state_to_redis(client, fake_redis):
    """The state token should be persisted so the callback can verify it."""
    with patch("app.main.auth.build_authorization_url", return_value="https://accounts.google.com/fake?state=teststate"):
        await client.get(
            "/auth/login",
            params={"ext_redirect": "https://abc123.chromiumapp.org/"},
            follow_redirects=False,
        )
    # At least one oauth_state key should exist
    keys = await fake_redis.keys("oauth_state:*")
    assert len(keys) == 1


async def test_callback_rejects_invalid_state(client):
    """Callback with an unknown state should return 400."""
    resp = await client.get(
        "/auth/callback",
        params={"code": "fake-code", "state": "nonexistent-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


async def test_callback_stores_session_and_redirects(client, fake_redis):
    """Valid callback should store a session and redirect to the extension."""
    ext_redirect = "https://abc123.chromiumapp.org/"
    state = "valid-state-token"
    await store.save_oauth_state(state, ext_redirect)

    fake_creds = {
        "token": "access-token",
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        "expiry": None,
    }
    with patch("app.main.auth.exchange_code", return_value=fake_creds), \
         patch("app.main.build") as mock_build:
        mock_build.return_value.userinfo.return_value.get.return_value.execute.return_value = {
            "email": "test@example.com"
        }
        resp = await client.get(
            "/auth/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )

    assert resp.status_code == 307
    location = resp.headers["location"]
    assert ext_redirect in location
    assert "session_id=" in location

    # Session should be persisted in Redis
    sessions = await fake_redis.keys("session:*")
    assert len(sessions) == 1


async def test_me_requires_session(client):
    """GET /me without a session header should return 401."""
    resp = await client.get("/me")
    assert resp.status_code == 401


async def test_me_returns_email(authed_client):
    """GET /me with a valid session should return the user's email."""
    resp = await authed_client.get("/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"
