"""Import a Google OAuth client into Keychain and authorize Sheets access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .auth import (
    KEYCHAIN_ACCOUNT,
    KEYCHAIN_CLIENT_ACCOUNT,
    KEYCHAIN_SERVICE,
    SCOPES,
    _keychain,
)


def _read_client_config(path: Path) -> dict[str, Any]:
    """Read and validate the installed-app JSON downloaded from Google Cloud."""
    try:
        client_config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("Could not read a valid OAuth client JSON file from the supplied path.") from None
    if not isinstance(client_config, dict) or not isinstance(client_config.get("installed"), dict):
        raise ValueError("The supplied JSON must be a Google OAuth Desktop app client.")
    installed = client_config["installed"]
    if not installed.get("client_id") or not installed.get("auth_uri") or not installed.get("token_uri"):
        raise ValueError("The OAuth Desktop app JSON is missing required client settings.")
    return client_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a Google OAuth Desktop client into macOS Keychain and authorize Sheets access."
    )
    parser.add_argument(
        "client_json",
        nargs="?",
        type=Path,
        help="path to the downloaded OAuth Desktop app JSON; optional after the first import",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Authorize from a supplied client JSON or the copy already in Keychain."""
    args = _parser().parse_args(argv)
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise SystemExit("Install MCP-tools dependencies first with: pip install -r requirements.txt") from None

    keyring = _keychain()
    source_path = args.client_json.expanduser().resolve() if args.client_json else None
    if source_path:
        try:
            client_config = _read_client_config(source_path)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_CLIENT_ACCOUNT, json.dumps(client_config))
    else:
        saved_config = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_CLIENT_ACCOUNT)
        if not saved_config:
            raise SystemExit(
                "Pass the downloaded OAuth Desktop app JSON path the first time; "
                "after importing it, the argument is optional."
            )
        try:
            client_config = json.loads(saved_config)
        except json.JSONDecodeError:
            raise SystemExit("The OAuth client entry in Keychain is invalid; import the JSON file again.") from None

    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        credentials = flow.run_local_server(port=0, open_browser=True)
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, credentials.to_json())
    except Exception:
        raise SystemExit("Google authorization failed. Check the OAuth client setup and retry.") from None

    source_removed = False
    if source_path:
        try:
            source_path.unlink()
            source_removed = True
        except OSError:
            pass

    print("Google Sheets authorization complete. The client and refreshable token are stored in macOS Keychain.")
    if source_path and source_removed:
        print("The imported OAuth JSON file was removed from its original location.")
    elif source_path:
        print("Remove the downloaded OAuth JSON file manually; Keychain now has the stored client configuration.")


if __name__ == "__main__":
    main()
