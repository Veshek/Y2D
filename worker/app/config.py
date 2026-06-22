"""Worker configuration."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    # Verify Cloud Tasks OIDC tokens in production (audience = the worker's URL).
    # Left blank locally where the worker is called directly.
    expected_audience: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
