"""Shared read-scope selection for area and Saved View consumers."""


def resolve_read_scope(items, config, *, area=None, saved_view=None):
    """Return ``(scoped_items, metadata)`` using authoritative selectors."""
    if saved_view and area:
        raise ValueError(
            "read scope: area and saved_view cannot be combined; choose one scope."
        )
    if saved_view:
        from .saved_views import run_saved_view

        filtered, diagnostics = run_saved_view(items, config, saved_view)
        errors = [d for d in diagnostics if d.get("severity") == "error"]
        if errors:
            raise ValueError(errors[0]["message"])
        return filtered, {"kind": "saved_view", "name": str(saved_view)}
    if area:
        from .areas import area_row_keys, area_show

        keys = area_row_keys(items, config, area)
        if not keys:
            area_show(items, config, area)
        return [it for it in items if (getattr(it, "source", None), it.line) in keys], {
            "kind": "area",
            "name": str(area),
        }
    return items, None


def resolve_temporal_read_scope(
    items, config, *, area=None, saved_view=None, id_key="id"
):
    """Retain selected targets and attributable native evidence for review.

    Selectors still run over the authoritative snapshot, including Saved View
    sorting and limits. Generic readers continue to use ``resolve_read_scope``.
    Associated malformed payloads remain available to the native validators.
    """
    from collections import Counter

    from .native_timeline import _is_history

    selected, metadata = resolve_read_scope(
        items, config, area=area, saved_view=saved_view
    )
    if metadata is None:
        return items, None

    targets = [item for item in selected if not _is_history(item)]
    identities = Counter(
        str(value)
        for item in items
        if not _is_history(item)
        for value in set(item.details.get(id_key, []))
    )
    selected_ids = set()
    ambiguous = "read scope: ambiguous native history association."
    for target in targets:
        values = target.details.get(id_key, [])
        if len(values) != 1:
            # Workspace Timeline already reports targets without a unique ID.
            continue
        target_id = str(values[0])
        if identities[target_id] != 1:
            raise ValueError(ambiguous)
        selected_ids.add(target_id)

    history = []
    for item in items:
        if not _is_history(item):
            continue
        parents = [str(value) for value in item.details.get("parent", [])]
        if not selected_ids.intersection(parents):
            continue
        if len(parents) != 1:
            raise ValueError(ambiguous)
        history.append(item)
    return targets + history, metadata
