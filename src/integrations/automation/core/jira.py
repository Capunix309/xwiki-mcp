"""Fetch sprint, issue, and worklog data from the configured Jira project."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from src.integrations.jira.core.client import request
from src.integrations.jira.core.validation import issue_key as validate_issue_key

from .settings import AutomationSettings


PAGE_SIZE = 100


def list_sprints(settings: AutomationSettings) -> list[dict[str, Any]]:
    """Return every sprint on the configured project board."""
    boards: list[dict[str, Any]] = []
    board_offset = 0
    while True:
        page = request(
            "GET", "/rest/agile/1.0/board",
            params={"projectKeyOrId": settings.project_key, "startAt": str(board_offset), "maxResults": str(PAGE_SIZE)},
        )
        values = page.get("values", [])
        boards.extend(values)
        board_offset += len(values)
        if not values or page.get("isLast", True):
            break
    if not any(str(board.get("id")) == str(settings.board_id) for board in boards):
        raise ValueError(f"Board {settings.board_id} does not belong to configured project '{settings.project_key}'.")

    result: list[dict[str, Any]] = []
    start_at = 0
    while True:
        page = request(
            "GET", f"/rest/agile/1.0/board/{settings.board_id}/sprint",
            params={"startAt": str(start_at), "maxResults": str(PAGE_SIZE)},
        )
        values = page.get("values", [])
        result.extend(values)
        if page.get("isLast", True) or not values:
            return result
        start_at += len(values)


def resolve_sprint(settings: AutomationSettings, sprint_name: str) -> dict[str, Any]:
    """Resolve an exact sprint name on the configured board."""
    requested = sprint_name.strip()
    if not requested:
        raise ValueError("sprint_name cannot be empty.")
    matches = [item for item in list_sprints(settings) if item.get("name") == requested]
    if not matches:
        raise ValueError(f"No sprint named '{requested}' exists on board {settings.board_id}.")
    if len(matches) > 1:
        ids = ", ".join(str(item.get("id")) for item in matches)
        raise ValueError(f"Sprint name '{requested}' is ambiguous on board {settings.board_id}; matching IDs: {ids}.")
    return dict(matches[0])


def list_sprint_issues(sprint_id: int, story_points_field: str) -> list[dict[str, Any]]:
    """Read all issues associated with a sprint, including paged results."""
    issues: list[dict[str, Any]] = []
    start_at = 0
    fields = ",".join((
        "summary", "issuetype", "status", "assignee", "reporter", "project",
        "resolutiondate", "parent", "components", "fixVersions",
        "timeoriginalestimate", "timeestimate", story_points_field,
    ))
    while True:
        page = request(
            "GET", f"/rest/agile/1.0/sprint/{sprint_id}/issue",
            params={"startAt": str(start_at), "maxResults": str(PAGE_SIZE), "fields": fields},
        )
        values = page.get("issues", [])
        issues.extend(values)
        total = page.get("total")
        start_at += len(values)
        if not values or (total is not None and start_at >= total) or (total is None and page.get("isLast", True)):
            return issues


def list_project_issues(project_key: str, story_points_field: str, epic_link_field: str | None = None) -> list[dict[str, Any]]:
    """Read all project issues so the sync can collect worklogs outside the sprint."""
    issues: list[dict[str, Any]] = []
    start_at = 0
    fields = ",".join((
        "summary", "issuetype", "status", "assignee", "reporter", "project",
        "resolutiondate", "parent", "components", "fixVersions",
        "timeoriginalestimate", "timeestimate", story_points_field,
    ))
    if epic_link_field:
        fields += f",{epic_link_field}"
    while True:
        page = request(
            "GET", "/rest/api/2/search",
            params={
                "jql": f'project = "{project_key}"',
                "fields": fields,
                "startAt": str(start_at),
                "maxResults": str(PAGE_SIZE),
            },
        )
        values = page.get("issues", [])
        issues.extend(values)
        start_at += len(values)
        if not values or start_at >= page.get("total", start_at):
            return issues


def list_issue_worklogs(issue_key: str) -> list[dict[str, Any]]:
    """Read every worklog for one issue using Jira's paged endpoint."""
    issue_key = validate_issue_key(issue_key)
    worklogs: list[dict[str, Any]] = []
    start_at = 0
    while True:
        page = request(
            "GET", f"/rest/api/2/issue/{issue_key}/worklog",
            params={"startAt": str(start_at), "maxResults": str(PAGE_SIZE)},
        )
        values = page.get("worklogs", [])
        worklogs.extend(values)
        start_at += len(values)
        if not values or start_at >= page.get("total", start_at):
            return worklogs


def collect_worklogs(project_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach issue details to the project's paginated Jira worklogs."""
    all_worklogs: list[dict[str, Any]] = []
    for issue in project_issues:
        for worklog in list_issue_worklogs(issue["key"]):
            all_worklogs.append({"issue": issue, "worklog": worklog})
    return all_worklogs


def sprint_date(value: str | None, *, field: str, sprint_name: str, timezone) -> date:
    """Parse Jira's sprint timestamp into a local calendar date."""
    if not value:
        raise ValueError(f"Sprint '{sprint_name}' has no {field}; provide it as a tool argument.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone)
        return parsed.date()
    except ValueError:
        raise ValueError(f"Sprint '{sprint_name}' has an invalid {field}: {value!r}.") from None
