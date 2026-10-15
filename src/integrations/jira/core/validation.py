"""Validate Jira identifiers used in REST paths and issue creation."""

import re

from ....shared import config


_ISSUE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-\d+$")


def issue_key(value: str) -> str:
    """Return a normalized Jira issue key or raise a helpful error."""
    normalized = value.strip()
    if not _ISSUE_KEY.fullmatch(normalized):
        raise ValueError("issue_key must be a Jira issue key such as TEAM-123.")
    return normalized


def project_key(value: str) -> str:
    """Resolve a configured Jira project selector to its project key for writes."""
    return config.jira_project(value, write=True)["key"]


def read_project_key(value: str) -> str:
    """Resolve a configured project without requiring write access."""
    return config.jira_project(value)["key"]


def project_selector(value: str | None) -> list[dict]:
    """Return one selected project or every configured project for search."""
    projects = config.CONFIG["integrations"]["jira"].get("projects", [])
    if value is None:
        if not projects:
            raise ValueError("Configure at least one Jira project in config.toml.")
        return projects
    return [config.jira_project(value)]


def scoped_read(project: str, path: str, params: dict[str, str] | None) -> dict[str, str]:
    """Validate a Jira read route and scope it to one configured project."""
    configured = config.jira_project(project)
    project_key = configured["key"]
    if not isinstance(path, str):
        raise ValueError("path must be a Jira REST resource path.")
    if params is not None and not isinstance(params, dict):
        raise ValueError("params must be a mapping of string keys and values.")
    query = dict(params or {})
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in query.items()):
        raise ValueError("params must contain string keys and values.")

    if path == "/rest/api/2/search":
        jql = query.get("jql", "").strip()
        order = ""
        order_match = re.search(r"\border\s+by\b", jql, flags=re.IGNORECASE)
        if order_match:
            jql, order = jql[:order_match.start()].strip(), jql[order_match.start():].strip()
        scoped_jql = f'project = "{project_key}"'
        if jql:
            scoped_jql += f" AND ({jql})"
        query["jql"] = f"{scoped_jql} {order}".strip()
        return query

    issue_match = re.fullmatch(
        r"/rest/api/2/issue/([A-Za-z][A-Za-z0-9_]*-\d+)(?:/(?:comment|worklog|changelog))?/?",
        path,
    )
    if issue_match:
        issue = issue_key(issue_match.group(1))
        if issue.rsplit("-", 1)[0].casefold() != project_key.casefold():
            raise ValueError(f"Issue '{issue}' does not belong to configured project '{configured['id']}'.")
        return query

    project_match = re.fullmatch(r"/rest/api/2/project/([A-Za-z][A-Za-z0-9_]*)/?", path)
    if project_match:
        if project_match.group(1).casefold() != project_key.casefold():
            raise ValueError(f"Project path is outside configured project '{configured['id']}'.")
        return query

    raise ValueError("Read path must be a Jira search, issue resource, or configured project resource.")
