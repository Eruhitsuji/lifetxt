"""Deterministic Personal Context helpers built on existing lifetxt records.

The toolkit intentionally introduces no new record kind or Format/Query
vocabulary.  Personal Context remains an ordinary Note convention (`N`,
`person:`, `tag:`, `source:`, `updated:`), while this module composes the
existing temporal, link, ID, and Unified Inbox foundations into bounded views.
"""

from __future__ import unicode_literals

import hashlib
import json
from collections import OrderedDict

from .ids import collect_item_ids, ensure_item_id, id_prefix_for_item
from .inbox import proposal_to_line, stage_create
from .links import build_id_index, link_records
from .model import Item, REFERENCE_KEYS
from .temporal_context import DEFAULT_STALE_DAYS, node_facts
from .timezone_policy import now as timezone_now


CORRECTION_KEY = "corrects"
PERSONAL_REFERENCE_KEYS = tuple(REFERENCE_KEYS) + (CORRECTION_KEY,)
DEFAULT_LIMIT = 100


def _values(item, key):
    return [str(value) for value in item.details.get(key, []) if str(value)]


def _first(item, key, default=""):
    values = _values(item, key)
    return values[0] if values else default


def _item_id(item):
    return _first(item, "id")


def _location(item):
    source = getattr(item, "source", None)
    line = getattr(item, "line", None)
    if source and line is not None:
        return "%s:%s" % (source, line)
    if source:
        return str(source)
    if line is not None:
        return "line %s" % line
    return "unknown location"


def is_personal_context_item(item, person="self"):
    """Return whether ``item`` participates in the Personal AI Memory convention."""
    if item.kind != "N":
        return False
    if person is None:
        return bool(_values(item, "person"))
    return str(person) in _values(item, "person")


def select_personal_context(items, person="self", tags=None):
    """Select Personal Context Notes using only existing person/tag semantics."""
    wanted_tags = {str(tag) for tag in (tags or []) if str(tag)}
    selected = []
    for item in items:
        if not is_personal_context_item(item, person=person):
            continue
        if wanted_tags and not wanted_tags.issubset(set(_values(item, "tag"))):
            continue
        selected.append(item)
    return selected


def correction_index(items):
    """Map corrected item IDs to the authoritative records that correct them."""
    result = OrderedDict()
    for item in items:
        for target_id in _values(item, CORRECTION_KEY):
            result.setdefault(target_id, []).append(item)
    return result


def _stale_fact(item, stale_after_days=DEFAULT_STALE_DAYS):
    for fact in node_facts(item, None, stale_after_days=stale_after_days):
        if fact.get("rule") == "stale_since":
            return fact
    return None


def _link_records(items):
    return link_records(items, reference_keys=PERSONAL_REFERENCE_KEYS)


def _links_by_source(items):
    grouped = {}
    for record in _link_records(items):
        source_id = record.get("source_id")
        if source_id:
            key = ("id", str(source_id))
        else:
            key = (
                "location",
                record.get("source_location"),
                record.get("source_line"),
            )
        grouped.setdefault(key, []).append(record)
    return grouped


def _records_for_item(grouped, item):
    item_id = _item_id(item)
    if item_id:
        return list(grouped.get(("id", item_id), []))
    return list(
        grouped.get(
            (
                "location",
                _location(item),
                getattr(item, "line", None),
            ),
            [],
        )
    )


def _public_item_record(item):
    details = OrderedDict(
        (str(key), [str(value) for value in values])
        for key, values in item.details.items()
    )
    return OrderedDict(
        (
            ("id", _item_id(item) or None),
            ("status", item.status),
            ("type", item.kind),
            ("title", item.title),
            ("person", _values(item, "person")),
            ("tags", _values(item, "tag")),
            ("project", _values(item, "project")),
            ("source", _values(item, "source")),
            ("updated", _values(item, "updated")),
            ("details", details),
        )
    )


