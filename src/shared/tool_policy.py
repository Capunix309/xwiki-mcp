"""Apply shared tool visibility rules during MCP tool registration."""

from mcp.types import ToolAnnotations

from . import config


class ToolPolicyServer:
    """Filter tools according to the shared MCP configuration."""

    def __init__(self, server):
        self._server = server

    def tool(self, *args, **kwargs):
        def register(function):
            annotations = kwargs.get("annotations")
            if not isinstance(annotations, ToolAnnotations):
                raise ValueError(f"MCP tool '{function.__name__}' needs read/write annotations.")
            if not annotations.readOnlyHint and not config.expose_write_tools():
                return function
            if annotations.destructiveHint and not config.expose_destructive_tools():
                return function
            return self._server.tool(*args, **kwargs)(function)

        if len(args) == 1 and callable(args[0]) and not kwargs:
            return register(args[0])
        return register
