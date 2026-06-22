"""Worker's view of the shared Redis store.

Reads sessions written by the backend, and writes transfer status + publishes
progress events that the backend's SSE endpoint relays to the extension.
"""
import json
from typing import Any, Optional

import redis

from .config import get_settings

_settings = get_settings()
_client = redis.from_url(_settings.redis_url, decode_responses=True)


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    raw = _client.get(f"session:{session_id}")
    return json.loads(raw) if raw else None


def update_transfer(transfer_id: str, **fields: Any) -> dict[str, Any]:
    raw = _client.get(f"transfer:{transfer_id}")
    record = json.loads(raw) if raw else {"id": transfer_id}
    record.update(fields)
    _client.set(f"transfer:{transfer_id}", json.dumps(record), ex=86400)
    # Notify any SSE subscribers.
    _client.publish(f"progress:{transfer_id}", json.dumps(record))
    return record
