"""Extract outgoing XWiki page links from a page's stored content."""

import json
import re

from ...core.client import get_page, value_text

LINK = re.compile(r"\[\[(.*?)\]\]")


def register(mcp):
    @mcp.tool()
    def get_page_links(space: str, page: str) -> str:
        """List page links found in XWiki syntax on a page."""
        data = get_page(space, page)
        content = value_text(data, "content")
        links = sorted({match.rsplit(">>", 1)[-1].strip() for match in LINK.findall(content) if match.strip()})
        return json.dumps({"page": f"{space}.{page}", "links": links}, ensure_ascii=False, indent=2)
