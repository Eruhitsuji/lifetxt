"""Static audit for direct host-clock boundaries.

Workflow-facing time must go through ``lifetxt.timezone_policy``.  A small set
of operational/compatibility boundaries still needs the host clock (lock age,
UTC audit evidence, animation cadence).  Those uses are reviewed by path/call
rather than silently growing.
"""
from __future__ import unicode_literals

import ast
import json
import os
from collections import OrderedDict

BASELINE_PATH = os.path.join("config", "release", "clock-boundary-baseline-v1.json")
CLOCK_CALLS = frozenset((
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "datetime.date.today",
    "datetime.now",
    "date.today",
    "time.time",
))


def audit_host_clocks(root):
    rows = []
    package = os.path.join(os.path.abspath(root), "lifetxt")
    for directory, subdirs, files in os.walk(package):
        subdirs[:] = [name for name in subdirs if name != "__pycache__"]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call = _call_name(node.func)
                if call in CLOCK_CALLS:
                    rows.append(OrderedDict((
                        ("path", os.path.relpath(path, root).replace("\\", "/")),
                        ("line", int(getattr(node, "lineno", 0) or 0)),
                        ("call", call),
                    )))
    return sorted(rows, key=lambda row: (row["path"], row["call"], row["line"]))


def clock_boundary_report(root):
    path = os.path.join(os.path.abspath(root), BASELINE_PATH)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            baseline = json.load(handle, object_pairs_hook=OrderedDict)
    except Exception as exc:
        return OrderedDict((
            ("ok", False), ("errors", [str(exc)]), ("new_findings", []),
            ("stale_allowances", []),
        ))
    allowed_rows = baseline.get("allowed") or []
    allowed = set((str(row.get("path")), str(row.get("call"))) for row in allowed_rows)
    current = audit_host_clocks(root)
    pairs = set((row["path"], row["call"]) for row in current)
    new = [row for row in current if (row["path"], row["call"]) not in allowed]
    stale = [
        {"path": path, "call": call}
        for path, call in sorted(allowed - pairs)
    ]
    classifications = OrderedDict()
    for row in allowed_rows:
        classifications["%s:%s" % (row.get("path"), row.get("call"))] = {
            "classification": row.get("classification"),
            "reason": row.get("reason"),
            "removal_condition": row.get("removal_condition"),
        }
    return OrderedDict((
        ("ok", not new),
        ("baseline_version", baseline.get("baseline_version")),
        ("finding_count", len(current)),
        ("new_findings", new),
        ("stale_allowances", stale),
        ("classifications", classifications),
    ))


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""
