"""Generate selector-aware daily series used by the existing burn-down charts."""

from __future__ import annotations

from ..core.sheets.client import Formula


def burndown_formulas(first_row: int = 2, last_row: int = 201) -> list[list[Formula]]:
    """Return ideal, worklog-proxy, Jira-completion, and hours formulas."""
    start = (
        'IF(Analysis!$B$3="All sprints";INT(MIN(Worklogs!$D$2:$D));'
        'IFERROR(INDEX(\'Sprint Setup\'!$B$2:$B$100;MATCH(Analysis!$B$3;\'Sprint Setup\'!$A$2:$A$100;0));""))'
    )
    end = (
        'IF(Analysis!$B$3="All sprints";INT(MAX(MAX(Worklogs!$D$2:$D);MAX(\'Task Analysis\'!$I$2:$I$1000)));'
        'IFERROR(INDEX(\'Sprint Setup\'!$C$2:$C$100;MATCH(Analysis!$B$3;\'Sprint Setup\'!$A$2:$A$100;0));""))'
    )
    rows: list[list[Formula]] = []
    for row in range(first_row, last_row + 1):
        date_formula = (
            f'=IFERROR(IF(AND(ISNUMBER({start});ISNUMBER({end});ROW()-1<={end}-{start}+1);'
            f'{start}+ROW()-2;"");"")'
        )
        count = (
            'IF(Analysis!$B$3="All sprints";'
            'COUNTA(\'Task Analysis\'!$A$2:$A$1000);'
            'COUNTIF(\'Task Analysis\'!$J$2:$J$1000;Analysis!$B$3))'
        )
        ideal = f'=IF(A{row}="";"";IFERROR({count}*IF({end}={start};0;1-(A{row}-{start})/({end}-{start}));0))'
        worklog_done = (
            'IF(Analysis!$B$3="All sprints";'
            f'COUNTIFS(\'Task Analysis\'!$C$2:$C$1000;"Done";'
            f'\'Task Analysis\'!$H$2:$H$1000;"<="&A{row});'
            f'COUNTIFS(\'Task Analysis\'!$C$2:$C$1000;"Done";'
            f'\'Task Analysis\'!$H$2:$H$1000;"<="&A{row};'
            f'\'Task Analysis\'!$J$2:$J$1000;Analysis!$B$3))'
        )
        jira_done = (
            'IF(Analysis!$B$3="All sprints";'
            f'COUNTIFS(\'Task Analysis\'!$C$2:$C$1000;"Done";'
            f'\'Task Analysis\'!$I$2:$I$1000;"<="&A{row});'
            f'COUNTIFS(\'Task Analysis\'!$C$2:$C$1000;"Done";'
            f'\'Task Analysis\'!$I$2:$I$1000;"<="&A{row};'
            f'\'Task Analysis\'!$J$2:$J$1000;Analysis!$B$3))'
        )
        proxy = f'=IF(A{row}="";"";{count}-{worklog_done})'
        actual = f'=IF(A{row}="";"";{count}-{jira_done})'
        hours = (
            f'=IF(A{row}="";"";IF(Analysis!$B$3="All sprints";'
            f'SUMIFS(Worklogs!$AF$2:$AF;Worklogs!$D$2:$D;">="&A{row};Worklogs!$D$2:$D;"<"&A{row}+1);'
            f'SUMIFS(Worklogs!$AF$2:$AF;Worklogs!$D$2:$D;">="&A{row};'
            f'Worklogs!$D$2:$D;"<"&A{row}+1;Worklogs!$AG$2:$AG;Analysis!$B$3)))'
        )
        rows.append([Formula(date_formula), Formula(ideal), Formula(proxy), Formula(actual), Formula(hours)])
    return rows
