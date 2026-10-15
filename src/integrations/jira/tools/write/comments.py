"""Add AI-attributed comments to Jira issues."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_add_comment(issue: str, comment: str) -> str:
        """Add an issue comment prefixed with [AI]."""
        key = config.jira_issue_key(issue, write=True)
        text = comment.strip()
        if not text:
            raise ValueError("comment cannot be empty.")
        if not text.startswith("[AI]"):
            text = f"[AI] {text}"
        result = request("POST", f"/rest/api/2/issue/{key}/comment", body={"body": text})
        return json.dumps(result, ensure_ascii=False, indent=2)
