"""Append a new heading and content to a page."""

from ...core import config
from ...core.client import get_page, page_url, request, value_text, xml_page


def register(mcp):
    if config.READ_ONLY:
        return

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
