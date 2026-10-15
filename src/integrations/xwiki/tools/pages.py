import re
import json
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from mcp.types import ToolAnnotations
from ..core import config
from ..core.client import get_page, page_url, request, value_text, xml_page


def _reference_xml(space: str, page: str, wiki: str) -> ET.Element:
    """Serialize a document reference in the format expected by XWiki jobs."""
    parts = [part.strip() for part in space.split("/")]
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("space must contain valid space names separated by '/'.")
    if not page.strip() or page in {".", ".."} or "/" in page or "\\" in page:
        raise ValueError("page must be a single, non-empty page name.")
    if not wiki or any(char in wiki for char in "/\\:"):
        raise ValueError("The configured wiki name is invalid for a page reference.")

    document = ET.Element("org.xwiki.model.reference.DocumentReference")
    ET.SubElement(document, "name").text = page.strip()
    parent = document
    space_references = []
    for part in reversed(parts):
        space_ref = ET.SubElement(parent, "parent", {"class": "org.xwiki.model.reference.SpaceReference"})
        ET.SubElement(space_ref, "name").text = part
        space_references.append(space_ref)
        parent = space_ref
    wiki_ref = ET.SubElement(parent, "parent", {"class": "org.xwiki.model.reference.WikiReference"})
    ET.SubElement(wiki_ref, "name").text = wiki
    ET.SubElement(wiki_ref, "type").text = "WIKI"
    for space_ref in reversed(space_references):
        ET.SubElement(space_ref, "type").text = "SPACE"
    ET.SubElement(document, "type").text = "DOCUMENT"
    return document


