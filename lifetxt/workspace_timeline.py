"""Bounded workspace-wide Life Timeline composed from Native Timelines."""

from __future__ import unicode_literals

from collections import OrderedDict

from .native_timeline import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    KNOWN_EVENT_FILTERS,
    _filter_instant,
    _sort_key,
    _is_history,
    native_timeline,
)


def workspace_timeline(
    items,
    id_key="id",
    limit=DEFAULT_LIMIT,
    since=None,
    until=None,
    event=None,
    target_id=None,
    project=None,
):
    """Merge bounded per-item Native Timelines into one deterministic stream.

    Git is intentionally not consulted.  Current item metadata is used only as
    navigation/provenance context and never synthesized as a historical event.
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise ValueError("Workspace Timeline limit must be an integer.")
    if limit < 0 or limit > MAX_LIMIT:
        raise ValueError(
            "Workspace Timeline limit must be between 0 and %d." % MAX_LIMIT
        )
    since_value = _filter_instant(since, "since")
    until_value = _filter_instant(until, "until")
    if (
        since_value is not None
        and until_value is not None
        and since_value > until_value
    ):
        raise ValueError("Workspace Timeline since must not be after until.")
    event_value = str(event).strip() if event not in (None, "") else None
    if event_value is not None and event_value not in KNOWN_EVENT_FILTERS:
        raise ValueError("Unknown Workspace Timeline event filter %r." % event_value)

    targets = [item for item in items if not _is_history(item)]
    if target_id not in (None, ""):
        target_value = str(target_id)
        targets = [
            item
            for item in targets
            if target_value in [str(value) for value in item.details.get(id_key, [])]
        ]
    if project not in (None, ""):
        project_value = str(project)
        targets = [
            item
            for item in targets
            if project_value
            in [str(value) for value in item.details.get("project", [])]
        ]

    rows = []
    limitations = set()
    diagnostics = []
    target_reports = []
    for target in targets:
        ids = [str(value) for value in target.details.get(id_key, [])]
        if len(ids) != 1:
            limitations.add("target_without_unique_id")
            continue
        item_id = ids[0]
        result = native_timeline(
            items,
            item_id,
            id_key=id_key,
            limit=MAX_LIMIT,
            since=since,
            until=until,
            event=event,
        )
        target_reports.append(result)
        limitations.update(result.get("limitations", []))
        diagnostics.extend(result.get("diagnostics", []))
        for row in result.get("events", []):
            enriched = OrderedDict(
                (
                    ("target_id", item_id),
                    ("target", result.get("target", {})),
                    ("source", getattr(target, "source", None)),
                )
            )
            enriched.update(row)
            rows.append(enriched)

    rows.sort(
        key=lambda row: (
            _sort_key(row),
            row.get("target_id") or "",
            row.get("source") or "",
        )
    )
    total_valid = len(rows)
    selected = rows[:limit]
    truncated = total_valid > len(selected)
    if truncated:
        limitations.add("event_limit_truncated")
    complete = bool(target_reports) and all(
        report.get("complete") for report in target_reports
    )
    if not complete:
        limitations.add("workspace_history_incomplete")
    return OrderedDict(
        (
            ("schema", "workspace-life-timeline-v1"),
            ("source", "native_life_txt"),
            ("git_composed", False),
            (
                "filters",
                OrderedDict(
                    (
                        ("since", since),
                        ("until", until),
                        ("event", event_value),
                        ("target_id", target_id),
                        ("project", project),
                    )
                ),
            ),
            (
                "bounds",
                OrderedDict(
                    (
                        ("limit", limit),
                        ("total_valid_events", total_valid),
                        ("returned_events", len(selected)),
                        ("truncated", truncated),
                    )
                ),
            ),
            ("complete", complete and not limitations),
            (
                "completeness",
                OrderedDict(
                    (
                        ("target_count", len(targets)),
                        ("target_reports", len(target_reports)),
                        ("complete", complete),
                    )
                ),
            ),
            ("limitations", sorted(limitations)),
            ("diagnostics", diagnostics),
            ("events", selected),
        )
    )
