"""Environment configuration for one XWiki MCP connection."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def _load_env(path: Path) -> None:
    """Load KEY=value settings without replacing environment variables."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_env(Path(__file__).resolve().parents[2] / ".env")

BASE_URL = os.environ.get("XWIKI_BASE_URL", "").strip().rstrip("/")
WIKI = os.environ.get("XWIKI_WIKI", "xwiki").strip()
USERNAME = os.environ.get("XWIKI_USERNAME", "")
PASSWORD = os.environ.get("XWIKI_PASSWORD", "")
READ_ONLY = os.environ.get("XWIKI_READ_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"}


def validate_config() -> None:
    """Validate required connection settings before the server starts."""
    parsed = urlparse(BASE_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Set XWIKI_BASE_URL to an absolute http:// or https:// URL in xwiki-mcp/.env.")
    if not WIKI:
        raise ValueError("XWIKI_WIKI cannot be empty.")
    if bool(USERNAME) != bool(PASSWORD):
        raise ValueError("Set both XWIKI_USERNAME and XWIKI_PASSWORD, or leave both empty.")


def rest_root() -> str:
    """Return the REST API root for the configured XWiki instance."""
    validate_config()
    parsed = urlparse(BASE_URL)
    path = parsed.path.rstrip("/")
    if not path.endswith("/rest"):
        path += "/rest"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
