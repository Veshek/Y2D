"""Redis-backed shared state: OAuth tokens, OAuth state, transfer status.

Both the backend and the worker read/write here. Tokens are the sensitive bit —
see the SECURITY note in the README: in production these should be encrypted at
rest (e.g. Fernet with a key from Secret Manager) rather than stored as plain JSON.
"""
import json
from typing import Any, Optional

import redis.asyncio as redis

from .config import get_settings

_settings = get_settings()
_client = redis.from_url(_settings.redis_url, decode_responses=True)


# --- OAuth "state" (CSRF) ---------------------------------------------------
async def save_oauth_state(state: str, ext_redirect: str) -> None:
    await _client.set(f"oauth_state:{state}", ext_redirect, ex=600)


async def pop_oauth_state(state: str) -> Optional[str]:
    key = f"oauth_state:{state}"
    value = await _client.get(key)
    if value is not None:
        await _client.delete(key)
    return value


# --- Sessions / tokens ------------------------------------------------------
async def save_session(session_id: str, data: dict[str, Any]) -> None:
    await _client.set(
        f"session:{session_id}",
        json.dumps(data),
        ex=_settings.session_ttl_seconds,
    )


async def get_session(session_id: str) -> Optional[dict[str, Any]]:
    raw = await _client.get(f"session:{session_id}")
    return json.loads(raw) if raw else None


# --- Transfer status --------------------------------------------------------
async def set_transfer(transfer_id: str, data: dict[str, Any]) -> None:
    await _client.set(f"transfer:{transfer_id}", json.dumps(data), ex=86400)


async def get_transfer(transfer_id: str) -> Optional[dict[str, Any]]:
    raw = await _client.get(f"transfer:{transfer_id}")
    return json.loads(raw) if raw else None