def _move_job_request(source_space: str, source_page: str, destination_space: str,
                      destination_page: str, wiki: str, update_links: bool) -> bytes:
    """Build an XWiki refactoring move request without losing page history."""
    root = ET.Element("jobRequest", xmlns="http://www.xwiki.org")
    job_id = ET.SubElement(root, "id")
    ET.SubElement(job_id, "element").text = str(uuid.uuid4())
    ET.SubElement(root, "interactive").text = "false"
    ET.SubElement(root, "remote").text = "true"
    ET.SubElement(root, "verbose").text = "true"
    for key, space, page in (("source", source_space, source_page),
                             ("destination", destination_space, destination_page)):
        prop = ET.SubElement(root, "property")
        ET.SubElement(prop, "key").text = key
        value = ET.SubElement(prop, "value")
        value.append(_reference_xml(space, page, wiki))
    prop = ET.SubElement(root, "property")
    ET.SubElement(prop, "key").text = "interactive"
    value = ET.SubElement(prop, "value")
    ET.SubElement(value, "boolean").text = "false"
    if not update_links:
        prop = ET.SubElement(root, "property")
        ET.SubElement(prop, "key").text = "updateLinks"
        value = ET.SubElement(prop, "value")
        ET.SubElement(value, "boolean").text = "false"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def append_section(space: str, page: str, heading: str, content: str) -> str:
        """Append a level-two XWiki section to a page."""
        current = get_page(space, page)
        old = value_text(current, "content")
        title = value_text(current, "title") or None
        syntax = value_text(current, "syntax") or "xwiki/2.1"
        addition = f"\n\n== {heading.strip()} ==\n{content.strip()}"
        payload, _ = request("PUT", page_url(space, page), xml_page(old.rstrip() + addition, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Added section '{heading}' to {space}.{page}."

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def create_page(space: str, page: str, content: str, title: str | None = None,
                    syntax: str = "xwiki/2.1") -> str:
        """Create a page with XWiki syntax content."""
        payload, _ = request("PUT", page_url(space, page), xml_page(content, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Created {space}.{page}."

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def edit_page(space: str, page: str, content: str, title: str | None = None,
                  syntax: str | None = None) -> str:
        """Replace a page's content and optionally update its title or syntax."""
        payload, _ = request("PUT", page_url(space, page), xml_page(content, title, syntax), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Updated {space}.{page}."

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    def move_page(source_space: str, source_page: str, destination_space: str,
                  destination_page: str, title: str | None = None,
                  update_links: bool = True) -> str:
        """Move or rename a page while preserving its XWiki version history.

        Spaces are paths separated by '/'. Set title only when the visible page
        title should also change; a destination page name changes its URL only.
        """
        get_page(source_space, source_page)
        if source_space.strip("/") == destination_space.strip("/") and source_page == destination_page:
            raise ValueError("The destination is the same as the source.")

        target_url = page_url(destination_space, destination_page)
        try:
            request("GET", target_url)
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
        else:
            raise ValueError(f"The destination already exists: {destination_space}.{destination_page}")

        wiki_name = config.current().wiki
        body = _move_job_request(source_space, source_page, destination_space,
                                 destination_page, wiki_name, update_links)
        endpoint = f"{config.rest_root()}/jobs?{urlencode([('jobType', 'refactoring/move'), ('async', 'false')])}"
        payload, content_type = request("PUT", endpoint, body, "application/xml")
        job = json.loads(payload.decode("utf-8")) if "json" in content_type.lower() else None
        if job is None:
            try:
                job = ET.fromstring(payload)
            except ET.ParseError:
                job = payload.decode("utf-8", errors="replace")
        if isinstance(job, dict):
            state = str(job.get("state", ""))
            error = str(job.get("errorMessage", ""))
            if state.upper() in {"ERROR", "FAILED"}:
                raise RuntimeError(f"XWiki move failed: {error or state}")
        elif isinstance(job, ET.Element):
            state = next((element.text for element in job.iter() if element.tag.endswith("state")), "")
            error = next((element.text for element in job.iter() if element.tag.endswith("errorMessage")), "")
            if state.upper() in {"ERROR", "FAILED"}:
                raise RuntimeError(f"XWiki move failed: {error or state}")

        moved = get_page(destination_space, destination_page)
        if title is not None:
            payload, _ = request(
                "PUT", target_url,
                xml_page(value_text(moved, "content"), title,
                         value_text(moved, "syntax") or "xwiki/2.1"),
                "application/xml",
            )

        return json.dumps({
            "source": f"{source_space}.{source_page}",
            "destination": f"{destination_space}.{destination_page}",
            "title": title,
            "history_preserved": True,
            "update_links": update_links,
            "job": job if isinstance(job, (dict, str)) else ET.tostring(job, encoding="unicode"),
        }, ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def edit_page_section(space: str, page: str, heading: str, replacement: str) -> str:
        """Replace a section's body, leaving its heading and sibling sections in place."""
        current = get_page(space, page)
        lines = value_text(current, "content").splitlines()
        start = next((i for i, line in enumerate(lines)
                      if (m := re.match(r"^(={1,6})\s+(.+?)\s*=*\s*$", line))
                      and m.group(2).strip().casefold() == heading.strip().casefold()), None)
        if start is None:
            raise ValueError(f"Heading not found: {heading}")
        level = len(re.match(r"^(={1,6})\s+", lines[start]).group(1))
        end = next((i for i in range(start + 1, len(lines))
                    if (m := re.match(r"^(={1,6})\s+", lines[i])) and len(m.group(1)) <= level), len(lines))
        updated = lines[:start + 1] + replacement.splitlines() + lines[end:]
        payload, _ = request("PUT", page_url(space, page),
                             xml_page("\n".join(updated), value_text(current, "title") or None,
                                      value_text(current, "syntax") or "xwiki/2.1"), "application/xml")
        return payload.decode("utf-8", errors="replace") or f"Updated section '{heading}' on {space}.{page}."

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def read_page(space: str, page: str) -> str:
        """Read a page using its space path and page name."""
        return json.dumps(get_page(space, page), ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def read_page_section(space: str, page: str, heading: str) -> str:
        """Read the content under a matching XWiki heading until the next heading of the same or higher level."""
        data = get_page(space, page)
        content = value_text(data, "content")
        lines = content.splitlines()
        for index, line in enumerate(lines):
            match = re.match(r"^(={1,6})\s+(.+?)\s*=*\s*$", line)
            if match and match.group(2).strip().casefold() == heading.strip().casefold():
                end = len(lines)
                for pos in range(index + 1, len(lines)):
                    next_heading = re.match(r"^(={1,6})\s+", lines[pos])
                    if next_heading and len(next_heading.group(1)) <= len(match.group(1)):
                        end = pos
                        break
                return json.dumps({"page": f"{space}.{page}", "heading": heading,
                                   "content": "\n".join(lines[index:end])}, ensure_ascii=False, indent=2)
        raise ValueError(f"Heading not found: {heading}")
