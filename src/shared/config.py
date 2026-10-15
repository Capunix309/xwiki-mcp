"""Read the single repository configuration and its referenced credentials."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.toml"
ENV_PATH = ROOT / ".env"


def _read_config(path: Path = CONFIG_PATH) -> dict:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Missing central configuration: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid {path.name}: {exc}") from None

    shared = data.get("shared", {})
    if not isinstance(shared, dict) or not isinstance(shared.get("base_url"), str):
        raise ValueError("[shared] must define a string base_url.")
    parsed = urlparse(shared["base_url"].rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("shared.base_url must be a valid HTTP(S) origin or base URL.")

    tools = data.get("tools", {})
    if not isinstance(tools, dict):
        raise ValueError("[tools] must be a table.")
    for setting, default in (("expose_write", True), ("expose_destructive", False)):
        if not isinstance(tools.get(setting, default), bool):
            raise ValueError(f"[tools].{setting} must be true or false.")

    integrations = data.get("integrations")
    if not isinstance(integrations, dict):
        raise ValueError("config.toml must define [integrations.xwiki] and [integrations.jira].")
    for name in ("xwiki", "jira"):
        entry = integrations.get(name)
        if not isinstance(entry, dict):
            raise ValueError(f"Missing [integrations.{name}] configuration.")
        if not isinstance(entry.get("enabled"), bool):
            raise ValueError(f"integrations.{name}.enabled must be true or false.")
        api_path = entry.get("api_path", "")
        if not isinstance(api_path, str) or (api_path and (not api_path.startswith("/") or ".." in api_path.split("/"))):
            raise ValueError(f"integrations.{name}.api_path must be an absolute path without '..'.")
        for field in ("username_env", "password_env"):
            value = entry.get(field)
            if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", value)):
                raise ValueError(f"integrations.{name}.{field} must be an environment variable name.")
        if bool(entry.get("username_env")) != bool(entry.get("password_env")):
            raise ValueError(f"Configure both credential environment names for {name}.")

    jira_projects = integrations["jira"].get("projects", [])
    if not isinstance(jira_projects, list) or any(not isinstance(item, dict) for item in jira_projects):
        raise ValueError("integrations.jira.projects must be an array of tables.")
    project_ids = [item.get("id") for item in jira_projects]
    project_keys = [item.get("key") for item in jira_projects]
    if any(not isinstance(value, str) or not value for value in project_ids):
        raise ValueError("Every Jira project needs a unique non-empty id.")
    if len(project_ids) != len(set(project_ids)):
        raise ValueError("Jira project ids must be unique.")
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", value) for value in project_keys):
        raise ValueError("Every Jira project key must use uppercase letters, digits, or underscores.")
    if len(project_keys) != len({value.casefold() for value in project_keys}):
        raise ValueError("Jira project keys must be unique.")
    for item in jira_projects:
        if not isinstance(item.get("read_only", True), bool):
            raise ValueError(f"read_only must be true or false for Jira project '{item['id']}'.")

    xwiki = integrations["xwiki"]
    wikis = xwiki.get("wikis", [])
    if not isinstance(wikis, list) or any(not isinstance(item, dict) for item in wikis):
        raise ValueError("integrations.xwiki.wikis must be an array of tables.")
    if xwiki["enabled"] and not wikis:
        raise ValueError("Add at least one wiki when the XWiki integration is enabled.")
    ids = [item.get("id") for item in wikis]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Every XWiki wiki needs a unique non-empty id.")
    for item in wikis:
        if not isinstance(item.get("wiki"), str) or not item["wiki"]:
            raise ValueError(f"Wiki '{item.get('id')}' needs a XWiki wiki name.")
        if not isinstance(item.get("read_only", True), bool):
            raise ValueError(f"read_only must be true or false for wiki '{item.get('id')}'.")
    default_wiki = xwiki.get("default_wiki", "")
    if xwiki["enabled"] and default_wiki not in ids:
        raise ValueError("integrations.xwiki.default_wiki must match a configured wiki id.")

    automation = integrations.get("automation", {"enabled": False})
    if not isinstance(automation, dict) or not isinstance(automation.get("enabled", False), bool):
        raise ValueError("integrations.automation.enabled must be true or false.")
    if automation.get("enabled", False):
        if not integrations["jira"]["enabled"]:
            raise ValueError("The automation integration requires Jira to be enabled.")
        project_id = automation.get("jira_project")
        if not isinstance(project_id, str) or project_id not in project_ids:
            raise ValueError("integrations.automation.jira_project must match a configured Jira project id.")
        board_id = automation.get("board_id")
        if isinstance(board_id, bool) or not isinstance(board_id, int) or board_id <= 0:
            raise ValueError("integrations.automation.board_id must be a positive integer.")
        spreadsheet_url = automation.get("spreadsheet_url")
        parsed_sheet = urlparse(spreadsheet_url) if isinstance(spreadsheet_url, str) else None
        if (not parsed_sheet or parsed_sheet.netloc not in {"docs.google.com", "sheets.google.com"}
                or not re.fullmatch(r"/spreadsheets/d/[A-Za-z0-9_-]+(?:/.*)?", parsed_sheet.path)):
            raise ValueError("Set integrations.automation.spreadsheet_url to a Google Sheets URL.")
        story_points_field = automation.get("story_points_field")
        if not isinstance(story_points_field, str) or not re.fullmatch(r"customfield_[0-9]+", story_points_field):
            raise ValueError("integrations.automation.story_points_field must look like customfield_12345.")
        epic_link_field = automation.get("epic_link_field")
        if epic_link_field is not None and (not isinstance(epic_link_field, str)
                                             or not re.fullmatch(r"customfield_[0-9]+", epic_link_field)):
            raise ValueError("integrations.automation.epic_link_field must look like customfield_12345.")
        members = automation.get("team_members")
        if (not isinstance(members, list) or not members
                or any(not isinstance(member, str) or not member.strip() for member in members)
                or len({member.casefold() for member in members}) != len(members)):
            raise ValueError("integrations.automation.team_members must contain unique, non-empty names.")
        timezone = automation.get("timezone", "UTC")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, TypeError):
            raise ValueError("integrations.automation.timezone must be a valid IANA timezone.") from None
    return data


def _credential_keys(data: dict) -> set[str]:
    return {
        key
        for entry in data.get("integrations", {}).values()
        for key in (entry.get("username_env"), entry.get("password_env"))
        if key
    }


def _load_env(path: Path, allowed: set[str]) -> None:
    """Load only credential variables referenced by the central configuration."""
    if not path.exists():
        return
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number}; expected a credential assignment.")
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in allowed:
            raise ValueError(f".env may contain credentials only; {key} is not referenced by config.toml.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


CONFIG = _read_config()
_load_env(ENV_PATH, _credential_keys(CONFIG))


@dataclass(frozen=True)
class IntegrationConfig:
    enabled: bool
    base_url: str
    api_path: str
    username: str
    password: str
    username_env: str | None
    password_env: str | None


def integration(name: str) -> IntegrationConfig:
    entry = CONFIG["integrations"][name]
    shared_url = CONFIG["shared"]["base_url"].rstrip("/")
    username_env = entry.get("username_env")
    password_env = entry.get("password_env")
    return IntegrationConfig(
        enabled=entry["enabled"],
        base_url=shared_url + entry.get("api_path", ""),
        api_path=entry.get("api_path", ""),
        username=os.environ.get(username_env, "") if username_env else "",
        password=os.environ.get(password_env, "") if password_env else "",
        username_env=username_env,
        password_env=password_env,
    )


def jira_project(project: str, *, write: bool = False) -> dict:
    """Resolve a Jira project id or key and enforce its configured access mode."""
    if not isinstance(project, str) or not project.strip():
        raise ValueError("project must be a configured Jira project id or key.")
    selector = project.strip().casefold()
    configured = CONFIG["integrations"]["jira"].get("projects", [])
    match = next(
        (item for item in configured if selector in {item["id"].casefold(), item["key"].casefold()}),
        None,
    )
    if match is None:
        raise ValueError(f"Jira project '{project}' is not configured in config.toml.")
    if write and match.get("read_only", True):
        raise PermissionError(f"Jira project '{match['id']}' is configured as read-only.")
    return match


def jira_issue_key(issue: str, *, write: bool = False) -> str:
    """Validate an issue key and check that its project is configured for access."""
    from ..integrations.jira.core.validation import issue_key

    normalized = issue_key(issue)
    project_key = normalized.rsplit("-", 1)[0]
    jira_project(project_key, write=write)
    return normalized


def expose_destructive_tools() -> bool:
    """Return whether tools marked destructive should be registered with the model."""
    return CONFIG.get("tools", {}).get("expose_destructive", False)


def expose_write_tools() -> bool:
    """Return whether tools that can change data should be registered with the model."""
    return CONFIG.get("tools", {}).get("expose_write", True)


def automation_settings() -> dict:
    """Return validated settings for the sprint sheet automation."""
    return CONFIG.get("integrations", {}).get("automation", {"enabled": False})


def validate_config() -> None:
    """Validate central settings and credentials required by enabled integrations."""
    data = _read_config()
    if data["integrations"]["xwiki"]["enabled"]:
        settings = integration("xwiki")
        if bool(settings.username_env) != bool(settings.password_env):
            raise ValueError("Configure both XWiki credential environment names.")
        if settings.username_env and (not settings.username or not settings.password):
            raise ValueError(
                f"Set {settings.username_env} and {settings.password_env} in {ENV_PATH}."
            )
