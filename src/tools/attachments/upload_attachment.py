"""Upload a staged local file as a page attachment."""

import mimetypes
from pathlib import Path

from ...core import config
from ...core.client import page_url, request

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def register(mcp):
    if config.READ_ONLY:
        return

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
