"""Register tools belonging to the automation integration."""

from .tools import sync


def register_all(server) -> None:
    """Register all currently implemented automation tools."""
    sync.register(server)
