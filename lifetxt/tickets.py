"""Development ticket (Redmine-style issue) core.

A ticket is a normal ``T`` record marked ``record:ticket``. It stays a plain
life.txt line that existing filters, agenda, and reports still understand; the
ticket layer adds canonical field semantics, a detailed ``ticket_status`` on top
of the coarse life.txt status, validation, and aggregation. No database becomes
the authority — life.txt remains the source of truth.

Generic project ``record:issue`` records remain available for operational
concerns that do not need the ticket workflow; this module only recognizes
``record:ticket``.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .config import config_section


TICKET_MARKER = "ticket"

# Canonical field registry. ``repeatable`` fields may appear multiple times;
# ``registry`` fields are validated against configured/allowed values when a
# registry is configured; the rest are free-form.
TICKET_FIELDS = OrderedDict(
    (
        ("tracker", {"repeatable": False, "registry": True}),
        ("ticket_status", {"repeatable": False, "registry": True}),
        ("priority", {"repeatable": False, "registry": True}),
        ("severity", {"repeatable": False, "registry": True}),
        ("reporter", {"repeatable": False, "registry": False}),
        ("assignee", {"repeatable": False, "registry": False}),
        ("watcher", {"repeatable": True, "registry": False}),
        ("component", {"repeatable": False, "registry": True}),
        ("category", {"repeatable": False, "registry": True}),
        ("version", {"repeatable": False, "registry": False}),
        ("milestone", {"repeatable": False, "registry": False}),
        ("sprint", {"repeatable": False, "registry": False}),
        ("est", {"repeatable": False, "registry": False}),
        ("elapsed", {"repeatable": False, "registry": False}),
        ("story_points", {"repeatable": False, "registry": False}),
        ("resolution", {"repeatable": False, "registry": False}),
        ("closed_by", {"repeatable": False, "registry": False}),
        ("branch", {"repeatable": False, "registry": False}),
        ("commit", {"repeatable": True, "registry": False}),
        ("pr", {"repeatable": True, "registry": False}),
        ("build", {"repeatable": False, "registry": False}),
    )
)

RELATION_FIELDS = ("parent", "depends_on", "blocks", "related", "duplicate_of", "replaced_by")

# Default detailed statuses and the coarse life.txt status each maps to. Users
# can override or extend through the ``ticketing.statuses`` config, but these
# keep a fresh workspace useful immediately.
DEFAULT_STATUS_MAP = OrderedDict(
    (
        ("new", "[ ]"),
        ("triaged", "[ ]"),
        ("assigned", "[ ]"),
        ("in_progress", "[/]"),
        ("review", "[/]"),
        ("testing", "[/]"),
        ("needs_info", "[?]"),
        ("blocked", "[?]"),
        ("deferred", "[>]"),
        ("resolved", "[x]"),
        ("closed", "[x]"),
        ("rejected", "[-]"),
        ("duplicate", "[-]"),
        ("wont_fix", "[-]"),
    )
)

TERMINAL_STATUSES = ("resolved", "closed", "rejected", "duplicate", "wont_fix")
OPEN_LIFE_STATUSES = ("[ ]", "[/]", "[?]", "[>]")

DEFAULT_PRIORITIES = ("low", "normal", "high", "urgent", "immediate")
DEFAULT_SEVERITIES = ("trivial", "minor", "major", "critical", "blocker")
DEFAULT_TRACKERS = ("bug", "feature", "task", "support")


def ticketing_config(config):
    return config_section(config, "ticketing")


def _configured_list(config, key, default):
    section = ticketing_config(config)
    value = section.get(key)
    if isinstance(value, dict):
        return list(value.keys())
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v)]
    return list(default)


def status_map(config):
    """Detailed status -> coarse life.txt status, config overriding defaults."""
    mapping = OrderedDict(DEFAULT_STATUS_MAP)
    section = ticketing_config(config)
    configured = section.get("statuses")
    if isinstance(configured, dict):
        for name, meta in configured.items():
            if isinstance(meta, dict) and meta.get("life_status"):
                mapping[str(name)] = str(meta["life_status"])
            elif isinstance(meta, str) and meta in ("[ ]", "[/]", "[?]", "[>]", "[x]", "[-]"):
                mapping[str(name)] = meta
            else:
                mapping.setdefault(str(name), "[ ]")
    return mapping


def id_prefix(config):
    return str(ticketing_config(config).get("id_prefix") or "TK")


def id_key(config):
    section = config_section(config, "ids")
    return str(section.get("key") or "id")


def is_ticket(item):
    return TICKET_MARKER in [str(v) for v in item.details.get("record", [])] and item.kind == "T"


def _first(item, key, default=None):
    values = item.details.get(key)
    return values[0] if values else default


def ticket_status_of(item):
    return _first(item, "ticket_status")


def iter_tickets(items):
    return [item for item in items if is_ticket(item)]


def ticket_id_of(item, key="id"):
    return _first(item, key)


def next_ticket_id(items, config):
    prefix = id_prefix(config)
    key = id_key(config)
    highest = 0
    for item in iter_tickets(items):
        value = ticket_id_of(item, key)
        if value and str(value).startswith(prefix + "-"):
            suffix = str(value)[len(prefix) + 1:]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return "%s-%d" % (prefix, highest + 1)


def ticket_summary(item, config, key="id"):
    return OrderedDict(
        (
            ("id", ticket_id_of(item, key)),
            ("title", item.title),
            ("tracker", _first(item, "tracker")),
            ("status", item.status),
            ("ticket_status", ticket_status_of(item)),
            ("priority", _first(item, "priority")),
            ("severity", _first(item, "severity")),
            ("assignee", _first(item, "assignee")),
            ("reporter", _first(item, "reporter")),
            ("component", _first(item, "component")),
            ("version", _first(item, "version")),
            ("sprint", _first(item, "sprint")),
            ("project", _first(item, "project")),
            ("due", _first(item, "due")),
            ("watchers", [str(v) for v in item.details.get("watcher", [])]),
            ("open", item.status in OPEN_LIFE_STATUSES),
            ("source", item.source),
            ("line", item.line),
        )
    )


def ticket_view(item, config, items=None, key="id"):
    """Aggregate a ticket's fields, relations, and time without modifying it."""
    summary = ticket_summary(item, config, key)
    relations = OrderedDict()
    for relation in RELATION_FIELDS:
        values = [str(v) for v in item.details.get(relation, [])]
        if values:
            relations[relation] = values
    incoming = []
    if items is not None:
        tid = summary["id"]
        if tid:
            from .links import backlink_records

            incoming = backlink_records(items, tid, key=key)
    fields = OrderedDict()
    for field in TICKET_FIELDS:
        values = [str(v) for v in item.details.get(field, [])]
        if values:
            fields[field] = values if TICKET_FIELDS[field]["repeatable"] else values[0]
    return OrderedDict(
        (
            ("summary", summary),
            ("fields", fields),
            ("relations", relations),
            ("incoming_links", incoming),
            ("est", _first(item, "est")),
            ("elapsed", _first(item, "elapsed")),
            ("resolution", _first(item, "resolution")),
        )
    )


