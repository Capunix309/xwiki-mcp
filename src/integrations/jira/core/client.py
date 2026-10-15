"""Small authenticated Jira REST client with bounded endpoint paths."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.shared import config


def _settings():
    settings = config.integration("jira")
    if not settings.username_env or not settings.password_env:
        raise ValueError("Configure Jira username_env and password_env in config.toml.")
    if not settings.username or not settings.password:
        raise ValueError(
            f"Set {settings.username_env} and {settings.password_env} in {config.ENV_PATH}."
        )
    return settings


def _path_url(path: str, params: dict[str, str] | None = None) -> str:
    """Build a URL for an absolute Jira REST resource path."""
    if not isinstance(path, str) or not path.startswith("/rest/"):
        raise ValueError("path must be a Jira REST path starting with /rest/.")
    if "?" in path or "#" in path or "\\" in path:
        raise ValueError("Pass query parameters separately; path cannot contain query, fragment, or backslash.")
    decoded = urllib.parse.unquote(path)
    if any(segment in {".", ".."} for segment in decoded.split("/")) or "\\" in decoded:
        raise ValueError("path cannot contain traversal segments.")
    safe_path = "/".join(urllib.parse.quote(urllib.parse.unquote(part), safe="-._~") for part in path.split("/"))
    settings = _settings()
    url = settings.base_url.rstrip("/") + safe_path
    if params:
        if not isinstance(params, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in params.items()):
            raise ValueError("params must be a mapping of string keys to string values.")
        url += "?" + urllib.parse.urlencode(params)
    return url


def request(method: str, path: str, params: dict[str, str] | None = None,
            body: dict[str, Any] | None = None) -> Any:
    """Send one authenticated request to a Jira REST resource."""
    settings = _settings()
    headers = {"Accept": "application/json"}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    token = base64.b64encode(f"{settings.username}:{settings.password}".encode()).decode("ascii")
    headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(_path_url(path, params), data=payload, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
            if not raw:
                return {"status": response.status}
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read(800).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Jira returned HTTP {exc.code}" + (f": {detail}" if detail else "")) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the Jira REST API: {exc.reason}") from None
