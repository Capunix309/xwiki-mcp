import unittest
from unittest.mock import patch

from src.integrations.xwiki.core import config as xwiki_config
from src.server import create_server
from src.shared import config


class XWikiMCPTests(unittest.TestCase):
    def test_central_config_keeps_wikis_and_permissions(self):
        self.assertEqual(xwiki_config.DEFAULT_WIKI, "team")
        self.assertEqual(set(xwiki_config.WIKIS), {"team", "global", "openshift", "SPEAM"})
        self.assertFalse(xwiki_config.WIKIS["team"].read_only)
        self.assertTrue(all(xwiki_config.WIKIS[name].read_only for name in ("global", "openshift", "SPEAM")))

    def test_combined_server_registers_xwiki_tools_without_upload_tool(self):
        server = create_server()
        names = {tool.name for tool in server._tool_manager.list_tools()}
        self.assertIn("read_page", names)
        self.assertIn("list_attachments", names)
        self.assertIn("read_attachment", names)
        self.assertNotIn("upload_attachment", names)
        self.assertNotIn("move_page", names)
        self.assertIn("jira_search", names)

    def test_xwiki_tools_declare_read_or_write_on_the_decorator(self):
        with patch("src.shared.config.expose_destructive_tools", return_value=True):
            server = create_server()
        tools = {tool.name: tool for tool in server._tool_manager.list_tools()}
        self.assertTrue(tools["read_page"].annotations.readOnlyHint)
        self.assertFalse(tools["edit_page"].annotations.readOnlyHint)
        self.assertTrue(tools["move_page"].annotations.destructiveHint)

    def test_write_tools_can_be_hidden_from_the_model(self):
        with patch("src.shared.config.expose_write_tools", return_value=False):
            server = create_server()
        names = {tool.name for tool in server._tool_manager.list_tools()}
        self.assertIn("read_page", names)
        self.assertIn("jira_search", names)
        self.assertNotIn("edit_page", names)
        self.assertNotIn("jira_create_issue", names)

    def test_disabled_xwiki_tools_are_not_registered(self):
        xwiki = config.IntegrationConfig(False, "", "", "", "", None, None)
        jira = config.IntegrationConfig(True, "https://jira.example", "", "", "", "JIRA_USERNAME", "JIRA_PASSWORD")
        with patch("src.shared.config.validate_config"), patch(
            "src.server.config.integration", side_effect=lambda name: {"xwiki": xwiki, "jira": jira}[name]
        ):
            server = create_server()
        names = {tool.name for tool in server._tool_manager.list_tools()}
        self.assertIn("jira_search", names)
        self.assertNotIn("read_page", names)


if __name__ == "__main__":
    unittest.main()
