"""Shared read backend for authenticated local/remote data surfaces."""

from __future__ import unicode_literals

import hashlib
from collections import OrderedDict

from .remote_access import RemoteAccessError, redact_remote_value

RESOURCE_NAMES = (
    "items",
    "tickets",
    "ticket-detail",
    "projects",
    "ticket-report",
    "links",
    "status",
    "agenda",
    "search",
)


def source_revision(paths):
    digest = hashlib.sha256()
    for path in paths or []:
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        try:
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def resource_catalog():
    return [
        {"name": "items", "parameters": ["q", "project", "type", "open_only", "limit"]},
        {
            "name": "tickets",
            "parameters": [
                "project",
                "status",
                "assignee",
                "limit",
                "cursor",
                "since_revision",
            ],
        },
        {"name": "ticket-detail", "parameters": ["id"]},
        {"name": "projects", "parameters": []},
        {"name": "ticket-report", "parameters": ["project", "stale_after_days"]},
        {"name": "links", "parameters": ["id", "direction", "relation", "limit"]},
        {"name": "status", "parameters": ["person", "active_only"]},
        {"name": "agenda", "parameters": ["after", "before", "limit"]},
        {"name": "search", "parameters": ["q", "types", "limit"]},
    ]


def _first(details, *keys):
    for key in keys:
        values = details.get(key) if isinstance(details, dict) else None
        if values:
            return values[0]
    return None


def _list(details, *keys):
    values = []
    for key in keys:
        current = details.get(key) if isinstance(details, dict) else None
        if current:
            values.extend(str(value) for value in current)
    return values


def _access_for_item(item):
    details = getattr(item, "details", {}) or {}
    return {
        "project": _first(details, "project"),
        "visibility": _first(details, "visibility") or "shared",
        "owner": _first(details, "owner", "assignee", "user", "person"),
        "groups": _list(details, "group", "groups", "team", "teams"),
    }


def _visible_items(items, principal):
    from .remote_access import can_access

    return [item for item in items if can_access(principal, **_access_for_item(item))]


def _read(paths, config):
    from .webapp import read_life_inputs

    return read_life_inputs(paths, config)


def _diagnostics(rows):
    """Return aggregate diagnostics without record text, source paths, or IDs."""
    counts = OrderedDict()
    for row in rows or []:
        value = row.to_dict() if hasattr(row, "to_dict") else dict(row or {})
        key = (
            str(value.get("severity") or "unknown"),
            str(value.get("code") or "UNKNOWN"),
        )
        counts[key] = counts.get(key, 0) + 1
    return [
        {"severity": severity, "code": code, "count": count}
        for (severity, code), count in counts.items()
    ]


def _item_rows(items, config):
    from .ids import id_key_from_config
    from .webapp import api_item

    key = id_key_from_config(config or {})
    rows = []
    for item in items:
        row = api_item(item, writable_path=None, id_key=key)
        row["editable"] = False
        # Raw source/text/markdown fields can embed absolute local attachment
        # paths. The structured title/details representation is authoritative
        # for this read-only remote contract.
        row.pop("source", None)
        row.pop("text", None)
        row.pop("markdown", None)
        rows.append(redact_remote_value(row))
    return rows


def _int(value, default=None, minimum=None, maximum=None, name="value"):
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise RemoteAccessError(
            "REMOTE_PARAMETER_INVALID", "%s must be an integer." % name, 400
        )
    if minimum is not None and parsed < minimum:
        raise RemoteAccessError(
            "REMOTE_PARAMETER_INVALID", "%s must be at least %s." % (name, minimum), 400
        )
    if maximum is not None and parsed > maximum:
        raise RemoteAccessError(
            "REMOTE_PARAMETER_INVALID", "%s must be at most %s." % (name, maximum), 400
        )
    return parsed


def _bool(value, default=False, name="value"):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    lowered = str(value).lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise RemoteAccessError(
        "REMOTE_PARAMETER_INVALID", "%s must be a boolean." % name, 400
    )


