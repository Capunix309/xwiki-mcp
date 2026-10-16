"""Access automation settings from the shared TOML configuration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from src.shared import config


@dataclass(frozen=True)
class AutomationSettings:
    project_id: str
    project_key: str
    board_id: int
    spreadsheet_url: str
    spreadsheet_id: str
    timezone: ZoneInfo
    story_points_field: str
    epic_link_field: str | None
    team_members: tuple[str, ...]


def load_settings() -> AutomationSettings:
    """Build settings and resolve the configured Jira project selector."""
    entry = config.automation_settings()
    if not entry.get("enabled", False):
        raise ValueError("The automation integration is disabled in config.toml.")
    project = config.jira_project(entry["jira_project"])
    return AutomationSettings(
        project_id=project["id"],
        project_key=project["key"],
        board_id=entry["board_id"],
        spreadsheet_url=entry["spreadsheet_url"],
        spreadsheet_id=_spreadsheet_id(entry["spreadsheet_url"]),
        timezone=ZoneInfo(entry.get("timezone", "UTC")),
        story_points_field=project["story_points_field"],
        epic_link_field=project.get("epic_link_field"),
        team_members=tuple(entry["team_members"]),
    )


def _spreadsheet_id(url: str) -> str:
    """Extract the workbook ID from its configured Google Sheets URL."""
    parts = urlparse(url)
    segments = parts.path.strip("/").split("/")
    if parts.netloc not in {"docs.google.com", "sheets.google.com"} or len(segments) < 3:
        raise ValueError("spreadsheet_url must be a Google Sheets URL containing /spreadsheets/d/<id>/.")
    if segments[0] != "spreadsheets" or segments[1] != "d" or not segments[2]:
        raise ValueError("spreadsheet_url must be a Google Sheets URL containing /spreadsheets/d/<id>/.")
    return segments[2]
