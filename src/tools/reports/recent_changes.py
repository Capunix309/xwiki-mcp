"""Summarize recent wiki modifications."""

import json
from datetime import datetime, timezone

from ...core import config
from ...core.client import get, records


def register(mcp):
    @mcp.tool()
    def recent_changes(days: int = 30, limit: int = 50) -> str:
        """List pages modified within the last number of days."""
        if not 1 <= days <= 3650 or not 1 <= limit <= 100:
            raise ValueError("days must be 1–3650 and limit must be 1–100.")
        timestamp = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
        data = get("modifications", [("date", str(timestamp)), ("start", "0"), ("number", str(limit))])
        return json.dumps({"wiki": config.WIKI, "days": days,
                           "changes": records(data, "modification") or records(data, "modifications") or data},
                          ensure_ascii=False, indent=2)
