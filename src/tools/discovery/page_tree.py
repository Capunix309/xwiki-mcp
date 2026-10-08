"""List wiki pages with authorship and modification metadata."""

import json

from ...core import config
from ...core.client import all_pages, page_fields


def register(mcp):
    @mcp.tool()
    def page_tree(space: str | None = None, author: str | None = None, limit: int = 500) -> str:
        """List pages with creator, last editor, modified date, and version; optionally filter by space or author."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")
        pages = [page_fields(page) for page in all_pages(space, author, max_pages=limit)]
        pages.sort(key=lambda row: (row["space"].casefold(), row["pageName"].casefold()))
        return json.dumps({"wiki": config.WIKI, "count": len(pages), "pages": pages,
                           "truncated": len(pages) == limit}, ensure_ascii=False, indent=2)
