"""List comments on a page."""

import json

from ...core.client import get_page, records


def register(mcp):
    @mcp.tool()
    def list_comments(space: str, page: str, limit: int = 50) -> str:
        """List comments attached to a page."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        data = get_page(space, page, "comments", [("start", "0"), ("number", str(limit))])
        return json.dumps({"page": f"{space}.{page}", "comments": records(data, "comment") or records(data, "comments") or data},
                          ensure_ascii=False, indent=2)
