"""List Jira boards belonging to configured projects."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from ...core.validation import read_project_key


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jira_list_boards(project: str) -> str:
        """List boards associated with a configured project."""
        key = read_project_key(project)
        result = request("GET", "/rest/agile/1.0/board", params={"projectKeyOrId": key, "maxResults": "100"})
        return json.dumps(result, ensure_ascii=False, indent=2)
