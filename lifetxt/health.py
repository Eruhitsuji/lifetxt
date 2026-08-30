"""Deterministic health-finding aggregation shared by the CLI and Report v2.

``build_health`` is the surface-neutral domain function behind the CLI
``health`` command's W301-W305 finding rules -- the same pattern
:mod:`lifetxt.review`'s ``build_review()`` and :mod:`lifetxt.stats`'s
``build_stats()`` already established for other aggregations. The CLI command
and the Report v2 ``health`` section provider both call this function instead
of each owning a copy of the finding rules.
"""

from __future__ import annotations

from collections import OrderedDict

from .ids import id_key_from_config
from .links import dependency_blocker_records
from .review import latest_item_date, parse_date_only

OPEN_STATUSES = ("[ ]", "[/]", "[>]", "[?]")


def build_health(
    items,
    today,
    since_days=30,
    lookahead_days=7,
    ignore_codes=None,
    kinds=None,
    config=None,
):
    """Return deterministic W301-W305 health findings for ``items``.

    ``ignore_codes`` and ``kinds`` are iterables of finding codes / item kinds
    to restrict the scan to, matching the CLI ``health`` command's existing
    ``--ignore``/``--types`` semantics.
    """
    ignore_codes = set(str(code).upper() for code in (ignore_codes or ()))
    type_filter = set(kinds or ())
    config = config or {}

    habit_completions = {}
    for item in items:
        if item.kind == "H" and item.status == "[x]":
            latest = latest_item_date(item)
            if latest:
                title = item.title
                if title not in habit_completions or latest > habit_completions[title]:
                    habit_completions[title] = latest

    recent_persons = set()
    for item in items:
        if item.kind == "S":
            person_vals = item.details.get("person", [])
            if not person_vals:
                continue
            person = str(person_vals[0])
            latest = latest_item_date(item)
            if latest and (today - latest).days <= since_days:
                recent_persons.add(person)
            elif item.status in OPEN_STATUSES and not item.details.get("to"):
                recent_persons.add(person)

    findings = []
    dependency_records = []
    if "W305" not in ignore_codes:
        dependency_records = dependency_blocker_records(
            items, key=id_key_from_config(config)
        )

    for item in items:
        if type_filter and item.kind not in type_filter:
            continue
        location = getattr(item, "source", None)
        line_no = item.line

        if "W301" not in ignore_codes:
            if (
                item.kind == "T"
                and item.status in OPEN_STATUSES
                and item.status != "[>]"
            ):
                latest = latest_item_date(item)
                if latest and (today - latest).days > since_days:
                    findings.append(
                        OrderedDict(
                            [
                                ("code", "W301"),
                                (
                                    "message",
                                    "Task open for %d days without update"
                                    % (today - latest).days,
                                ),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]
                        )
                    )

        if "W302" not in ignore_codes:
            if item.kind == "H" and item.status in OPEN_STATUSES:
                last_done = habit_completions.get(item.title)
                if last_done is None or (today - last_done).days > since_days:
                    findings.append(
                        OrderedDict(
                            [
                                ("code", "W302"),
                                (
                                    "message",
                                    "Habit has no completion within %d days"
                                    % since_days,
                                ),
                                ("line", line_no),
                                ("source", location),
                                ("title", item.title),
                            ]
                        )
                    )

        if "W303" not in ignore_codes:
            if item.status in OPEN_STATUSES:
                for val in item.details.get("due", []):
                    parsed = parse_date_only(str(val))
                    if parsed:
                        days_until = (parsed - today).days
                        if days_until < 0:
                            findings.append(
                                OrderedDict(
                                    [
                                        ("code", "W303"),
                                        (
                                            "message",
                                            "Overdue by %d day(s) since %s"
                                            % (-days_until, val),
                                        ),
                                        ("line", line_no),
                                        ("source", location),
                                        ("title", item.title),
                                    ]
                                )
                            )
                        elif days_until <= lookahead_days:
                            findings.append(
                                OrderedDict(
                                    [
                                        ("code", "W303"),
                                        (
                                            "message",
                                            "Due in %d day(s) on %s"
                                            % (days_until, val),
                                        ),
                                        ("line", line_no),
                                        ("source", location),
                                        ("title", item.title),
                                    ]
                                )
                            )

        if "W304" not in ignore_codes:
            if item.status in OPEN_STATUSES:
                for key in ("assignee", "owner"):
                    for val in item.details.get(key, []):
                        person = str(val)
                        if person not in recent_persons:
                            findings.append(
                                OrderedDict(
                                    [
                                        ("code", "W304"),
                                        (
                                            "message",
                                            "%s:%s has no recent S presence record within %d days"
                                            % (key, person, since_days),
                                        ),
                                        ("line", line_no),
                                        ("source", location),
                                        ("title", item.title),
                                    ]
                                )
                            )

    for record in dependency_records:
        findings.append(
            OrderedDict(
                [
                    ("code", "W305"),
                    (
                        "message",
                        "Blocked by %s via %s"
                        % (
                            record["blocker_id"] or record["blocker_location"],
                            record["relation"],
                        ),
                    ),
                    ("line", record["blocked_line"]),
                    ("source", record["blocked_source"]),
                    ("title", record["blocked_title"]),
                    ("blocked_by", record["blocker_id"] or record["blocker_location"]),
                    ("relation", record["relation"]),
                ]
            )
        )

    return findings
