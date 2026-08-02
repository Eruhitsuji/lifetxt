import json
import re
from collections import OrderedDict

from .model import Diagnostic, REFERENCE_KEYS


OPEN_DEPENDENCY_STATUSES = ("[ ]", "[/]", "[>]", "[?]")
DONE_DEPENDENCY_STATUS = "[x]"


def link_records(
    items,
    key="id",
    focus_id=None,
    direction="both",
    reference_keys=None,
    relations=None,
):
    reference_keys = tuple(reference_keys or REFERENCE_KEYS)
    if relations:
        wanted = set(str(relation) for relation in relations)
        reference_keys = tuple(
            relation for relation in reference_keys if relation in wanted
        )
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
                records.append(
                    _link_record(item, source_id, relation, target_id, index, key)
                )
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
    diagnostics.extend(_completed_dependency_diagnostics(items, index, key))
    return diagnostics


def dependency_blocker_records(items, key="id"):
    """Return open dependency blockers for open items.

    ``depends_on:`` is a direct prerequisite relation: the source item is
    blocked while the referenced target is still open.

    ``blocks:`` is an independent inverse assertion: the source item blocks the
    referenced target while the source is still open. It does not have to be
    mirrored by a matching ``depends_on:`` on the target.
    """
    index = build_id_index(items, key)
    records = []

    for item in items:
        for target_id in item.details.get("depends_on", []):
            target_id = str(target_id)
            target = _unique_reference_target(index, target_id, item, key)
            if target is None:
                continue
            if _is_open_dependency_item(item) and _is_open_dependency_item(target):
                records.append(
                    _dependency_blocker_record(
                        blocked=item,
                        blocker=target,
                        relation="depends_on",
                        reference_id=target_id,
                        key=key,
                    )
                )

        for target_id in item.details.get("blocks", []):
            target_id = str(target_id)
            target = _unique_reference_target(index, target_id, item, key)
            if target is None:
                continue
            if _is_open_dependency_item(item) and _is_open_dependency_item(target):
                records.append(
                    _dependency_blocker_record(
                        blocked=target,
                        blocker=item,
                        relation="blocks",
                        reference_id=target_id,
                        key=key,
                    )
                )

    return records


def dependency_blockers_by_item(items, key="id"):
    blockers = OrderedDict()
    for record in dependency_blocker_records(items, key=key):
        blockers.setdefault(record["_blocked_item_key"], []).append(
            OrderedDict(
                [
                    ("relation", record["relation"]),
                    ("id", record["blocker_id"]),
                    ("status", record["blocker_status"]),
                    ("type", record["blocker_type"]),
                    ("title", record["blocker_title"]),
                    ("location", record["blocker_location"]),
                ]
            )
        )
    return blockers


