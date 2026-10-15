"""Register the single public sprint-to-sheet automation tool."""

from __future__ import annotations

import json

from mcp.types import ToolAnnotations

from ..sync.service import sync_sprint


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def sync_sprint_sheet(
        sprint_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Fetch Jira data and update the configured sprint analysis sheet.

        Provide the exact sprint name. Optional YYYY-MM-DD date overrides change
        the reporting window; otherwise Jira's sprint dates are used.
        This tool writes to the configured Google Sheet and requires approval.
        """
        result = sync_sprint(sprint_name, start_date=start_date, end_date=end_date)
        return json.dumps(result, ensure_ascii=False, indent=2)
