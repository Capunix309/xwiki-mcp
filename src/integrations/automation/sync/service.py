"""Coordinate deterministic Jira collection, date resolution, and sheet updates."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ..core import jira
from ..core.normalize import worklog_record
from ..core.settings import AutomationSettings, load_settings
from .workbook import update_workbook


def sync_sprint(
    sprint_name: str, start_date: str | None = None, end_date: str | None = None,
    *, settings: AutomationSettings | None = None, sheets_client=None,
) -> dict[str, Any]:
    """Fetch all source data and update the workbook only after validation passes."""
    settings = settings or load_settings()
    sprint = jira.resolve_sprint(settings, sprint_name)
    sprint_name = sprint["name"]
    start = _override_date(start_date, "start_date") or jira.sprint_date(
        sprint.get("startDate"), field="start date", sprint_name=sprint_name, timezone=settings.timezone,
    )
    end = _override_date(end_date, "end_date") or jira.sprint_date(
        sprint.get("endDate"), field="end date", sprint_name=sprint_name, timezone=settings.timezone,
    )
    if start > end:
        raise ValueError("The sprint start date must be on or before its end date.")

    sprint_issues = jira.list_sprint_issues(int(sprint["id"]), settings.story_points_field)
    project_issues = jira.list_project_issues(
        settings.project_key, settings.story_points_field, settings.epic_link_field,
    )
    _validate_issues(settings, sprint_issues, project_issues)
    fetched_worklogs = jira.collect_worklogs(project_issues)
    normalized_worklogs = []
    for item in fetched_worklogs:
        record = worklog_record(item, sprint_name, settings)
        if start <= record["started"].date() <= end:
            normalized_worklogs.append(record)
    _validate_worklog_ids(normalized_worklogs)

    result = update_workbook(
        settings, sprint_name, start, end, sprint_issues, normalized_worklogs, client=sheets_client,
    )
    result["project"] = settings.project_key
    result["board_id"] = settings.board_id
    return result


def _override_date(value: str | None, name: str) -> date | None:
    if value is None:
        return None
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must use YYYY-MM-DD.") from None


def _validate_issues(settings: AutomationSettings, sprint_issues: list[dict], project_issues: list[dict]) -> None:
    if not sprint_issues:
        raise ValueError("Jira returned no issues for this sprint; refusing to replace workbook data.")
    keys = [issue.get("key") for issue in sprint_issues]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Jira returned missing or duplicate sprint issue keys.")
    invalid = [
        issue.get("key", "unknown") for issue in sprint_issues
        if ((issue.get("fields", {}).get("project") or {}).get("key") != settings.project_key)
    ]
    if invalid:
        issue_list = ", ".join(invalid)
        raise ValueError(
            f"Board {settings.board_id} returned issues outside "
            f"project {settings.project_key}: {issue_list}."
        )
    project_keys = {issue.get("key") for issue in project_issues}
    missing = sorted(set(keys) - project_keys)
    if missing:
        raise ValueError(f"Project search did not return sprint issues: {', '.join(missing)}.")


def _validate_worklog_ids(worklogs: list[dict]) -> None:
    ids = [item["id"] for item in worklogs]
    if len(ids) != len(set(ids)):
        raise ValueError("Jira returned duplicate worklog IDs; refusing to update the workbook.")