def ticket_list(items, config, filters=None, key="id"):
    filters = filters or {}
    rows = []
    for item in iter_tickets(items):
        summary = ticket_summary(item, config, key)
        if not _matches_filters(summary, filters):
            continue
        rows.append(summary)
    rows.sort(key=lambda r: (str(r["id"] or "")))
    return rows


def _matches_filters(summary, filters):
    for field in ("tracker", "ticket_status", "priority", "severity", "assignee",
                  "component", "version", "sprint", "project"):
        wanted = filters.get(field)
        if wanted and str(summary.get(field)) != str(wanted):
            return False
    if filters.get("open_only") and not summary["open"]:
        return False
    return True


def validate_ticket(item, config, key="id"):
    """Return typed diagnostics for one ticket record."""
    rows = []
    tid = ticket_id_of(item, key)
    if not tid:
        rows.append(_diag("warning", "TK001", "Ticket has no id.", "Assign a stable id.", item))

    detailed = ticket_status_of(item)
    mapping = status_map(config)
    if detailed:
        if detailed not in mapping:
            rows.append(_diag("warning", "TK002",
                              "Unknown ticket_status %r." % detailed,
                              "Add it to ticketing.statuses or use a known status.", item))
        else:
            expected_life = mapping[detailed]
            if item.status != expected_life:
                rows.append(_diag("error", "TK003",
                                  "ticket_status %r expects life status %s but item is %s."
                                  % (detailed, expected_life, item.status),
                                  "Align the [ ]/[x]/... status with the ticket_status.", item))

    rows.extend(_registry_diagnostics(item, config))
    rows.extend(_required_field_diagnostics(item, config))
    return rows


