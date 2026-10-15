"""Tests for the Jira integration and its project access boundaries."""

import json
import unittest
from unittest.mock import patch

from mcp.server.fastmcp import FastMCP

from src.integrations.jira.tools import registry
from src.integrations.jira.tools.read import issue as issue_reads
from src.integrations.jira.tools.read import search as issue_search
from src.integrations.jira.tools.write import issues as issue_writes
from src.integrations.jira.tools.write import worklogs
from src.shared import config


class JiraMCPTests(unittest.TestCase):
    def setUp(self):
        integrations = dict(config.CONFIG["integrations"])
        integrations["jira"] = {
            **integrations["jira"],
            "projects": [
                {"id": "team", "key": "ABC", "read_only": False},
                {"id": "reference", "key": "RO", "read_only": True},
            ],
        }
        self.config_patch = patch.object(config, "CONFIG", {**config.CONFIG, "integrations": integrations})
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.server = FastMCP("jira-test")
        registry.register_all(self.server)

    def test_registers_the_final_jira_tool_list(self):
        names = {tool.name for tool in self.server._tool_manager.list_tools()}
        expected = {
            "jira_search", "jira_get_issue", "jira_list_boards", "jira_list_sprints",
            "jira_search_users", "jira_get_issue_types", "jira_get_priorities",
            "jira_create_issue", "jira_update_issue", "jira_add_comment", "jira_add_worklog",
            "jira_transition_issue", "jira_add_issue_to_sprint",
        }
        self.assertEqual(names, expected)

    def test_issue_creation_requires_description_and_adds_ai_marker(self):
        create = self.server._tool_manager.get_tool("jira_create_issue").fn
        with self.assertRaises(ValueError):
            create("team", "Story", "A feature", "")

        with patch.object(issue_writes, "request", return_value={"key": "ABC-1"}) as request_mock:
            create("team", "Story", "A feature", "Details", ["backend"])
        fields = request_mock.call_args.kwargs["body"]["fields"]
        self.assertEqual(fields["description"], "[AI] Details")
        self.assertEqual(fields["labels"], ["backend", "ai-assisted"])

    def test_search_scopes_each_configured_project(self):
        with patch.object(issue_search, "request", return_value={"issues": [{"key": "ABC-2"}]}) as request_mock:
            result = self.server._tool_manager.get_tool("jira_search").fn(
                text='quote "this"', status="Open", max_results=20,
            )
        self.assertEqual(request_mock.call_count, 2)
        first_jql = request_mock.call_args_list[0].kwargs["params"]["jql"]
        self.assertIn('project = "ABC"', first_jql)
        self.assertIn('text ~ "quote \\"this\\""', first_jql)
        self.assertEqual(json.loads(result)["issues"][0]["key"], "ABC-2")

    def test_issue_read_can_include_epic_children(self):
        with patch.object(issue_reads, "request", side_effect=[
            {"key": "ABC-3", "fields": {"issuetype": {"name": "Epic"}}},
            {"issues": [{"key": "ABC-4"}]},
        ]) as request_mock:
            result = self.server._tool_manager.get_tool("jira_get_issue").fn(
                "ABC-3", include_comments=True, include_worklogs=True,
                include_changelog=True, include_epic_issues=True,
            )
        self.assertEqual(
            request_mock.call_args_list[0].kwargs["params"]["fields"],
            "summary,description,issuetype,status,assignee,reporter,priority,labels,comment,worklog",
        )
        self.assertEqual(json.loads(result)["epic_issues"][0]["key"], "ABC-4")

    def test_worklog_comment_is_required_and_prefixed(self):
        add_worklog = self.server._tool_manager.get_tool("jira_add_worklog").fn
        with self.assertRaises(ValueError):
            add_worklog("ABC-1", "30m", " ")
        with patch.object(worklogs, "request", return_value={"id": "1"}) as request_mock:
            add_worklog("ABC-1", "30m", "Reviewed tests")
        self.assertEqual(request_mock.call_args.kwargs["body"]["comment"], "[AI] Reviewed tests")

    def test_read_only_project_rejects_writes_and_write_tools_are_annotated(self):
        with self.assertRaises(PermissionError):
            self.server._tool_manager.get_tool("jira_create_issue").fn(
                "reference", "Bug", "No write", "Description",
            )
        for name in (
            "jira_create_issue", "jira_update_issue", "jira_add_comment", "jira_add_worklog",
            "jira_transition_issue", "jira_add_issue_to_sprint",
        ):
            with self.subTest(tool=name):
                self.assertFalse(self.server._tool_manager.get_tool(name).annotations.readOnlyHint)


if __name__ == "__main__":
    unittest.main()
