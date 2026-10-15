"""Load and refresh Google OAuth credentials stored in macOS Keychain."""

from __future__ import annotations

import json
import platform


KEYCHAIN_SERVICE = "mcp-tools.google-sheets"
KEYCHAIN_ACCOUNT = "automation"
KEYCHAIN_CLIENT_ACCOUNT = "oauth-client"


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _keychain():
    """Return the native macOS Keychain backend, refusing file-based fallbacks."""
    if platform.system() != "Darwin":
        raise RuntimeError("Google Sheets authorization requires macOS Keychain on this setup.")
    try:
        import keyring
    except ImportError:
        raise RuntimeError("Install MCP-tools dependencies before using Google Sheets automation.") from None
    backend = keyring.get_keyring()
    if not backend.__class__.__module__.startswith("keyring.backends.macOS"):
        raise RuntimeError("Python keyring is not using the macOS Keychain backend.")
    return keyring


def load_credentials():
    """Load or refresh a token saved by the local authorization flow."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise RuntimeError("Install MCP-tools dependencies before using Google Sheets automation.") from None

    keyring = _keychain()
    token = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    if not token:
        raise RuntimeError(
            f"Google Sheets has not been authorized yet. Run "
            "python -m src.integrations.automation.core.sheets.authorize."
        )
    try:
        credentials = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, credentials.to_json())
        if not credentials.valid:
            raise RuntimeError("The saved Google authorization is expired or revoked; authorize again locally.")
        return credentials
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError(
            "Could not load Google Sheets authorization; rerun the local authorization command."
        ) from None
