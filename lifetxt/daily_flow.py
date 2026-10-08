"""Pure, bounded Daily Flow Lite proposals (#1144).

Consumes already admitted parsed snapshots; does no IO or mutation. Consumers
must admit active/context-only sources and certify occupancy visibility/currentness.
No CLI, public endpoint, or generated schema is registered by this module.
"""

import re
from collections import Counter
from datetime import date as Date, datetime, timedelta, timezone as UTC
from itertools import islice

from .agenda import filter_items
from .daily_flow_time import (
    OccupancyError,
    constant_offset,
    day_window,
    deadline,
    instant,
    occupancy,
    plain,
    release_time,
    stamp,
)
from .extra_common import _rank_key
from .links import build_id_index
from .mutation import hash_text
from .daily_flow_model import (
    _json,
    _source,
    _id,
    _ref,
    _why,
    _diag,
    _unplaced,
    _limits,
    _admit,
    _revisions,
    _serial_rank,
)
from .nextaction import blocked_map, is_actionable
from .priority_matrix import classify_item
from .read_scope import resolve_read_scope
from .timeutil import normalize_duration, parse_date, parse_elapsed
from .timezone_policy import timezone_context, timezone_info


def _task(item, blockers, index, day, zone, effective, result):
    if not is_actionable(
        item.status, item.details, blocked=bool(blockers.get(id(item))), kind=item.kind
    ):
        return None, "unresolved_dependency" if blockers.get(
            id(item)
        ) else "not_actionable"
    if _id(item) is None:
        return None, "missing_identity"
    if _id(item) in item.details.get("depends_on", []) or _id(item) in item.details.get(
        "blocks", []
    ):
        return None, "unresolved_dependency"
    if any(str(dep) not in index for dep in item.details.get("depends_on", [])):
        return None, "unresolved_dependency"
    estimate = item.details.get("est", [])
    if not estimate:
        return None, "missing_estimate"
    if len(estimate) != 1:
        return None, "ambiguous_estimate"
    try:
        minutes = parse_elapsed(normalize_duration(estimate[0]))
        if minutes <= 0:
            return None, "invalid_estimate"
    except (ValueError, OverflowError):
        return None, "invalid_estimate"
    release, due = effective, None
    for key in ("do", "due"):
        values = item.details.get(key, [])
        if len(values) > 1:
            return None, "ambiguous_" + key
        if values:
            try:
                if key == "due":
                    due = deadline(values[0], zone)
                else:
                    release = max(release, release_time(values[0], zone))
            except (ValueError, OverflowError):
                return None, "invalid_" + key
    if release.astimezone(timezone_info(zone)).date() > day:
        return None, "future_intent"
    why = [_why("eligible_task"), _why("full_estimate", minutes=minutes)]
    elapsed = item.details.get("elapsed", [])
    if elapsed:
        try:
            if len(elapsed) != 1:
                raise ValueError("Ambiguous elapsed")
            why.append(
                _why(
                    "historical_elapsed",
                    minutes=parse_elapsed(normalize_duration(elapsed[0])),
                )
            )
        except (ValueError, OverflowError):
            result["diagnostics"].append(
                _diag("invalid_elapsed", item, effect="warning")
            )
    with timezone_context(zone):
        classification = classify_item(item, effective)
    why.append(
        _why(
            "priority_context",
            priority=(item.details.get("priority") or [None])[0],
            **classification,
        )
    )
    return {
        "item": item,
        "minutes": minutes,
        "release": release,
        "due": due,
        "why": why,
    }, None


