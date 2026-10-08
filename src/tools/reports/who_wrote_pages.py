"""Report page creators and last editors."""

import json

from ...core import config
from ...core.client import all_pages, page_fields


def register(mcp):
    @mcp.tool()
    def who_wrote_pages(space: str | None = None, author: str | None = None, limit: int = 500) -> str:
        """List page titles, creators, last editors, and modified dates."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")
        pages = [page_fields(item) for item in all_pages(space, author, max_pages=limit)]
        return json.dumps({"wiki": config.WIKI, "pages": pages, "count": len(pages),
                           "truncated": len(pages) == limit}, ensure_ascii=False, indent=2)
