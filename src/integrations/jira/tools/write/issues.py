"""Create Jira issues and update common issue fields."""

import json
from typing import Any

from mcp.types import ToolAnnotations

from ...core.client import request
from ...core.validation import project_key
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_create_issue(
        project: str,
        issue_type: str,
        summary: str,
        description: str,
        labels: list[str] | None = None,
    ) -> str:
        """Create an issue with a required [AI]-prefixed description and ai-assisted label."""
        key = project_key(project)
        if not issue_type.strip() or not summary.strip():
            raise ValueError("issue_type and summary are required.")
        description_text = description.strip()
        if not description_text:
            raise ValueError("description is required.")
        if not description_text.startswith("[AI]"):
            description_text = f"[AI] {description_text}"
        issue_labels = list(dict.fromkeys([*(labels or []), "ai-assisted"]))
        body = {"fields": {
            "project": {"key": key},
            "issuetype": {"name": issue_type.strip()},
            "summary": summary.strip(),
            "description": description_text,
            "labels": issue_labels,
        }}
        return _format(request("POST", "/rest/api/2/issue", body=body))

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_update_issue(
        issue: str,
        summary: str | None = None,
        description: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Update an issue's summary, description, assignee, priority, or labels."""
        key = config.jira_issue_key(issue, write=True)
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
        if not fields:
            raise ValueError("Provide at least one field to update.")
        return _format(request("PUT", f"/rest/api/2/issue/{key}", body={"fields": fields}))


def _format(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
