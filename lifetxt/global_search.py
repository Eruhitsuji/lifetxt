"""Global search across items and derived entities.

The item-level ``search`` command matches within life.txt records. Global search
widens the net to the derived entities lifetxt already computes — projects,
people, groups, areas — and to staged inbox proposals, returning results grouped
by entity type with the field that matched and a short snippet. It scans
directly; no index is built until benchmarks justify one.

Deterministic: the same items, config, and term always produce the same ordered
result set. With ``fuzzy=True``, each entity type's rows are additionally
ranked exact-substring matches first, then by descending similarity score,
ties broken by original scan order (Python's sort is stable).
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .fuzzy_search import fuzzy_contains, is_exact_match, similarity


ENTITY_TYPES = ("item", "project", "person", "group", "area", "proposal")


def _match(term, text, fuzzy=False):
    if fuzzy:
        return fuzzy_contains(term, text)
    return term in str(text).lower()


def _rank(rows_with_text, fuzzy, term):
    """``rows_with_text`` is a list of ``(row, matched_text)`` pairs in scan
    order. Returns just the rows, unchanged when ``fuzzy`` is false."""
    if not fuzzy:
        return [row for row, _matched_text in rows_with_text]
    scored = [
        (row, is_exact_match(term, text), similarity(term, text))
        for row, text in rows_with_text
    ]
    scored.sort(key=lambda entry: (not entry[1], -entry[2]))
    return [row for row, _is_exact, _score in scored]


def _result(entity, name, field, snippet, source=None, line=None):
    return OrderedDict(
        (
            ("type", entity),
            ("name", name),
            ("field", field),
            ("snippet", snippet),
            ("source", source),
            ("line", line),
        )
    )


def _search_items(items, term, fuzzy=False):
    rows = []
    for item in items:
        matched = None
        snippet = None
        matched_text = None
        if _match(term, item.title, fuzzy):
            matched, snippet, matched_text = "title", item.title, item.title
        else:
            body = item.details.get("body")
            body_text = " ".join(str(v) for v in body) if body else None
            if body_text and _match(term, body_text, fuzzy):
                matched, snippet, matched_text = "body", body_text, body_text
            else:
                for key, values in item.details.items():
                    for value in values:
                        if _match(term, value, fuzzy):
                            matched = key
                            snippet = "%s:%s" % (key, value)
                            matched_text = value
                            break
                    if matched:
                        break
        if matched:
            name = item.details.get("id", [item.title])[0]
            row = _result("item", str(name), matched, snippet, item.source, item.line)
            rows.append((row, matched_text))
    return _rank(rows, fuzzy, term)


def _search_projects(items, config, term, fuzzy=False):
    from .projects import collect_projects

    rows = []
    for proj in collect_projects(items, config).values():
        for field in ("name", "display_name", "owner", "area"):
            value = proj.get(field)
            if value and _match(term, value, fuzzy):
                row = _result("project", proj["name"], field, "%s:%s" % (field, value))
                rows.append((row, value))
                break
    return _rank(rows, fuzzy, term)


def _search_people(items, config, term, fuzzy=False):
    from .people import people_list

    rows = []
    for entry in people_list(items, config):
        if _match(term, entry["person"], fuzzy):
            row = _result("person", entry["person"], "person", entry["person"])
            rows.append((row, entry["person"]))
    return _rank(rows, fuzzy, term)


def _search_groups(config, term, fuzzy=False):
    from .groups import group_directory

    rows = []
    for name, group in group_directory(config).items():
        if _match(term, name, fuzzy):
            rows.append((_result("group", name, "name", name), name))
            continue
        matched_alias = None
        for alias in group.get("aliases", []):
            if _match(term, alias, fuzzy):
                matched_alias = alias
                break
        if matched_alias:
            rows.append((_result("group", name, "alias", matched_alias), matched_alias))
            continue
        for member in group.get("members", []):
            if _match(term, member, fuzzy):
                rows.append((_result("group", name, "member", member), member))
                break
    return _rank(rows, fuzzy, term)


def _search_areas(items, config, term, fuzzy=False):
    from .areas import collect_areas

    rows = []
    for name in collect_areas(items, config):
        if name and _match(term, name, fuzzy):
            rows.append((_result("area", name, "name", name), name))
    return _rank(rows, fuzzy, term)


def _search_proposals(config, term, fuzzy=False):
    from .inbox import list_proposals, proposal_to_line

    rows = []
    for proposal in list_proposals(config):
        try:
            line = proposal_to_line(proposal)
        except ValueError:
            line = proposal.get("operation", "")
        source = proposal.get("source", "")
        line_match = _match(term, line, fuzzy)
        source_match = _match(term, source, fuzzy) if source else False
        if line_match or source_match:
            row = _result(
                "proposal",
                proposal["id"],
                "proposal",
                "[%s] %s" % (proposal.get("status", "pending"), line),
            )
            # Score against whichever field actually matched, preferring the
            # line since it is the primary display text.
            matched_text = line if line_match else source
            rows.append((row, matched_text))
    return _rank(rows, fuzzy, term)


def global_search(items, config=None, term="", types=None, limit=None, fuzzy=False):
    """Search across every entity type, grouped by type."""
    config = config or {}
    term = str(term or "").lower()
    wanted = set(types) if types else set(ENTITY_TYPES)
    groups = OrderedDict()
    if not term:
        return OrderedDict((("term", term), ("total", 0), ("groups", groups)))

    searchers = OrderedDict(
        (
            ("item", lambda: _search_items(items, term, fuzzy)),
            ("project", lambda: _search_projects(items, config, term, fuzzy)),
            ("person", lambda: _search_people(items, config, term, fuzzy)),
            ("group", lambda: _search_groups(config, term, fuzzy)),
            ("area", lambda: _search_areas(items, config, term, fuzzy)),
            ("proposal", lambda: _search_proposals(config, term, fuzzy)),
        )
    )
    total = 0
    for entity, search in searchers.items():
        if entity not in wanted:
            continue
        rows = search()
        if limit:
            rows = rows[:limit]
        if rows:
            groups[entity] = rows
            total += len(rows)
    return OrderedDict((("term", term), ("total", total), ("groups", groups)))


def flatten(result):
    rows = []
    for entity_rows in result.get("groups", {}).values():
        rows.extend(entity_rows)
    return rows