def context_health(items, person="self", stale_after_days=DEFAULT_STALE_DAYS):
    """Return bounded health facts for Personal Context records.

    ``current``/``stale``/``superseded`` are mutually exclusive lifecycle
    states.  ``missing_source`` and ``broken_reference`` are independent
    health findings and may overlap those lifecycle states.
    """
    selected = select_personal_context(items, person=person)
    corrections = correction_index(items)
    links = _links_by_source(items)
    findings = []
    counts = OrderedDict(
        (
            ("total", len(selected)),
            ("current", 0),
            ("stale", 0),
            ("superseded", 0),
            ("missing_source", 0),
            ("broken_reference", 0),
        )
    )

    for item in selected:
        item_id = _item_id(item)
        stale = _stale_fact(item, stale_after_days=stale_after_days)
        correcting = corrections.get(item_id, []) if item_id else []
        if correcting:
            state = "superseded"
        elif stale is not None:
            state = "stale"
        else:
            state = "current"
        counts[state] += 1

        missing_source = not bool(_values(item, "source"))
        broken = [
            record
            for record in _records_for_item(links, item)
            if record.get("status") in ("missing", "ambiguous")
        ]
        if missing_source:
            counts["missing_source"] += 1
        if broken:
            counts["broken_reference"] += 1

        findings.append(
            OrderedDict(
                (
                    ("id", item_id or None),
                    ("title", item.title),
                    ("state", state),
                    ("missing_source", missing_source),
                    ("broken_references", broken),
                    ("stale_fact", stale),
                    (
                        "corrected_by",
                        [
                            OrderedDict(
                                (
                                    ("id", _item_id(candidate) or None),
                                    ("title", candidate.title),
                                )
                            )
                            for candidate in correcting
                        ],
                    ),
                )
            )
        )

    findings.sort(key=lambda row: ((row.get("id") or ""), row.get("title") or ""))
    return OrderedDict(
        (
            ("schema", "personal-context-health-v1"),
            ("person", person),
            ("stale_after_days", int(stale_after_days)),
            ("counts", counts),
            ("items", findings),
        )
    )


def _unique_item(items, item_id, key="id"):
    index = build_id_index(items, key)
    matches = index.get(str(item_id), [])
    if not matches:
        raise ValueError("Item ID not found: %s" % item_id)
    if len(matches) > 1:
        raise ValueError(
            "Item ID %s is duplicated at %s"
            % (item_id, ", ".join(_location(item) for item in matches))
        )
    return matches[0]


def explain_personal_context_item(
    items, item_id, stale_after_days=DEFAULT_STALE_DAYS, key="id"
):
    """Explain one item from deterministic provenance/temporal/link evidence."""
    target = _unique_item(items, item_id, key=key)
    corrections = correction_index(items)
    correcting = corrections.get(str(item_id), [])
    stale = _stale_fact(target, stale_after_days=stale_after_days)
    state = "superseded" if correcting else ("stale" if stale else "current")

    links = link_records(
        items,
        key=key,
        focus_id=str(item_id),
        direction="both",
        reference_keys=PERSONAL_REFERENCE_KEYS,
    )
    normalized_links = []
    for record in links:
        row = OrderedDict(record)
        row["direction"] = (
            "outgoing" if str(record.get("source_id")) == str(item_id) else "incoming"
        )
        normalized_links.append(row)
    normalized_links.sort(
        key=lambda row: (
            row.get("direction", ""),
            row.get("relation", ""),
            row.get("source_id", ""),
            row.get("target_id", ""),
        )
    )

    facts = node_facts(target, None, stale_after_days=stale_after_days)
    return OrderedDict(
        (
            ("schema", "personal-context-why-v1"),
            ("id", str(item_id)),
            ("state", state),
            ("item", _public_item_record(target)),
            ("temporal_facts", facts),
            ("links", normalized_links),
            (
                "corrected_by",
                [
                    OrderedDict(
                        (("id", _item_id(item) or None), ("title", item.title))
                    )
                    for item in correcting
                ],
            ),
        )
    )


def _capsule_item_record(item, stale_after_days=DEFAULT_STALE_DAYS):
    record = _public_item_record(item)
    stale = _stale_fact(item, stale_after_days=stale_after_days)
    record["stale"] = stale is not None
    if stale is not None:
        record["stale_fact"] = stale
    return record


def _coerce_limit(limit):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer")
    if limit < 0:
        raise ValueError("limit must be zero or greater")
    return limit


