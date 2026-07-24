"""Surface-neutral project and portfolio aggregation.

Projects are not a new item type. A project is any value that appears in a
``project:`` detail, optionally described by a metadata record: a Note carrying
``record:project`` plus ``project:<name>`` and documented custom keys (``owner``,
``area``, ``state``, ``due``, ``do`` for start, ``visibility``). Milestones,
risks, issues, decisions, and meetings are ordinary Deadline/Note/Journal/Event
records tagged with ``record:<kind>`` and linked by ``project:``.

Static, slow-changing metadata (display name, aliases, default source/assignee,
templates, visibility) lives in the configuration registry under ``projects``.
Everything that changes — progress, risks, decisions, activity — stays in
life.txt records. This module reads both and produces deterministic summaries;
it never writes.

Every derived number exposes how it was computed. ``progress`` carries its
numerator, denominator, and formula, and ``health`` carries its label, reasons,
and any missing-data limitations, so no caller has to trust an opaque score.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .timeutil import parse_date_or_datetime


OPEN_STATUSES = ("[ ]", "[/]", "[?]")
DONE_STATUS = "[x]"
CANCELLED_STATUS = "[-]"
DEFERRED_STATUS = "[>]"
WORK_KINDS = ("T", "D")

RECORD_KINDS = ("project", "milestone", "risk", "issue", "decision", "meeting")
SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def _first(item, key, default=None):
    values = item.details.get(key)
    if values:
        return values[0]
    return default


def _record_marker(item):
    marker = _first(item, "record")
    return marker.lower() if marker else None


def _registry(config):
    projects = config.get("projects") if isinstance(config, dict) else None
    return projects if isinstance(projects, dict) else {}


def _alias_map(registry):
    aliases = OrderedDict()
    for name, meta in registry.items():
        aliases[name] = name
        if isinstance(meta, dict):
            for alias in meta.get("aliases") or []:
                aliases[str(alias)] = name
    return aliases


def alias_map(config=None):
    """Public alias→canonical map from the registry, for name resolution."""
    return _alias_map(_registry(config or {}))


def _new_project(name, meta):
    meta = meta if isinstance(meta, dict) else {}
    return OrderedDict(
        (
            ("name", name),
            ("display_name", meta.get("display_name") or name),
            ("aliases", list(meta.get("aliases") or [])),
            ("default_source", meta.get("default_source")),
            ("default_assignee", meta.get("default_assignee")),
            ("default_area", meta.get("default_area")),
            ("registry_visibility", meta.get("visibility")),
            ("has_registry", bool(meta)),
            ("has_record", False),
            ("state", None),
            ("owner", None),
            ("area", meta.get("default_area")),
            ("visibility", meta.get("visibility")),
            ("due", None),
            ("start", None),
            ("archived", False),
            ("tasks", []),
            ("milestones", []),
            ("risks", []),
            ("issues", []),
            ("decisions", []),
            ("meetings", []),
            ("other", []),
        )
    )


def _date_of(value):
    if not value:
        return None
    try:
        parsed = parse_date_or_datetime(value)
    except Exception:
        return None
    if parsed is None:
        return None
    return getattr(parsed, "date", lambda: parsed)()


def _is_blocked(item, status_by_id):
    targets = item.details.get("depends_on") or []
    for target in targets:
        blocker = status_by_id.get(str(target))
        if blocker is not None and blocker.status != DONE_STATUS and blocker.status != CANCELLED_STATUS:
            return True
    return False


def collect_projects(items, config=None, today=None):
    """Group items into project buckets merged with the registry."""
    config = config or {}
    registry = _registry(config)
    alias_map = _alias_map(registry)
    projects = OrderedDict()
    for name, meta in registry.items():
        projects[name] = _new_project(name, meta)

    status_by_id = {}
    for item in items:
        for value in item.details.get("id", []):
            status_by_id[str(value)] = item

    for item in items:
        names = [alias_map.get(v, v) for v in item.details.get("project", [])]
        if not names:
            continue
        marker = _record_marker(item)
        for name in names:
            proj = projects.get(name)
            if proj is None:
                proj = _new_project(name, {})
                projects[name] = proj
            _place_item(proj, item, marker, status_by_id)

    for proj in projects.values():
        proj["blocked_count"] = sum(1 for row in proj["tasks"] if row["blocked"])
    return projects


def _place_item(proj, item, marker, status_by_id):
    if marker == "project":
        proj["has_record"] = True
        proj["state"] = _first(item, "state") or proj["state"]
        proj["owner"] = _first(item, "owner") or _first(item, "assignee") or proj["owner"]
        proj["area"] = _first(item, "area") or proj["area"]
        proj["visibility"] = _first(item, "visibility") or proj["visibility"]
        proj["due"] = _first(item, "due") or proj["due"]
        proj["start"] = _first(item, "do") or _first(item, "from") or proj["start"]
        if item.status == CANCELLED_STATUS or _first(item, "state") in ("archived", "done", "closed"):
            proj["archived"] = True
        proj["other"].append(_item_ref(item))
        return
    if marker == "milestone" or (marker is None and item.kind == "D"):
        proj["milestones"].append(_milestone_ref(item))
        return
    if marker == "risk":
        proj["risks"].append(_risk_ref(item))
        return
    if marker == "issue":
        proj["issues"].append(_risk_ref(item))
        return
    if marker == "decision":
        proj["decisions"].append(_decision_ref(item))
        return
    if marker == "meeting" or (marker is None and item.kind == "E"):
        proj["meetings"].append(_item_ref(item))
        return
    if item.kind in WORK_KINDS:
        proj["tasks"].append(_task_ref(item, status_by_id))
        return
    proj["other"].append(_item_ref(item))


def _item_ref(item):
    return OrderedDict(
        (
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("source", item.source),
            ("line", item.line),
        )
    )


def _task_ref(item, status_by_id):
    ref = _item_ref(item)
    ref["assignee"] = _first(item, "assignee") or _first(item, "owner")
    ref["due"] = _first(item, "due")
    ref["elapsed"] = _first(item, "elapsed")
    ref["done"] = item.status == DONE_STATUS
    ref["open"] = item.status in OPEN_STATUSES
    ref["cancelled"] = item.status == CANCELLED_STATUS
    ref["blocked"] = _is_blocked(item, status_by_id)
    return ref


def _milestone_ref(item):
    ref = _item_ref(item)
    ref["due"] = _first(item, "due")
    ref["done"] = item.status == DONE_STATUS
    return ref


def _risk_ref(item):
    ref = _item_ref(item)
    ref["severity"] = (_first(item, "severity") or "medium").lower()
    ref["state"] = _first(item, "state") or "open"
    ref["owner"] = _first(item, "owner") or _first(item, "assignee")
    ref["open"] = ref["state"] not in ("closed", "resolved", "mitigated", "done")
    return ref


def _decision_ref(item):
    ref = _item_ref(item)
    ref["on"] = _first(item, "on") or _first(item, "at") or _first(item, "done")
    return ref


def compute_progress(proj):
    active = [row for row in proj["tasks"] if not row["cancelled"]]
    total = len(active)
    done = sum(1 for row in active if row["done"])
    percent = round(100.0 * done / total, 1) if total else None
    return OrderedDict(
        (
            ("done", done),
            ("total", total),
            ("percent", percent),
            ("formula", "done_tasks / non_cancelled_tasks * 100"),
            ("undefined_reason", None if total else "no non-cancelled task or deadline items"),
        )
    )


def overdue_tasks(proj, today):
    if today is None:
        return []
    rows = []
    for row in proj["tasks"]:
        if row["done"] or row["cancelled"]:
            continue
        due = _date_of(row.get("due"))
        if due is not None and due < today:
            rows.append(row)
    return rows


def top_risk_severity(proj):
    open_risks = [r for r in proj["risks"] if r["open"]]
    for severity in SEVERITY_ORDER:
        if any(r["severity"] == severity for r in open_risks):
            return severity
    return None


def compute_health(proj, today=None):
    progress = compute_progress(proj)
    overdue = overdue_tasks(proj, today)
    blocked = proj.get("blocked_count", 0)
    top_severity = top_risk_severity(proj)
    reasons = []
    limitations = []
    label = "green"

    if top_severity in ("critical", "high"):
        label = "red"
        reasons.append("open %s-severity risk" % top_severity)
    if overdue:
        reasons.append("%d overdue item(s)" % len(overdue))
        if progress["percent"] is not None and progress["percent"] < 50:
            label = "red"
        elif label != "red":
            label = "yellow"
    if blocked:
        reasons.append("%d blocked item(s)" % blocked)
        if label == "green":
            label = "yellow"
    if top_severity in ("medium", "low") and label == "green":
        label = "yellow"
        reasons.append("open %s-severity risk" % top_severity)

    if progress["percent"] is None:
        limitations.append("progress undefined: %s" % progress["undefined_reason"])
    if today is None:
        limitations.append("overdue not evaluated: no reference date supplied")
    if not proj["has_record"] and not proj["has_registry"]:
        limitations.append("no project record or registry entry; metadata inferred from tasks only")

    return OrderedDict(
        (
            ("label", label),
            ("reasons", reasons or ["no open risks, overdue, or blocked work"]),
            ("progress", progress),
            ("overdue_count", len(overdue)),
            ("blocked_count", blocked),
            ("top_risk_severity", top_severity),
            (
                "formula",
                "red if open critical/high risk, or overdue with progress<50%; "
                "yellow if overdue/blocked/open medium-low risk; green otherwise",
            ),
            ("limitations", limitations),
        )
    )


def project_summary(proj, today=None):
    progress = compute_progress(proj)
    return OrderedDict(
        (
            ("name", proj["name"]),
            ("display_name", proj["display_name"]),
            ("state", proj["state"] or ("archived" if proj["archived"] else "active")),
            ("owner", proj["owner"]),
            ("area", proj["area"]),
            ("archived", proj["archived"]),
            ("task_total", progress["total"]),
            ("task_done", progress["done"]),
            ("progress_percent", progress["percent"]),
            ("open_count", sum(1 for r in proj["tasks"] if r["open"])),
            ("overdue_count", len(overdue_tasks(proj, today))),
            ("blocked_count", proj.get("blocked_count", 0)),
            ("milestone_count", len(proj["milestones"])),
            ("open_risk_count", sum(1 for r in proj["risks"] if r["open"])),
            ("health", compute_health(proj, today)["label"]),
        )
    )


def project_list(items, config=None, today=None, include_archived=True):
    projects = collect_projects(items, config, today)
    rows = []
    for proj in projects.values():
        if not include_archived and proj["archived"]:
            continue
        rows.append(project_summary(proj, today))
    rows.sort(key=lambda r: r["name"])
    return rows


def _resolve_project(items, config, name, today):
    projects = collect_projects(items, config, today)
    alias_map = _alias_map(_registry(config or {}))
    canonical = alias_map.get(name, name)
    proj = projects.get(canonical) or projects.get(name)
    if proj is None:
        raise ValueError("Unknown project %r. Known: %s"
                         % (name, ", ".join(projects.keys()) or "(none)"))
    return proj


def project_hub(items, config=None, name=None, today=None):
    """One aggregation for a project's overview without duplicating records."""
    proj = _resolve_project(items, config, name, today)
    health = compute_health(proj, today)
    overdue = overdue_tasks(proj, today)
    return OrderedDict(
        (
            ("name", proj["name"]),
            ("display_name", proj["display_name"]),
            ("state", proj["state"] or ("archived" if proj["archived"] else "active")),
            ("owner", proj["owner"]),
            ("area", proj["area"]),
            ("visibility", proj["visibility"]),
            ("due", proj["due"]),
            ("start", proj["start"]),
            ("archived", proj["archived"]),
            ("progress", health["progress"]),
            ("health", health),
            ("open_tasks", [r for r in proj["tasks"] if r["open"]]),
            ("overdue_tasks", overdue),
            ("blocked_tasks", [r for r in proj["tasks"] if r["blocked"]]),
            ("milestones", proj["milestones"]),
            ("risks", sorted(proj["risks"], key=_risk_sort_key)),
            ("issues", proj["issues"]),
            ("decisions", proj["decisions"]),
            ("meetings", proj["meetings"]),
            ("workload", project_workload(items, config, proj["name"], today)),
        )
    )