def _registry_diagnostics(item, config):
    rows = []
    registries = OrderedDict(
        (
            ("tracker", _configured_list(config, "trackers", DEFAULT_TRACKERS)),
            ("priority", _configured_list(config, "priorities", DEFAULT_PRIORITIES)),
            ("severity", _configured_list(config, "severities", DEFAULT_SEVERITIES)),
        )
    )
    components = _configured_list(config, "components", [])
    if components:
        registries["component"] = components
    for field, allowed in registries.items():
        value = _first(item, field)
        if value and allowed and str(value) not in allowed:
            rows.append(_diag("warning", "TK004",
                              "%s %r is not in the configured list." % (field, value),
                              "Use one of: %s." % ", ".join(allowed), item))
    return rows


def _required_field_diagnostics(item, config):
    rows = []
    required = _configured_list(config, "required_fields", [])
    for field in required:
        if not item.details.get(field):
            rows.append(_diag("error", "TK005",
                              "Required ticket field %r is missing." % field,
                              "Set %s: on the ticket." % field, item))
    return rows


def _diag(severity, code, message, hint, item):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("hint", hint),
            ("source", getattr(item, "source", None)),
            ("line", getattr(item, "line", None)),
        )
    )


def build_ticket_line(config, subject, tracker=None, priority=None, severity=None,
                      assignee=None, reporter=None, component=None, version=None,
                      sprint=None, ticket_status="new", project=None, due=None,
                      est=None, watchers=None, ticket_id=None, extra=None):
    """Build a new ticket life.txt line with defaults applied."""
    section = ticketing_config(config)
    defaults = section.get("defaults") if isinstance(section.get("defaults"), dict) else {}
    tracker = tracker or defaults.get("tracker") or "task"
    priority = priority or defaults.get("priority") or "normal"
    mapping = status_map(config)
    life_status = mapping.get(ticket_status, "[ ]")

    parts = [life_status, "T", "_".join(str(subject).split()), "record:ticket"]
    ordered = OrderedDict(
        (
            (id_key(config), ticket_id),
            ("tracker", tracker),
            ("ticket_status", ticket_status),
            ("priority", priority),
            ("severity", severity),
            ("project", project),
            ("component", component),
            ("version", version),
            ("sprint", sprint),
            ("reporter", reporter),
            ("assignee", assignee),
            ("due", due),
            ("est", est),
        )
    )
    for detail_key, value in ordered.items():
        if value:
            parts.append("%s:%s" % (detail_key, value))
    for watcher in watchers or []:
        parts.append("watcher:%s" % watcher)
    for detail_key, value in (extra or {}).items():
        if value:
            parts.append("%s:%s" % (detail_key, value))
    return " ".join(parts)


def find_ticket_file(paths, ticket_id, key="id"):
    """Return the first input path that contains the ticket id, or None."""
    from .webapp import find_item_line_by_id

    for path in paths:
        if not path or path == "-":
            continue
        try:
            line_no, item = find_item_line_by_id(path, ticket_id, kind="T", key=key)
        except Exception:
            continue
        if line_no and item is not None and is_ticket(item):
            return path
    return None


def apply_ticket_patch(path, ticket_id, detail_updates=None, status=None, key="id"):
    """Patch a ticket's details and/or coarse status in one rewrite.

    Details set to ``None`` are removed. ``status`` overrides the coarse life.txt
    status while every other field is preserved. Returns the write result.
    """
    from .webapp import find_item_line_by_id, update_item_in_file

    line_no, item = find_item_line_by_id(path, ticket_id, kind="T", key=key)
    if item is None or not is_ticket(item):
        raise ValueError("Ticket %r not found in %s." % (ticket_id, path))
    details = OrderedDict((k, list(v)) for k, v in item.details.items())
    for detail_key, value in (detail_updates or {}).items():
        if value is None:
            details.pop(detail_key, None)
        elif isinstance(value, (list, tuple)):
            details[detail_key] = [str(v) for v in value]
        else:
            details[detail_key] = [str(value)]
    payload = OrderedDict(
        (
            ("status", status or item.status),
            ("type", item.kind),
            ("title", item.title),
            ("details", details),
        )
    )
    return update_item_in_file(path, line_no, payload)


def transition_updates(config, ticket_status, actor=None):
    """Detail/status updates for moving a ticket to ``ticket_status``."""
    mapping = status_map(config)
    life = mapping.get(ticket_status, "[ ]")
    updates = OrderedDict((("ticket_status", ticket_status),))
    if ticket_status in TERMINAL_STATUSES:
        if actor:
            updates["closed_by"] = actor
    return updates, life