def context_capsule(
    items,
    person="self",
    tags=None,
    include_stale=False,
    limit=DEFAULT_LIMIT,
    stale_after_days=DEFAULT_STALE_DAYS,
):
    """Return a deterministic, read-only Personal Context projection."""
    limit = _coerce_limit(limit)

    corrections = correction_index(items)
    selected = []
    for item in select_personal_context(items, person=person, tags=tags):
        item_id = _item_id(item)
        if item_id and corrections.get(item_id):
            continue
        stale = _stale_fact(item, stale_after_days=stale_after_days)
        if stale is not None and not include_stale:
            continue
        selected.append(_capsule_item_record(item, stale_after_days=stale_after_days))

    selected.sort(
        key=lambda row: json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    selected = selected[:limit]
    tag_values = sorted({str(tag) for tag in (tags or []) if str(tag)})
    revision_input = OrderedDict(
        (
            ("person", person),
            ("tags", tag_values),
            ("include_stale", bool(include_stale)),
            ("stale_after_days", int(stale_after_days)),
            ("items", selected),
        )
    )
    canonical = json.dumps(
        revision_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    revision = hashlib.sha256(canonical).hexdigest()
    return OrderedDict(
        (
            ("schema", "personal-context-capsule-v1"),
            ("revision", revision),
            ("person", person),
            ("tags", tag_values),
            ("include_stale", bool(include_stale)),
            ("stale_after_days", int(stale_after_days)),
            ("limit", limit),
            ("count", len(selected)),
            ("items", selected),
        )
    )


def decision_memory(
    items,
    person="self",
    project=None,
    include_stale=False,
    limit=DEFAULT_LIMIT,
    stale_after_days=DEFAULT_STALE_DAYS,
):
    """Project `tag:decision` Personal Context records without a new kind."""
    limit = _coerce_limit(limit)
    capsule = context_capsule(
        items,
        person=person,
        tags=("decision",),
        include_stale=include_stale,
        limit=len(items),
        stale_after_days=stale_after_days,
    )
    records = list(capsule["items"])
    if project:
        records = [record for record in records if str(project) in record["project"]]
    records = records[:limit]
    return OrderedDict(
        (
            ("schema", "personal-decision-memory-v1"),
            ("person", person),
            ("project", project),
            ("include_stale", bool(include_stale)),
            ("count", len(records)),
            ("items", records),
        )
    )


def _timestamp(value=None):
    value = value or timezone_now()
    value = value.replace(microsecond=0)
    return value.isoformat()


def correction_details(
    target, items, config=None, source="manual", now_value=None, key="id"
):
    """Build details for a replacement Note while preserving the old history."""
    target_id = _first(target, key)
    if not target_id:
        raise ValueError("Memory correction requires a target with %s:." % key)

    details = OrderedDict()
    for detail_key in ("person", "tag", "project"):
        values = _values(target, detail_key)
        if values:
            details[detail_key] = values
    details[CORRECTION_KEY] = [target_id]
    details["source"] = [str(source)]
    details["updated"] = [_timestamp(now_value)]

    proposed = Item(status="[ ]", kind="N", title="", details=details)
    prefix = id_prefix_for_item(proposed, config=config)
    ensure_item_id(
        proposed,
        existing_ids=collect_item_ids(items, key=key),
        key=key,
        prefix=prefix,
        now=now_value,
    )
    return proposed.details


def stage_memory_correction(
    config,
    items,
    target_id,
    replacement_text,
    source="manual",
    now_value=None,
    key="id",
):
    """Stage a reviewable correction proposal; never mutate authoritative data."""
    target = _unique_item(items, target_id, key=key)
    details = correction_details(
        target,
        items,
        config=config,
        source=source,
        now_value=now_value,
        key=key,
    )
    proposal = stage_create(
        config,
        str(replacement_text),
        kind="N",
        details=details,
        source=source,
        status="[ ]",
    )
    return OrderedDict(
        (
            ("schema", "personal-memory-correction-proposal-v1"),
            ("target_id", str(target_id)),
            ("proposal_id", proposal.get("id")),
            ("line", proposal_to_line(proposal)),
            ("proposal", proposal),
        )
    )
