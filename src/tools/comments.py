import xml.etree.ElementTree as ET
import json

from ..core.client import get_page, page_url, records, request


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool()
    def add_comment(space: str, page: str, text: str) -> str:
        """Post a comment on a page."""
        root = ET.Element("comment", xmlns="http://www.xwiki.org")
        ET.SubElement(root, "text").text = text
        response, _ = request("POST", page_url(space, page, "comments"),
                              ET.tostring(root, encoding="utf-8", xml_declaration=True), "application/xml")
        return response.decode("utf-8", errors="replace") or f"Added comment to {space}.{page}."

    @mcp.tool()
    def list_comments(space: str, page: str, limit: int = 50) -> str:
        """List comments attached to a page."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        data = get_page(space, page, "comments", [("start", "0"), ("number", str(limit))])
        return json.dumps({"page": f"{space}.{page}", "comments": records(data, "comment") or records(data, "comments") or data},
                          ensure_ascii=False, indent=2)
