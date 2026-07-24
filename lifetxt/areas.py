"""Area-based aggregation.

``area:`` is an optional organizing dimension above ``project:``. An item's area
comes from its own ``area:`` detail; a project's area comes from its metadata
record or the registry. This module groups items and projects by area without
requiring a mandatory taxonomy — areas are whatever appears in the data plus any
declared project defaults.

Example presets (never enforced): work, research, health, home, finance,
family, learning.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .projects import collect_projects


OPEN_STATUSES = ("[ ]", "[/]", "[?]")
DONE_STATUS = "[x]"
CANCELLED_STATUS = "[-]"
WORK_KINDS = ("T", "D")

AREA_PRESETS = ("work", "research", "health", "home", "finance", "family", "learning")


def _first(item, key, default=None):
    values = item.details.get(key)
    return values[0] if values else default


def _project_area_map(items, config):
    mapping = OrderedDict()
    for name, proj in collect_projects(items, config).items():
        if proj["area"]:
            mapping[name] = proj["area"]
    return mapping


def collect_areas(items, config=None):
    """Group items and projects by area. Unassigned items fall under ``None``."""
    config = config or {}
    project_area = _project_area_map(items, config)
    areas = OrderedDict()

    def bucket(name):
        return areas.setdefault(
            name,
            OrderedDict(
                (
                    ("name", name),
                    ("task_total", 0),
                    ("task_done", 0),
                    ("task_open", 0),
                    ("projects", []),
                    ("items", []),
                )
            ),
        )

    for item in items:
        area = _first(item, "area")
        if area is None:
            for project in item.details.get("project", []):
                if project in project_area:
                    area = project_area[project]
                    break
        b = bucket(area or "(unassigned)")
        b["items"].append(_ref(item))
        if item.kind in WORK_KINDS and item.status != CANCELLED_STATUS:
            b["task_total"] += 1
            if item.status == DONE_STATUS:
                b["task_done"] += 1
            elif item.status in OPEN_STATUSES:
                b["task_open"] += 1

    for name, area in project_area.items():
        b = bucket(area or "(unassigned)")
        if name not in b["projects"]:
            b["projects"].append(name)

    return areas


def _ref(item):
    return OrderedDict(
        (
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("project", _first(item, "project")),
            ("source", item.source),
            ("line", item.line),
        )
    )


def area_summary(area):
    percent = (
        round(100.0 * area["task_done"] / area["task_total"], 1)
        if area["task_total"]
        else None
    )
    return OrderedDict(
        (
            ("name", area["name"]),
            ("task_total", area["task_total"]),
            ("task_done", area["task_done"]),
            ("task_open", area["task_open"]),
            ("progress_percent", percent),
            ("project_count", len(area["projects"])),
            ("projects", list(area["projects"])),
        )
    )


def area_list(items, config=None):
    areas = collect_areas(items, config)
    rows = [area_summary(area) for area in areas.values()]
    rows.sort(key=lambda r: (r["name"] == "(unassigned)", r["name"]))
    return rows


def area_show(items, config=None, name=None):
    areas = collect_areas(items, config)
    area = areas.get(name)
    if area is None:
        raise ValueError(
            "Unknown area %r. Known: %s" % (name, ", ".join(areas.keys()) or "(none)")
        )
    summary = area_summary(area)
    summary["open_items"] = [ref for ref in area["items"] if ref["status"] in OPEN_STATUSES]
    return summary
