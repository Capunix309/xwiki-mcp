import re
import json

from ..core.client import get_page, page_url, request, value_text, xml_page


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool()
    def append_section(space: str, page: str, heading: str, content: str) -> str:
        """Append a level-two XWiki section to a page."""
        current = get_page(space, page)
        old = value_text(current, "content")
        title = value_text(current, "title") or None
        syntax = value_text(current, "syntax") or "xwiki/2.1"
        addition = f"\n\n== {heading.strip()} ==\n{content.strip()}"
        payload, _ = request("PUT", page_url(space, page), xml_page(old.rstrip() + addition, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Added section '{heading}' to {space}.{page}."

    @mcp.tool()
    def create_page(space: str, page: str, content: str, title: str | None = None,
                    syntax: str = "xwiki/2.1") -> str:
        """Create a page with XWiki syntax content."""
        payload, _ = request("PUT", page_url(space, page), xml_page(content, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Created {space}.{page}."

    @mcp.tool()
    def edit_page(space: str, page: str, content: str, title: str | None = None,
                  syntax: str | None = None) -> str:
        """Replace a page's content and optionally update its title or syntax."""
        payload, _ = request("PUT", page_url(space, page), xml_page(content, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Updated {space}.{page}."

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

    @mcp.tool()
    def read_page(space: str, page: str) -> str:
        """Read a page using its space path and page name."""
        return json.dumps(get_page(space, page), ensure_ascii=False, indent=2)

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
