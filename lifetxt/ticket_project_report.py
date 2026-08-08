"""Deterministic ticket/project report construction."""

from collections import Counter, OrderedDict
from datetime import timedelta
from typing import Any, Dict, Iterable, List, MutableMapping, Optional

from .ticket_project_values import (
    DEFAULT_HIGH_SEVERITIES,
    DEFAULT_STALE_DAYS,
    DEFAULT_TERMINAL_STATUSES,
    REPORT_SCHEMA,
    STATUS_ORDER,
    detail_values,
    due_time,
    is_ticket,
    last_activity,
    normalize_status,
    reference_time,
    sort_key,
    ticket_id,
    ticket_project,
    ticket_row,
    ticket_status,
)


def _counter(values: Iterable[str]) -> Dict[str, int]:
    counts = Counter(str(value or "(unspecified)") for value in values)
    return OrderedDict((key, counts[key]) for key in sorted(counts))


def build_ticket_project_report(
    items: Iterable[Any],
    reference_time_value=None,
    stale_after_days: int = DEFAULT_STALE_DAYS,
    project: Optional[str] = None,
    terminal_statuses: Iterable[str] = DEFAULT_TERMINAL_STATUSES,
    high_severities: Iterable[str] = DEFAULT_HIGH_SEVERITIES,
    **compat: Any,
) -> Dict[str, Any]:
    """Build one read-only report with explicit formulas and caveats.

    ``reference_time`` remains accepted through ``compat`` so callers can use
    the public keyword without shadowing the imported normalization helper.
    """
    if "reference_time" in compat:
        if reference_time_value is not None:
            raise TypeError("reference_time supplied twice")
        reference_time_value = compat.pop("reference_time")
    if compat:
        raise TypeError("unexpected keyword: %s" % sorted(compat)[0])
    if stale_after_days < 0:
        raise ValueError("stale_after_days must be zero or greater.")
    now = reference_time(reference_time_value)
    terminal = set(normalize_status(value) for value in terminal_statuses)
    severe = set(str(value).strip().lower() for value in high_severities)
    all_tickets = [item for item in items if is_ticket(item)]
    selected = all_tickets
    if project is not None:
        selected = [item for item in selected if ticket_project(item) == project]

    # Ids visible anywhere in the read set (before project filtering), used
    # only to distinguish "in a different in-scope project" from "missing" --
    # never to expose the other ticket's own fields. Callers that must not
    # disclose a ticket's existence (e.g. Remote Safe Mode) already filter
    # invisible tickets out of `items` before calling this function, so this
    # set never contains anything the caller could not already see.
    all_ticket_ids = set(ticket_id(item) for item in all_tickets if ticket_id(item))
    by_id = dict((ticket_id(item), item) for item in selected if ticket_id(item))

    # Reverse index of open `blocks:` references, built from the full read
    # set: `blocks:` is declared on the blocker, pointing at the ticket it
    # blocks, so evaluating a ticket's own blockers requires scanning every
    # ticket's outgoing `blocks:`, not just the ticket's own details.
    blockers_by_target = {}  # type: MutableMapping[str, List[Any]]
    for item in all_tickets:
        if ticket_status(item) in terminal:
            continue
        for target_id in detail_values(item, "blocks"):
            blockers_by_target.setdefault(str(target_id), []).append(item)

    all_rows = []  # type: List[Dict[str, Any]]
    projects = {}  # type: MutableMapping[str, List[Dict[str, Any]]]
    attention = OrderedDict(
        (
            ("blocked", []),
            ("dependency_unknown", []),
            ("overdue", []),
            ("unassigned", []),
            ("high_severity", []),
            ("stale", []),
        )
    )  # type: MutableMapping[str, List[Dict[str, Any]]]

    for item in selected:
        row = dict(ticket_row(item))
        is_open = row["status"] not in terminal
        open_dependencies, unknown_dependencies = [], []
        unknown_reasons = OrderedDict()  # type: MutableMapping[str, str]
        if is_open:
            for dependency_id in row["depends_on"]:
                dependency = by_id.get(dependency_id)
                if dependency is None:
                    unknown_dependencies.append(dependency_id)
                    unknown_reasons[dependency_id] = (
                        "out_of_scope" if dependency_id in all_ticket_ids else "missing"
                    )
                elif ticket_status(dependency) not in terminal:
                    open_dependencies.append(dependency_id)
            row_id = row["id"]
            for blocker in blockers_by_target.get(row_id, []) if row_id else []:
                blocker_id = ticket_id(blocker)
                if not blocker_id:
                    continue
                known_blocker = by_id.get(blocker_id)
                if known_blocker is not None:
                    if blocker_id not in open_dependencies:
                        open_dependencies.append(blocker_id)
                elif blocker_id not in unknown_dependencies:
                    # Found by scanning the full read set, so its existence
                    # is already known -- always out_of_scope, never missing.
                    unknown_dependencies.append(blocker_id)
                    unknown_reasons[blocker_id] = "out_of_scope"
        row.update(
            {
                "terminal": not is_open,
                "blocked": bool(
                    is_open and (row["status"] == "blocked" or open_dependencies)
                ),
                "dependency_unknown": bool(is_open and unknown_dependencies),
                "unresolved_dependencies": open_dependencies,
                "unevaluated_dependency_reasons": unknown_reasons,
                "unevaluated_dependencies": unknown_dependencies,
            }
        )
        due = due_time(item)
        activity = last_activity(item)
        row.update(
            {
                "overdue": bool(is_open and due is not None and due <= now),
                "unassigned": bool(is_open and not row["assignee"]),
                "high_severity": bool(
                    is_open and str(row["severity"]).lower() in severe
                ),
                "stale": bool(
                    is_open
                    and activity is not None
                    and activity < now - timedelta(days=stale_after_days)
                ),
                "variance_hours": (
                    row["elapsed_hours"] - row["estimate_hours"]
                    if row["estimate_hours"] is not None
                    and row["elapsed_hours"] is not None
                    else None
                ),
            }
        )
        all_rows.append(row)
        projects.setdefault(row["project"], []).append(row)
        for key in attention:
            if row[key]:
                attention[key].append(row)

    for rows in projects.values():
        rows.sort(key=sort_key)
    all_rows.sort(key=lambda row: (str(row["project"]).lower(),) + sort_key(row))
    for rows in attention.values():
        rows.sort(key=lambda row: (str(row["project"]).lower(),) + sort_key(row))

    project_summaries = []
    for project_name in sorted(projects):
        rows = projects[project_name]
        total = len(rows)
        terminal_count = sum(1 for row in rows if row["terminal"])
        estimates = [
            row["estimate_hours"] for row in rows if row["estimate_hours"] is not None
        ]
        elapsed = [
            row["elapsed_hours"] for row in rows if row["elapsed_hours"] is not None
        ]
        paired = [
            row["variance_hours"] for row in rows if row["variance_hours"] is not None
        ]
        project_summaries.append(
            {
                "project": project_name,
                "total": total,
                "open": total - terminal_count,
                "terminal": terminal_count,
                "progress_percent": round(terminal_count * 100.0 / total, 2)
                if total
                else None,
                "blocked": sum(1 for row in rows if row["blocked"]),
                "dependency_unknown": sum(
                    1 for row in rows if row["dependency_unknown"]
                ),
                "overdue": sum(1 for row in rows if row["overdue"]),
                "unassigned": sum(1 for row in rows if row["unassigned"]),
                "high_severity": sum(1 for row in rows if row["high_severity"]),
                "stale": sum(1 for row in rows if row["stale"]),
                "by_status": _counter(row["status"] for row in rows),
                "by_priority": _counter(row["priority"] for row in rows),
                "by_severity": _counter(row["severity"] for row in rows),
                "by_tracker": _counter(row["tracker"] for row in rows),
                "by_assignee": _counter(
                    row["assignee"] or "(unassigned)" for row in rows
                ),
                "by_component": _counter(row["component"] for row in rows),
                "estimate_hours": round(sum(estimates), 4) if estimates else None,
                "estimate_ticket_count": len(estimates),
                "elapsed_hours": round(sum(elapsed), 4) if elapsed else None,
                "elapsed_ticket_count": len(elapsed),
                "paired_variance_hours": round(sum(paired), 4) if paired else None,
                "paired_variance_ticket_count": len(paired),
            }
        )

    board = OrderedDict()
    known = list(STATUS_ORDER)
    extras = sorted(
        set(row["status"] for row in all_rows if row["status"] not in known)
    )
    for status in known + extras:
        rows = [row for row in all_rows if row["status"] == status]
        if rows:
            board[status] = rows

    total = len(all_rows)
    terminal_count = sum(1 for row in all_rows if row["terminal"])
    caveats = [
        "Tickets without project are grouped under (unassigned-project).",
        "Missing timestamps are not classified as stale.",
        "Dependencies absent from the selected report are marked dependency_unknown; their state is not guessed. unevaluated_dependency_reasons discloses out_of_scope only when the id is directly known to exist in the read set (a different in-scope project, or an open blocks: reference); every other case -- genuinely missing, private, archived outside scope, or rejected by workspace resolution -- is reported as missing without distinguishing which, since distinguishing further would disclose the referenced ticket's existence.",
        "Date-only due values remain current through that UTC calendar date; aware datetimes use their explicit offset.",
        "Estimate and elapsed totals include only parseable values; coverage counts are reported separately.",
        "Ticket-count progress does not model subtasks, effort, scope growth, or delivery probability.",
    ]
    if project is not None:
        caveats.append(
            "Project filtering occurs before dependency evaluation, so cross-project dependencies may be dependency_unknown (reported with reason out_of_scope)."
        )
    summary = {
        "total": total,
        "open": total - terminal_count,
        "terminal": terminal_count,
        "progress_percent": round(terminal_count * 100.0 / total, 2) if total else None,
        "project_count": len(project_summaries),
        "blocked": len(attention["blocked"]),
        "dependency_unknown": len(attention["dependency_unknown"]),
        "overdue": len(attention["overdue"]),
        "unassigned": len(attention["unassigned"]),
        "high_severity": len(attention["high_severity"]),
        "stale": len(attention["stale"]),
    }
    return {
        "schema": REPORT_SCHEMA,
        "reference_time": now.isoformat(),
        "stale_after_days": stale_after_days,
        "scope": {"project": project},
        "configuration": {
            "terminal_statuses": sorted(terminal),
            "high_severities": sorted(severe),
        },
        "summary": summary,
        "projects": project_summaries,
        "board": board,
        "attention": attention,
        "tickets": all_rows,
        "formulas": {
            "open": "ticket_status not in configured terminal_statuses",
            "progress_percent": "terminal ticket count / total ticket count * 100; count-based, not a forecast",
            "overdue": "open ticket due at/before reference_time; date-only values expire at next UTC midnight",
            "blocked": "open ticket blocked by status or an open dependency present in scope",
            "dependency_unknown": "open ticket with a depends_on id, or an open blocks: reference naming it, absent from selected report scope",
            "unassigned": "open ticket without assignee",
            "high_severity": "open ticket whose severity is in configured high_severities",
            "stale": "open ticket whose latest available activity timestamp is older than stale_after_days",
            "paired_variance_hours": "sum(elapsed - estimate) only where both values parse",
        },
        "caveats": caveats,
    }
