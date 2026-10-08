"""List revisions of a page."""

import json

from ...core.client import get_page, records


def register(mcp):
    @mcp.tool()
    def page_history(space: str, page: str, limit: int = 30) -> str:
        """List recent page versions, including author and date when available."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        data = get_page(space, page, "history", [("start", "0"), ("number", str(limit))])
        return json.dumps({"page": f"{space}.{page}", "history": records(data, "version") or records(data, "versions") or data},
                          ensure_ascii=False, indent=2)
