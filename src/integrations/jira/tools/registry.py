"""Register Jira tools with the combined server by responsibility."""

from .read import boards, fields, issue, search, sprints, users
from .workflow import transitions
from .write import comments, issues, sprints as sprint_writes, worklogs


def register_all(server) -> None:
    """Register the public Jira read and write tools."""
    for tool_group in (
        search, issue, boards, sprints, users, fields,
        issues, comments, worklogs, transitions, sprint_writes,
    ):
        tool_group.register(server)
