"""Search Jira users."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from ...core.validation import read_project_key


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jira_search_users(project: str, query: str) -> str:
        """Find assignable Jira users in a configured project by name or email."""
        key = read_project_key(project)
        if not query.strip():
            raise ValueError("query cannot be empty.")
        result = request(
            "GET", "/rest/api/2/user/assignable/search",
            params={"project": key, "query": query.strip(), "maxResults": "50"},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
