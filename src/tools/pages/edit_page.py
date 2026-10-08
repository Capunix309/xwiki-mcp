"""Replace the content of an existing XWiki page."""

from ...core import config
from ...core.client import page_url, request, xml_page


def register(mcp):
    if config.READ_ONLY:
        return

    @mcp.tool()
    def edit_page(space: str, page: str, content: str, title: str | None = None,
                  syntax: str | None = None) -> str:
        """Replace a page's content and optionally update its title or syntax."""
        payload, _ = request("PUT", page_url(space, page), xml_page(content, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Updated {space}.{page}."
