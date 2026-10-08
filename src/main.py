"""Start the project-scoped XWiki MCP server over stdio."""

import sys

from mcp.server.fastmcp import FastMCP

from src.core import config
from src.tools.registry import register_all


def main() -> None:
    config.validate_config()
    server = FastMCP("xwiki")
    register_all(server)
    print(f"XWiki MCP ready for: {', '.join(config.WIKIS)}.", file=sys.stderr)
    server.run(transport="stdio")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
