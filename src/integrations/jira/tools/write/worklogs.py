"""Record work against Jira issues with an AI-attributed comment."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_add_worklog(issue: str, time_spent: str, comment: str) -> str:
        """Record time spent using Jira duration syntax and a required [AI]-prefixed comment."""
        key = config.jira_issue_key(issue, write=True)
        if not time_spent.strip():
            raise ValueError("time_spent is required, for example '1h 30m'.")
        text = comment.strip()
        if not text:
            raise ValueError("comment is required for every worklog.")
        if not text.startswith("[AI]"):
            text = f"[AI] {text}"
        result = request(
            "POST", f"/rest/api/2/issue/{key}/worklog",
            body={"timeSpent": time_spent.strip(), "comment": text},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
