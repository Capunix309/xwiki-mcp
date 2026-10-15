"""Read project-specific issue types and Jira priorities."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from ...core.validation import read_project_key


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jira_get_issue_types(project: str) -> str:
        """List issue types available to a configured project."""
        key = read_project_key(project)
        result = request("GET", f"/rest/api/2/project/{key}")
        issue_types = result.get("issueTypes", [])
        return json.dumps(issue_types, ensure_ascii=False, indent=2)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jira_get_priorities(project: str) -> str:
        """List priorities available in Jira for a configured project."""
        read_project_key(project)
        result = request("GET", "/rest/api/2/priority")
        return json.dumps(result, ensure_ascii=False, indent=2)
