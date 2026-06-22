"""Google OAuth: build consent URLs and exchange auth codes for tokens.

Tokens never leave the backend. The extension only ever receives an opaque
session_id, which maps to the stored tokens in Redis.
"""
from google_auth_oauthlib.flow import Flow

from .config import get_settings

_settings = get_settings()


def _client_config() -> dict:
    return {
        "web": {
            "client_id": _settings.google_client_id,
            "client_secret": _settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_settings.oauth_redirect_uri],
        }
    }


def build_authorization_url(state: str) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=_settings.oauth_scopes)
    flow.redirect_uri = _settings.oauth_redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",        # ask for a refresh token...
        include_granted_scopes="true",
        prompt="consent",             # ...and force it to be returned every time
        state=state,
    )
    return auth_url


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for credentials, returned as a plain dict."""
    flow = Flow.from_client_config(_client_config(), scopes=_settings.oauth_scopes)
    flow.redirect_uri = _settings.oauth_redirect_uri
    flow.fetch_token(code=code)
    c = flow.credentials
    return {
        "token": c.token,
        "refresh_token": c.refresh_token,
        "token_uri": c.token_uri,
        "client_id": c.client_id,
        "client_secret": c.client_secret,
        "scopes": list(c.scopes or []),
        "expiry": c.expiry.isoformat() if c.expiry else None,
    }
