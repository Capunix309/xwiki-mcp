"""Create a page in the configured wiki."""

from ...core import config
from ...core.client import page_url, request, xml_page


def register(mcp):
    if config.READ_ONLY:
        return

    @mcp.tool()
    def create_page(space: str, page: str, content: str, title: str | None = None,
                    syntax: str = "xwiki/2.1") -> str:
        """Create a page with XWiki syntax content."""
        payload, _ = request("PUT", page_url(space, page), xml_page(content, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Created {space}.{page}."
