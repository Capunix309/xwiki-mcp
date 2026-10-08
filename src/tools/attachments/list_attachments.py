"""List attachments on a page."""

import json

from ...core.client import get_page, records


def register(mcp):
    @mcp.tool()
    def list_attachments(space: str, page: str) -> str:
        """List attachment metadata for a page."""
        data = get_page(space, page, "attachments", [("start", "0"), ("number", "100")])
        return json.dumps({"page": f"{space}.{page}", "attachments": records(data, "attachment") or records(data, "attachments") or data},
                          ensure_ascii=False, indent=2)
