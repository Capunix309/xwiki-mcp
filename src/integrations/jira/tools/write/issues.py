"""Create Jira issues and update common issue fields."""

import json
import math
from typing import Any

from mcp.types import ToolAnnotations

from ...core.client import request
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_create_issue(
        project: str,
        issue_type: str,
        summary: str,
        description: str,
        labels: list[str] | None = None,
        epic_name: str | None = None,
        story_points: float | None = None,
        epic_key: str | None = None,
    ) -> str:
        """Create an issue, optionally setting Epic Name, story points, and its parent Epic."""
        project_settings = config.jira_project(project, write=True)
        key = project_settings["key"]
        if not issue_type.strip() or not summary.strip():
            raise ValueError("issue_type and summary are required.")
        description_text = description.strip()
        if not description_text:
            raise ValueError("description is required.")
        if not description_text.startswith("[AI]"):
            description_text = f"[AI] {description_text}"
        issue_labels = list(dict.fromkeys([*(labels or []), "ai-assisted"]))
        issue_fields: dict[str, Any] = {
            "project": {"key": key},
            "issuetype": {"name": issue_type.strip()},
            "summary": summary.strip(),
            "description": description_text,
            "labels": issue_labels,
        }
        is_epic = issue_type.strip().casefold() == "epic"
        if is_epic and (epic_name is None or not epic_name.strip()):
            raise ValueError("epic_name is required when creating an Epic.")
        if epic_name is not None:
            if not is_epic:
                raise ValueError("epic_name can only be set when issue_type is Epic.")
            issue_fields[_jira_field(project_settings, "epic_name_field", "Epic Name")] = epic_name.strip()
        if story_points is not None:
            issue_fields[_jira_field(project_settings, "story_points_field", "Story Points")] = _story_points(story_points)
        if epic_key is not None:
            issue_fields[_jira_field(project_settings, "epic_link_field", "Epic Link")] = _epic_key(epic_key)
        body = {"fields": issue_fields}
        return _format(request("POST", "/rest/api/2/issue", body=body))

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_update_issue(
        issue: str,
        summary: str | None = None,
        description: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        story_points: float | None = None,
        epic_key: str | None = None,
        clear_epic_link: bool = False,
    ) -> str:
        """Update issue fields, story points, and Epic link; set clear_epic_link to remove the link."""
        key = config.jira_issue_key(issue, write=True)
        project_settings = config.jira_project(key.rsplit("-", 1)[0], write=True)
        if epic_key is not None and clear_epic_link:
            raise ValueError("Set epic_key or clear_epic_link, not both.")
        fields: dict[str, Any] = {}
        if summary is not None:
            if not summary.strip():
                raise ValueError("summary cannot be empty.")
            fields["summary"] = summary.strip()
        if description is not None:
            fields["description"] = description
        if assignee is not None:
            if not assignee.strip():
                raise ValueError("assignee cannot be empty; use an account id or username.")
            fields["assignee"] = {"name": assignee.strip()}
        if priority is not None:
            if not priority.strip():
                raise ValueError("priority cannot be empty.")
            fields["priority"] = {"name": priority.strip()}
        if labels is not None:
            fields["labels"] = labels
        if story_points is not None:
            fields[_jira_field(project_settings, "story_points_field", "Story Points")] = _story_points(story_points)
        if epic_key is not None:
            fields[_jira_field(project_settings, "epic_link_field", "Epic Link")] = _epic_key(epic_key)
        if clear_epic_link:
            fields[_jira_field(project_settings, "epic_link_field", "Epic Link")] = None
        if not fields:
            raise ValueError("Provide at least one field to update.")
        return _format(request("PUT", f"/rest/api/2/issue/{key}", body={"fields": fields}))


def _format(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _jira_field(project: dict, setting: str, display_name: str) -> str:
    """Resolve a Jira custom field from the selected project's settings."""
    field_id = project.get(setting)
    if not isinstance(field_id, str) or not field_id:
        raise ValueError(f"Configure {setting} on the Jira project before setting {display_name}.")
    return field_id


def _story_points(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("story_points must be a non-negative number.")
    if not math.isfinite(value) or value < 0:
        raise ValueError("story_points must be a finite, non-negative number.")
    return value


def _epic_key(value: str) -> str:
    key = config.jira_issue_key(value)
    return key
