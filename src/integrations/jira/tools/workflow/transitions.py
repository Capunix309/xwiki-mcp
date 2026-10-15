"""Move Jira issues through their available workflow transitions."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from .....shared import config


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def jira_transition_issue(issue: str, transition: str) -> str:
        """Move an issue using the exact name or id of one of its available transitions."""
        key = config.jira_issue_key(issue, write=True)
        if not transition.strip():
            raise ValueError("transition must be a name or id shown by Jira.")
        available = request("GET", f"/rest/api/2/issue/{key}/transitions")
        selected = next(
            (item for item in available.get("transitions", [])
             if str(item.get("id")) == transition.strip()
             or item.get("name", "").casefold() == transition.strip().casefold()),
            None,
        )
        if selected is None:
            choices = ", ".join(item.get("name", "") for item in available.get("transitions", []))
            raise ValueError(f"Transition is not available for {key}. Available: {choices or 'none'}.")
        result = request(
            "POST", f"/rest/api/2/issue/{key}/transitions",
            body={"transition": {"id": str(selected["id"])}},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
