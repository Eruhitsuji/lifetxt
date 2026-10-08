"""Bounded snapshot admission and provenance helpers for Daily Flow."""

import json
import posixpath
from datetime import date as Date
from itertools import islice

from .daily_flow_time import OccupancyError
from .extra_common import _rank_key
from .mutation import hash_text

HARD_LIMITS = {
    "context": 10000,
    "edges": 20000,
    "candidates": 1000,
    "events": 1000,
    "slots": 2048,
    "conflicts": 10000,
    "detail_values": 40000,
    "text_chars": 4000000,
    "title_chars": 1024,
    "value_chars": 4096,
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source(item):
    return (
        posixpath.normpath(str(item.source).replace("\\", "/"))
        if item.source
        else "memory"
    )


def _id(item):
    values = item.details.get("id", [])
    return str(values[0]) if len(values) == 1 and str(values[0]).strip() else None


def _key(item):
    return (
        _source(item),
        item.line or 0,
        _id(item) or "",
        item.kind,
        item.title,
        _json(item.details),
    )


def _ref(item):
    return {
        "id": _id(item),
        "source": hash_text(_source(item)),
        "line": item.line,
        "title": item.title,
        "kind": item.kind,
        "status": item.status,
    }


def _why(code, **params):
    return {"code": code, "params": params}


def _diag(code, item=None, effect="reject", **params):
    return {
        "code": code,
        "severity": "warning" if effect == "warning" else "error",
        "effect": effect,
        "item": _ref(item) if item else None,
        "params": params,
    }


def _unplaced(item, code, secondary=()):
    return {
        "item": _ref(item),
        "reason": code,
        "secondary": list(secondary),
        "why": [_why(code)],
    }


def _limits(policy):
    limits = dict(HARD_LIMITS)
    custom = policy.get("limits", {})
    if not isinstance(custom, dict) or set(custom) - set(limits):
        raise ValueError("Unknown Daily Flow limit.")
    for key, value in custom.items():
        if type(value) is not int or not 1 <= value <= limits[key]:
            raise ValueError(
                "Limits must be positive integers no larger than hard limits."
            )
        limits[key] = value
    return limits


def _admit(items, context, limits):
    # Bounded enumeration even for infinite iterators. Never truncate occupancy.
    active = list(islice(iter(items), limits["context"] + 1))
    archive = list(islice(iter(context), limits["context"] + 1))
    if len(active) + len(archive) > limits["context"]:
        return [], [], "limit_exceeded"
    detail_count = edge_count = text_chars = 0
    for item in active + archive:
        if (
            len(str(item.title)) > limits["title_chars"]
            or len(str(item.source or "")) > limits["value_chars"]
        ):
            return [], [], "limit_exceeded"
        text_chars += len(str(item.title)) + len(str(item.source or ""))
        for key, values in item.details.items():
            if len(key) > limits["value_chars"] or any(
                len(str(v)) > limits["value_chars"] for v in values
            ):
                return [], [], "limit_exceeded"
            detail_count += len(values)
            text_chars += len(key) + sum(len(str(v)) for v in values)
            if key in ("depends_on", "blocks"):
                edge_count += len(values)
        if (
            detail_count > limits["detail_values"]
            or edge_count > limits["edges"]
            or text_chars > limits["text_chars"]
        ):
            return [], [], "limit_exceeded"
    seen = {}

    def unique(records):
        result = []
        for item in sorted(records, key=_key):
            # Only explicit physical row identity proves a repeated admission.
            location = (
                (_source(item), item.line)
                if item.source and item.line is not None
                else None
            )
            if location is not None and location in seen:
                identity = item.to_dict()
                identity["_source_file"] = _source(item)
                if seen[location] != identity:
                    raise OccupancyError("ambiguous_source")
                continue
            if location is not None:
                identity = item.to_dict()
                identity["_source_file"] = _source(item)
                seen[location] = identity
            result.append(item)
        return result

    try:
        active = unique(active)
        archive = unique(archive)
    except OccupancyError as exc:
        return [], [], exc.code
    return active, archive, None


def _revisions(active, context, supplied, config, scope):
    groups = {}
    for item in active + context:
        groups.setdefault(_source(item), []).append(
            {
                "line": item.line,
                "status": item.status,
                "kind": item.kind,
                "title": item.title,
                "details": item.details,
            }
        )
    rows = []
    for source, records in sorted(groups.items()):
        revision = (supplied or {}).get(source)
        rows.append(
            {
                "source": hash_text(source),
                "revision": revision or hash_text(_json(records)),
                "basis": "source_snapshot" if revision else "parsed_snapshot",
            }
        )
    return {
        "sources": rows,
        "scope_revision": hash_text(_json({"config": config, "scope": scope})),
    }


def _serial_rank(item, day):
    def serial(value):
        if isinstance(value, Date):
            return value.isoformat()
        if isinstance(value, tuple):
            return [serial(v) for v in value]
        return value

    return [serial(v) for v in _rank_key(item, day)] + [
        hash_text(_source(item)),
        _id(item),
    ]
