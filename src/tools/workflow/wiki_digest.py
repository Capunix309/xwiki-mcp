"""Create a compact digest of recently changed pages."""

import json

from ...core import config
from ...core.client import all_pages, page_fields


def register(mcp):
    @mcp.tool()
    def wiki_digest(days: int = 14, limit: int = 30) -> str:
        """List recently changed pages with title, author, and modified date."""
        if not 1 <= days <= 3650 or not 1 <= limit <= 100:
            raise ValueError("days must be 1–3650 and limit must be 1–100.")
        pages = [page_fields(item) for item in all_pages(max_pages=500)]
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        selected = []
        for page in pages:
            try:
                modified = datetime.fromisoformat(page["modified"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if modified >= cutoff:
                selected.append(page)
        selected.sort(key=lambda row: row["modified"], reverse=True)
        return json.dumps({"wiki": config.WIKI, "days": days, "changes": selected[:limit],
                           "truncated": len(selected) > limit}, ensure_ascii=False, indent=2)