def _risk_sort_key(risk):
    try:
        rank = SEVERITY_ORDER.index(risk["severity"])
    except ValueError:
        rank = len(SEVERITY_ORDER)
    return (0 if risk["open"] else 1, rank, risk["title"] or "")


def project_workload(items, config=None, name=None, today=None):
    proj = _resolve_project(items, config, name, today)
    by_assignee = OrderedDict()
    for row in proj["tasks"]:
        assignee = row.get("assignee") or "(unassigned)"
        bucket = by_assignee.setdefault(
            assignee,
            OrderedDict((("assignee", assignee), ("open", 0), ("done", 0), ("overdue", 0))),
        )
        if row["done"]:
            bucket["done"] += 1
        elif row["open"]:
            bucket["open"] += 1
        if not row["done"] and not row["cancelled"]:
            due = _date_of(row.get("due"))
            if today is not None and due is not None and due < today:
                bucket["overdue"] += 1
    return list(by_assignee.values())


def project_timeline(items, config=None, name=None, today=None):
    proj = _resolve_project(items, config, name, today)
    dated = []
    for row in proj["tasks"] + proj["milestones"]:
        due = row.get("due")
        if due:
            dated.append((due, row))
    for meeting in proj["meetings"]:
        dated.append((meeting.get("title"), meeting))
    dated = [(d, r) for d, r in dated if d]
    dated.sort(key=lambda pair: str(pair[0]))
    return [OrderedDict((("when", when), ("item", row))) for when, row in dated]


