"""Application configuration, loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Google OAuth ---
    google_client_id: str = ""
    google_client_secret: str = ""
    # Public URL of THIS backend's callback. Must be registered as an authorized
    # redirect URI in the Google Cloud console. Locally this is the host-mapped port.
    oauth_redirect_uri: str = "http://localhost:8000/auth/callback"
    oauth_scopes: list[str] = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        # drive.readonly is used by the worker to download file bytes.
        # File *listing/selection* is done by the content script reading the
        # Drive DOM — no API call needed there.
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/youtube.upload",
    ]

    # --- Shared store ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Queue ---
    # "cloud_tasks" (real or emulator) or "http" (POST straight to the worker; handy
    # for a zero-dependency local run).
    queue_backend: str = "cloud_tasks"
    worker_url: str = "http://worker:8080"
    gcp_project: str = "y2d-local"
    gcp_location: str = "us-central1"
    queue_name: str = "transfers"
    # When set, the backend talks to a Cloud Tasks emulator instead of real GCP.
    cloud_tasks_emulator_host: str = ""
    # Service account email Cloud Tasks uses to mint an OIDC token when calling the
    # worker in production. Leave blank locally.
    worker_invoker_sa: str = ""

    session_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days


@lru_cache
def get_settings() -> Settings:
    return Settings()
