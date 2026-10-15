from mcp.types import ToolAnnotations
from ..core.client import page_url, request


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def add_tags(space: str, page: str, tags: list[str]) -> str:
        """Add one or more tags to a page."""
        if not tags or any(not tag.strip() for tag in tags):
            raise ValueError("Provide at least one non-empty tag.")
        results = []
        for tag in tags:
            body = tag.strip().encode("utf-8")
            response, _ = request("PUT", page_url(space, page, "tags"), body, "text/plain")
            results.append(response.decode("utf-8", errors="replace") or tag.strip())
        return f"Added tags to {space}.{page}: {', '.join(tags)}"