def dependency_chain_records(
    items, key="id", root_id=None, blocked_only=False, max_depth=None
):
    """Return dependency chains rooted at blocked items.

    The chain treats ``depends_on:ID`` and inverse ``blocks:ID`` as the same
    user-facing concept: the root item is waiting on the child nodes in
    ``deps``. Missing and ambiguous references are included as placeholder
    nodes so CLI users can see why a chain cannot be resolved.
    """
    index = build_id_index(items, key)
    unique = OrderedDict(
        (value, matches[0]) for value, matches in index.items() if len(matches) == 1
    )
    incoming_blocks = _incoming_blocks(items)

    def item_id(item):
        values = item_id_values(item, key)
        return values[0] if values else _item_location(item)

    def placeholder(reference_id, relation, status):
        title = "(missing)" if status == "missing" else "(ambiguous)"
        node = OrderedDict()
        node["id"] = str(reference_id)
        node["status"] = "?"
        node["type"] = "?"
        node["title"] = title
        node["relation"] = relation
        node["reference_status"] = status
        node["deps"] = []
        return node

    if max_depth is not None:
        try:
            max_depth = max(0, int(max_depth))
        except (TypeError, ValueError):
            max_depth = None

    def build_node(item, relation=None, path=None, depth=0):
        if path is None:
            path = []
        current_id = item_id(item)
        node = OrderedDict()
        node["id"] = current_id
        node["status"] = item.status
        node["type"] = item.kind
        node["title"] = item.title
        location = _item_location(item)
        if location:
            node["location"] = location
        if relation:
            node["relation"] = relation
        if current_id in path:
            node["cycle"] = True
            node["deps"] = []
            return node

        has_more = bool(item.details.get("depends_on"))
        for current_value in item_id_values(item, key):
            if incoming_blocks.get(current_value):
                has_more = True
                break
        if max_depth is not None and depth >= max_depth:
            if has_more:
                node["truncated"] = True
            node["deps"] = []
            return node

        deps = []
        next_path = path + [current_id]
        for target_id in item.details.get("depends_on", []):
            target_id = str(target_id)
            matches = index.get(target_id, [])
            if target_id in unique and unique[target_id] is not item:
                deps.append(
                    build_node(
                        unique[target_id],
                        relation="depends_on",
                        path=next_path,
                        depth=depth + 1,
                    )
                )
            elif len(matches) > 1:
                deps.append(placeholder(target_id, "depends_on", "ambiguous"))
            else:
                deps.append(placeholder(target_id, "depends_on", "missing"))

        for current_value in item_id_values(item, key):
            for blocker in incoming_blocks.get(current_value, []):
                if blocker is item:
                    continue
                deps.append(
                    build_node(
                        blocker, relation="blocks", path=next_path, depth=depth + 1
                    )
                )

        node["deps"] = deps
        return node

    def direct_open_blocker(node):
        for dep in node.get("deps", []):
            if dep.get("status") in OPEN_DEPENDENCY_STATUSES:
                return True
        return False

    if root_id:
        root_id = str(root_id)
        matches = index.get(root_id, [])
        if root_id in unique:
            return [build_node(unique[root_id])]
        if len(matches) > 1:
            return [placeholder(root_id, None, "ambiguous")]
        return [placeholder(root_id, None, "missing")]

    records = []
    seen_roots = set()
    for item in items:
        values = item_id_values(item, key)
        if not values:
            continue
        node = build_node(item)
        if not node.get("deps"):
            continue
        if blocked_only and (
            item.status not in OPEN_DEPENDENCY_STATUSES or not direct_open_blocker(node)
        ):
            continue
        root_key = (node["id"], node.get("location", ""))
        if root_key in seen_roots:
            continue
        seen_roots.add(root_key)
        records.append(node)
    return records


def format_dependency_chain(records):
    if not records:
        return "No dependency chains found.\n"

    lines = []

    def add_node(node, depth=0):
        indent = "  " * depth
        relation = node.get("relation")
        suffix = " (%s)" % relation if relation else ""
        if node.get("reference_status") in ("missing", "ambiguous"):
            suffix += " %s" % node["reference_status"]
        if node.get("cycle"):
            suffix += " cycle"
        if node.get("truncated"):
            suffix += " truncated"
        lines.append(
            "%s%s [%s] %s%s"
            % (
                indent,
                node.get("id", ""),
                node.get("status", "?"),
                node.get("title", ""),
                suffix,
            )
        )
        for dep in node.get("deps", []):
            add_node(dep, depth + 1)

    for record in records:
        add_node(record)
    return "\n".join(lines) + "\n"


def dependency_chains_to_mermaid(records):
    """Serialize dependency chains as a Mermaid graph LR diagram."""
    nodes, edges = _dependency_graph_parts(records)
    lines = ["graph LR"]
    if not nodes:
        lines.append("")
        return "\n".join(lines)

    for node_id, node in nodes.items():
        safe = _mermaid_node_id(node_id)
        label = _dependency_node_label(node_id, node).replace('"', "'")
        done_cls = ":::done" if node.get("status") in _DONE_STATUSES else ""
        lines.append('    %s["%s"]%s' % (safe, label, done_cls))

    lines.append("")
    for source, target, relation in edges:
        lines.append(
            "    %s -- %s --> %s"
            % (
                _mermaid_node_id(source),
                relation or "depends",
                _mermaid_node_id(target),
            )
        )

    if any(node.get("status") in _DONE_STATUSES for node in nodes.values()):
        lines.append("")
        lines.append("    classDef done stroke-dasharray:5 5")

    lines.append("")
    return "\n".join(lines)


