"""Compare two stored versions of a page."""

import difflib
import json

from ...core.client import get_page, value_text


def register(mcp):
    @mcp.tool()
    def diff_page_versions(space: str, page: str, old_version: str, new_version: str) -> str:
        """Return a unified text diff between two page versions, such as 1.2 and 1.3."""
        old = get_page(space, page, f"history/{old_version}")
        new = get_page(space, page, f"history/{new_version}")
        diff = "".join(difflib.unified_diff(
            value_text(old, "content").splitlines(keepends=True),
            value_text(new, "content").splitlines(keepends=True),
            fromfile=old_version, tofile=new_version,
        ))
        return json.dumps({"page": f"{space}.{page}", "oldVersion": old_version,
                           "newVersion": new_version, "diff": diff}, ensure_ascii=False, indent=2)
