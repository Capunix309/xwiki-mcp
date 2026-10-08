"""Check scanned pages for missing common sections and broken local links."""

import json
import re

from ...core.client import all_pages, get_page, page_fields, value_text

LINK = re.compile(r"\[\[(.*?)\]\]")
HEADING = re.compile(r"^(={1,6})\s+(.+?)\s*=*\s*$", re.M)


def register(mcp):
    @mcp.tool()
    def consistency_check(space: str, required_headings: list[str] | None = None,
                          scan_limit: int = 100) -> str:
        """Check pages for required headings and unresolved internal page links."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        required = [heading.casefold() for heading in (required_headings or [])]
        pages = all_pages(space, max_pages=scan_limit)
        known = {page_fields(item)["fullName"].split(":")[-1] for item in pages}
        issues = []
        for item in pages:
            meta = page_fields(item)
            try:
                body = get_page(meta["space"], meta["pageName"])
            except RuntimeError as exc:
                issues.append({"page": meta["fullName"], "error": str(exc)})
                continue
            content = value_text(body, "content")
            headings = {match.group(2).casefold() for match in HEADING.finditer(content)}
            missing = [heading for heading in required if heading not in headings]
            broken = []
            for raw in LINK.findall(content):
                target = raw.rsplit(">>", 1)[-1].strip().split("#", 1)[0]
                if not target or target.startswith(("http:", "https:", "mailto:")):
                    continue
                normalized = target.replace("/", ".").strip(".")
                if "." in normalized and normalized not in known:
                    broken.append(target)
            if missing or broken:
                issues.append({"page": meta["fullName"], "missingHeadings": missing,
                               "unresolvedLinks": sorted(set(broken))})
        return json.dumps({"space": space, "pagesScanned": len(pages), "truncated": len(pages) == scan_limit,
                           "issues": issues}, ensure_ascii=False, indent=2)
