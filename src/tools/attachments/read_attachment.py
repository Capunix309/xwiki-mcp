"""Read an attachment's bytes or textual content."""

import base64
import json

from ...core.client import page_url, request


def register(mcp):
    @mcp.tool()
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
