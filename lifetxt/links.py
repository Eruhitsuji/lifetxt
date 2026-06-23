import json
from collections import OrderedDict

from .model import Diagnostic, REFERENCE_KEYS


def link_records(items, key="id", focus_id=None, direction="both", reference_keys=None):
    reference_keys = tuple(reference_keys or REFERENCE_KEYS)
    direction = _normalize_direction(direction)
    index = build_id_index(items, key)
    records = []

    for item in items:
        source_ids = item_id_values(item, key)
        source_id = source_ids[0] if source_ids else ""
        for relation in reference_keys:
            for target_id in item.details.get(relation, []):
                target_id = str(target_id)
                outgoing = focus_id is None or focus_id in source_ids
                incoming = focus_id is None or target_id == focus_id
                if focus_id is not None:
                    if direction == "outgoing" and not outgoing:
                        continue
                    if direction == "incoming" and not incoming:
                        continue
                    if direction == "both" and not (outgoing or incoming):
                        continue
                records.append(_link_record(item, source_id, relation, target_id, index, key))
    return records


def reference_diagnostics(items, key="id", reference_keys=None):
    reference_keys = tuple(reference_keys or REFERENCE_KEYS)
    index = build_id_index(items, key)
    diagnostics = []

    for item in items:
        source_ids = set(item_id_values(item, key))
        for relation in reference_keys:
            for value in item.details.get(relation, []):
                value = str(value)
                matches = index.get(value, [])
                if value in source_ids:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "W216",
                            "Self reference %s:%s." % (relation, value),
                            item.line,
                            None,
                            getattr(item, "source", None),
                        )
                    )
                elif not matches:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "W215",
                            "Reference %s:%s does not match any %s: value."
                            % (relation, value, key),
                            item.line,
                            None,
                            getattr(item, "source", None),
                        )
                    )
                elif len(matches) > 1:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "W218",
                            "Reference %s:%s is ambiguous because %s:%s appears %d times."
                            % (relation, value, key, value, len(matches)),
                            item.line,
                            None,
                            getattr(item, "source", None),
                        )
                    )

    diagnostics.extend(_parent_cycle_diagnostics(items, index, key))
    return diagnostics


def build_id_index(items, key="id"):
    index = OrderedDict()
    for item in items:
        for value in item_id_values(item, key):
            index.setdefault(value, []).append(item)
    return index


def item_id_values(item, key="id"):
    return [str(value) for value in item.details.get(key, []) if value]


def format_link_table(records):
    if not records:
        return "No links found.\n"
    columns = ("relation", "source", "target", "status", "source_title", "target_title")
    rows = []
    for record in records:
        rows.append(
            OrderedDict(
                [
                    ("relation", record["relation"]),
                    ("source", record["source_id"] or record["source_location"]),
                    ("target", record["target_id"]),
                    ("status", record["status"]),
                    ("source_title", record["source_title"]),
                    ("target_title", record.get("target_title", "")),
                ]
            )
        )
    return "\n".join(_format_table(rows, columns)) + "\n"


def links_to_json(records, pretty=False):
    return json.dumps(
        records,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )


def links_to_jsonl(records):
    return "\n".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    )


def _link_record(item, source_id, relation, target_id, index, key):
    matches = index.get(target_id, [])
    status = "missing"
    target = None
    if target_id in item_id_values(item, key):
        status = "self"
        target = item
    elif len(matches) == 1:
        status = "ok"
        target = matches[0]
    elif len(matches) > 1:
        status = "ambiguous"
        target = matches[0]

    record = OrderedDict()
    record["relation"] = relation
    record["status"] = status
    record["source_id"] = source_id
    record["source_line"] = item.line
    record["source_location"] = _item_location(item)
    record["source_type"] = item.kind
    record["source_status"] = item.status
    record["source_title"] = item.title
    record["target_id"] = target_id
    if target is not None:
        record["target_line"] = target.line
        record["target_location"] = _item_location(target)
        record["target_type"] = target.kind
        record["target_status"] = target.status
        record["target_title"] = target.title
    elif matches:
        record["target_matches"] = [_item_location(match) for match in matches]
    return record


def _parent_cycle_diagnostics(items, index, key):
    owners = {
        value: matches[0]
        for value, matches in index.items()
        if len(matches) == 1
    }
    edges = {}
    for value, item in owners.items():
        edges[value] = [
            str(parent)
            for parent in item.details.get("parent", [])
            if str(parent) in owners
        ]

    diagnostics = []
    visiting = set()
    visited = set()
    path = []
    reported = set()

    def visit(node):
        if node in visited:
            return
        if node in visiting:
            start = path.index(node)
            cycle = path[start:] + [node]
            key_value = frozenset(cycle)
            if key_value not in reported:
                reported.add(key_value)
                item = owners.get(node)
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "W217",
                        "Parent reference cycle detected: %s." % " -> ".join(cycle),
                        item.line if item else None,
                        None,
                        getattr(item, "source", None) if item else None,
                    )
                )
            return
        visiting.add(node)
        path.append(node)
        for parent in edges.get(node, []):
            visit(parent)
        path.pop()
        visiting.remove(node)
        visited.add(node)

    for node in edges:
        visit(node)
    return diagnostics


def _normalize_direction(value):
    value = str(value or "both").lower()
    if value not in ("incoming", "outgoing", "both"):
        return "both"
    return value


def _item_location(item):
    source = getattr(item, "source", None)
    line = getattr(item, "line", None)
    if source and line is not None:
        return "%s:%s" % (source, line)
    if source:
        return str(source)
    if line is not None:
        return "line %s" % line
    return ""


def _format_table(rows, columns):
    widths = []
    for column in columns:
        width = len(column)
        for row in rows:
            width = max(width, len(str(row.get(column, ""))))
        widths.append(width)
    lines = []
    lines.append(_format_table_row(columns, widths))
    lines.append(_format_table_row(["-" * width for width in widths], widths))
    for row in rows:
        lines.append(_format_table_row([row.get(column, "") for column in columns], widths))
    return lines


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"
