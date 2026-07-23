import re
from collections import OrderedDict
from datetime import datetime

from .model import Diagnostic


DEFAULT_ID_PREFIXES = OrderedDict(
    [
        ("T", "task"),
        ("E", "event"),
        ("D", "deadline"),
        ("R", "reminder"),
        ("H", "habit"),
        ("N", "note"),
        ("S", "status"),
        ("M", "msg"),
        ("J", "journal"),
    ]
)

_UNSAFE_ID_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")
ID_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]*$")


def auto_ids_enabled(config):
    ids = _section(config, "ids")
    if not ids:
        return False
    return bool(ids.get("auto", False))


def id_key_from_config(config):
    ids = _section(config, "ids")
    api = _section(config, "api")
    value = ids.get("key") or api.get("id_key") or "id"
    return str(value)


def id_prefix_for_item(item, config=None):
    ids = _section(config, "ids")
    prefixes = ids.get("prefixes")
    if isinstance(prefixes, dict) and item.kind in prefixes:
        return _safe_id_part(prefixes[item.kind])
    return DEFAULT_ID_PREFIXES.get(item.kind, "item")


def collect_item_ids(items, key="id"):
    values = set()
    for item in items:
        for value in item.details.get(key, []):
            if value:
                values.add(str(value))
    return values


def duplicate_id_diagnostics(items, key="id", cross_source_only=False):
    seen = {}
    diagnostics = []
    for item in items:
        item_source = getattr(item, "source", None)
        for value in item.details.get(key, []):
            if not value:
                continue
            value = str(value)
            if value in seen:
                first = seen[value]
                first_source = getattr(first, "source", None)
                if cross_source_only and first_source == item_source:
                    continue
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "W213",
                        "Duplicate %s:%s; first seen at %s."
                        % (key, value, _item_location(first)),
                        item.line,
                        None,
                        item_source,
                    )
                )
                continue
            seen[value] = item
    return diagnostics


def id_audit(items, key="id"):
    index = OrderedDict()
    missing = []
    total_items = 0
    for item in items:
        total_items += 1
        values = [str(value) for value in item.details.get(key, []) if value]
        if not values:
            missing.append(_audit_item(item))
            continue
        for value in values:
            index.setdefault(value, []).append(_audit_item(item))

    present = []
    duplicates = []
    for value, entries in index.items():
        sources = {e["source"] for e in entries if e["source"] is not None}
        cross_file = len(sources) > 1
        record = OrderedDict(
            [
                ("id", value),
                ("count", len(entries)),
                ("cross_file", cross_file),
                ("items", entries),
            ]
        )
        present.append(record)
        if len(entries) > 1:
            duplicates.append(record)

    cross_file_duplicates = [r for r in duplicates if r["cross_file"]]

    return OrderedDict(
        [
            ("key", key),
            ("total_items", total_items),
            ("id_count", len(index)),
            ("duplicate_count", len(duplicates)),
            ("cross_file_duplicate_count", len(cross_file_duplicates)),
            ("missing_count", len(missing)),
            ("present", present),
            ("duplicates", duplicates),
            ("cross_file_duplicates", cross_file_duplicates),
            ("missing", missing),
        ]
    )


def ensure_item_id(item, existing_ids=None, key="id", prefix=None, now=None):
    if item.details.get(key):
        return item.details[key][0]
    generated = generate_item_id(
        item,
        existing_ids=existing_ids,
        prefix=prefix,
        now=now,
    )
    item.details[key] = [generated]
    if existing_ids is not None:
        existing_ids.add(generated)
    return generated


def generate_item_id(item, existing_ids=None, prefix=None, now=None):
    if existing_ids is None:
        existing_ids = set()
    if now is None:
        from .timezone_policy import now as timezone_now

        now = timezone_now().replace(microsecond=0, tzinfo=None)
    prefix = _safe_id_part(prefix or DEFAULT_ID_PREFIXES.get(item.kind, "item"))
    base = "%s_%s" % (prefix, now.strftime("%Y%m%d%H%M%S"))
    candidate = base
    index = 2
    while candidate in existing_ids:
        candidate = "%s_%d" % (base, index)
        index += 1
    return candidate


def id_value_is_safe(value):
    return bool(ID_VALUE_RE.match(str(value or "")))


def _section(config, name):
    value = config.get(name) if isinstance(config, dict) else None
    if isinstance(value, dict):
        return value
    return {}


def _safe_id_part(value):
    value = str(value or "item").strip()
    value = _UNSAFE_ID_PART_RE.sub("_", value)
    value = value.strip("._-")
    return value or "item"


def _item_location(item):
    source = getattr(item, "source", None)
    line = getattr(item, "line", None)
    if source and line is not None:
        return "%s:%s" % (source, line)
    if source:
        return str(source)
    if line is not None:
        return "line %s" % line
    return "unknown location"


def _audit_item(item):
    return OrderedDict(
        [
            ("source", getattr(item, "source", None)),
            ("line", item.line),
            ("status", item.status),
            ("type", item.kind),
            ("title", item.title),
            ("location", _item_location(item)),
        ]
    )
