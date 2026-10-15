import json

from mcp.types import ToolAnnotations
from ..core import config
from ..core.client import all_pages, page_fields
from ..core.client import get, records


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def recent_changes(days: int = 30, limit: int = 50) -> str:
        """List pages modified within the last number of days."""
        if not 1 <= days <= 3650 or not 1 <= limit <= 100:
            raise ValueError("days must be 1–3650 and limit must be 1–100.")
        timestamp = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
        data = get("modifications", [("date", str(timestamp)), ("start", "0"), ("number", str(limit))])
        return json.dumps({"wiki": config.current().wiki, "days": days,
                           "changes": records(data, "modification") or records(data, "modifications") or data},
                          ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def who_wrote_pages(space: str | None = None, author: str | None = None, limit: int = 500) -> str:
        """List page titles, creators, last editors, and modified dates."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")
        pages = [page_fields(item) for item in all_pages(space, author, max_pages=limit)]
        return json.dumps({"wiki": config.current().wiki, "pages": pages, "count": len(pages),
                           "truncated": len(pages) == limit}, ensure_ascii=False, indent=2)
