"""A shared, surface-neutral query language for life.txt items.

One grammar, one set of typed diagnostics, reused by the CLI ``query`` command,
saved views, and MCP ``run_query`` so a filter written once behaves identically
everywhere. The language compiles to the existing ``filter_items`` engine for
membership fields and adds date comparisons and arbitrary-detail matching on
top, keeping OR-within-a-field / AND-across-fields semantics consistent.

Grammar (whitespace-separated terms; values may be quoted):

    field:value            membership or detail equality (comma = OR of values)
    field=value            same as ':'
    field<DATE  field>DATE  field<=DATE  field>=DATE  field!=DATE
    -tag:value             exclude (also exclude_tag:value)
    open                   only open workflow statuses
    text:"free text"       substring match on title (also bare words)

Unknown fields are reported (Q001) and ignored rather than silently dropped, so
a typo never quietly returns the wrong set.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .model import KNOWN_KEYS
from .timeutil import parse_date


# Query field -> filter_items keyword. These use the tuned membership engine.
MEMBERSHIP_FIELDS = OrderedDict(
    (
        ("status", "statuses"),
        ("s", "statuses"),
        ("type", "kinds"),
        ("kind", "kinds"),
        ("t", "kinds"),
        ("project", "projects"),
        ("p", "projects"),
        ("tag", "tags"),
        ("tag_all", "tag_all"),
        ("user", "users"),
        ("person", "persons"),
        ("owner", "owners"),
        ("assignee", "assignees"),
        ("attendee", "attendees"),
        ("sender", "senders"),
        ("recipient", "recipients"),
        ("team", "teams"),
    )
)

# Detail keys compared as dates rather than string membership.
DATE_FIELDS = (
    "due",
    "do",
    "from",
    "to",
    "on",
    "at",
    "done",
    "created",
    "updated",
    "notify_at",
    "notify_from",
    "notify_to",
    "until",
)

EXCLUDE_FIELDS = ("exclude_tag", "extag", "-tag")
COMPARISON_OPS = ("<=", ">=", "!=", "<", ">", "=", ":")

# Documented custom detail keys that are not in KNOWN_KEYS but are first-class
# organizing dimensions (Life Hub areas, project records). Queried as details.
CUSTOM_DETAIL_FIELDS = ("area", "record", "severity")


def diagnostic(severity, code, message, hint="", term=None):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("hint", hint),
            ("term", term),
        )
    )


def query_fields():
    """All recognized field names, for completion and documentation."""
    fields = list(MEMBERSHIP_FIELDS.keys())
    fields.extend(DATE_FIELDS)
    fields.extend(list(CUSTOM_DETAIL_FIELDS))
    fields.extend(["text", "q", "context", "loc", "priority", "exclude_tag"])
    seen = []
    for field in fields:
        if field not in seen:
            seen.append(field)
    return seen


def _tokenize(text):
    tokens = []
    current = []
    quote = None
    for char in str(text or ""):
        if quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char in ('"', "'"):
            quote = char
        elif char.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _split_field_op(token):
    for op in COMPARISON_OPS:
        index = token.find(op)
        if index > 0:
            return token[:index], op, token[index + len(op) :]
    return None, None, None


def parse_query(text):
    """Compile a query string into a plan plus typed diagnostics."""
    plan = OrderedDict(
        (
            ("query", str(text or "")),
            ("membership", OrderedDict()),
            ("excludes", []),
            ("details", OrderedDict()),
            ("date_filters", []),
            ("text", []),
            ("open_only", False),
        )
    )
    diagnostics = []

    for token in _tokenize(text):
        if not token:
            continue
        if token.lower() == "open":
            plan["open_only"] = True
            continue

        negate = token.startswith("-")
        field, op, value = _split_field_op(token)
        if field is None:
            plan["text"].append(token)
            continue

        raw_field = field
        field = field.lstrip("-").lower()

        if raw_field.lower() in EXCLUDE_FIELDS or (negate and field == "tag"):
            _add_values(plan["excludes"], value, diagnostics, token)
            continue

        if field in ("text", "q"):
            if value:
                plan["text"].append(value)
            continue

        if field in DATE_FIELDS:
            parsed = _parse_date_literal(value)
            if parsed is None:
                diagnostics.append(
                    diagnostic(
                        "error",
                        "Q002",
                        "Invalid date %r in %r." % (value, token),
                        "Use YYYY-MM-DD.",
                        token,
                    )
                )
                continue
            plan["date_filters"].append(
                OrderedDict(
                    (("field", field), ("op", op), ("date", parsed.isoformat()))
                )
            )
            continue

        if field in MEMBERSHIP_FIELDS:
            if op not in (":", "="):
                diagnostics.append(
                    diagnostic(
                        "error",
                        "Q004",
                        "Operator %r is not supported for %r." % (op, field),
                        "Use field:value for membership fields.",
                        token,
                    )
                )
                continue
            values = plan["membership"].setdefault(field, [])
            _add_values(values, value, diagnostics, token)
            continue

        if field in KNOWN_KEYS or field in CUSTOM_DETAIL_FIELDS:
            if op not in (":", "="):
                diagnostics.append(
                    diagnostic(
                        "error",
                        "Q004",
                        "Operator %r is not supported for detail %r." % (op, field),
                        "Use field:value.",
                        token,
                    )
                )
                continue
            values = plan["details"].setdefault(field, [])
            _add_values(values, value, diagnostics, token)
            continue

        diagnostics.append(
            diagnostic(
                "warning",
                "Q001",
                "Unknown query field %r; term ignored." % field,
                "Known fields: %s." % ", ".join(query_fields()),
                token,
            )
        )

    plan["diagnostics"] = diagnostics
    return plan, diagnostics


def _add_values(target, value, diagnostics, token):
    if value is None or value == "":
        diagnostics.append(
            diagnostic(
                "warning",
                "Q003",
                "Empty value in %r; term ignored." % token,
                "Provide a value after the field.",
                token,
            )
        )
        return
    for part in value.split(","):
        part = part.strip()
        if part and part not in target:
            target.append(part)


def _parse_date_literal(value):
    if not value:
        return None
    try:
        return parse_date(value)
    except Exception:
        return None


def apply_query(items, plan, config=None):
    """Filter ``items`` by a compiled plan, returning the matching items."""
    from .agenda import filter_items
    from .config import (
        config_tag_aliases,
        config_team_aliases,
        config_team_members,
        config_user_aliases,
    )

    config = config or {}
    membership = plan.get("membership", {})
    kwargs = {}
    for field, values in membership.items():
        kwargs[MEMBERSHIP_FIELDS[field]] = list(values)

    filtered = filter_items(
        items,
        open_only=plan.get("open_only", False),
        exclude_tags=list(plan.get("excludes") or []) or None,
        text=" ".join(plan.get("text") or []) or None,
        user_aliases=config_user_aliases(config),
        team_members=config_team_members(config),
        team_aliases=config_team_aliases(config),
        tag_aliases=config_tag_aliases(config),
        **kwargs,
    )

    details = plan.get("details") or {}
    if details:
        filtered = [item for item in filtered if _matches_details(item, details)]

    date_filters = plan.get("date_filters") or []
    if date_filters:
        filtered = [item for item in filtered if _matches_dates(item, date_filters)]

    return filtered


def _matches_details(item, details):
    for field, values in details.items():
        item_values = [str(v) for v in item.details.get(field, [])]
        if not any(value in item_values for value in values):
            return False
    return True


def _matches_dates(item, date_filters):
    for spec in date_filters:
        field = spec["field"]
        op = spec["op"]
        target = _parse_date_literal(spec["date"])
        raw = item.details.get(field)
        actual = _parse_date_literal(raw[0]) if raw else None
        if actual is None or target is None:
            return False
        if not _compare(actual, op, target):
            return False
    return True


def _compare(actual, op, target):
    if op in (":", "="):
        return actual == target
    if op == "!=":
        return actual != target
    if op == "<":
        return actual < target
    if op == "<=":
        return actual <= target
    if op == ">":
        return actual > target
    if op == ">=":
        return actual >= target
    return False


def run_query(items, query_text, config=None, sort=None, order="asc", limit=None):
    """Parse, apply, sort, and limit in one call. Returns (items, diagnostics)."""
    plan, diagnostics = parse_query(query_text)
    filtered = apply_query(items, plan, config)
    if sort:
        from .webapp import sort_items

        filtered = sort_items(filtered, sort, order)
    if limit not in (None, "", 0):
        from .webapp import limit_items

        filtered = limit_items(filtered, limit)
    return filtered, diagnostics
