"""Start the combined XWiki, Jira, and automation MCP server over stdio."""

import sys

from mcp.server.fastmcp import FastMCP

from .shared import config
from .shared.tool_policy import ToolPolicyServer


def create_server() -> FastMCP:
    """Build a server from the integrations enabled in config.toml."""
    config.validate_config()
    server = FastMCP("mcp-tools")
    tool_server = ToolPolicyServer(server)
    enabled: list[str] = []
    if config.integration("xwiki").enabled:
        from .integrations.xwiki.core.config import validate_config as validate_xwiki
        from .integrations.xwiki.tools.registry import register_all

        validate_xwiki()
        register_all(tool_server)
        enabled.append("XWiki")
    if config.integration("jira").enabled:
        from .integrations.jira.tools.registry import register_all

        register_all(tool_server)
        enabled.append("Jira")
    if config.automation_settings().get("enabled", False):
        from .integrations.automation.registry import register_all

        register_all(tool_server)
        enabled.append("Automation")
    print(f"MCP-tools ready for: {', '.join(enabled) or 'no integrations'}.", file=sys.stderr)
    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
