"""List accessible spaces in the configured wiki."""

import json

from ...core.client import get, records, value_text


def register(mcp):
    @mcp.tool()
    def list_spaces() -> str:
        """List spaces available in this XWiki."""
        data = get("spaces", [("start", "0"), ("number", "500")])
        spaces = records(data, "space")
        result = [{"name": value_text(row, "name", "id"), "wiki": value_text(row, "wiki"),
                   "home": value_text(row, "home")} for row in spaces]
        result.sort(key=lambda row: row["name"].casefold())
        return json.dumps({"count": len(result), "spaces": result}, ensure_ascii=False, indent=2)