def project_risks(items, config=None, name=None, today=None):
    proj = _resolve_project(items, config, name, today)
    return sorted(proj["risks"], key=_risk_sort_key)


def portfolio(items, config=None, today=None, include_archived=False):
    """Compare projects with transparent, per-row derivations."""
    projects = collect_projects(items, config, today)
    rows = []
    for proj in projects.values():
        if not include_archived and proj["archived"]:
            continue
        health = compute_health(proj, today)
        rows.append(
            OrderedDict(
                (
                    ("name", proj["name"]),
                    ("display_name", proj["display_name"]),
                    ("state", proj["state"] or "active"),
                    ("owner", proj["owner"]),
                    ("area", proj["area"]),
                    ("progress_percent", health["progress"]["percent"]),
                    ("progress_formula", health["progress"]["formula"]),
                    ("open_count", sum(1 for r in proj["tasks"] if r["open"])),
                    ("overdue_count", health["overdue_count"]),
                    ("blocked_count", health["blocked_count"]),
                    ("milestone_open", sum(1 for m in proj["milestones"] if not m["done"])),
                    ("top_risk_severity", health["top_risk_severity"]),
                    ("health", health["label"]),
                    ("limitations", health["limitations"]),
                )
            )
        )
    rows.sort(key=lambda r: (_health_rank(r["health"]), r["name"]))
    return OrderedDict(
        (
            ("count", len(rows)),
            ("projects", rows),
            (
                "legend",
                OrderedDict(
                    (
                        ("progress", "done_tasks / non_cancelled_tasks * 100"),
                        ("health", "green/yellow/red by risk, overdue, and blocked work"),
                    )
                ),
            ),
        )
    )


