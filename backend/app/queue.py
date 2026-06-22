"""Enqueue a transfer job for the worker to process.

Two backends:
  * cloud_tasks - creates a Cloud Tasks HTTP task targeting the worker. Works
    against real GCP or a local emulator (set CLOUD_TASKS_EMULATOR_HOST). In prod
    the task carries an OIDC token so the worker (a private Cloud Run service) can
    authenticate the call.
  * http        - POSTs straight to the worker. Zero infra; handy if you don't want
    the emulator running locally. No retries/backoff, so not for production.
"""
import json

import httpx

from .config import get_settings

_settings = get_settings()


def _cloud_tasks_client():
    from google.cloud import tasks_v2

    if _settings.cloud_tasks_emulator_host:
        # Point the client at the emulator over an insecure gRPC channel.
        import grpc
        from google.cloud.tasks_v2.services.cloud_tasks.transports import (
            CloudTasksGrpcTransport,
        )

        channel = grpc.insecure_channel(_settings.cloud_tasks_emulator_host)
        transport = CloudTasksGrpcTransport(channel=channel)
        return tasks_v2.CloudTasksClient(transport=transport)
    return tasks_v2.CloudTasksClient()


def ensure_queue() -> None:
    """Create the queue if it doesn't exist. Safe to call on startup."""
    if _settings.queue_backend != "cloud_tasks":
        return
    from google.api_core.exceptions import AlreadyExists
    from google.cloud import tasks_v2

    client = _cloud_tasks_client()
    parent = client.common_location_path(_settings.gcp_project, _settings.gcp_location)
    queue_path = client.queue_path(
        _settings.gcp_project, _settings.gcp_location, _settings.queue_name
    )
    try:
        client.create_queue(parent=parent, queue=tasks_v2.Queue(name=queue_path))
    except AlreadyExists:
        pass
    except Exception:
        # The emulator may pre-declare the queue; ignore wiring errors here.
        pass


async def enqueue_transfer(payload: dict) -> None:
    if _settings.queue_backend == "http":
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(f"{_settings.worker_url}/tasks/process", json=payload)
        return

    from google.cloud import tasks_v2

    client = _cloud_tasks_client()
    queue_path = client.queue_path(
        _settings.gcp_project, _settings.gcp_location, _settings.queue_name
    )

    http_request = tasks_v2.HttpRequest(
        http_method=tasks_v2.HttpMethod.POST,
        url=f"{_settings.worker_url}/tasks/process",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode(),
    )
    # In production, attach an OIDC token so Cloud Tasks can call a private worker.
    if _settings.worker_invoker_sa:
        http_request.oidc_token = tasks_v2.OidcToken(
            service_account_email=_settings.worker_invoker_sa,
            audience=_settings.worker_url,
        )

    client.create_task(
        parent=queue_path,
        task=tasks_v2.Task(http_request=http_request),
    )
