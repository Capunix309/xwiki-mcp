"""Extract checkbox tasks and owners from project pages."""

import json
import re

from ...core.client import all_pages, get_page, page_fields, value_text

TASK = re.compile(r"^\s*(?:[-*]\s*)?\[([ xX])\]\s*(.+)$")
OWNER = re.compile(r"(?:owner|responsible|assigned\s+to)\s*:\s*([^,;]+)", re.I)


def register(mcp):
    @mcp.tool()
    def project_status(space: str, scan_limit: int = 100) -> str:
        """Collect checkbox tasks and nearby owner labels from pages in a space."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        pages = all_pages(space, max_pages=scan_limit)
        tasks = []
        for item in pages:
            meta = page_fields(item)
            body = get_page(meta["space"], meta["pageName"])
            lines = value_text(body, "content").splitlines()
            owner = next((match.group(1).strip() for line in lines if (match := OWNER.search(line))), "")
            for line in lines:
                match = TASK.match(line)
                if match:
                    tasks.append({"page": meta["fullName"], "task": match.group(2).strip(),
                                  "complete": match.group(1).lower() == "x", "owner": owner})
        return json.dumps({"space": space, "pagesScanned": len(pages), "truncated": len(pages) == scan_limit,
                           "total": len(tasks), "completed": sum(task["complete"] for task in tasks),
                           "tasks": tasks}, ensure_ascii=False, indent=2)
