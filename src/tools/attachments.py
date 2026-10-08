import base64
import json
import mimetypes
from pathlib import Path

from ..core.client import get_page, page_url, records, request

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool()
    def list_attachments(space: str, page: str) -> str:
        """List attachment metadata for a page."""
        data = get_page(space, page, "attachments", [("start", "0"), ("number", "100")])
        return json.dumps({"page": f"{space}.{page}", "attachments": records(data, "attachment") or records(data, "attachments") or data},
                          ensure_ascii=False, indent=2)

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

    @mcp.tool()
    def upload_attachment(space: str, page: str, filename: str) -> str:
        """Upload a file from xwiki-mcp/uploads/ to a page; files are limited to 10 MiB."""
        if not filename or Path(filename).name != filename or filename in {".", ".."}:
            raise ValueError("filename must be a single file name inside xwiki-mcp/uploads/.")
        root = UPLOAD_DIR.resolve()
        source = (root / filename).resolve(strict=True)
        if source.parent != root or not source.is_file():
            raise ValueError("The upload must be a regular file directly inside xwiki-mcp/uploads/.")
        size = source.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise ValueError("The maximum attachment size is 10 MiB.")
        content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        payload, _ = request("PUT", page_url(space, page, f"attachments/{filename}"),
                             source.read_bytes(), content_type)
        return payload.decode("utf-8", errors="replace") or f"Uploaded {filename} to {space}.{page}."