def _csv(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        rows = value
    else:
        rows = str(value).split(",")
    return [str(row).strip() for row in rows if str(row).strip()]


def _limit(rows, value):
    maximum = _int(value, default=None, minimum=0, maximum=5000, name="limit")
    return rows if maximum is None else rows[:maximum]


def _resource_items(items, config, params):
    from .agenda import filter_items

    filtered = filter_items(
        items,
        open_only=_bool(params.get("open_only"), name="open_only"),
        kinds=_csv(params.get("type")),
        projects=_csv(params.get("project")),
        text=params.get("q"),
    )
    filtered = _limit(filtered, params.get("limit"))
    return {"count": len(filtered), "items": _item_rows(filtered, config)}


_TICKETS_DEFAULT_PAGE_SIZE = 200


def _resource_tickets(items, config, params):
    from .tickets import ticket_list

    rows = ticket_list(items, config or {})
    project = params.get("project")
    status = params.get("status")
    assignee = params.get("assignee")
    if project:
        rows = [row for row in rows if str(row.get("project") or "") == str(project)]
    if status:
        rows = [
            row
            for row in rows
            if str(row.get("status") or row.get("ticket_status") or "") == str(status)
        ]
    if assignee:
        rows = [row for row in rows if str(row.get("assignee") or "") == str(assignee)]
    cursor = params.get("cursor")
    if cursor:
        cursor = str(cursor)
        rows = [row for row in rows if str(row.get("id") or "") > cursor]
    limit = _int(
        params.get("limit"),
        default=_TICKETS_DEFAULT_PAGE_SIZE,
        minimum=0,
        maximum=5000,
        name="limit",
    )
    page = rows[:limit]
    has_more = len(page) < len(rows)
    if not has_more:
        next_cursor = None
    elif page:
        next_cursor = str(page[-1].get("id") or "")
    else:
        # limit=0 (or another degenerate value) returned no rows even though
        # more exist past the cursor; resuming means retrying from the same
        # cursor, not advancing past data the caller never actually saw.
        next_cursor = cursor or None
    return {
        "count": len(page),
        "tickets": redact_remote_value(page),
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def _resource_ticket_detail(items, config, params):
    from .tickets import id_key, iter_tickets, ticket_id_of, ticket_view

    key = id_key(config or {})
    wanted = str(params.get("id") or "").strip()
    ticket = None
    if wanted:
        for item in iter_tickets(items):
            if str(ticket_id_of(item, key) or "") == wanted:
                ticket = item
                break
    if ticket is None:
        raise RemoteAccessError(
            "REMOTE_TICKET_NOT_FOUND",
            "Ticket %r was not found." % wanted,
            404,
        )
    return redact_remote_value(ticket_view(ticket, config or {}, items=items, key=key))


def _ticket_report(items, config, params):
    from .ticket_project_report import build_ticket_project_report

    stale = _int(
        params.get("stale_after_days"),
        default=14,
        minimum=0,
        maximum=36500,
        name="stale_after_days",
    )
    report = build_ticket_project_report(
        items, stale_after_days=stale, project=params.get("project")
    )
    return redact_remote_value(report)


def _resource_projects(items, config, params):
    report = _ticket_report(items, config, params)
    rows = report.get("projects", [])
    return {"count": len(rows), "projects": rows, "summary": report.get("summary", {})}


def _resource_links(items, config, params):
    from .ids import id_key_from_config
    from .links import link_records

    rows = link_records(
        items,
        key=id_key_from_config(config or {}),
        focus_id=params.get("id"),
        direction=params.get("direction") or "both",
        relations=_csv(params.get("relation")),
    )
    rows = _limit(rows, params.get("limit"))
    return {"count": len(rows), "links": redact_remote_value(rows)}


def _resource_status(items, config, params):
    from .status_summary import latest_status_records

    rows = latest_status_records(
        items,
        person=params.get("person"),
        active_only=_bool(params.get("active_only"), name="active_only"),
    )
    return {"count": len(rows), "status": redact_remote_value(rows)}


def _resource_agenda(items, config, params):
    from .agenda import agenda_records, parse_optional_time_range

    start, end = parse_optional_time_range(params.get("after"), params.get("before"))
    rows = agenda_records(items, start, end)
    rows = _limit(rows, params.get("limit"))
    return {"count": len(rows), "agenda": redact_remote_value(rows)}


def _resource_search(items, config, params):
    term = str(params.get("q") or "").lower()
    wanted = set(_csv(params.get("types")) or ["item", "project", "person"])
    allowed = {"item", "project", "person"}
    unsupported = wanted - allowed
    if unsupported:
        raise RemoteAccessError(
            "REMOTE_PARAMETER_INVALID",
            "Unsupported remote search types: %s" % ", ".join(sorted(unsupported)),
            400,
        )
    limit = _int(
        params.get("limit"), default=None, minimum=0, maximum=1000, name="limit"
    )
    groups = OrderedDict()
    if not term:
        return {"term": term, "total": 0, "groups": groups}

    if "item" in wanted:
        rows = []
        for item in items:
            details = getattr(item, "details", {}) or {}
            searchable = [getattr(item, "title", "")]
            for key, values in details.items():
                if key in (
                    "body",
                    "project",
                    "tag",
                    "context",
                    "id",
                    "assignee",
                    "owner",
                ):
                    searchable.extend(str(value) for value in values)
            if any(term in str(value).lower() for value in searchable):
                item_id = _first(details, "id") or getattr(item, "title", "")
                rows.append(
                    {
                        "type": "item",
                        "name": str(item_id),
                        "title": getattr(item, "title", ""),
                        "line": getattr(item, "line", None),
                    }
                )
        if limit is not None:
            rows = rows[:limit]
        if rows:
            groups["item"] = rows

    if "project" in wanted:
        names = sorted(
            set(
                str(_first(getattr(item, "details", {}) or {}, "project"))
                for item in items
                if _first(getattr(item, "details", {}) or {}, "project")
            )
        )
        rows = [
            {"type": "project", "name": name} for name in names if term in name.lower()
        ]
        if limit is not None:
            rows = rows[:limit]
        if rows:
            groups["project"] = rows

    if "person" in wanted:
        names = set()
        for item in items:
            details = getattr(item, "details", {}) or {}
            names.update(_list(details, "person", "owner", "assignee", "user"))
        rows = [
            {"type": "person", "name": name}
            for name in sorted(names)
            if term in name.lower()
        ]
        if limit is not None:
            rows = rows[:limit]
        if rows:
            groups["person"] = rows

    total = sum(len(rows) for rows in groups.values())
    return redact_remote_value({"term": term, "total": total, "groups": groups})


_BUILDERS = {
    "items": _resource_items,
    "tickets": _resource_tickets,
    "ticket-detail": _resource_ticket_detail,
    "projects": _resource_projects,
    "ticket-report": _ticket_report,
    "links": _resource_links,
    "status": _resource_status,
    "agenda": _resource_agenda,
    "search": _resource_search,
}


def read_resource(name, paths, config, principal, params=None):
    name = str(name or "").strip().lower()
    if name not in _BUILDERS:
        raise RemoteAccessError(
            "REMOTE_RESOURCE_UNKNOWN", "Unknown remote read resource: %s" % name, 404
        )
    revision = source_revision(paths)
    params = dict(params or {})
    if name == "tickets":
        since_revision = params.get("since_revision")
        if since_revision and str(since_revision) != revision:
            raise RemoteAccessError(
                "REMOTE_RESOURCE_REVISION_CHANGED",
                "The workspace changed since the requested page's revision; "
                "restart pagination without since_revision.",
                409,
                {"since_revision": str(since_revision), "current_revision": revision},
            )
    items, diagnostics = _read(paths, config)
    visible = _visible_items(items, principal)
    data = _BUILDERS[name](visible, config or {}, params)
    from .timezone_policy import utcnow

    return OrderedDict(
        (
            ("schema", "remote-read-response-v1.schema.json"),
            ("resource", name),
            ("revision", revision),
            ("generated_at", utcnow().isoformat()),
            ("data", redact_remote_value(data)),
            ("diagnostics", _diagnostics(diagnostics)),
        )
    )


def snapshot(paths, config, principal):
    tickets = read_resource("tickets", paths, config, principal)
    projects = read_resource("projects", paths, config, principal)
    return OrderedDict(
        (
            ("schema", "remote-snapshot-v1.schema.json"),
            ("revision", source_revision(paths)),
            ("tickets", tickets["data"].get("tickets", [])),
            ("projects", projects["data"].get("projects", [])),
            ("read_only", True),
        )
    )
