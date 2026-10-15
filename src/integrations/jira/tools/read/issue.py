"""Retrieve issue details and optionally its related records."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jira_get_issue(
        issue: str,
        include_comments: bool = False,
        include_worklogs: bool = False,
        include_changelog: bool = False,
        include_epic_issues: bool = False,
    ) -> str:
        """Get issue details and optionally comments, worklogs, history, or epic issues."""
        key = config.jira_issue_key(issue)
        fields = [
            "summary", "description", "issuetype", "status", "assignee",
            "reporter", "priority", "labels",
        ]
        if include_comments:
            fields.append("comment")
        if include_worklogs:
            fields.append("worklog")
        params = {"fields": ",".join(fields)}
        if include_changelog:
            params["expand"] = "changelog"
        result = request("GET", f"/rest/api/2/issue/{key}", params=params)
        issue_type = str(result.get("fields", {}).get("issuetype", {}).get("name", ""))
        if include_epic_issues and issue_type.casefold() == "epic":
            child_search = request(
                "GET", "/rest/api/2/search",
                params={"jql": f'"Epic Link" = "{key}"', "maxResults": "100"},
            )
            result["epic_issues"] = child_search.get("issues", [])
        return json.dumps(result, ensure_ascii=False, indent=2)
