"""Parser and CLI utilities for the life.txt format."""

__version__ = "0.1.0"

from .model import Diagnostic, Item
from .parser import parse_line, parse_text
from .serializer import item_to_line, items_to_json, items_to_jsonl

# Keep the one remaining pre-atomic direct writer on the same shared mutation
# contract as CLI, TUI, Web, MCP, timer, and notification writes.  This is a
# compatibility bridge; command-focused modules can import mutation directly
# when the planned CLI/TUI split happens.
from .compat_writes import install_legacy_write_routes as _install_legacy_write_routes

_install_legacy_write_routes()
del _install_legacy_write_routes

# Connect the shared CAS layer to public Web and MCP requests.  Installation is
# dependency-free: FastAPI is still imported only when create_app() is called.
from .surface_runtime import install_runtime_contracts as _install_runtime_contracts

_install_runtime_contracts()
del _install_runtime_contracts

__all__ = [
    "Diagnostic",
    "Item",
    "item_to_line",
    "items_to_json",
    "items_to_jsonl",
    "parse_line",
    "parse_text",
]
