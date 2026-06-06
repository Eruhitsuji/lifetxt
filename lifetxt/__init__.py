"""Parser and CLI utilities for the life.txt format."""

__version__ = "0.1.0"

from .model import Diagnostic, Item
from .parser import parse_line, parse_text
from .serializer import item_to_line, items_to_json, items_to_jsonl

__all__ = [
    "Diagnostic",
    "Item",
    "item_to_line",
    "items_to_json",
    "items_to_jsonl",
    "parse_line",
    "parse_text",
]
