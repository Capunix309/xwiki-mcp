"""Replace the text below one XWiki heading while preserving other sections."""

import re

from ...core import config
from ...core.client import get_page, page_url, request, value_text, xml_page


def register(mcp):
    if config.READ_ONLY:
        return

    @mcp.tool()
    def edit_page_section(space: str, page: str, heading: str, replacement: str) -> str:
        """Replace a section's body, leaving its heading and sibling sections in place."""
        current = get_page(space, page)
        lines = value_text(current, "content").splitlines()
        start = next((i for i, line in enumerate(lines)
                      if (m := re.match(r"^(={1,6})\s+(.+?)\s*=*\s*$", line))
                      and m.group(2).strip().casefold() == heading.strip().casefold()), None)
        if start is None:
            raise ValueError(f"Heading not found: {heading}")
        level = len(re.match(r"^(={1,6})\s+", lines[start]).group(1))
        end = next((i for i in range(start + 1, len(lines))
                    if (m := re.match(r"^(={1,6})\s+", lines[i])) and len(m.group(1)) <= level), len(lines))
        updated = lines[:start + 1] + replacement.splitlines() + lines[end:]
        payload, _ = request("PUT", page_url(space, page),
                             xml_page("\n".join(updated), value_text(current, "title") or None,
                                      value_text(current, "syntax") or "xwiki/2.1"), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Updated section '{heading}' on {space}.{page}."
