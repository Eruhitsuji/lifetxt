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
