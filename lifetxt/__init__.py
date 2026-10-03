"""Small, side-effect-free public Core import surface."""

__version__ = "1.0.3"

from .model import Diagnostic, Item
from .parser import parse_line, parse_text
from .serializer import item_to_line, items_to_json, items_to_jsonl


def bootstrap_legacy_surfaces():
    """Install the historical CLI/Web/Remote compatibility surface once."""
    from ._legacy_bootstrap import bootstrap

    bootstrap()


def __getattr__(name):
    """Retain lazy access to legacy package attributes without eager imports."""
    if name.startswith("_"):
        raise AttributeError(name)
    bootstrap_legacy_surfaces()
    try:
        return globals()[name]
    except KeyError as error:
        raise AttributeError(name) from error


__all__ = [
    "Diagnostic", "Item", "item_to_line", "items_to_json", "items_to_jsonl",
    "parse_line", "parse_text", "bootstrap_legacy_surfaces",
]
