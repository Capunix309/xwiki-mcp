"""Formulas and labels for the multi-sprint Analysis dashboard."""

from __future__ import annotations

from ..core.sheets.client import Formula


SUMMARY_HEADERS = [
    "Hours logged", "Worklog entries", "Jira tasks", "Done",
    "In progress", "Contributors", "Story points",
]
HOW_TO_READ_HEADER = "How to read this analysis"
HOW_TO_READ = [
    "Assigned effort is shown in story points because Jira has no per-person hour allocation; unassigned issue points are split evenly across the configured team.",
    "For partial work, each person's share of an issue's story points equals their logged hours ÷ total issue hours × issue story points.",
    "The burn-down compares the ideal line, the last-worklog completion proxy, and Jira's resolution-date line.",
]

EFFORT_HEADERS = {
    0: "Person",
    1: "Min",
    2: "Task at Min",
    7: "Mean",
    8: "Max",
    9: "Task at Max",
}


def summary_formulas() -> list[Formula]:
    """Return formulas for the summary cards after the existing Hours Logged cell."""
    selected = 'Analysis!$B$3'
    all_sprints = f'{selected}="All sprints"'
    return [
        Formula(
            f'=IF({all_sprints};COUNTA(Worklogs!$A$2:$A);'
            f'COUNTIFS(Worklogs!$AG$2:$AG;{selected};Worklogs!$A$2:$A;"<>"))'
        ),
        Formula(
            f'=IF({all_sprints};COUNTIF(\'Task Analysis\'!$A$2:$A$1000;"<>");'
            f'COUNTIFS(\'Task Analysis\'!$A$2:$A$1000;"<>";\'Task Analysis\'!$J$2:$J$1000;{selected}))'
        ),
        _task_status_count("Done", all_sprints, selected),
        _task_status_count("In Progress", all_sprints, selected),
        Formula(
            '=COUNTIF(\'Hours by Person\'!$C$2:$C$6;">0")'
        ),
        Formula(
            f'=IF({all_sprints};SUM(\'Task Analysis\'!$E$2:$E$1000);'
            f'SUMIFS(\'Task Analysis\'!$E$2:$E$1000;\'Task Analysis\'!$J$2:$J$1000;{selected}))'
        ),
    ]


def hours_logged_formula() -> Formula:
    """Return the total-hours card formula for the selected sprint."""
    return Formula(
        '=IF($B$3="All sprints";SUM(Worklogs!$AF$2:$AF);'
        'SUMIFS(Worklogs!$AF$2:$AF;Worklogs!$AG$2:$AG;$B$3))'
    )


def effort_column_formulas() -> dict[int, list[Formula]]:
    """Map visible Analysis columns to Hours by Person outputs."""
    source_columns = {0: "A", 1: "G", 2: "H", 7: "K", 8: "I", 9: "J"}
    return {
        column: [Formula(f"='Hours by Person'!{source_column}{row}") for row in range(2, 8)]
        for column, source_column in source_columns.items()
    }


def _task_status_count(status: str, all_sprints: str, selected: str) -> Formula:
    return Formula(
        f'=IF({all_sprints};COUNTIF(\'Task Analysis\'!$C$2:$C$1000;"{status}");'
        f'COUNTIFS(\'Task Analysis\'!$C$2:$C$1000;"{status}";'
        f'\'Task Analysis\'!$J$2:$J$1000;{selected}))'
    )
