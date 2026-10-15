"""Convert Jira API objects into the workbook's established row layout."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .settings import AutomationSettings


SHEETS_EPOCH = date(1899, 12, 30)


def sheets_serial(value: date | datetime) -> float:
    """Convert a date or datetime to a Google Sheets serial number."""
    if isinstance(value, datetime):
        day_fraction = (value.hour * 3600 + value.minute * 60 + value.second) / 86400
        return (value.date() - SHEETS_EPOCH).days + day_fraction
    return float((value - SHEETS_EPOCH).days)


def worklog_record(item: dict[str, Any], sprint_name: str, settings: AutomationSettings) -> dict[str, Any]:
    """Normalize a Jira worklog and require a stable ID and timestamp."""
    issue, worklog = item["issue"], item["worklog"]
    if not worklog.get("id") or not worklog.get("started"):
        raise ValueError("A Jira worklog is missing its ID or start time; refusing an incomplete sync.")
    started = datetime.fromisoformat(worklog["started"].replace("Z", "+00:00"))
    if started.tzinfo is None:
        started = started.replace(tzinfo=settings.timezone)
    local_start = started.astimezone(settings.timezone)
    fields = issue.get("fields", {})
    seconds = int(worklog.get("timeSpentSeconds") or 0)
    if seconds < 0:
        raise ValueError(f"Jira worklog {worklog['id']} has negative duration.")
    author = worklog.get("author") or {}
    project = fields.get("project") or {}
    issue_type = fields.get("issuetype") or {}
    status = fields.get("status") or {}
    reporter = fields.get("reporter") or {}
    parent = fields.get("parent") or {}
    components = fields.get("components") or []
    versions = fields.get("fixVersions") or []
    comment = worklog.get("comment", "")
    if isinstance(comment, dict):
        comment = _adf_text(comment)
    hours = seconds / 3600
    description = fields.get("summary", "")
    period = f"{local_start.month}{local_start.year % 100:02d}"
    cells = [
        issue.get("key", ""), description, worklog.get("timeSpent", ""), sheets_serial(local_start),
        author.get("key") or author.get("name") or author.get("accountId", ""),
        author.get("displayName", ""), period, "", "", "", "", "", project.get("name", ""),
        ", ".join(component.get("name", "") for component in components),
        ", ".join(component.get("name", "") for component in components),
        ", ".join(version.get("name", "") for version in versions), issue_type.get("name", ""),
        status.get("statusCategory", {}).get("name") or status.get("name", ""),
        project.get("key", ""), project.get("name", ""), "",
        fields.get(settings.epic_link_field) if settings.epic_link_field else "", str(comment), parent.get("key", ""),
        reporter.get("displayName", ""), "", "",
        (fields.get("timeoriginalestimate") or 0) / 3600,
        (fields.get("timeestimate") or 0) / 3600, "", "", hours, sprint_name,
        str(worklog["id"]), "automation",
    ]
    return {
        "cells": cells,
        "id": str(worklog["id"]),
        "issue_key": issue.get("key", ""),
        "started": local_start,
        "hours": hours,
        "author_key": cells[4],
        "author_name": cells[5],
        "comment": str(comment),
    }


def issue_record(issue: dict[str, Any], sprint_name: str, settings: AutomationSettings) -> list[Any]:
    """Create Task Analysis cells and formulas for a Jira sprint issue."""
    fields = issue.get("fields", {})
    status = fields.get("status") or {}
    category = (status.get("statusCategory") or {}).get("name") or status.get("name", "")
    assignee = (fields.get("assignee") or {}).get("displayName") or "Unassigned"
    story_points = fields.get(settings.story_points_field)
    completion = fields.get("resolutiondate")
    completion_value = ""
    if completion:
        completed = datetime.fromisoformat(completion.replace("Z", "+00:00"))
        if completed.tzinfo is not None:
            completed = completed.astimezone(settings.timezone)
        completion_value = sheets_serial(completed.date())
    row = [issue.get("key", ""), fields.get("summary", ""), category, assignee,
           story_points if isinstance(story_points, (int, float)) else "", None, None, None,
           completion_value, sprint_name, None, None, None]
    return row


def issue_formulas(row_number: int) -> dict[int, str]:
    """Return formula cells for one Task Analysis row (zero-based columns)."""
    r = row_number
    return {
        5: f'=IF(OR(A{r}="";J{r}="");"";SUMIFS(Worklogs!$AF$2:$AF;Worklogs!$A$2:$A;A{r};Worklogs!$AG$2:$AG;J{r}))',
        6: f'=IF(OR(A{r}="";J{r}="");"";IF(C{r}="Done";IFERROR(F{r}/E{r};"");""))',
        7: (
            f'=IF(OR(A{r}="";J{r}="");"";IF(COUNTIFS(Worklogs!$A$2:$A;A{r};'
            f'Worklogs!$AG$2:$AG;J{r})=0;"";MAXIFS(Worklogs!$D$2:$D;'
            f'Worklogs!$A$2:$A;A{r};Worklogs!$AG$2:$AG;J{r})))'
        ),
        10: f'=IF(OR($A{r}="";$J{r}="");"";IF(OR(Analysis!$B$3="All sprints";$J{r}=Analysis!$B$3);$A{r};""))',
        11: f'=IF(K{r}="";"";E{r})',
        12: f'=IF(K{r}="";"";F{r})',
    }


def person_effort_rows(issue: dict[str, Any], sprint_name: str, settings: AutomationSettings) -> list[list[Any]]:
    """Create a row per configured contributor for an issue and sprint."""
    fields = issue.get("fields", {})
    task = fields.get("summary", "")
    key = issue.get("key", "")
    result: list[list[Any]] = []
    for person in settings.team_members:
        result.append([key, task, person, None, None, None, None, None, None, sprint_name])
    return result


def person_effort_formulas(row_number: int) -> dict[int, str]:
    """Return formula cells for a Person Task Effort row."""
    r = row_number
    return {
        3: (
            f'=IF(OR(A{r}="";J{r}="");"";SUMIFS(\'Task Analysis\'!$E$2:$E$1000;'
            f'\'Task Analysis\'!$A$2:$A$1000;A{r};\'Task Analysis\'!$J$2:$J$1000;J{r}))'
        ),
        4: (
            f'=IF(OR(A{r}="";J{r}="");"";SUMIFS(\'Task Analysis\'!$F$2:$F$1000;'
            f'\'Task Analysis\'!$A$2:$A$1000;A{r};\'Task Analysis\'!$J$2:$J$1000;J{r}))'
        ),
        5: (
            f'=IF(OR(A{r}="";J{r}="");"";SUMIFS(Worklogs!$AF$2:$AF;'
            f'Worklogs!$A$2:$A;A{r};Worklogs!$F$2:$F;C{r};Worklogs!$AG$2:$AG;J{r}))'
        ),
        6: f'=IFERROR(F{r}/E{r};0)',
        7: f'=D{r}*G{r}',
        8: (
            f'=IF(OR(A{r}="";J{r}="";F{r}<=0);"";IF(SUMIFS(\'Task Analysis\'!$E$2:$E$1000;'
            f'\'Task Analysis\'!$A$2:$A$1000;A{r};\'Task Analysis\'!$J$2:$J$1000;J{r};'
            f'\'Task Analysis\'!$C$2:$C$1000;"Done")>0;IFERROR(F{r}/H{r};"");""))'
        ),
    }


def _adf_text(node: dict[str, Any]) -> str:
    """Extract readable text from a Jira rich-text comment."""
    parts: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "text":
                parts.append(str(value.get("text", "")))
            elif value.get("type") in {"hardBreak", "paragraph"}:
                if value.get("type") == "hardBreak":
                    parts.append("\n")
                else:
                    for child in value.get("content", []):
                        visit(child)
                    parts.append("\n")
            else:
                for child in value.get("content", []):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(node)
    return "".join(parts).strip()