def _place(tasks, gaps, result, zone, day, policy):
    for task in tasks:
        item, minutes = task["item"], task["minutes"]
        total = minutes + policy["break_minutes"] + policy["buffer_minutes"]
        # Avoid datetime overflow for huge authored estimates.
        choices = []
        for index, (left, right) in enumerate(gaps):
            begin = max(left, task["release"])
            if (right - begin).total_seconds() >= total * 60:
                finish = begin + timedelta(minutes=minutes)
                choices.append((index, begin, finish))
        on_time = [
            choice
            for choice in choices
            if task["due"] is None or choice[2] <= task["due"]
        ]
        if not choices:
            result["unplaced"].append(_unplaced(item, "insufficient_capacity"))
            continue
        index, begin, finish = (on_time or choices)[0]
        why = list(task["why"]) + [_why("earliest_fit")]
        deadline_status = (
            "none"
            if task["due"] is None
            else "met"
            if finish <= task["due"]
            else "missed"
        )
        if deadline_status == "missed":
            why.append(_why("deadline_missed", due=stamp(task["due"], zone)))
        result["timeline"].append(
            {
                "kind": "candidate",
                "start": stamp(begin, zone),
                "end": stamp(finish, zone),
                "item": _ref(item),
                "why": why,
                "duration_minutes": minutes,
                "rank_key": _serial_rank(item, day),
                "deadline_status": deadline_status,
            }
        )
        cursor = finish
        for kind, key in (
            ("policy_break", "break_minutes"),
            ("buffer", "buffer_minutes"),
        ):
            if policy[key]:
                stop = cursor + timedelta(minutes=policy[key])
                result["timeline"].append(
                    {
                        "kind": kind,
                        "start": stamp(cursor, zone),
                        "end": stamp(stop, zone),
                        "item": None,
                        "candidate": _ref(item),
                        "why": [_why("reserved_after_task", minutes=policy[key])],
                    }
                )
                cursor = stop
        left, right = gaps[index]
        gaps[index : index + 1] = ([(left, begin)] if begin > left else []) + (
            [(cursor, right)] if cursor < right else []
        )


def _finish(result):
    blockers = [d["code"] for d in result["diagnostics"] if d["effect"] == "block"]
    rejects = [d["code"] for d in result["diagnostics"] if d["effect"] == "reject"]
    result["completeness"]["state"] = (
        "blocked" if blockers else "partial" if rejects else "complete"
    )
    result["completeness"]["reasons"] = sorted(set(blockers + rejects))
    kinds = {"fixed": 0, "candidate": 1, "policy_break": 2, "buffer": 3}
    result["timeline"].sort(
        key=lambda row: (
            row["start"],
            kinds[row["kind"]],
            _json(row.get("item") or row.get("candidate")),
        )
    )
    result["instants"].sort(key=lambda row: (row["at"], _json(row["item"])))
    result["unplaced"].sort(
        key=lambda row: (
            row["item"]["source"],
            row["item"]["line"] or 0,
            row["item"]["id"] or "",
            row["item"]["title"],
        )
    )
    result["diagnostics"].sort(
        key=lambda row: (row["code"], _json(row["item"]), _json(row["params"]))
    )
    return result


