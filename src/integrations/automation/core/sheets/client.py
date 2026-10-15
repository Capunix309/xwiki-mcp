"""Minimal Google Sheets API client for reading and updating workbook cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .auth import load_credentials


@dataclass(frozen=True)
class Formula:
    """Mark a string as a Sheets formula rather than a literal value."""
    expression: str


class SheetsClient:
    """Read workbook tables and atomically update their cell values."""

    def __init__(self, spreadsheet_id: str):
        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError("Install MCP-tools dependencies before using Google Sheets automation.") from None
        credentials = load_credentials()
        self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.spreadsheet_id = spreadsheet_id

    def metadata(self) -> dict[str, Any]:
        """Return sheet IDs and grid sizes required for safe updates."""
        fields = (
            "spreadsheetId,sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)),"
            "bandedRanges(bandedRangeId,range)),tables(tableId,name,range)"
        )
        try:
            return self._service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                fields=fields,
            ).execute()
        except Exception as detailed_error:
            try:
                return self._service.spreadsheets().get(
                    spreadsheetId=self.spreadsheet_id,
                    fields="spreadsheetId,sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))",
                ).execute()
            except Exception:
                raise RuntimeError("Could not read Google Sheets workbook metadata.") from detailed_error

    def values(self, sheet_title: str, a1_range: str) -> list[list[Any]]:
        """Fetch a bounded range using unformatted values for stable matching."""
        try:
            result = self._service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{sheet_title}'!{a1_range}",
                valueRenderOption="UNFORMATTED_VALUE",
            ).execute()
            return result.get("values", [])
        except Exception:
            raise RuntimeError(f"Could not read the '{sheet_title}' sheet.") from None

    def apply(self, requests: list[dict[str, Any]]) -> None:
        """Apply the complete workbook value update in one Sheets batch."""
        if not requests:
            return
        try:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"requests": requests},
            ).execute()
        except Exception:
            raise RuntimeError("Google Sheets rejected the update; no confirmation was received.") from None


def cell_data(value: Any) -> dict[str, Any]:
    """Convert values into the Sheets API's userEnteredValue representation."""
    if isinstance(value, Formula):
        return {"userEnteredValue": {"formulaValue": value.expression}}
    if value is None or value == "":
        return {"userEnteredValue": {}}
    if isinstance(value, bool):
        return {"userEnteredValue": {"boolValue": value}}
    if isinstance(value, (int, float)):
        return {"userEnteredValue": {"numberValue": value}}
    return {"userEnteredValue": {"stringValue": str(value)}}


def update_cells_request(sheet_id: int, row_index: int, column_index: int,
                         rows: list[list[Any]]) -> dict[str, Any]:
    """Build an exactly bounded updateCells request.

    Explicit bounds prevent Sheets from clearing unrelated cells to the right
    or below a partial write.
    """
    row_count = len(rows)
    column_count = max((len(row) for row in rows), default=0)
    return {
        "updateCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_index,
                "endRowIndex": row_index + row_count,
                "startColumnIndex": column_index,
                "endColumnIndex": column_index + column_count,
            },
            "rows": [{"values": [cell_data(value) for value in row]} for row in rows],
            "fields": "userEnteredValue",
        }
    }
