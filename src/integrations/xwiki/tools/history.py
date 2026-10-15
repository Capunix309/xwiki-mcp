import difflib
import json

from mcp.types import ToolAnnotations
from ..core.client import get_page, records, value_text


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def diff_page_versions(space: str, page: str, old_version: str, new_version: str) -> str:
        """Return a unified text diff between two page versions, such as 1.2 and 1.3."""
        old = get_page(space, page, f"history/{old_version}")
        new = get_page(space, page, f"history/{new_version}")
        diff = "".join(difflib.unified_diff(
            value_text(old, "content").splitlines(keepends=True),
            value_text(new, "content").splitlines(keepends=True),
            fromfile=old_version, tofile=new_version,
        ))
        return json.dumps({"page": f"{space}.{page}", "oldVersion": old_version,
                           "newVersion": new_version, "diff": diff}, ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def page_history(space: str, page: str, limit: int = 30) -> str:
        """List recent page versions, including author and date when available."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        data = get_page(space, page, "history", [("start", "0"), ("number", str(limit))])
        return json.dumps({"page": f"{space}.{page}", "history": records(data, "version") or records(data, "versions") or data},
                          ensure_ascii=False, indent=2)
