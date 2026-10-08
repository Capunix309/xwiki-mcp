"""Load wiki definitions and select one for each MCP tool call."""

from __future__ import annotations

import contextvars
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "wikis.toml"
ENV_PATH = ROOT / ".env"


def _load_wiki_data() -> dict:
    try:
        data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Missing wiki configuration: {CONFIG_PATH}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid {CONFIG_PATH.name}: {exc}") from None
    entries = data.get("wikis")
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("wikis.toml must contain one or more [[wikis]] tables.")
    for entry in entries:
        for field in ("id", "base_url", "wiki"):
            if not isinstance(entry.get(field), str):
                raise ValueError(f"Each [[wikis]] entry needs a string {field} field.")
        if "read_only" in entry and not isinstance(entry["read_only"], bool):
            raise ValueError(f"read_only must be true or false for wiki '{entry['id']}'.")
        for field in ("username_env", "password_env"):
            if field in entry and not isinstance(entry[field], str):
                raise ValueError(f"{field} must be a string for wiki '{entry['id']}'.")
    if not isinstance(data.get("default_wiki", ""), str):
        raise ValueError("default_wiki must be a string wiki id.")
    return data


_WIKI_DATA = _load_wiki_data()
_SECRET_KEYS = {
    key
    for entry in _WIKI_DATA.get("wikis", [])
    for key in (entry.get("username_env"), entry.get("password_env"))
    if key
}


def _load_env(path: Path) -> None:
    """Load only credential variables referenced by the wiki configuration."""
    if not path.exists():
        return
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number}; expected a credential assignment.")
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in _SECRET_KEYS:
            raise ValueError(f".env may contain credentials only; {key} is not referenced by wikis.toml.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_env(ENV_PATH)


@dataclass(frozen=True)
class WikiConfig:
    name: str
    base_url: str
    wiki: str
    read_only: bool
    username: str
    password: str
    username_env: str | None
    password_env: str | None


def _make_wiki(entry: dict) -> WikiConfig:
    username_env = entry.get("username_env")
    password_env = entry.get("password_env")
    return WikiConfig(
        name=entry.get("id", "").strip(),
        base_url=entry.get("base_url", "").strip().rstrip("/"),
        wiki=entry.get("wiki", "").strip(),
        read_only=entry.get("read_only", True),
        username=os.environ.get(username_env, "") if username_env else "",
        password=os.environ.get(password_env, "") if password_env else "",
        username_env=username_env,
        password_env=password_env,
    )


WIKIS = {wiki.name: wiki for wiki in map(_make_wiki, _WIKI_DATA.get("wikis", []))}
DEFAULT_WIKI = _WIKI_DATA.get("default_wiki", "")
_CURRENT: contextvars.ContextVar[WikiConfig | None] = contextvars.ContextVar(
    "xwiki_config", default=WIKIS.get(DEFAULT_WIKI)
)


def select_wiki(name: str) -> contextvars.Token[WikiConfig]:
    """Select a configured wiki for the current MCP call."""
    normalized = name.strip()
    if normalized not in WIKIS:
        choices = ", ".join(sorted(WIKIS)) or "none configured"
        raise ValueError(f"Unknown wiki '{name}'. Choose one of: {choices}.")
    return _CURRENT.set(WIKIS[normalized])


def current() -> WikiConfig:
    selected = _CURRENT.get()
    if selected is None:
        raise ValueError("Set default_wiki to the id of a configured wiki in wikis.toml.")
    return selected


def reset_wiki(token: contextvars.Token[WikiConfig | None]) -> None:
    _CURRENT.reset(token)


def validate_config() -> None:
    """Validate wiki definitions, permissions, and referenced credentials."""
    entries = _WIKI_DATA.get("wikis", [])
    if not entries:
        raise ValueError("Add at least one [[wikis]] entry to wikis.toml.")
    if len(WIKIS) != len(entries):
        raise ValueError("Every wiki in wikis.toml must have a unique id.")
    if DEFAULT_WIKI not in WIKIS:
        raise ValueError("default_wiki must match a configured wiki id in wikis.toml.")

    for settings in WIKIS.values():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", settings.name):
            raise ValueError(f"Invalid wiki id '{settings.name}'; use letters, numbers, '_' or '-'.")
        parsed = urlparse(settings.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Set a valid base_url for wiki '{settings.name}' in wikis.toml.")
        if not settings.wiki:
            raise ValueError(f"Set the XWiki wiki value for '{settings.name}' in wikis.toml.")
        if not isinstance(settings.read_only, bool):
            raise ValueError(f"read_only must be true or false for wiki '{settings.name}'.")
        for key in (settings.username_env, settings.password_env):
            if key and not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                raise ValueError(f"Invalid credential environment variable name for wiki '{settings.name}'.")
        if bool(settings.username_env) != bool(settings.password_env):
            raise ValueError(f"Configure both username_env and password_env for wiki '{settings.name}'.")
        if settings.username_env and (not settings.username or not settings.password):
            raise ValueError(f"Set both {settings.username_env} and {settings.password_env} in xwiki-mcp/.env.")


def rest_root() -> str:
    """Return the REST API root for the selected XWiki instance."""
    settings = current()
    parsed = urlparse(settings.base_url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/rest"):
        path += "/rest"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
