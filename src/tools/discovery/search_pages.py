"""Search page names, titles, and content."""

import json
import urllib.parse

from ...core import config
from ...core.client import get


def register(mcp):
    @mcp.tool()
    def search_pages(query: str, limit: int = 20, start: int = 0,
                     scopes: list[str] | None = None, space: str | None = None) -> str:
        """Search pages, optionally limited to a space; use start and limit to paginate."""
        if not 1 <= limit <= 50 or start < 0:
            raise ValueError("limit must be 1–50 and start must be zero or greater.")
        selected = scopes or ["name", "title", "content"]
        if not set(selected) <= {"name", "title", "content", "objects"}:
            raise ValueError("scopes may contain name, title, content, or objects.")
        params = [("q", query), ("number", str(limit)), ("start", str(start))]
        params.extend(("scope", scope) for scope in selected)
        resource = f"spaces/{'/spaces/'.join(urllib.parse.quote(p.strip(), safe='') for p in space.split('/'))}/search" if space else "search"
        return json.dumps({"wiki": config.WIKI, "results": get(resource, params)}, ensure_ascii=False, indent=2)
