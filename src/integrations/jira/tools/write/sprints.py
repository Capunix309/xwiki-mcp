"""Add a Jira issue to a sprint on a board in its configured project."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_add_issue_to_sprint(project: str, issue: str, sprint_id: int) -> str:
        """Add an issue to a sprint after verifying both belong to the writable project."""
        configured = config.jira_project(project, write=True)
        issue_key = config.jira_issue_key(issue, write=True)
        issue_project = issue_key.rsplit("-", 1)[0]
        if issue_project.casefold() != configured["key"].casefold():
            raise ValueError(f"Issue '{issue_key}' is outside configured project '{configured['id']}'.")
        if sprint_id <= 0:
            raise ValueError("sprint_id must be a positive integer.")
        sprint = request("GET", f"/rest/agile/1.0/sprint/{sprint_id}")
        board_id = sprint.get("originBoardId")
        boards = request(
            "GET", "/rest/agile/1.0/board",
            params={"projectKeyOrId": configured["key"], "maxResults": "100"},
        )
        if board_id is None or not any(str(item.get("id")) == str(board_id) for item in boards.get("values", [])):
            raise ValueError(f"Sprint {sprint_id} does not belong to configured project '{configured['id']}'.")
        result = request(
            "PUT", f"/rest/agile/1.0/sprint/{sprint_id}/issue",
            body={"issues": [issue_key]},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
