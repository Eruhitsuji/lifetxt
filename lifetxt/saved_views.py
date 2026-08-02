"""Saved views: named queries stored in configuration.

A saved view pairs a name with a query string (the shared query language) plus
optional sort/order/limit. Views live under the ``saved_views`` configuration
section, either as a name->definition object or a list of definitions. They are
validated against ``saved-view-v1.schema.json`` and executed through the same
``run_query`` path as ad-hoc queries, so a saved view and the query it wraps
always return the same items.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .query import parse_query, run_query


VIEW_VERSION = "1"


def _raw_views(config):
    section = config.get("saved_views") if isinstance(config, dict) else None
    result = OrderedDict()
    if isinstance(section, dict):
        for name, definition in section.items():
            result[str(name)] = definition
    elif isinstance(section, (list, tuple)):
        for definition in section:
            if isinstance(definition, dict) and definition.get("name"):
                result[str(definition["name"])] = definition
    return result


def normalize_view(name, definition):
    """Return a saved-view-v1 shaped record for one definition."""
    if isinstance(definition, str):
        definition = {"query": definition}
    definition = definition if isinstance(definition, dict) else {}
    sort = definition.get("sort")
    if isinstance(sort, str):
        sort = [sort]
    elif not isinstance(sort, (list, tuple)):
        sort = []
    limit = definition.get("limit")
    try:
        limit = int(limit) if limit not in (None, "") else None
    except (TypeError, ValueError):
        limit = None
    return OrderedDict(
        (
            ("view_version", VIEW_VERSION),
            ("name", str(name)),
            ("query", str(definition.get("query") or "")),
            ("sort", [str(value) for value in sort]),
            ("limit", limit),
            ("order", str(definition.get("order") or "asc")),
        )
    )


def list_saved_views(config):
    return [
        normalize_view(name, definition)
        for name, definition in _raw_views(config).items()
    ]


def get_saved_view(config, name):
    raw = _raw_views(config)
    if str(name) not in raw:
        raise ValueError(
            "Unknown saved view %r. Known: %s"
            % (name, ", ".join(raw.keys()) or "(none)")
        )
    return normalize_view(name, raw[str(name)])


def validate_saved_views(config):
    """Return typed diagnostics for every saved view's query and shape."""
    rows = []
    for view in list_saved_views(config):
        if not view["query"]:
            rows.append(
                _view_diagnostic(
                    "error",
                    "V001",
                    "Saved view %r has an empty query." % view["name"],
                    view["name"],
                )
            )
            continue
        _plan, query_diags = parse_query(view["query"])
        for diag in query_diags:
            if diag["severity"] == "error":
                rows.append(
                    _view_diagnostic(
                        "error",
                        "V002",
                        "Saved view %r: %s" % (view["name"], diag["message"]),
                        view["name"],
                    )
                )
    return rows


def _view_diagnostic(severity, code, message, name):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("view", name),
        )
    )


def run_saved_view(items, config, name):
    view = get_saved_view(config, name)
    sort = view["sort"][0] if view["sort"] else None
    return run_query(
        items,
        view["query"],
        config=config,
        sort=sort,
        order=view["order"],
        limit=view["limit"],
    )