def dependency_chains_to_dot(records):
    """Serialize dependency chains as a Graphviz DOT digraph."""
    nodes, edges = _dependency_graph_parts(records)
    lines = ["digraph deps {"]
    if not nodes:
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    for node_id, node in nodes.items():
        attrs = "label=%s" % _dot_quote(_dependency_node_label(node_id, node))
        if node.get("status") in _DONE_STATUSES:
            attrs += " style=dashed"
        lines.append("    %s [%s];" % (_dot_quote(node_id), attrs))

    for source, target, relation in edges:
        lines.append(
            "    %s -> %s [label=%s];"
            % (
                _dot_quote(source),
                _dot_quote(target),
                _dot_quote(relation or "depends"),
            )
        )

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _dependency_graph_parts(records):
    nodes = OrderedDict()
    edges = []

    def add_node(node):
        node_id = str(node.get("id", ""))
        if not node_id:
            return
        if node_id not in nodes:
            nodes[node_id] = node

    def walk(node):
        add_node(node)
        source = str(node.get("id", ""))
        for dep in node.get("deps", []):
            add_node(dep)
            target = str(dep.get("id", ""))
            if source and target:
                edges.append((source, target, dep.get("relation")))
            walk(dep)

    for record in records:
        walk(record)
    return nodes, edges


def _dependency_node_label(node_id, node):
    title = node.get("title", "")
    suffixes = []
    if node.get("reference_status"):
        suffixes.append(str(node["reference_status"]))
    if node.get("cycle"):
        suffixes.append("cycle")
    if node.get("truncated"):
        suffixes.append("truncated")
    label = "%s: %s" % (node_id, title)
    if suffixes:
        label += " (%s)" % ", ".join(suffixes)
    return label


def build_id_index(items, key="id"):
    index = OrderedDict()
    for item in items:
        for value in item_id_values(item, key):
            index.setdefault(value, []).append(item)
    return index


def item_id_values(item, key="id"):
    return [str(value) for value in item.details.get(key, []) if value]


def backlink_records(items, target_id, key="id", reference_keys=None):
    """Return items that reference ``target_id`` through any reference key.

    This answers "what points at this item?" — the incoming half of the link
    graph — grouped by the relation that made the connection. It reuses the same
    reference keys as :func:`link_records` so navigation stays consistent.
    """
    reference_keys = tuple(reference_keys or REFERENCE_KEYS)
    target_id = str(target_id)
    records = []
    for item in items:
        source_ids = item_id_values(item, key)
        source_id = source_ids[0] if source_ids else ""
        for relation in reference_keys:
            for value in item.details.get(relation, []):
                if str(value) != target_id:
                    continue
                records.append(
                    OrderedDict(
                        (
                            ("relation", relation),
                            ("source_id", source_id),
                            ("source_title", item.title),
                            ("source_status", item.status),
                            ("source_kind", item.kind),
                            ("source", item.source),
                            ("line", item.line),
                            ("target_id", target_id),
                        )
                    )
                )
    return records


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


_DONE_STATUSES = ("[x]", "[-]")


def links_to_mermaid(records):
    """Serialize link graph as a Mermaid graph LR diagram."""
    lines = ["graph LR"]
    if not records:
        lines.append("")
        return "\n".join(lines)

    nodes = {}
    for record in records:
        src_id = record["source_id"] or record["source_location"]
        if src_id not in nodes:
            nodes[src_id] = (record["source_title"], record.get("source_status", ""))
        tgt_id = record["target_id"]
        tgt_title = record.get("target_title", tgt_id)
        tgt_status = record.get("target_status", "")
        if tgt_id not in nodes:
            nodes[tgt_id] = (tgt_title, tgt_status)

    for node_id, (title, status) in nodes.items():
        safe = _mermaid_node_id(node_id)
        label = ("%s: %s" % (node_id, title)).replace('"', "'")
        done_cls = ":::done" if status in _DONE_STATUSES else ""
        lines.append('    %s["%s"]%s' % (safe, label, done_cls))

    lines.append("")
    for record in records:
        src_safe = _mermaid_node_id(record["source_id"] or record["source_location"])
        tgt_safe = _mermaid_node_id(record["target_id"])
        lines.append("    %s -- %s --> %s" % (src_safe, record["relation"], tgt_safe))

    has_done = any(
        record.get("source_status", "") in _DONE_STATUSES
        or record.get("target_status", "") in _DONE_STATUSES
        for record in records
    )
    if has_done:
        lines.append("")
        lines.append("    classDef done stroke-dasharray:5 5")

    lines.append("")
    return "\n".join(lines)


