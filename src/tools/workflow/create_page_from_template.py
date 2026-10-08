"""Create a structured page from a built-in project template."""

from ...core import config
from ...core.client import page_url, request, xml_page

TEMPLATES = {
    "meeting": "= Meeting: {title} =\n\nDate: {date}\nAttendees: {attendees}\n\n== Agenda ==\n{agenda}\n\n== Notes ==\n{notes}\n\n== Decisions ==\n{decisions}\n\n== Actions ==\n{actions}",
    "decision": "= Decision: {title} =\n\nDate: {date}\nStatus: Proposed\n\n== Context ==\n{context}\n\n== Decision ==\n{decision}\n\n== Consequences ==\n{consequences}",
    "task": "= {title} =\n\nStatus: To do\nOwner: {owner}\nDue date: {due_date}\n\n== Description ==\n{description}\n\n== Notes ==\n{notes}",
    "report": "= {title} =\n\nDate: {date}\n\n== Summary ==\n{summary}\n\n== Details ==\n{details}\n\n== Next steps ==\n{next_steps}",
}


def register(mcp):
    if config.READ_ONLY:
        return

    @mcp.tool()
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
