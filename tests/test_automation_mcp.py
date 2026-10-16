"""Tests for deterministic Jira-to-Sheets automation."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
import unittest
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from src.integrations.automation import registry
from src.integrations.automation.core import jira
from src.integrations.automation.core.normalize import worklog_record
from src.integrations.automation.core.settings import AutomationSettings, load_settings
from src.integrations.automation.core.sheets.client import Formula, update_cells_request
from src.integrations.automation.core.settings import _spreadsheet_id
from src.integrations.automation.core.sheets import authorize
from src.integrations.automation.sync import analysis, burndown, issue_tables, worklog_table
from src.integrations.automation.sync.service import sync_sprint
from src.integrations.automation.sync.workbook import (
    _remove_overlapping_banding,
    _resize_table,
    update_workbook,
)
from src.shared import config


def settings() -> AutomationSettings:
    return AutomationSettings(
        project_id="primary",
        project_key="ABC",
        board_id=42,
        spreadsheet_url="https://docs.google.com/spreadsheets/d/sheet-id/edit",
        spreadsheet_id="sheet-id",
        timezone=ZoneInfo("UTC"),
        story_points_field="customfield_12345",
        epic_link_field="customfield_12346",
        team_members=("Person One", "Person Two"),
    )


def issue(key: str = "ABC-1", name: str = "First task") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": name,
            "project": {"key": "ABC", "name": "Project ABC"},
            "issuetype": {"name": "Task"},
            "status": {"name": "Closed", "statusCategory": {"name": "Done"}},
            "assignee": {"displayName": "Person One"},
            "reporter": {"displayName": "Person Two"},
            "resolutiondate": "2026-10-15T10:00:00.000+0200",
            "customfield_12345": 3,
        },
    }


def worklog(worklog_id: str = "99", key: str = "ABC-1") -> dict:
    return {
        "id": worklog_id,
        "started": "2026-10-10T12:30:00.000Z",
        "timeSpent": "1h",
        "timeSpentSeconds": 3600,
        "comment": "Reviewed implementation",
        "author": {"key": "person-one", "displayName": "Person One"},
        "issue": issue(key),
    }


class AutomationMCPTests(unittest.TestCase):
    def test_automation_uses_custom_fields_from_its_selected_jira_project(self):
        integrations = dict(config.CONFIG["integrations"])
        jira = dict(integrations["jira"])
        jira["projects"] = [{
            "id": "primary", "key": "ABC", "read_only": False,
            "story_points_field": "customfield_54321",
            "epic_link_field": "customfield_54322",
        }]
        integrations["jira"] = jira
        automation = dict(integrations["automation"])
        automation.update({"enabled": True, "jira_project": "primary"})
        automation.pop("story_points_field", None)
        automation.pop("epic_link_field", None)
        integrations["automation"] = automation
        with patch.object(config, "CONFIG", {**config.CONFIG, "integrations": integrations}):
            loaded = load_settings()
        self.assertEqual(loaded.story_points_field, "customfield_54321")
        self.assertEqual(loaded.epic_link_field, "customfield_54322")

    def test_authorize_imports_client_and_token_into_keychain(self):
        class FakeCredentials:
            @staticmethod
            def to_json():
                return "sample-token"

        class FakeFlow:
            @classmethod
            def from_client_config(cls, client_config, scopes):
                cls.client_config = client_config
                cls.scopes = scopes
                return cls()

            def run_local_server(self, port, open_browser):
                self.port = port
                self.open_browser = open_browser
                return FakeCredentials()

        class FakeKeyring:
            def __init__(self):
                self.values = {}

            def set_password(self, service, account, value):
                self.values[account] = value

            def get_password(self, service, account):
                return self.values.get(account)

        flow_module = ModuleType("google_auth_oauthlib.flow")
        flow_module.InstalledAppFlow = FakeFlow
        package_module = ModuleType("google_auth_oauthlib")
        package_module.flow = flow_module
        fake_keyring = FakeKeyring()

        with tempfile.TemporaryDirectory() as temporary_directory:
            client_path = Path(temporary_directory) / "client.json"
            client_config = {
                "installed": {
                    "client_id": "sample-client",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            client_path.write_text(json.dumps(client_config), encoding="utf-8")
            with (
                patch.dict(sys.modules, {
                    "google_auth_oauthlib": package_module,
                    "google_auth_oauthlib.flow": flow_module,
                }),
                patch.object(authorize, "_keychain", return_value=fake_keyring),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                authorize.main([str(client_path)])

            self.assertFalse(client_path.exists())
            self.assertEqual(json.loads(fake_keyring.values["oauth-client"]), client_config)
            self.assertEqual(fake_keyring.values["automation"], "sample-token")
            self.assertEqual(FakeFlow.client_config, client_config)
            self.assertIn("https://www.googleapis.com/auth/spreadsheets", FakeFlow.scopes)

    def test_spreadsheet_id_is_resolved_from_configured_url(self):
        self.assertEqual(
            _spreadsheet_id("https://docs.google.com/spreadsheets/d/example-sheet/edit"),
            "example-sheet",
        )

    def test_registers_one_annotated_write_tool(self):
        server = FastMCP("automation-test")
        registry.register_all(server)
        tools = server._tool_manager.list_tools()
        self.assertEqual([tool.name for tool in tools], ["sync_sprint_sheet"])
        self.assertFalse(tools[0].annotations.readOnlyHint)
        self.assertFalse(tools[0].annotations.destructiveHint)

    def test_automation_disabled_is_not_registered_at_server_startup(self):
        from src import server as combined_server

        with (
            patch.object(config, "validate_config"),
            patch.object(config, "integration", side_effect=lambda name: type("State", (), {"enabled": False})()),
            patch.object(config, "automation_settings", return_value={"enabled": False}),
        ):
            server = combined_server.create_server()
        self.assertEqual(server._tool_manager.list_tools(), [])

    def test_automation_enabled_registers_its_tool_in_the_combined_server(self):
        from src import server as combined_server

        with (
            patch.object(config, "validate_config"),
            patch.object(config, "integration", side_effect=lambda name: type("State", (), {"enabled": False})()),
            patch.object(config, "automation_settings", return_value={"enabled": True}),
        ):
            server = combined_server.create_server()
        self.assertEqual(
            [tool.name for tool in server._tool_manager.list_tools()],
            ["sync_sprint_sheet"],
        )

    def test_resolves_exact_sprint_without_changing_jira_dates(self):
        with patch.object(jira, "list_sprints", return_value=[{
            "id": 657, "name": "Sprint 0",
            "startDate": "2026-10-07T10:00:00.000Z",
            "endDate": "2026-10-19T22:00:00.000Z",
        }]):
            result = jira.resolve_sprint(settings(), "Sprint 0")
        self.assertEqual(result["startDate"], "2026-10-07T10:00:00.000Z")

    def test_ambiguous_sprint_name_reports_matching_ids(self):
        with patch.object(jira, "list_sprints", return_value=[
            {"id": 1, "name": "Sprint X"}, {"id": 2, "name": "Sprint X"},
        ]):
            with self.assertRaisesRegex(ValueError, "IDs: 1, 2"):
                jira.resolve_sprint(settings(), "Sprint X")

    def test_project_issue_fetch_paginates_and_requests_story_points(self):
        with patch.object(jira, "request", side_effect=[
            {"issues": [{"key": "ABC-1"}], "total": 2},
            {"issues": [{"key": "ABC-2"}], "total": 2},
        ]) as request_mock:
            result = jira.list_project_issues("ABC", "customfield_12345")
        self.assertEqual(len(result), 2)
        self.assertEqual(request_mock.call_args_list[0].kwargs["params"]["startAt"], "0")
        self.assertEqual(request_mock.call_args_list[1].kwargs["params"]["startAt"], "1")
        self.assertIn("customfield_12345", request_mock.call_args_list[0].kwargs["params"]["fields"])

    def test_issue_worklogs_are_paginated(self):
        with patch.object(jira, "request", side_effect=[
            {"worklogs": [{"id": "1"}], "total": 2},
            {"worklogs": [{"id": "2"}], "total": 2},
        ]) as request_mock:
            result = jira.list_issue_worklogs("ABC-1")
        self.assertEqual([item["id"] for item in result], ["1", "2"])
        self.assertEqual(request_mock.call_args_list[1].kwargs["params"]["startAt"], "1")

    def test_worklog_normalizes_time_and_hours(self):
        normalized = worklog_record(
            {"issue": issue(), "worklog": worklog()},
            "Sprint 1",
            settings(),
        )
        self.assertEqual(normalized["started"], datetime(2026, 10, 10, 12, 30, tzinfo=ZoneInfo("UTC")))
        self.assertEqual(normalized["hours"], 1)
        self.assertEqual(normalized["cells"][32], "Sprint 1")
        self.assertEqual(normalized["cells"][33:35], ["99", "automation"])

    def test_sync_replaces_target_sprint_and_preserves_other_sprints(self):
        old_target = [""] * 35
        old_target[0], old_target[32], old_target[33], old_target[34] = "ABC-1", "Sprint 0", "old", "automation"
        other_sprint = [""] * 35
        other_sprint[0], other_sprint[32], other_sprint[33], other_sprint[34] = "ABC-2", "Sprint 1", "keep", "automation"
        incoming = worklog_record(
            {"issue": issue(), "worklog": worklog("new")},
            "Sprint 0",
            settings(),
        )

        result = worklog_table.refresh_worklogs(
            [["header"] * 35, old_target, other_sprint], [incoming], "Sprint 0",
        )

        self.assertEqual(len(result), 3)
        self.assertEqual(result[1][33:35], ["keep", "automation"])
        self.assertEqual(result[2][33:35], ["new", "automation"])

    def test_worklogs_table_range_tracks_replaced_rows(self):
        request = _resize_table({
            "tableId": "table-123",
            "range": {
                "sheetId": 17,
                "startRowIndex": 0,
                "endRowIndex": 90,
                "startColumnIndex": 0,
                "endColumnIndex": 33,
            },
        }, row_count=58)

        self.assertEqual(request["updateTable"]["table"]["tableId"], "table-123")
        self.assertEqual(request["updateTable"]["table"]["range"]["endRowIndex"], 58)
        self.assertEqual(request["updateTable"]["table"]["range"]["endColumnIndex"], 33)

    def test_table_expansion_removes_only_trailing_copied_banding(self):
        table = {
            "tableId": "table-123",
            "range": {"sheetId": 17, "startRowIndex": 0, "endRowIndex": 67,
                      "startColumnIndex": 0, "endColumnIndex": 31},
        }
        metadata = {"sheets": [{
            "properties": {"sheetId": 17},
            "bandedRanges": [
                {"bandedRangeId": 100, "range": {"sheetId": 17, "startRowIndex": 0,
                    "endRowIndex": 67, "startColumnIndex": 0, "endColumnIndex": 31}},
                {"bandedRangeId": 101, "range": {"sheetId": 17, "startRowIndex": 67,
                    "endRowIndex": 68, "startColumnIndex": 0, "endColumnIndex": 31}},
            ],
        }]}

        requests = _remove_overlapping_banding(metadata, table, row_count=72)

        self.assertEqual(requests, [{"deleteBanding": {"bandedRangeId": 101}}])

    def test_repeat_sync_replaces_sprint_rows_without_duplicates(self):
        prior = worklog_record({"issue": issue(), "worklog": worklog()}, "Sprint 1", settings())
        old = list(prior["cells"])
        revised = worklog_record(
            {"issue": issue(), "worklog": {**worklog(), "comment": "Updated comment"}},
            "Sprint 1",
            settings(),
        )
        refreshed = worklog_table.refresh_worklogs(
            [["header"] * 35, old], [revised], "Sprint 1",
        )
        self.assertEqual(len(refreshed), 2)
        self.assertEqual(refreshed[1][22], "Updated comment")

    def test_issue_rows_generate_spreadsheet_formulas(self):
        tasks, people = issue_tables.plan_issue_updates(
            [["key", "task", "status", "assignee", "points", "hours", "per point", "last", "done", "sprint"]],
            [["key", "task", "person", "points", "task hours", "actual", "share", "allocated", "per point", "sprint"]],
            [issue()], "Sprint 1", settings(),
        )
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(people), 2)
        self.assertIsInstance(tasks[0][1][5], Formula)
        self.assertIn("SUMIFS", tasks[0][1][5].expression)
        self.assertIsInstance(people[0][1][5], Formula)

    def test_burndown_formulas_use_sprint_setup_date_columns(self):
        formulas = burndown.burndown_formulas()
        self.assertEqual(len(formulas), 200)
        self.assertIn("Sprint Setup", formulas[0][0].expression)
        self.assertIn("Task Analysis", formulas[0][3].expression)

    def test_analysis_dashboard_formulas_cover_summary_and_effort_table(self):
        summary = analysis.summary_formulas()
        self.assertEqual(len(summary), 6)
        self.assertIn("COUNTIFS(Worklogs!", summary[0].expression)
        self.assertIn('"Done"', summary[2].expression)
        effort = analysis.effort_column_formulas()
        self.assertEqual(set(effort), {0, 1, 2, 7, 8, 9})
        self.assertEqual(len(effort[2]), 6)
        self.assertIn("'Hours by Person'!H2", effort[2][0].expression)

    def test_cell_updates_are_bounded_to_the_values_being_written(self):
        request = update_cells_request(17, 4, 2, [["value"]])
        self.assertEqual(request["updateCells"]["range"], {
            "sheetId": 17,
            "startRowIndex": 4,
            "endRowIndex": 5,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        })

    def test_sync_filters_all_project_worklogs_by_local_date_window(self):
        fake_settings = settings()
        sprint = {
            "id": 1, "name": "Sprint 1",
            "startDate": "2026-10-01T00:00:00+00:00",
            "endDate": "2026-10-20T00:00:00+00:00",
        }
        inside = worklog("1")
        outside = worklog("2")
        outside["started"] = "2026-09-30T21:30:00Z"
        with (
            patch("src.integrations.automation.sync.service.jira.resolve_sprint", return_value=sprint),
            patch("src.integrations.automation.sync.service.jira.list_sprint_issues", return_value=[issue()]),
            patch("src.integrations.automation.sync.service.jira.list_project_issues", return_value=[issue()]),
            patch("src.integrations.automation.sync.service.jira.collect_worklogs", return_value=[
                {"issue": issue(), "worklog": inside},
                {"issue": issue(), "worklog": outside},
            ]),
            patch("src.integrations.automation.sync.service.update_workbook", return_value={"updated": True}) as update,
        ):
            sync_sprint("Sprint 1", settings=fake_settings)
        sent_logs = update.call_args.args[5]
        self.assertEqual([item["id"] for item in sent_logs], ["1"])

    def test_caller_dates_override_jira_sprint_dates(self):
        fake_settings = settings()
        sprint = {
            "id": 1, "name": "Sprint 1",
            "startDate": "2026-10-01T00:00:00+02:00",
            "endDate": "2026-10-20T00:00:00+02:00",
        }
        with (
            patch("src.integrations.automation.sync.service.jira.resolve_sprint", return_value=sprint),
            patch("src.integrations.automation.sync.service.jira.list_sprint_issues", return_value=[issue()]),
            patch("src.integrations.automation.sync.service.jira.list_project_issues", return_value=[issue()]),
            patch("src.integrations.automation.sync.service.jira.collect_worklogs", return_value=[]),
            patch("src.integrations.automation.sync.service.update_workbook", return_value={}) as update,
        ):
            sync_sprint(
                "Sprint 1", start_date="2026-10-03", end_date="2026-10-18", settings=fake_settings,
            )
        self.assertEqual(update.call_args.args[2:4], (date(2026, 10, 3), date(2026, 10, 18)))

    def test_sheet_preflight_failure_does_not_apply_any_requests(self):
        class FakeSheets:
            def metadata(self):
                return {"sheets": []}

            def apply(self, requests):
                raise AssertionError("must not write on failed preflight")

        with self.assertRaisesRegex(ValueError, "missing sheets"):
            update_workbook(
                settings(), "Sprint 1", date(2026, 10, 1), date(2026, 10, 20),
                [issue()], [], client=FakeSheets(),
            )

    def test_successful_sheet_update_is_sent_as_one_batch(self):
        headers = {
            "Worklogs": [["h"] * 33],
            "Task Analysis": [["Issue Key", "Task", "Status", "Assignee", "Story Points", "Actual Hours",
                               "Hours per Point", "Last Worklog", "Jira Completion Date", "Sprint",
                               "Chart Issue", "Chart Story Points", "Chart Actual Hours"]],
            "Person Task Effort": [["Issue Key", "Task", "Person", "Task Story Points", "Task Actual Hours",
                                    "Person Actual Hours", "Share of Task Hours", "Person Allocated Story Points",
                                    "Hours per Allocated Point", "Sprint"]],
            "Sprint Setup": [["Sprint options"], ["All sprints"]],
        }

        class FakeSheets:
            def __init__(self):
                self.batch = None

            def metadata(self):
                return {"sheets": [
                    {"properties": {"title": name, "sheetId": index, "gridProperties": {
                        "rowCount": 2000, "columnCount": 33 if name == "Worklogs" else 26,
                    }}}
                    for index, name in enumerate((
                        "Worklogs", "Analysis", "Task Analysis", "Person Task Effort",
                        "Burndown Data", "Sprint Setup",
                    ), start=1)
                ]}

            def values(self, sheet, _range):
                return headers.get(sheet, [])

            def apply(self, requests):
                self.batch = requests

        client = FakeSheets()
        result = update_workbook(
            settings(), "Sprint 1", date(2026, 10, 1), date(2026, 10, 20),
            [issue()], [], client=client,
        )
        self.assertEqual(result["issues_updated"], 1)
        self.assertIsNotNone(client.batch)
        self.assertTrue(any("appendDimension" in item for item in client.batch))
        self.assertTrue(any(
            item.get("updateCells", {}).get("range", {}).get("sheetId") == 3
            for item in client.batch
        ))


if __name__ == "__main__":
    unittest.main()
