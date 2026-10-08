"""Add a comment to a page."""

import xml.etree.ElementTree as ET

from ...core import config
from ...core.client import page_url, request


def register(mcp):
    if config.READ_ONLY:
        return

    @mcp.tool()
    def add_comment(space: str, page: str, text: str) -> str:
        """Post a comment on a page."""
        root = ET.Element("comment", xmlns="http://www.xwiki.org")
        ET.SubElement(root, "text").text = text
        response, _ = request("POST", page_url(space, page, "comments"),
                              ET.tostring(root, encoding="utf-8", xml_declaration=True), "application/xml")
        return response.decode("utf-8", errors="replace") or f"Added comment to {space}.{page}."
