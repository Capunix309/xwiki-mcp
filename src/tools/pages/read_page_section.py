"""Read a named section from an XWiki page."""

import json
import re

from ...core.client import get_page, value_text


def register(mcp):
    @mcp.tool()
    def read_page_section(space: str, page: str, heading: str) -> str:
        """Read the content under a matching XWiki heading until the next heading of the same or higher level."""
        data = get_page(space, page)
        content = value_text(data, "content")
        lines = content.splitlines()
        for index, line in enumerate(lines):
            match = re.match(r"^(={1,6})\s+(.+?)\s*=*\s*$", line)
            if match and match.group(2).strip().casefold() == heading.strip().casefold():
                end = len(lines)
                for pos in range(index + 1, len(lines)):
                    next_heading = re.match(r"^(={1,6})\s+", lines[pos])
                    if next_heading and len(next_heading.group(1)) <= len(match.group(1)):
                        end = pos
                        break
                return json.dumps({"page": f"{space}.{page}", "heading": heading,
                                   "content": "\n".join(lines[index:end])}, ensure_ascii=False, indent=2)
        raise ValueError(f"Heading not found: {heading}")
