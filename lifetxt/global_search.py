"""Global search across items and derived entities.

The item-level ``search`` command matches within life.txt records. Global search
widens the net to the derived entities lifetxt already computes — projects,
people, groups, areas — and to staged inbox proposals, returning results grouped
by entity type with the field that matched and a short snippet. It scans
directly; no index is built until benchmarks justify one.

Deterministic: the same items, config, and term always produce the same ordered
result set.
"""

from __future__ import unicode_literals

from collections import OrderedDict


ENTITY_TYPES = ("item", "project", "person", "group", "area", "proposal")


def _match(term, text):
    return term in str(text).lower()


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


def _search_items(items, term):
    results = []
    for item in items:
        matched = None
        snippet = None
        if _match(term, item.title):
            matched, snippet = "title", item.title
        else:
            body = item.details.get("body")
            if body and _match(term, " ".join(str(v) for v in body)):
                matched, snippet = "body", " ".join(str(v) for v in body)
            else:
                for key, values in item.details.items():
                    for value in values:
                        if _match(term, value):
                            matched, snippet = key, "%s:%s" % (key, value)
                            break
                    if matched:
                        break
        if matched:
            name = item.details.get("id", [item.title])[0]
            results.append(_result("item", str(name), matched, snippet, item.source, item.line))
    return results


def _search_projects(items, config, term):
    from .projects import collect_projects

    results = []
    for proj in collect_projects(items, config).values():
        for field in ("name", "display_name", "owner", "area"):
            value = proj.get(field)
            if value and _match(term, value):
                results.append(_result("project", proj["name"], field, "%s:%s" % (field, value)))
                break
    return results


def _search_people(items, config, term):
    from .people import people_list

    results = []
    for row in people_list(items, config):
        if _match(term, row["person"]):
            results.append(_result("person", row["person"], "person", row["person"]))
    return results


def _search_groups(config, term):
    from .groups import group_directory

    results = []
    for name, group in group_directory(config).items():
        if _match(term, name):
            results.append(_result("group", name, "name", name))
            continue
        for alias in group.get("aliases", []):
            if _match(term, alias):
                results.append(_result("group", name, "alias", alias))
                break
        else:
            for member in group.get("members", []):
                if _match(term, member):
                    results.append(_result("group", name, "member", member))
                    break
    return results


def _search_areas(items, config, term):
    from .areas import collect_areas

    results = []
    for name in collect_areas(items, config):
        if name and _match(term, name):
            results.append(_result("area", name, "name", name))
    return results


def _search_proposals(config, term):
    from .inbox import list_proposals, proposal_to_line

    results = []
    for proposal in list_proposals(config):
        try:
            line = proposal_to_line(proposal)
        except ValueError:
            line = proposal.get("operation", "")
        if _match(term, line) or _match(term, proposal.get("source", "")):
            results.append(
                _result("proposal", proposal["id"], "proposal",
                        "[%s] %s" % (proposal.get("status", "pending"), line))
            )
    return results


def global_search(items, config=None, term="", types=None, limit=None):
    """Search across every entity type, grouped by type."""
    config = config or {}
    term = str(term or "").lower()
    wanted = set(types) if types else set(ENTITY_TYPES)
    groups = OrderedDict()
    if not term:
        return OrderedDict((("term", term), ("total", 0), ("groups", groups)))

    searchers = OrderedDict(
        (
            ("item", lambda: _search_items(items, term)),
            ("project", lambda: _search_projects(items, config, term)),
            ("person", lambda: _search_people(items, config, term)),
            ("group", lambda: _search_groups(config, term)),
            ("area", lambda: _search_areas(items, config, term)),
            ("proposal", lambda: _search_proposals(config, term)),
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