def links_to_dot(records):
    """Serialize link graph as a Graphviz DOT digraph."""
    lines = ["digraph links {"]
    if not records:
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    nodes = {}
    for record in records:
        src_id = record["source_id"] or record["source_location"]
        if src_id not in nodes:
            nodes[src_id] = (record["source_title"], record.get("source_status", ""))
        tgt_id = record["target_id"]
        tgt_title = record.get("target_title", tgt_id)
        tgt_status = record.get("target_status", "")
        if tgt_id not in nodes:
            nodes[tgt_id] = (tgt_title, tgt_status)

    for node_id, (title, status) in nodes.items():
        label = _dot_quote("%s: %s" % (node_id, title))
        attrs = "label=%s" % label
        if status in _DONE_STATUSES:
            attrs += " style=dashed"
        lines.append("    %s [%s];" % (_dot_quote(node_id), attrs))

    for record in records:
        src_id = record["source_id"] or record["source_location"]
        tgt_id = record["target_id"]
        lines.append(
            "    %s -> %s [label=%s];"
            % (_dot_quote(src_id), _dot_quote(tgt_id), _dot_quote(record["relation"]))
        )

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _mermaid_node_id(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))


def _dot_quote(value):
    text = str(value)
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
        return text
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


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


def _completed_dependency_diagnostics(items, index, key):
    diagnostics = []
    for item in items:
        if item.status != DONE_DEPENDENCY_STATUS:
            continue
        for target_id in item.details.get("depends_on", []):
            target_id = str(target_id)
            target = _unique_reference_target(index, target_id, item, key)
            if target is None:
                continue
            if _is_open_dependency_item(target):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "W224",
                        "Completed item depends_on:%s but the prerequisite is still open (%s)."
                        % (target_id, target.status),
                        item.line,
                        None,
                        getattr(item, "source", None),
                    )
                )
    return diagnostics


def _dependency_blocker_record(blocked, blocker, relation, reference_id, key):
    blocked_id = _first_item_id(blocked, key)
    blocker_id = _first_item_id(blocker, key)
    record = OrderedDict()
    record["relation"] = relation
    record["reference_id"] = reference_id
    record["blocked_id"] = blocked_id
    record["blocked_line"] = blocked.line
    record["blocked_location"] = _item_location(blocked)
    record["blocked_source"] = getattr(blocked, "source", None)
    record["blocked_status"] = blocked.status
    record["blocked_type"] = blocked.kind
    record["blocked_title"] = blocked.title
    record["blocker_id"] = blocker_id
    record["blocker_line"] = blocker.line
    record["blocker_location"] = _item_location(blocker)
    record["blocker_source"] = getattr(blocker, "source", None)
    record["blocker_status"] = blocker.status
    record["blocker_type"] = blocker.kind
    record["blocker_title"] = blocker.title
    record["_blocked_item_key"] = id(blocked)
    record["_blocker_item_key"] = id(blocker)
    return record


def _incoming_blocks(items):
    incoming = OrderedDict()
    for item in items:
        for target_id in item.details.get("blocks", []):
            incoming.setdefault(str(target_id), []).append(item)
    return incoming


def _unique_reference_target(index, target_id, item, key):
    matches = index.get(target_id, [])
    if len(matches) != 1:
        return None
    target = matches[0]
    if target is item or target_id in item_id_values(item, key):
        return None
    return target


def _is_open_dependency_item(item):
    return item.status in OPEN_DEPENDENCY_STATUSES


def _first_item_id(item, key):
    values = item_id_values(item, key)
    if values:
        return values[0]
    return _item_location(item)


def _parent_cycle_diagnostics(items, index, key):
    owners = {
        value: matches[0] for value, matches in index.items() if len(matches) == 1
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
        lines.append(
            _format_table_row([row.get(column, "") for column in columns], widths)
        )
    return lines


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"
