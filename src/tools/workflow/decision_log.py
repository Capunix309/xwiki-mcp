"""Find decision sections and decision-related statements in pages."""

import json
import re

from ...core.client import all_pages, get_page, page_fields, value_text

DECISION = re.compile(r"\b(decision|decided|we will|agreed to|chosen option)\b", re.I)


def register(mcp):
    @mcp.tool()
    def decision_log(space: str, scan_limit: int = 100) -> str:
        """Find likely decisions in a space, with the source page and matching lines."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        pages = all_pages(space, max_pages=scan_limit)
        matches = []
        for item in pages:
            meta = page_fields(item)
            try:
                body = get_page(meta["space"], meta["pageName"])
            except RuntimeError:
                continue
            lines = [line.strip() for line in value_text(body, "content").splitlines()
                     if line.strip() and DECISION.search(line)]
            if lines:
                matches.append({"page": meta["fullName"], "title": meta["title"], "statements": lines[:20]})
        return json.dumps({"space": space, "pagesScanned": len(pages), "truncated": len(pages) == scan_limit,
                           "decisions": matches}, ensure_ascii=False, indent=2)
