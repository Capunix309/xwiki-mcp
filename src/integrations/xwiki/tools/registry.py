"""Register tool groups with a per-call team/global wiki selector."""

from functools import wraps
import inspect

from ..core import config
from . import attachments, comments, discovery, history, pages, reports, tags, workflow


class _WikiAwareServer:
    """Add a wiki argument to tools and bind that selection for each call."""

    def __init__(self, server):
        self._server = server

    def tool(self, *args, **kwargs):
        def decorate(function):
            tool_kwargs = dict(kwargs)
            register = self._server.tool(*args, **tool_kwargs)
            signature = inspect.signature(function)
            parameters = list(signature.parameters.values())
            parameters.append(inspect.Parameter(
                "wiki", inspect.Parameter.KEYWORD_ONLY, default=config.DEFAULT_WIKI,
                annotation=str,
            ))

            @wraps(function)
            def invoke(*call_args, **call_kwargs):
                token = config.select_wiki(call_kwargs.pop("wiki", "team"))
                try:
                    return function(*call_args, **call_kwargs)
                finally:
                    config.reset_wiki(token)

            invoke.__signature__ = signature.replace(parameters=parameters)
            invoke.__annotations__ = {**function.__annotations__, "wiki": str}
            configured = ", ".join(
                f"{item.name} ({'read-only' if item.read_only else 'read-write'})"
                for item in config.WIKIS.values()
            )
            invoke.__doc__ = (function.__doc__ or "") + (
                f"\n\nSelect a configured wiki by id: {configured}. Defaults to {config.DEFAULT_WIKI}."
            )
            return register(invoke)

        return decorate


def register_all(server) -> None:
    """Register every XWiki tool category on one MCP server."""
    scoped = _WikiAwareServer(server)
    for module in (attachments, comments, discovery, history, pages, reports, tags, workflow):
        module.register(scoped)