def build_daily_flow(
    items,
    *,
    date,
    day_start,
    day_end,
    timezone,
    evaluated_at,
    occupancy_complete,
    context_items=(),
    config=None,
    project=None,
    area=None,
    saved_view=None,
    policy=None,
    source_revisions=None,
    snapshot_consistent=True,
    input_diagnostics=(),
):
    """Build an unsaved suggestion from authorized parsed snapshot inputs.

    Missing/invalid explicit window/policy is a ValueError. Unsafe occupancy,
    identity, source or resource inputs return completeness=blocked. Source IO,
    admission, archive selection, authorization and snapshot retries are callers'
    responsibilities; occupancy_complete must be explicitly certified by them.
    """
    day = parse_date(date) if isinstance(date, str) else date
    if not isinstance(day, Date) or isinstance(day, datetime) or day == Date.max:
        raise ValueError("Daily Flow requires an explicit calendar date.")
    if type(occupancy_complete) is not bool or type(snapshot_consistent) is not bool:
        raise ValueError("Snapshot certification flags must be booleans.")
    if not isinstance(timezone, str) or not timezone or timezone == "local":
        raise ValueError("An explicit resolved timezone is required.")
    timezone_info(timezone)
    if source_revisions is not None:
        if (
            not isinstance(source_revisions, dict)
            or len(source_revisions) > 10000
            or any(
                not isinstance(k, str)
                or len(k) > 4096
                or not isinstance(v, str)
                or not re.fullmatch(r"[0-9a-f]{64}", v)
                for k, v in source_revisions.items()
            )
        ):
            raise ValueError(
                "Source revisions must be existing SHA-256 snapshot digests."
            )
    evaluated = instant(evaluated_at, timezone)
    config = config or {}
    policy = dict(policy or {})
    if set(policy) - {"break_minutes", "buffer_minutes", "limits"}:
        raise ValueError("Unknown Daily Flow policy.")
    limits = _limits(policy)
    for key in ("break_minutes", "buffer_minutes"):
        value = policy.setdefault(key, 0)
        if type(value) is not int or value < 0 or value > 1440:
            raise ValueError(
                "Break/buffer must be nonnegative whole minutes within one day."
            )
    policy["limits"] = limits
    result = {
        "schema": "daily-flow-lite-v1",
        "policy_version": "lite-greedy-v1",
        "date": day.isoformat(),
        "timezone": timezone,
        "evaluated_at": stamp(evaluated, timezone),
        "source_revision": None,
        "scope": None,
        "window": None,
        "policy": {
            **policy,
            "duration_mode": "full_estimate",
            "rank_reference_date": day.isoformat(),
            "urgency_reference_time": None,
        },
        "completeness": {
            "state": "complete",
            "occupancy": "unknown",
            "inventory": "complete",
            "reasons": [],
        },
        "timeline": [],
        "instants": [],
        "free": [],
        "unplaced": [],
        "excluded": {},
        "diagnostics": [],
    }
    if not occupancy_complete:
        result["diagnostics"].append(_diag("occupancy_unavailable", effect="block"))
        return _finish(result)
    if not snapshot_consistent:
        result["diagnostics"].append(_diag("source_changed", effect="block"))
        return _finish(result)
    active, context, error = _admit(items, context_items, limits)
    if error:
        result["completeness"]["inventory"] = "bounded"
        result["diagnostics"].append(_diag(error, effect="block"))
        return _finish(result)
    selected, selector = resolve_read_scope(
        active, config, area=area, saved_view=saved_view
    )
    if project:
        selected = filter_items(selected, projects=[project])
    result["scope"] = {
        "candidate_selector": selector,
        "project": project,
        "active_sources": sorted({hash_text(_source(it)) for it in active}),
        "context_sources": sorted({hash_text(_source(it)) for it in context}),
        "occupancy": "authorized_active_sources",
    }
    result["source_revision"] = _revisions(
        active, context, source_revisions, config, result["scope"]
    )
    try:
        start, end = day_window(day, day_start, day_end, timezone)
        effective = (
            max(start, evaluated)
            if evaluated.astimezone(timezone_info(timezone)).date() == day
            else start
        )
        result["window"] = {
            "start": stamp(start, timezone),
            "end": stamp(end, timezone),
            "effective_start": stamp(min(effective, end), timezone),
            "effective_end": stamp(end, timezone),
        }
        result["policy"]["urgency_reference_time"] = stamp(effective, timezone)
        if any(
            policy[key] * 60 > (end - start).total_seconds()
            for key in ("break_minutes", "buffer_minutes")
        ):
            raise ValueError("Break/buffer exceeds the requested window.")
        midnight = instant(day.isoformat() + "T00:00", timezone)
        next_midnight = instant(
            (day + timedelta(days=1)).isoformat() + "T00:00", timezone
        )
        constant_offset(midnight, next_midnight, timezone)
    except OccupancyError as exc:
        result["diagnostics"].append(_diag(exc.code, effect="block"))
        return _finish(result)
    except ValueError as exc:
        from .timezone_policy import TimezonePolicyError

        if not isinstance(exc, TimezonePolicyError):
            raise
        result["diagnostics"].append(
            _diag("unsupported_timezone_window", effect="block")
        )
        return _finish(result)
    if day < evaluated.astimezone(timezone_info(timezone)).date():
        result["diagnostics"].append(_diag("past_date_unsupported", effect="block"))
    if effective >= end:
        result["diagnostics"].append(_diag("window_elapsed", effect="block"))
    # Parser errors mean records may have been lost: never certify apparent gaps.
    incoming = list(islice(iter(input_diagnostics), limits["detail_values"] + 1))
    if len(incoming) > limits["detail_values"] or any(
        (d.get("severity") if isinstance(d, dict) else d.severity) == "error"
        for d in incoming
    ):
        result["diagnostics"].append(_diag("input_parse_error", effect="block"))
    all_items = active + context
    index = build_id_index(all_items)
    if any(len(matches) != 1 for matches in index.values()) or any(
        len(it.details.get("id", [])) > 1 for it in all_items
    ):
        result["diagnostics"].append(_diag("ambiguous_identity", effect="block"))
    report, diagnostics = occupancy(
        active, day, start, end, timezone, limits, _ref, _diag
    )
    result["diagnostics"].extend(diagnostics)
    if any(d["effect"] == "block" for d in diagnostics) or any(
        d["code"] == "input_parse_error" for d in result["diagnostics"]
    ):
        result["diagnostics"].append(_diag("occupancy_unknown", effect="block"))
    else:
        result["completeness"]["occupancy"] = "certified"
    gaps = []
    if report:
        for entry in report["busy"]:
            result["timeline"].append(
                {
                    "kind": "fixed",
                    "start": stamp(instant(entry["start"], timezone), timezone),
                    "end": stamp(instant(entry["end"], timezone), timezone),
                    "item": entry["item"],
                    "why": [_why("fixed_attendance", field=entry["source_field"])],
                }
            )
        result["instants"] = [
            {
                "at": stamp(instant(row["at"], timezone), timezone),
                "item": row["item"],
                "source_field": row["source_field"],
            }
            for row in report["instants"]
        ]
        gaps = [
            (
                max(effective, instant(gap["start"], timezone)),
                instant(gap["end"], timezone),
            )
            for gap in report["free"]
            if instant(gap["end"], timezone) > effective
        ]
    blockers = blocked_map(all_items)
    tasks = []
    excluded = Counter()
    for item in selected:
        if item.kind != "T":
            excluded[item.kind] += 1
            continue
        task, reason = _task(item, blockers, index, day, timezone, effective, result)
        if reason:
            result["unplaced"].append(_unplaced(item, reason))
            # Parking/completion is a valid exclusion, not missing input.
            if reason not in (
                "not_actionable",
                "unresolved_dependency",
                "future_intent",
            ):
                result["diagnostics"].append(_diag(reason, item))
        else:
            tasks.append(task)
    result["excluded"] = dict(sorted(excluded.items()))
    tasks.sort(
        key=lambda task: (
            _rank_key(task["item"], day),
            _source(task["item"]),
            _id(task["item"]),
        )
    )
    if len(tasks) > limits["candidates"]:
        result["completeness"]["inventory"] = "bounded"
        for task in tasks[limits["candidates"] :]:
            result["unplaced"].append(_unplaced(task["item"], "limit_exceeded"))
        tasks = tasks[: limits["candidates"]]
        result["diagnostics"].append(_diag("limit_exceeded", resource="candidates"))
    if len(gaps) + len(tasks) > limits["slots"]:
        result["diagnostics"].append(
            _diag("limit_exceeded", effect="block", resource="slots")
        )
    blocked = any(d["effect"] == "block" for d in result["diagnostics"])
    if blocked:
        for task in tasks:
            result["unplaced"].append(
                _unplaced(
                    task["item"],
                    "plan_blocked",
                    sorted(
                        {
                            d["code"]
                            for d in result["diagnostics"]
                            if d["effect"] == "block"
                        }
                    ),
                )
            )
    else:
        _place(tasks, gaps, result, timezone, day, policy)
        result["free"] = [
            {"start": stamp(a, timezone), "end": stamp(b, timezone)} for a, b in gaps
        ]
    return _finish(result)
