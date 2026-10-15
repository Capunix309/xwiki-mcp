"""Replace one sprint's worklogs while retaining other sprints' history."""

from __future__ import annotations

from typing import Any

WORKLOG_HEADERS = ["Jira Worklog ID", "Managed By"]
WORKLOG_WIDTH = 35


def refresh_worklogs(sheet_rows: list[list[Any]], incoming: list[dict[str, Any]], sprint_name: str) -> list[list[Any]]:
    """Replace all rows for this sprint with the current Jira snapshot.

    Rows for other sprints remain untouched. Replacing the selected sprint as
    a unit removes stale rows and makes repeated syncs naturally idempotent.
    """
    old_rows = [list(row[:WORKLOG_WIDTH]) + [""] * max(0, WORKLOG_WIDTH - len(row)) for row in sheet_rows[1:]]
    incoming_by_id = {str(item["id"]): item for item in incoming}
    if len(incoming_by_id) != len(incoming):
        raise ValueError("Jira returned duplicate worklog IDs; refusing to update the sheet.")

    output = [row for row in old_rows if row[32] != sprint_name]
    output.extend(list(item["cells"]) for item in incoming)

    header = list(sheet_rows[0][:33]) + WORKLOG_HEADERS
    if len(sheet_rows[0]) > 33:
        header = list(sheet_rows[0][:WORKLOG_WIDTH])
        if not header[33]:
            header[33] = WORKLOG_HEADERS[0]
        if not header[34]:
            header[34] = WORKLOG_HEADERS[1]
    return [header, *output]
