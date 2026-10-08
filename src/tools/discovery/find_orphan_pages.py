"""Find pages that are not linked to by other pages in a bounded scan."""

import json
import re

from ...core.client import all_pages, get_page, page_fields, value_text

LINK = re.compile(r"\[\[(.*?)\]\]")


def register(mcp):
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
