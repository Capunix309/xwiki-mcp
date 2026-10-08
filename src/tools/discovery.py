import json
import re
import urllib.parse

from ..core import config
from ..core.client import all_pages, get, get_page, page_fields, records, value_text

LINK = re.compile(r"\[\[(.*?)\]\]")


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool()
    def find_orphan_pages(space: str | None = None, scan_limit: int = 100) -> str:
        """Find pages with no incoming XWiki syntax links among the scanned pages."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        pages = all_pages(space=space, max_pages=scan_limit)
        targets: set[str] = set()
        for item in pages:
            fields = page_fields(item)
            full_name = fields["fullName"]
            if not full_name:
                continue
            page_space = fields["space"]
            page_name = fields["pageName"]
            try:
                body = get_page(page_space, page_name)
            except RuntimeError:
                continue
            for link in LINK.findall(value_text(body, "content")):
                target = link.rsplit(">>", 1)[-1].split("%", 1)[0].strip()
                if target:
                    targets.add(target.replace("/", "."))
        orphans = [page_fields(item) for item in pages
                   if page_fields(item)["fullName"].split(":")[-1] not in targets]
        return json.dumps({"scanned": len(pages), "truncated": len(pages) == scan_limit,
                           "orphans": orphans}, ensure_ascii=False, indent=2)

    @mcp.tool()
    def get_page_links(space: str, page: str) -> str:
        """List page links found in XWiki syntax on a page."""
        data = get_page(space, page)
        content = value_text(data, "content")
        links = sorted({match.rsplit(">>", 1)[-1].strip() for match in LINK.findall(content) if match.strip()})
        return json.dumps({"page": f"{space}.{page}", "links": links}, ensure_ascii=False, indent=2)

    @mcp.tool()
    def list_spaces() -> str:
        """List spaces available in this XWiki."""
        data = get("spaces", [("start", "0"), ("number", "500")])
        spaces = records(data, "spaces") or records(data, "space")
        result = [{"name": value_text(row, "name", "id"), "wiki": value_text(row, "wiki"),
                   "home": value_text(row, "home")} for row in spaces]
        result.sort(key=lambda row: row["name"].casefold())
        return json.dumps({"count": len(result), "spaces": result}, ensure_ascii=False, indent=2)

    @mcp.tool()
    def page_tree(space: str | None = None, author: str | None = None, limit: int = 500) -> str:
        """List pages with creator, last editor, modified date, and version; optionally filter by space or author."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")
        pages = [page_fields(page) for page in all_pages(space, author, max_pages=limit)]
        pages.sort(key=lambda row: (row["space"].casefold(), row["pageName"].casefold()))
        return json.dumps({"wiki": config.current().wiki, "count": len(pages), "pages": pages,
                           "truncated": len(pages) == limit}, ensure_ascii=False, indent=2)

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
        return json.dumps({"wiki": config.current().wiki, "results": get(resource, params)}, ensure_ascii=False, indent=2)