def _health_rank(label):
    return {"red": 0, "yellow": 1, "green": 2}.get(label, 3)


# --- Record line builders (for `project new` and standardized templates) ------

def _slug(value):
    return "_".join(str(value).split())


def _detail(parts, key, value):
    if value:
        parts.append("%s:%s" % (key, value))


def build_project_record_line(name, owner=None, area=None, state="active",
                              due=None, start=None, visibility=None):
    parts = ["[N] N", _slug(name), "record:project", "project:%s" % name]
    _detail(parts, "state", state)
    _detail(parts, "owner", owner)
    _detail(parts, "area", area)
    _detail(parts, "due", due)
    _detail(parts, "do", start)
    _detail(parts, "visibility", visibility)
    return " ".join(parts)


def build_milestone_line(project, title, due=None, owner=None):
    parts = ["[ ] D", _slug(title), "record:milestone", "project:%s" % project]
    _detail(parts, "due", due)
    _detail(parts, "owner", owner)
    return " ".join(parts)


def build_risk_line(project, title, severity="medium", owner=None, state="open"):
    parts = ["[N] N", _slug(title), "record:risk", "project:%s" % project]
    _detail(parts, "severity", severity)
    _detail(parts, "state", state)
    _detail(parts, "owner", owner)
    return " ".join(parts)


def build_decision_line(project, title, on=None, owner=None):
    parts = ["[N] N", _slug(title), "record:decision", "project:%s" % project]
    _detail(parts, "on", on)
    _detail(parts, "owner", owner)
    return " ".join(parts)


def build_meeting_line(project, title, on=None, at=None):
    parts = ["[ ] E", _slug(title), "record:meeting", "project:%s" % project]
    _detail(parts, "on", on)
    _detail(parts, "at", at)
    return " ".join(parts)


RECORD_BUILDERS = OrderedDict(
    (
        ("project", build_project_record_line),
        ("milestone", build_milestone_line),
        ("risk", build_risk_line),
        ("decision", build_decision_line),
        ("meeting", build_meeting_line),
    )
)
