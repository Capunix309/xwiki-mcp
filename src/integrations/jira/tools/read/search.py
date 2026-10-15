"""Search issues in configured Jira projects."""

import json

from mcp.types import ToolAnnotations

from ...core.client import request
from ...core.validation import project_selector


def register(server) -> None:
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jira_search(
        project: str | None = None,
        text: str | None = None,
        issue_type: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        sprint: int | None = None,
        updated_after: str | None = None,
        max_results: int = 50,
        start_at: int = 0,
    ) -> str:
        """Search configured Jira projects using common issue filters."""
        projects = project_selector(project)
        if not 1 <= max_results <= 100 or start_at < 0:
            raise ValueError("max_results must be 1-100 and start_at cannot be negative.")

        clauses: list[str] = []
        if text:
            clauses.append(f'text ~ "{_quote(text)}"')
        if issue_type:
            clauses.append(f'issuetype = "{_quote(issue_type)}"')
        if status:
            clauses.append(f'status = "{_quote(status)}"')
        if assignee:
            clauses.append(f'assignee = "{_quote(assignee)}"')
        if sprint is not None:
            if sprint <= 0:
                raise ValueError("sprint must be a positive sprint id.")
            clauses.append(f"sprint = {sprint}")
        if updated_after:
            clauses.append(f'updated >= "{_quote(updated_after)}"')

        results = []
        for configured in projects:
            jql = f'project = "{configured["key"]}"'
            if clauses:
                jql += " AND " + " AND ".join(f"({clause})" for clause in clauses)
            result = request(
                "GET", "/rest/api/2/search",
                params={"jql": jql, "maxResults": str(max_results), "startAt": str(start_at)},
            )
            results.extend(result.get("issues", []))
        return json.dumps({"issues": results}, ensure_ascii=False, indent=2)


def _quote(value: str) -> str:
    """Escape user text embedded in a quoted JQL value."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
