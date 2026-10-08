"""Tool groups registered by the MCP entry point."""

from importlib import import_module
from pathlib import Path


def register_all(mcp) -> None:
    """Import and register each one-tool module in this package."""
    root = Path(__file__).parent
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        for module_path in sorted(folder.glob("*.py")):
            if module_path.name.startswith("_"):
                continue
            module = import_module(f"{__name__}.{folder.name}.{module_path.stem}")
            module.register(mcp)
