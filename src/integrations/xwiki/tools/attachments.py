import base64
import json
from mcp.types import ToolAnnotations
from ..core.client import get_page, page_url, records, request


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def list_attachments(space: str, page: str) -> str:
        """List attachment metadata for a page."""
        data = get_page(space, page, "attachments", [("start", "0"), ("number", "100")])
        return json.dumps({"page": f"{space}.{page}", "attachments": records(data, "attachment") or records(data, "attachments") or data},
                          ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def read_attachment(space: str, page: str, attachment: str, max_bytes: int = 1_000_000) -> str:
        """Read a page attachment; text files are returned as text, binary files as base64 up to max_bytes."""
        if not 1 <= max_bytes <= 5_000_000:
            raise ValueError("max_bytes must be between 1 and 5000000.")
        payload, content_type = request("GET", page_url(space, page, f"attachments/{attachment}"))
        if len(payload) > max_bytes:
            raise ValueError(f"Attachment is {len(payload)} bytes, above max_bytes={max_bytes}.")
        media = content_type.split(";", 1)[0].lower()
        if media.startswith("text/") or media in {"application/json", "application/xml", "application/javascript"}:
            return json.dumps({"contentType": media, "text": payload.decode("utf-8", errors="replace")},
                              ensure_ascii=False, indent=2)
        return json.dumps({"contentType": media, "size": len(payload),
                           "base64": base64.b64encode(payload).decode("ascii")}, indent=2)
