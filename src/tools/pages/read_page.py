"""Read a complete XWiki page."""

import json

from ...core.client import get_page


def register(mcp):
    @mcp.tool()
    def read_page(space: str, page: str) -> str:
        """Read a page using its space path and page name."""
        return json.dumps(get_page(space, page), ensure_ascii=False, indent=2)
