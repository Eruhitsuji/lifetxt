"""Shared native life.txt payload helpers.

Extracted from :mod:`lifetxt.cli` (``_copy_item``/``_canonical_hierarchy_items``/
``_items_to_life_text``) so that other codecs -- the ``sqlite`` interchange
format (#691) and the ``.lifetxtz`` compressed archive (#693) -- can reuse the
exact same item-copying, hierarchy-canonicalization, and native-line rendering
semantics instead of re-deriving a parallel item model (#689).

This module has no dependency on :mod:`lifetxt.cli`, so it can be imported
from a codec module that :mod:`lifetxt.cli` itself imports without creating a
cycle.
"""

from collections import OrderedDict

from .model import Item
from .serializer import item_to_line


def copy_item(item):
    """Return a shallow-independent copy of ``item`` (details/list-safe)."""
    cloned = Item(
        item.status,
        item.kind,
        item.title,
        OrderedDict((key, list(values)) for key, values in item.details.items()),
        line=item.line,
        source_text=getattr(item, "source_text", None),
        source=getattr(item, "source", None),
        indent=getattr(item, "indent", 0),
    )
    if hasattr(item, "end_line"):
        cloned.end_line = item.end_line
    return cloned


def canonical_hierarchy_items(items, key="id"):
    """Return item copies with explicit ``parent:`` links and no indentation.

    Converts indentation-based hierarchy into an explicit ``parent:`` detail
    referencing the nearest enclosing item's ``key`` value, matching the
    behavior ``lifetxt filter --canonical`` and ``lifetxt archive`` already
    rely on. Items whose parent has no ``key`` value are left unlinked.
    """
    canonical = []
    stack = []
    for item in items:
        cloned = copy_item(item)
        indent = int(getattr(item, "indent", 0) or 0)
        while stack and stack[-1][0] >= indent:
            stack.pop()

        if indent > 0 and not cloned.details.get("parent") and stack:
            parent = stack[-1][1]
            parent_ids = parent.details.get(key, [])
            if parent_ids:
                cloned.details.setdefault("parent", []).append(parent_ids[0])

        cloned.indent = 0
        canonical.append(cloned)
        stack.append((indent, cloned))
    return canonical


def items_to_life_text(items, canonical=False, key="id"):
    """Render ``items`` as native life.txt text.

    When ``canonical`` is false (the default), each item's original
    ``source_text`` is reused verbatim when available -- this is the
    round-trip-preserving path native ``export``/``import`` and ``filter``
    rely on. When ``canonical`` is true, hierarchy is flattened via
    :func:`canonical_hierarchy_items` and every line is freshly rendered
    through :func:`lifetxt.serializer.item_to_line`, matching the
    deterministic output the SQLite (#691) and ``.lifetxtz`` (#693) codecs
    require.
    """
    if canonical:
        items = canonical_hierarchy_items(items, key=key)
    lines = []
    for item in items:
        if canonical:
            lines.append(item_to_line(item))
        else:
            lines.append(getattr(item, "source_text", None) or item_to_line(item))
    text = "\n".join(lines)
    if text:
        text += "\n"
    return text
