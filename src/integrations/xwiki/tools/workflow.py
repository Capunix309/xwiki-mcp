import json
import re

from mcp.types import ToolAnnotations
from ..core import config
from ..core.client import all_pages, get_page, page_fields, page_url, request, value_text, xml_page

LINK = re.compile(r"\[\[(.*?)\]\]")
HEADING = re.compile(r"^(={1,6})\s+(.+?)\s*=*\s*$", re.M)
TEMPLATES = {
    "meeting": "= Meeting: {title} =\n\nDate: {date}\nAttendees: {attendees}\n\n== Agenda ==\n{agenda}\n\n== Notes ==\n{notes}\n\n== Decisions ==\n{decisions}\n\n== Actions ==\n{actions}",
    "decision": "= Decision: {title} =\n\nDate: {date}\nStatus: Proposed\n\n== Context ==\n{context}\n\n== Decision ==\n{decision}\n\n== Consequences ==\n{consequences}",
    "task": "= {title} =\n\nStatus: To do\nOwner: {owner}\nDue date: {due_date}\n\n== Description ==\n{description}\n\n== Notes ==\n{notes}",
    "report": "= {title} =\n\nDate: {date}\n\n== Summary ==\n{summary}\n\n== Details ==\n{details}\n\n== Next steps ==\n{next_steps}",
}
DECISION = re.compile(r"\b(decision|decided|we will|agreed to|chosen option)\b", re.I)
TASK = re.compile(r"^\s*(?:[-*]\s*)?\[([ xX])\]\s*(.+)$")
OWNER = re.compile(r"(?:owner|responsible|assigned\s+to)\s*:\s*([^,;]+)", re.I)


def register(mcp):
    """Register this category of XWiki tools."""
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def consistency_check(space: str, required_headings: list[str] | None = None,
                          scan_limit: int = 100) -> str:
        """Check pages for required headings and unresolved internal page links."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        required = [heading.casefold() for heading in (required_headings or [])]
        pages = all_pages(space, max_pages=scan_limit)
        known = {page_fields(item)["fullName"].split(":")[-1] for item in pages}
        issues = []
        for item in pages:
            meta = page_fields(item)
            try:
                body = get_page(meta["space"], meta["pageName"])
            except RuntimeError as exc:
                issues.append({"page": meta["fullName"], "error": str(exc)})
                continue
            content = value_text(body, "content")
            headings = {match.group(2).casefold() for match in HEADING.finditer(content)}
            missing = [heading for heading in required if heading not in headings]
            broken = []
            for raw in LINK.findall(content):
                target = raw.rsplit(">>", 1)[-1].strip().split("#", 1)[0]
                if not target or target.startswith(("http:", "https:", "mailto:")):
                    continue
                normalized = target.replace("/", ".").strip(".")
                if "." in normalized and normalized not in known:
                    broken.append(target)
            if missing or broken:
                issues.append({"page": meta["fullName"], "missingHeadings": missing,
                               "unresolvedLinks": sorted(set(broken))})
        return json.dumps({"space": space, "pagesScanned": len(pages), "truncated": len(pages) == scan_limit,
                           "issues": issues}, ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def create_page_from_template(space: str, page: str, template: str, title: str,
                                  fields: dict[str, str] | None = None) -> str:
        """Create a meeting, decision, task, or report page using supplied field values."""
        if template not in TEMPLATES:
            raise ValueError("template must be meeting, decision, task, or report.")
        values = {key: "" for key in {part.split("}")[0] for part in TEMPLATES[template].split("{")[1:]}}
        values.update(fields or {})
        values["title"] = title
        try:
            content = TEMPLATES[template].format_map(values)
        except KeyError as exc:
            raise ValueError(f"Missing template field: {exc.args[0]}") from None
        response, _ = request("PUT", page_url(space, page), xml_page(content, title, "xwiki/2.1"), "application/xml")
        return response.decode("utf-8", errors="replace") or f"Created {template} page {space}.{page}."

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def decision_log(space: str, scan_limit: int = 100) -> str:
        """Find likely decisions in a space, with the source page and matching lines."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        pages = all_pages(space, max_pages=scan_limit)
        matches = []
        for item in pages:
            meta = page_fields(item)
            try:
                body = get_page(meta["space"], meta["pageName"])
            except RuntimeError:
                continue
            lines = [line.strip() for line in value_text(body, "content").splitlines()
                     if line.strip() and DECISION.search(line)]
            if lines:
                matches.append({"page": meta["fullName"], "title": meta["title"], "statements": lines[:20]})
        return json.dumps({"space": space, "pagesScanned": len(pages), "truncated": len(pages) == scan_limit,
                           "decisions": matches}, ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def project_status(space: str, scan_limit: int = 100) -> str:
        """Collect checkbox tasks and nearby owner labels from pages in a space."""
        if not 1 <= scan_limit <= 250:
            raise ValueError("scan_limit must be between 1 and 250.")
        pages = all_pages(space, max_pages=scan_limit)
        tasks = []
        errors = []
        for item in pages:
            meta = page_fields(item)
            try:
                body = get_page(meta["space"], meta["pageName"])
            except RuntimeError as exc:
                errors.append({"page": meta["fullName"], "error": str(exc)})
                continue
            lines = value_text(body, "content").splitlines()
            owner = next((match.group(1).strip() for line in lines if (match := OWNER.search(line))), "")
            for line in lines:
                match = TASK.match(line)
                if match:
                    tasks.append({"page": meta["fullName"], "task": match.group(2).strip(),
                                  "complete": match.group(1).lower() == "x", "owner": owner})
        return json.dumps({"space": space, "pagesScanned": len(pages), "truncated": len(pages) == scan_limit,
                           "readErrors": errors,
                           "total": len(tasks), "completed": sum(task["complete"] for task in tasks),
                           "tasks": tasks}, ensure_ascii=False, indent=2)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def wiki_digest(days: int = 14, limit: int = 30) -> str:
        """List recently changed pages with title, author, and modified date."""
        if not 1 <= days <= 3650 or not 1 <= limit <= 100:
            raise ValueError("days must be 1–3650 and limit must be 1–100.")
        pages = [page_fields(item) for item in all_pages(max_pages=500)]
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        selected = []
        for page in pages:
            try:
                modified = datetime.fromisoformat(page["modified"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if modified >= cutoff:
                selected.append(page)
        selected.sort(key=lambda row: row["modified"], reverse=True)
        return json.dumps({"wiki": config.current().wiki, "days": days, "changes": selected[:limit],
                           "truncated": len(selected) > limit}, ensure_ascii=False, indent=2)
