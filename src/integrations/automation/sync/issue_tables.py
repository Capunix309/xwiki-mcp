"""Upsert issue and per-person source rows while retaining sheet formulas."""

from __future__ import annotations

from typing import Any

from ..core.normalize import issue_formulas, issue_record, person_effort_formulas, person_effort_rows
from ..core.settings import AutomationSettings
from ..core.sheets.client import Formula


def plan_issue_updates(
    task_rows: list[list[Any]], person_rows: list[list[Any]],
    issues: list[dict[str, Any]], sprint_name: str, settings: AutomationSettings,
) -> tuple[list[tuple[int, list[Any]]], list[tuple[int, list[Any]]]]:
    """Return changed Task Analysis and Person Task Effort rows with formulas."""
    task_index = _row_index(task_rows, (0, 9), "Task Analysis")
    person_index = _row_index(person_rows, (0, 2, 9), "Person Task Effort")
    task_updates: list[tuple[int, list[Any]]] = []
    person_updates: list[tuple[int, list[Any]]] = []
    next_task_row = _next_empty_row(task_rows, 0)
    next_person_row = _next_empty_row(person_rows, 0)

    for issue in issues:
        key = issue.get("key", "")
        task_key = (key, sprint_name)
        task_row_index = task_index.get(task_key)
        if task_row_index is None:
            task_row_index = next_task_row
            next_task_row += 1
            task_index[task_key] = task_row_index
        sheet_row = task_row_index + 1
        row = issue_record(issue, sprint_name, settings)
        for column, formula in issue_formulas(sheet_row).items():
            row[column] = Formula(formula)
        task_updates.append((task_row_index, row))

        for effort in person_effort_rows(issue, sprint_name, settings):
            effort_key = (effort[0], effort[2], sprint_name)
            effort_row_index = person_index.get(effort_key)
            if effort_row_index is None:
                effort_row_index = next_person_row
                next_person_row += 1
                person_index[effort_key] = effort_row_index
            sheet_row = effort_row_index + 1
            for column, formula in person_effort_formulas(sheet_row).items():
                effort[column] = Formula(formula)
            person_updates.append((effort_row_index, effort))
    return task_updates, person_updates


def _row_index(rows: list[list[Any]], key_columns: tuple[int, ...], sheet: str) -> dict[tuple[Any, ...], int]:
    """Map existing business keys to zero-based row indexes and detect duplicates."""
    result: dict[tuple[Any, ...], int] = {}
    for index, row in enumerate(rows[1:]):
        padded = row + [""] * max(0, max(key_columns, default=0) + 1 - len(row))
        if not padded[0]:
            continue
        key = tuple(padded[column] for column in key_columns)
        if key in result:
            raise ValueError(f"Duplicate row key {key!r} exists in '{sheet}'. Resolve it before syncing.")
        result[key] = index + 1
    return result


def _next_empty_row(rows: list[list[Any]], key_column: int) -> int:
    """Find the zero-based row after the last populated business-key cell."""
    last_row = 0
    for row_index, row in enumerate(rows[1:], start=1):
        if len(row) > key_column and row[key_column]:
            last_row = row_index
    return last_row + 1
