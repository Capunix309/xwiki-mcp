"""Load XWiki endpoints from the repository-wide MCP configuration."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from src.shared import config as shared_config


_XWIKI_DATA = shared_config.CONFIG["integrations"]["xwiki"]
_XWIKI_SETTINGS = shared_config.integration("xwiki")


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
    return WikiConfig(
        name=entry["id"].strip(),
        base_url=_XWIKI_SETTINGS.base_url.rstrip("/"),
        wiki=entry["wiki"].strip(),
        read_only=entry.get("read_only", True),
        username=_XWIKI_SETTINGS.username,
        password=_XWIKI_SETTINGS.password,
        username_env=_XWIKI_SETTINGS.username_env,
        password_env=_XWIKI_SETTINGS.password_env,
    )


WIKIS = {wiki.name: wiki for wiki in map(_make_wiki, _XWIKI_DATA.get("wikis", []))}
DEFAULT_WIKI = _XWIKI_DATA.get("default_wiki", "")
_CURRENT: contextvars.ContextVar[WikiConfig | None] = contextvars.ContextVar(
    "xwiki_config", default=WIKIS.get(DEFAULT_WIKI)
)


def select_wiki(name: str) -> contextvars.Token[WikiConfig | None]:
    """Select a configured wiki for the current MCP call."""
    normalized = name.strip()
    if normalized not in WIKIS:
        choices = ", ".join(sorted(WIKIS)) or "none configured"
        raise ValueError(f"Unknown wiki '{name}'. Choose one of: {choices}.")
    return _CURRENT.set(WIKIS[normalized])


def current() -> WikiConfig:
    selected = _CURRENT.get()
    if selected is None:
        raise ValueError("Set integrations.xwiki.default_wiki in config.toml.")
    return selected


def reset_wiki(token: contextvars.Token[WikiConfig | None]) -> None:
    _CURRENT.reset(token)


def validate_config() -> None:
    """Validate the shared configuration and XWiki endpoint."""
    shared_config.validate_config()
    if not WIKIS:
        raise ValueError("Add at least one wiki to integrations.xwiki.wikis in config.toml.")
    for settings in WIKIS.values():
        if not settings.name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Invalid wiki id '{settings.name}'; use letters, numbers, '_' or '-'.")
        parsed = urlparse(settings.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Set a valid shared.base_url for wiki '{settings.name}'.")
        if not settings.wiki:
            raise ValueError(f"Set a XWiki wiki name for '{settings.name}' in config.toml.")


def rest_root() -> str:
    """Return the REST API root for the selected XWiki instance."""
    settings = current()
    parsed = urlparse(settings.base_url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/rest"):
        path += "/rest"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
