"""Build and apply one complete sprint update to the existing workbook."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..core.normalize import sheets_serial
from ..core.settings import AutomationSettings
from ..core.sheets.client import SheetsClient, update_cells_request
from . import analysis, burndown, issue_tables, worklog_table


REQUIRED_SHEETS = {"Worklogs", "Analysis", "Task Analysis", "Person Task Effort", "Burndown Data", "Sprint Setup"}


def update_workbook(
    settings: AutomationSettings, sprint_name: str, start_date: date, end_date: date,
    issues: list[dict[str, Any]], worklogs: list[dict[str, Any]], client: SheetsClient | None = None,
) -> dict[str, Any]:
    """Preflight all sheet content, then send a single workbook batch update."""
    client = client or SheetsClient(settings.spreadsheet_id)
    metadata = client.metadata()
    sheets = {
        sheet["properties"]["title"]: sheet["properties"]
        for sheet in metadata.get("sheets", [])
    }
    missing = REQUIRED_SHEETS - sheets.keys()
    if missing:
        raise ValueError(f"The configured workbook is missing sheets: {', '.join(sorted(missing))}.")
    worklog_columns = sheets["Worklogs"]["gridProperties"]["columnCount"]
    worklogs_table = _table_for_sheet(metadata, sheets["Worklogs"]["sheetId"])
    worklog_range = "A1:AI2000" if worklog_columns >= 35 else "A1:AG2000"
    existing_worklogs = client.values("Worklogs", worklog_range)
    task_rows = client.values("Task Analysis", "A1:M1000")
    person_rows = client.values("Person Task Effort", "A1:J2000")
    setup_rows = client.values("Sprint Setup", "A1:C100")
    if not existing_worklogs or not task_rows or not person_rows or not setup_rows:
        raise ValueError("One or more workbook tables are missing their header row.")

    worklog_values = worklog_table.refresh_worklogs(existing_worklogs, worklogs, sprint_name)
    task_updates, person_updates = issue_tables.plan_issue_updates(
        task_rows, person_rows, issues, sprint_name, settings,
    )
    setup_values = _sprint_setup(setup_rows, sprint_name, start_date, end_date)
    requests: list[dict[str, Any]] = []
    last_task_row = issue_tables._next_empty_row(task_rows, 0) - 1
    last_person_row = issue_tables._next_empty_row(person_rows, 0) - 1
    new_task_rows = [index for index, _ in task_updates if index > last_task_row]
    new_person_rows = [index for index, _ in person_updates if index > last_person_row]

    if worklog_columns < 35:
        requests.append({"appendDimension": {
            "sheetId": sheets["Worklogs"]["sheetId"], "dimension": "COLUMNS", "length": 35 - worklog_columns,
        }})
    _extend_rows(requests, sheets["Worklogs"], len(worklog_values))
    old_count = max(0, len(existing_worklogs) - 1)
    body_rows = worklog_values[1:]
    clear_to = max(old_count, len(body_rows))
    body_rows += [[""] * 35 for _ in range(clear_to - len(body_rows))]
    if body_rows:
        requests.append(update_cells_request(sheets["Worklogs"]["sheetId"], 1, 0, body_rows))
    if len(body_rows) > old_count and worklogs_table is None:
        first_new_row = old_count + 1
        source_row = max(1, old_count)
        requests.append(_copy_format(
            sheets["Worklogs"]["sheetId"], source_row, first_new_row, 1 + len(body_rows), 35,
        ))
    if worklogs_table is not None:
        requests.extend(_remove_overlapping_banding(metadata, worklogs_table, len(worklog_values)))
        requests.append(_resize_table(worklogs_table, len(worklog_values)))
    if worklog_columns < 35:
        requests.append(update_cells_request(sheets["Worklogs"]["sheetId"], 0, 33, [worklog_values[0][33:35]]))

    for row_index, row in task_updates:
        _extend_rows(requests, sheets["Task Analysis"], row_index + 1)
        requests.append(update_cells_request(sheets["Task Analysis"]["sheetId"], row_index, 0, [row]))
    for row_index, row in person_updates:
        _extend_rows(requests, sheets["Person Task Effort"], row_index + 1)
        requests.append(update_cells_request(sheets["Person Task Effort"]["sheetId"], row_index, 0, [row]))

    if new_task_rows and last_task_row >= 1:
        requests.append(_copy_format(
            sheets["Task Analysis"]["sheetId"], last_task_row, min(new_task_rows),
            max(new_task_rows) + 1, 13,
        ))
    if new_person_rows and last_person_row >= 1:
        requests.append(_copy_format(
            sheets["Person Task Effort"]["sheetId"], last_person_row, min(new_person_rows),
            max(new_person_rows) + 1, 10,
        ))

    requests.append(update_cells_request(sheets["Sprint Setup"]["sheetId"], 0, 0, setup_values))
    analysis_id = sheets["Analysis"]["sheetId"]
    requests.append(update_cells_request(analysis_id, 2, 1, [[sprint_name]]))
    requests.append(update_cells_request(analysis_id, 3, 0, [analysis.SUMMARY_HEADERS]))
    requests.append(update_cells_request(analysis_id, 4, 0, [[analysis.hours_logged_formula()]]))
    requests.append(update_cells_request(analysis_id, 4, 1, [analysis.summary_formulas()]))
    requests.append(update_cells_request(analysis_id, 6, 0, [[analysis.HOW_TO_READ_HEADER]]))
    requests.append(update_cells_request(analysis_id, 7, 0, [[text] for text in analysis.HOW_TO_READ]))
    requests.append(update_cells_request(
        analysis_id, 11, 0, [[f"Hours per story point — {sprint_name} — finished tasks only"]],
    ))
    for column, header in analysis.EFFORT_HEADERS.items():
        requests.append(update_cells_request(analysis_id, 12, column, [[header]]))
    for column, formulas in analysis.effort_column_formulas().items():
        requests.append(update_cells_request(
            analysis_id, 13, column, [[formula] for formula in formulas],
        ))
    requests.append(update_cells_request(sheets["Burndown Data"]["sheetId"], 1, 0, burndown.burndown_formulas()))
    requests.extend(_date_formats(sheets, max(2, clear_to + 1)))
    client.apply(requests)
    return {
        "sprint": sprint_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "issues_updated": len(issues),
        "worklogs_in_window": len(worklogs),
        "worklog_hours": round(sum(float(item["hours"]) for item in worklogs), 2),
        "analysis_selection": sprint_name,
    }


def _sprint_setup(existing: list[list[Any]], sprint_name: str, start_date: date, end_date: date) -> list[list[Any]]:
    """Update the selector list and store the resolved reporting window."""
    rows = [list(row[:3]) + [""] * max(0, 3 - len(row)) for row in existing]
    rows += [[""] * 3 for _ in range(100 - len(rows))]
    rows[0][0:3] = [rows[0][0] or "Sprint options", "Start date", "End date"]
    found = None
    first_empty = None
    for index in range(1, len(rows)):
        if rows[index][0] == sprint_name:
            found = index
            break
        if not rows[index][0] and first_empty is None:
            first_empty = index
    target = found if found is not None else first_empty
    if target is None:
        raise ValueError("Sprint Setup has no free rows for another sprint.")
    rows[target][0] = sprint_name
    rows[target][1] = sheets_serial(start_date)
    rows[target][2] = sheets_serial(end_date)
    return rows


def _extend_rows(requests: list[dict[str, Any]], sheet: dict[str, Any], required_rows: int) -> None:
    """Grow a sheet only when a table exceeds its current grid."""
    current = sheet["gridProperties"]["rowCount"]
    if required_rows > current:
        requests.append({"appendDimension": {
            "sheetId": sheet["sheetId"], "dimension": "ROWS", "length": required_rows - current,
        }})
        sheet["gridProperties"]["rowCount"] = required_rows


def _table_for_sheet(metadata: dict[str, Any], sheet_id: int) -> dict[str, Any] | None:
    """Return the unique Google Sheets table attached to a sheet, if present."""
    matches = [table for table in metadata.get("tables", [])
               if table.get("range", {}).get("sheetId") == sheet_id]
    if len(matches) > 1:
        raise ValueError("The Worklogs sheet has multiple Google Sheets tables; refusing to resize them.")
    if matches and matches[0].get("range", {}).get("startRowIndex", 0) != 0:
        raise ValueError("The Worklogs table must start in the first row to sync safely.")
    return matches[0] if matches else None


def _resize_table(table: dict[str, Any], row_count: int) -> dict[str, Any]:
    """Resize the Worklogs table vertically without absorbing sync metadata columns."""
    table_range = dict(table["range"])
    table_range["endRowIndex"] = max(1, row_count)
    return {
        "updateTable": {
            "table": {"tableId": table["tableId"], "range": table_range},
            "fields": "range",
        }
    }


def _remove_overlapping_banding(
    metadata: dict[str, Any], table: dict[str, Any], row_count: int,
) -> list[dict[str, Any]]:
    """Remove old copied banding that would block extending the Google table."""
    table_range = table["range"]
    old_end = table_range.get("endRowIndex", 0)
    new_end = max(1, row_count)
    if new_end <= old_end:
        return []

    sheet = next((item for item in metadata.get("sheets", [])
                  if item.get("properties", {}).get("sheetId") == table_range.get("sheetId")), {})
    start_column = table_range.get("startColumnIndex", 0)
    end_column = table_range.get("endColumnIndex", 0)
    requests = []
    for banding in sheet.get("bandedRanges", []):
        band_range = banding.get("range", {})
        band_start = band_range.get("startRowIndex", 0)
        band_end = band_range.get("endRowIndex", 0)
        columns_overlap = (
            band_range.get("startColumnIndex", 0) < end_column
            and band_range.get("endColumnIndex", 0) > start_column
        )
        if band_start >= old_end and band_start < new_end and band_end > old_end and columns_overlap:
            requests.append({"deleteBanding": {"bandedRangeId": banding["bandedRangeId"]}})
    return requests


def _copy_format(sheet_id: int, source_row: int, first_target: int, end_target: int, columns: int) -> dict[str, Any]:
    """Copy only formatting from the last existing row to newly appended rows."""
    return {
        "copyPaste": {
            "source": {"sheetId": sheet_id, "startRowIndex": source_row, "endRowIndex": source_row + 1,
                       "startColumnIndex": 0, "endColumnIndex": columns},
            "destination": {"sheetId": sheet_id, "startRowIndex": first_target, "endRowIndex": end_target,
                            "startColumnIndex": 0, "endColumnIndex": columns},
            "pasteType": "PASTE_FORMAT",
            "pasteOrientation": "NORMAL",
        }
    }


def _date_formats(sheets: dict[str, dict[str, Any]], last_worklog_row: int) -> list[dict[str, Any]]:
    """Set date number formats for values written as Sheets serial numbers."""
    return [
        {"repeatCell": {
            "range": {"sheetId": sheets["Worklogs"]["sheetId"], "startRowIndex": 1,
                      "endRowIndex": max(2, last_worklog_row), "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm"}}},
            "fields": "userEnteredFormat.numberFormat",
        }},
        {"repeatCell": {
            "range": {"sheetId": sheets["Task Analysis"]["sheetId"], "startRowIndex": 1,
                      "endRowIndex": sheets["Task Analysis"]["gridProperties"]["rowCount"],
                      "startColumnIndex": 8, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
            "fields": "userEnteredFormat.numberFormat",
        }},
        {"repeatCell": {
            "range": {"sheetId": sheets["Sprint Setup"]["sheetId"], "startRowIndex": 1,
                      "endRowIndex": 100, "startColumnIndex": 1, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
            "fields": "userEnteredFormat.numberFormat",
        }},
    ]
