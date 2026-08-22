"""Typed, configuration-backed custom fields for development tickets.

Only fields declared under ``ticketing.custom_fields`` are typed here. Unknown
life.txt detail keys remain valid and are deliberately ignored so this feature
does not turn the extensible plain-text format into a closed global schema.
"""

from __future__ import unicode_literals

import argparse
import copy
import json
import re
from collections import OrderedDict
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation

from .timeutil import parse_iso_date, parse_iso_datetime


SUPPORTED_TYPES = (
    "string",
    "integer",
    "number",
    "boolean",
    "date",
    "datetime",
    "duration",
    "enum",
)
PRIVACY_LEVELS = ("public", "internal", "private", "secret")
_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_ACTIVE_CONFIG = ContextVar("lifetxt_ticket_custom_field_config", default=None)
_INSTALLED = False
_ORIGINALS = {}

_DEFINITION_KEYS = frozenset(
    (
        "type",
        "label",
        "description",
        "repeatable",
        "required",
        "default",
        "enum",
        "values",
        "minimum",
        "maximum",
        "min_length",
        "max_length",
        "pattern",
        "filterable",
        "searchable",
        "privacy",
        "trackers",
        "projects",
        "applicable_trackers",
        "applicable_projects",
        "editable_roles",
        "visible_roles",
    )
)


def _diag(code, message, field=None, hint=None, item=None):
    row = OrderedDict(
        (
            ("severity", "error"),
            ("code", code),
            ("message", message),
            ("hint", hint or "Fix ticketing.custom_fields before writing tickets."),
            ("source", getattr(item, "source", None) if item is not None else None),
            ("line", getattr(item, "line", None) if item is not None else None),
        )
    )
    if field is not None:
        row["field"] = str(field)
    return row


def _string_list(value):
    if value in (None, ""):
        return []
    source = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
    result = []
    for entry in source:
        text = str(entry).strip()
        if text and text not in result:
            result.append(text)
    return result


def _definition_boolean(raw, key, field, diagnostics, default=False):
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    diagnostics.append(
        _diag(
            "TK006",
            "Custom field %r metadata %s must be a boolean." % (field, key),
            field,
        )
    )
    return bool(default)


def _definition_integer(raw, key, field, diagnostics):
    if raw is None:
        return None
    if isinstance(raw, bool):
        diagnostics.append(
            _diag(
                "TK006",
                "Custom field %r metadata %s must be an integer." % (field, key),
                field,
            )
        )
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        diagnostics.append(
            _diag(
                "TK006",
                "Custom field %r metadata %s must be an integer." % (field, key),
                field,
            )
        )
        return None
    if value < 0:
        diagnostics.append(
            _diag(
                "TK006",
                "Custom field %r metadata %s must be zero or greater." % (field, key),
                field,
            )
        )
        return None
    return value


def _definition_decimal(raw, key, field, diagnostics):
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        diagnostics.append(
            _diag(
                "TK006",
                "Custom field %r metadata %s must be numeric." % (field, key),
                field,
            )
        )
        return None
    if not value.is_finite():
        diagnostics.append(
            _diag(
                "TK006",
                "Custom field %r metadata %s must be finite." % (field, key),
                field,
            )
        )
        return None
    return value


def _reserved_names():
    from .tickets import RELATION_FIELDS, TICKET_FIELDS

    return (
        set(TICKET_FIELDS)
        | set(RELATION_FIELDS)
        | {
            "record",
            "id",
            "source",
            "uid",
            "project",
            "created",
            "updated",
            "done",
            "due",
            "do",
            "tag",
            "note",
            "body",
            "url",
        }
    )


def custom_field_registry_report(config=None):
    """Return normalized definitions plus stable registry diagnostics."""
    from .tickets import ticketing_config

    section = ticketing_config(config or {})
    raw_registry = section.get("custom_fields")
    definitions = OrderedDict()
    diagnostics = []
    if raw_registry in (None, ""):
        return OrderedDict(
            (
                ("schema", "ticket-custom-field-registry-v1.schema.json"),
                ("valid", True),
                ("definitions", definitions),
                ("diagnostics", diagnostics),
            )
        )
    if not isinstance(raw_registry, dict):
        diagnostics.append(
            _diag(
                "TK006",
                "ticketing.custom_fields must be an object keyed by field name.",
            )
        )
        return OrderedDict(
            (
                ("schema", "ticket-custom-field-registry-v1.schema.json"),
                ("valid", False),
                ("definitions", definitions),
                ("diagnostics", diagnostics),
            )
        )

    reserved = _reserved_names()
    for raw_name, raw_definition in raw_registry.items():
        name = str(raw_name).strip()
        before = len(diagnostics)
        if not _FIELD_NAME_RE.match(name):
            diagnostics.append(
                _diag(
                    "TK006",
                    "Invalid custom field name %r; use letters, digits, underscore, dot, or hyphen."
                    % name,
                    name,
                )
            )
        if name in reserved:
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r conflicts with a canonical, relation, or system ticket field."
                    % name,
                    name,
                )
            )
        if isinstance(raw_definition, str):
            raw_definition = {"type": raw_definition}
        if not isinstance(raw_definition, dict):
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r definition must be an object or type string."
                    % name,
                    name,
                )
            )
            continue
        unknown = sorted(set(raw_definition) - _DEFINITION_KEYS)
        if unknown:
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r has unknown metadata keys: %s."
                    % (name, ", ".join(unknown)),
                    name,
                )
            )

        field_type = str(raw_definition.get("type") or "string").strip().lower()
        if field_type not in SUPPORTED_TYPES:
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r has unsupported type %r; use one of: %s."
                    % (name, field_type, ", ".join(SUPPORTED_TYPES)),
                    name,
                )
            )
            field_type = "string"

        repeatable = _definition_boolean(
            raw_definition.get("repeatable"), "repeatable", name, diagnostics, False
        )
        required = _definition_boolean(
            raw_definition.get("required"), "required", name, diagnostics, False
        )
        filterable = _definition_boolean(
            raw_definition.get("filterable"), "filterable", name, diagnostics, False
        )
        searchable = _definition_boolean(
            raw_definition.get("searchable"), "searchable", name, diagnostics, False
        )
        privacy = str(raw_definition.get("privacy") or "internal").strip().lower()
        if privacy not in PRIVACY_LEVELS:
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r privacy %r must be one of: %s."
                    % (name, privacy, ", ".join(PRIVACY_LEVELS)),
                    name,
                )
            )
            privacy = "internal"

        enum_values = raw_definition.get("enum")
        if enum_values is None:
            enum_values = raw_definition.get("values")
        enum_values = _string_list(enum_values)
        if field_type == "enum" and not enum_values:
            diagnostics.append(
                _diag(
                    "TK006",
                    "Enum custom field %r requires a non-empty enum or values list."
                    % name,
                    name,
                )
            )

        minimum = _definition_decimal(
            raw_definition.get("minimum"), "minimum", name, diagnostics
        )
        maximum = _definition_decimal(
            raw_definition.get("maximum"), "maximum", name, diagnostics
        )
        if minimum is not None and maximum is not None and minimum > maximum:
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r minimum is greater than maximum." % name,
                    name,
                )
            )
        min_length = _definition_integer(
            raw_definition.get("min_length"), "min_length", name, diagnostics
        )
        max_length = _definition_integer(
            raw_definition.get("max_length"), "max_length", name, diagnostics
        )
        if (
            min_length is not None
            and max_length is not None
            and min_length > max_length
        ):
            diagnostics.append(
                _diag(
                    "TK006",
                    "Custom field %r min_length is greater than max_length." % name,
                    name,
                )
            )
        pattern = raw_definition.get("pattern")
        if pattern is not None:
            pattern = str(pattern)
            try:
                re.compile(pattern)
            except re.error as exc:
                diagnostics.append(
                    _diag(
                        "TK006",
                        "Custom field %r pattern is invalid: %s." % (name, exc),
                        name,
                    )
                )

        trackers = _string_list(
            raw_definition.get("trackers", raw_definition.get("applicable_trackers"))
        )
        projects = _string_list(
            raw_definition.get("projects", raw_definition.get("applicable_projects"))
        )
        editable_roles = _string_list(raw_definition.get("editable_roles"))
        visible_roles = _string_list(raw_definition.get("visible_roles"))

        definition = OrderedDict(
            (
                ("type", field_type),
                ("label", str(raw_definition.get("label") or name)),
                ("description", str(raw_definition.get("description") or "")),
                ("repeatable", repeatable),
                ("required", required),
                ("filterable", filterable),
                ("searchable", searchable),
                ("privacy", privacy),
                ("enum", enum_values),
                ("minimum", None if minimum is None else _decimal_text(minimum)),
                ("maximum", None if maximum is None else _decimal_text(maximum)),
                ("min_length", min_length),
                ("max_length", max_length),
                ("pattern", pattern),
                ("trackers", trackers),
                ("projects", projects),
                ("editable_roles", editable_roles),
                ("visible_roles", visible_roles),
            )
        )
        if "default" in raw_definition:
            definition["default"] = copy.deepcopy(raw_definition.get("default"))

        if len(diagnostics) == before:
            default_values = _definition_default_values(name, definition, diagnostics)
            if default_values is not None:
                definition["default_values"] = default_values
        definitions[name] = definition

    return OrderedDict(
        (
            ("schema", "ticket-custom-field-registry-v1.schema.json"),
            ("valid", not diagnostics),
            ("definitions", definitions),
            ("diagnostics", diagnostics),
        )
    )


def custom_field_definitions(config=None, strict=False):
    report = custom_field_registry_report(config)
    if strict and not report["valid"]:
        raise ValueError(report["diagnostics"])
    return report["definitions"]


def _decimal_text(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _normalize_boolean(value):
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return "true", Decimal(1)
    if text in ("0", "false", "no", "off"):
        return "false", Decimal(0)
    raise ValueError("must be true/false, yes/no, on/off, or 1/0")


def _normalize_custom_value(value, definition):
    field_type = definition["type"]
    text = str(value)
    comparable = None
    if field_type in ("string", "enum"):
        normalized = text
    elif field_type == "integer":
        if not re.match(r"^[+-]?\d+$", text.strip()):
            raise ValueError("must be an integer")
        number = int(text.strip())
        normalized = str(number)
        comparable = Decimal(number)
    elif field_type == "number":
        try:
            number = Decimal(text.strip())
        except (InvalidOperation, ValueError):
            raise ValueError("must be a number")
        if not number.is_finite():
            raise ValueError("must be a finite number")
        normalized = _decimal_text(number)
        comparable = number
    elif field_type == "boolean":
        normalized, comparable = _normalize_boolean(text)
    elif field_type == "date":
        if "T" in text or " " in text:
            raise ValueError("must be an ISO date without a time")
        parsed = parse_iso_date(text)
        if parsed is None:
            raise ValueError("must be an ISO date (YYYY-MM-DD)")
        normalized = parsed.isoformat()
    elif field_type == "datetime":
        if "T" not in text and " " not in text:
            raise ValueError("must include a date and time")
        parsed = parse_iso_datetime(text)
        if parsed is None:
            raise ValueError("must be an ISO date-time")
        normalized = parsed.isoformat()
    elif field_type == "duration":
        from .agenda import parse_duration

        try:
            parsed = parse_duration(text)
        except (TypeError, ValueError):
            raise ValueError("must be a lifetxt duration such as 30m, 2h, or 1d")
        normalized = text.strip()
        comparable = Decimal(str(parsed.total_seconds()))
    else:
        raise ValueError("uses unsupported type %r" % field_type)

    allowed = definition.get("enum") or []
    if allowed and normalized not in allowed:
        raise ValueError("must be one of: %s" % ", ".join(allowed))
    minimum = definition.get("minimum")
    maximum = definition.get("maximum")
    if (
        comparable is not None
        and minimum is not None
        and comparable < Decimal(str(minimum))
    ):
        raise ValueError("must be at least %s" % minimum)
    if (
        comparable is not None
        and maximum is not None
        and comparable > Decimal(str(maximum))
    ):
        raise ValueError("must be at most %s" % maximum)
    min_length = definition.get("min_length")
    max_length = definition.get("max_length")
    if min_length is not None and len(normalized) < int(min_length):
        raise ValueError("must contain at least %s characters" % min_length)
    if max_length is not None and len(normalized) > int(max_length):
        raise ValueError("must contain at most %s characters" % max_length)
    pattern = definition.get("pattern")
    if pattern and re.search(pattern, normalized) is None:
        raise ValueError("does not match pattern %s" % pattern)
    return normalized


def _definition_default_values(name, definition, diagnostics):
    if "default" not in definition:
        return None
    raw = definition.get("default")
    values = list(raw) if isinstance(raw, (list, tuple)) else [raw]
    if not definition["repeatable"] and len(values) > 1:
        diagnostics.append(
            _diag(
                "TK006",
                "Custom field %r has multiple defaults but is not repeatable." % name,
                name,
            )
        )
        return None
    normalized = []
    for value in values:
        try:
            normalized.append(_normalize_custom_value(value, definition))
        except ValueError as exc:
            diagnostics.append(
                _diag(
                    "TK006", "Custom field %r default %r %s." % (name, value, exc), name
                )
            )
    return (
        normalized
        if normalized and not any(row.get("field") == name for row in diagnostics)
        else None
    )


def _field_applies(definition, tracker_values=None, project_values=None):
    trackers = set(str(value) for value in (tracker_values or []) if str(value))
    projects = set(str(value) for value in (project_values or []) if str(value))
    allowed_trackers = set(definition.get("trackers") or [])
    allowed_projects = set(definition.get("projects") or [])
    if (
        allowed_trackers
        and tracker_values is not None
        and not (allowed_trackers & trackers)
    ):
        return False
    if (
        allowed_projects
        and project_values is not None
        and not (allowed_projects & projects)
    ):
        return False
    return True


def _role_allowed(definition, role, key):
    allowed = definition.get(key) or []
    if not allowed or role in (None, ""):
        return True
    return str(role) in allowed


def validate_ticket_custom_fields(item, config=None):
    """Validate only configured custom fields; unknown detail keys stay valid."""
    report = custom_field_registry_report(config)
    rows = []
    for diagnostic in report["diagnostics"]:
        copied = OrderedDict(diagnostic)
        copied["source"] = getattr(item, "source", None)
        copied["line"] = getattr(item, "line", None)
        rows.append(copied)
    tracker_values = item.details.get("tracker") or []
    project_values = item.details.get("project") or []
    for name, definition in report["definitions"].items():
        values = [str(value) for value in item.details.get(name, [])]
        meaningful = [value for value in values if value != ""]
        applies = _field_applies(definition, tracker_values, project_values)
        if values and not applies:
            rows.append(
                _diag(
                    "TK010",
                    "Custom field %r is not applicable to this ticket tracker/project."
                    % name,
                    name,
                    "Remove %s: or adjust its trackers/projects configuration." % name,
                    item,
                )
            )
            continue
        if applies and definition.get("required") and not meaningful:
            rows.append(
                _diag(
                    "TK007",
                    "Required custom ticket field %r is missing." % name,
                    name,
                    "Set %s: to a value allowed by ticketing.custom_fields.%s."
                    % (name, name),
                    item,
                )
            )
        if not definition.get("repeatable") and len(values) > 1:
            rows.append(
                _diag(
                    "TK008",
                    "Custom field %r is not repeatable but appears %d times."
                    % (name, len(values)),
                    name,
                    "Keep exactly one %s: value." % name,
                    item,
                )
            )
        for value in values:
            try:
                _normalize_custom_value(value, definition)
            except ValueError as exc:
                rows.append(
                    _diag(
                        "TK009",
                        "Custom field %r value %r %s." % (name, value, exc),
                        name,
                        "Use the configured %s constraints." % definition.get("type"),
                        item,
                    )
                )
    return rows


def custom_field_values(item, config=None, role=None, include_hidden=False):
    definitions = custom_field_definitions(config)
    result = OrderedDict()
    for name, definition in definitions.items():
        values = [str(value) for value in item.details.get(name, [])]
        if not values:
            continue
        if not include_hidden and not _role_allowed(definition, role, "visible_roles"):
            continue
        result[name] = values if definition.get("repeatable") else values[0]
    return result


def apply_custom_defaults(
    details, config=None, tracker_values=None, project_values=None
):
    definitions = custom_field_definitions(config, strict=True)
    for name, definition in definitions.items():
        if details.get(name):
            continue
        if not _field_applies(definition, tracker_values, project_values):
            continue
        values = definition.get("default_values")
        if values:
            details[name] = list(values)
    return details


def parse_custom_field_assignments(pairs, config=None, filter_only=False):
    definitions = custom_field_definitions(config, strict=True)
    result = OrderedDict()
    for pair in pairs or []:
        if "=" not in str(pair):
            raise ValueError("--field expects KEY=VALUE, got %r" % pair)
        name, value = str(pair).split("=", 1)
        name = name.strip()
        if name not in definitions:
            raise ValueError(
                "Unknown configured custom field %r. Use `ticket fields` to inspect the registry."
                % name
            )
        definition = definitions[name]
        if filter_only and not definition.get("filterable"):
            raise ValueError("Custom field %r is not filterable." % name)
        normalized = _normalize_custom_value(value.strip(), definition)
        result.setdefault(name, []).append(normalized)
        if not definition.get("repeatable") and len(result[name]) > 1:
            raise ValueError("Custom field %r is not repeatable." % name)
    return result


def ticket_custom_field_contract(config=None, role=None):
    report = custom_field_registry_report(config)
    definitions = OrderedDict()
    for name, definition in report["definitions"].items():
        value = OrderedDict(definition)
        value.pop("default_values", None)
        if role not in (None, ""):
            value["visible_for_role"] = _role_allowed(definition, role, "visible_roles")
            value["editable_for_role"] = _role_allowed(
                definition, role, "editable_roles"
            )
        definitions[name] = value
    return OrderedDict(
        (
            ("contract_version", "1"),
            ("schema", report["schema"]),
            ("supported_types", list(SUPPORTED_TYPES)),
            ("privacy_levels", list(PRIVACY_LEVELS)),
            ("unknown_unconfigured_keys_allowed", True),
            ("remote_write_enforcement", False),
            ("valid", report["valid"]),
            ("definitions", definitions),
            ("diagnostics", report["diagnostics"]),
        )
    )


def _patch_ticket_core():
    from . import tickets
    from .parser import parse_text
    from .serializer import item_to_line

    if "validate_ticket" in _ORIGINALS:
        return
    _ORIGINALS["validate_ticket"] = tickets.validate_ticket
    _ORIGINALS["ticket_view"] = tickets.ticket_view
    _ORIGINALS["build_ticket_line"] = tickets.build_ticket_line

    def validate_ticket(item, config, key="id"):
        rows = list(_ORIGINALS["validate_ticket"](item, config, key=key))
        rows.extend(validate_ticket_custom_fields(item, config))
        return rows

    def ticket_view(item, config, items=None, key="id"):
        result = OrderedDict(
            _ORIGINALS["ticket_view"](item, config, items=items, key=key)
        )
        result["custom_fields"] = custom_field_values(item, config)
        return result

    def build_ticket_line(
        config,
        subject,
        tracker=None,
        priority=None,
        severity=None,
        assignee=None,
        reporter=None,
        component=None,
        version=None,
        sprint=None,
        ticket_status="new",
        project=None,
        due=None,
        est=None,
        watchers=None,
        ticket_id=None,
        extra=None,
    ):
        line = _ORIGINALS["build_ticket_line"](
            config,
            subject,
            tracker=tracker,
            priority=priority,
            severity=severity,
            assignee=assignee,
            reporter=reporter,
            component=component,
            version=version,
            sprint=sprint,
            ticket_status=ticket_status,
            project=project,
            due=due,
            est=est,
            watchers=watchers,
            ticket_id=ticket_id,
            extra=None,
        )
        parsed, diagnostics = parse_text(
            line + "\n",
            id_key=tickets.id_key(config),
            check_ids=False,
            check_references=False,
        )
        errors = [
            d.to_dict() for d in diagnostics if getattr(d, "severity", None) == "error"
        ]
        if not parsed or errors:
            raise ValueError(errors or "Generated ticket did not parse.")
        item = parsed[0]
        for name, raw in (extra or {}).items():
            values = list(raw) if isinstance(raw, (list, tuple)) else [raw]
            item.details[name] = [str(value) for value in values]
        apply_custom_defaults(
            item.details,
            config,
            tracker_values=item.details.get("tracker") or [],
            project_values=item.details.get("project") or [],
        )
        field_errors = validate_ticket_custom_fields(item, config)
        if field_errors:
            raise ValueError(field_errors)
        return item_to_line(item)

    tickets.validate_ticket = validate_ticket
    tickets.ticket_view = ticket_view
    tickets.build_ticket_line = build_ticket_line
    tickets.custom_field_definitions = custom_field_definitions
    tickets.custom_field_registry_report = custom_field_registry_report
    tickets.validate_ticket_custom_fields = validate_ticket_custom_fields
    tickets.ticket_custom_field_contract = ticket_custom_field_contract


def _patch_revision_validation():
    from . import ticket_revision_writes as revision
    from . import tickets

    if "revision_replace_ticket_text" in _ORIGINALS:
        return
    _ORIGINALS["revision_replace_ticket_text"] = revision._replace_ticket_text
    _ORIGINALS["revision_apply_ticket_patch"] = revision.apply_ticket_patch
    _ORIGINALS["revision_apply_ticket_relation"] = revision.apply_ticket_relation

    def replace_ticket_text(text, ticket_id, key, update_item):
        replacement, updated = _ORIGINALS["revision_replace_ticket_text"](
            text, ticket_id, key, update_item
        )
        config = _ACTIVE_CONFIG.get() or {}
        errors = validate_ticket_custom_fields(updated, config)
        if errors:
            raise ValueError(errors)
        return replacement, updated

    def apply_ticket_patch(
        path,
        ticket_id,
        detail_updates=None,
        status=None,
        key="id",
        expected_revision=None,
        require_revision=False,
        dry_run=False,
        operation="ticket.patch",
        config=None,
    ):
        token = _ACTIVE_CONFIG.set(
            config if config is not None else _ACTIVE_CONFIG.get()
        )
        try:
            return _ORIGINALS["revision_apply_ticket_patch"](
                path,
                ticket_id,
                detail_updates=detail_updates,
                status=status,
                key=key,
                expected_revision=expected_revision,
                require_revision=require_revision,
                dry_run=dry_run,
                operation=operation,
            )
        finally:
            _ACTIVE_CONFIG.reset(token)

    def apply_ticket_relation(
        path,
        ticket_id,
        relation,
        target_id,
        add=True,
        key="id",
        expected_revision=None,
        require_revision=False,
        dry_run=False,
        operation=None,
        config=None,
    ):
        token = _ACTIVE_CONFIG.set(
            config if config is not None else _ACTIVE_CONFIG.get()
        )
        try:
            return _ORIGINALS["revision_apply_ticket_relation"](
                path,
                ticket_id,
                relation,
                target_id,
                add=add,
                key=key,
                expected_revision=expected_revision,
                require_revision=require_revision,
                dry_run=dry_run,
                operation=operation,
            )
        finally:
            _ACTIVE_CONFIG.reset(token)

    revision._replace_ticket_text = replace_ticket_text
    revision.apply_ticket_patch = apply_ticket_patch
    revision.apply_ticket_relation = apply_ticket_relation
    tickets.apply_ticket_patch = apply_ticket_patch
    tickets.apply_ticket_relation = apply_ticket_relation


def _subparsers_action(parser):
    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _has_option(parser, option):
    return any(
        option in getattr(action, "option_strings", []) for action in parser._actions
    )


def _install_cli_arguments(parser, cli_module):
    root = _subparsers_action(parser)
    ticket_parser = root.choices.get("ticket") if root is not None else None
    actions = _subparsers_action(ticket_parser) if ticket_parser is not None else None
    if actions is None:
        return parser
    new_parser = actions.choices.get("new")
    if new_parser is not None and not _has_option(new_parser, "--field"):
        new_parser.add_argument(
            "--field",
            action="append",
            dest="custom_fields",
            metavar="KEY=VALUE",
            help="Set a configured typed custom field. Repeat for repeatable fields.",
        )
    list_parser = actions.choices.get("list")
    if list_parser is not None and not _has_option(list_parser, "--field"):
        list_parser.add_argument(
            "--field",
            action="append",
            dest="custom_filters",
            metavar="KEY=VALUE",
            help="Filter by a configured custom field whose filterable flag is true.",
        )
        list_parser.add_argument(
            "--has-field",
            action="append",
            dest="has_custom_fields",
            metavar="KEY",
            help="Require a configured filterable custom field to be present.",
        )
    if "fields" not in actions.choices:
        fields = actions.add_parser(
            "fields",
            help="Inspect and validate the effective typed custom-field registry.",
        )
        fields.add_argument(
            "--tracker", help="Show whether each field applies to this tracker."
        )
        fields.add_argument(
            "--project", help="Show whether each field applies to this project."
        )
        fields.add_argument(
            "--role", help="Evaluate visible/editable role restrictions."
        )
        fields.add_argument("--format", choices=("text", "json"), default="text")
        fields.add_argument("--pretty", action="store_true")
        fields.set_defaults(func=_command_ticket_fields)
    return parser


def _config_scoped_command(cli_module, function):
    def command(args):
        token = _ACTIVE_CONFIG.set(cli_module._config(args))
        try:
            return function(args)
        finally:
            _ACTIVE_CONFIG.reset(token)

    command.__name__ = getattr(function, "__name__", "ticket_custom_field_command")
    return command


def _command_ticket_fields(args):
    from . import cli as cli_module

    config = cli_module._config(args)
    contract = ticket_custom_field_contract(config, role=getattr(args, "role", None))
    tracker = getattr(args, "tracker", None)
    project = getattr(args, "project", None)
    if tracker or project:
        for definition in contract["definitions"].values():
            definition["applicable"] = _field_applies(
                definition,
                [tracker] if tracker else None,
                [project] if project else None,
            )
    if getattr(args, "format", "text") == "json":
        cli_module.write_text(
            None,
            json.dumps(
                contract,
                ensure_ascii=False,
                indent=2 if getattr(args, "pretty", False) else None,
                separators=None if getattr(args, "pretty", False) else (",", ":"),
            )
            + "\n",
        )
    else:
        if not contract["definitions"]:
            cli_module.write_text(None, "No ticket custom fields are configured.\n")
        for name, definition in contract["definitions"].items():
            flags = []
            if definition.get("required"):
                flags.append("required")
            if definition.get("repeatable"):
                flags.append("repeatable")
            if definition.get("filterable"):
                flags.append("filterable")
            if definition.get("searchable"):
                flags.append("searchable")
            if "applicable" in definition and not definition["applicable"]:
                flags.append("not-applicable")
            cli_module.write_text(
                None,
                "%-20s %-9s %-9s %s\n"
                % (
                    name,
                    definition["type"],
                    definition["privacy"],
                    ", ".join(flags) or "-",
                ),
            )
        for diagnostic in contract["diagnostics"]:
            cli_module.sys.stderr.write(
                "%s %s: %s\n"
                % (
                    diagnostic["severity"].upper(),
                    diagnostic["code"],
                    diagnostic["message"],
                )
            )
    return 0 if contract["valid"] else 1


def _patch_cli():
    from . import cli as cli_module
    from . import tickets

    if "custom_cli_build_parser" in _ORIGINALS:
        return
    _ORIGINALS["custom_cli_build_parser"] = cli_module.build_parser
    _ORIGINALS["command_ticket_new"] = cli_module.command_ticket_new
    _ORIGINALS["command_ticket_list"] = cli_module.command_ticket_list
    _ORIGINALS["command_ticket_show"] = cli_module.command_ticket_show

    def build_parser():
        return _install_cli_arguments(
            _ORIGINALS["custom_cli_build_parser"](), cli_module
        )

    def command_ticket_new(args):
        config = cli_module._config(args)
        custom = parse_custom_field_assignments(
            getattr(args, "custom_fields", None), config=config
        )
        key = cli_module.id_key_from_config(config)
        items, _diagnostics = cli_module._parse_or_exit(
            cli_module._ticket_paths(args), config
        )
        ticket_id = getattr(args, "id", None) or tickets.next_ticket_id(items, config)
        line = tickets.build_ticket_line(
            config,
            args.subject,
            tracker=args.tracker,
            priority=args.priority,
            severity=args.severity,
            assignee=args.assignee,
            reporter=args.reporter,
            component=args.component,
            version=args.version,
            sprint=args.sprint,
            project=args.project,
            due=args.due,
            est=args.est,
            ticket_status=getattr(args, "status", "new"),
            watchers=getattr(args, "watcher", None),
            ticket_id=ticket_id,
            extra=custom,
        )
        parsed, diagnostics = cli_module.parse_text(
            line + "\n", id_key=key, check_ids=False, check_references=False
        )
        if not parsed:
            raise ValueError("Generated ticket did not parse.")
        errors = [
            row
            for row in tickets.validate_ticket(parsed[0], config, key=key)
            if row["severity"] == "error"
        ]
        if errors:
            raise ValueError(errors)
        if getattr(args, "dry_run", False):
            cli_module.write_text(None, line + "\n")
            return 0
        target = getattr(args, "to", None) or cli_module.config_write_file(config)
        if not target:
            paths = cli_module.config_paths(config)
            target = paths[0] if paths else "life.txt"
        cli_module._ensure_writable_path(target, config, "ticket new")
        event_line = cli_module._ticket_creation_event_line(
            ticket_id,
            config,
            project=args.project,
            tracker=args.tracker,
            author=args.reporter,
        )
        cli_module.append_line(target, line + "\n" + event_line)
        cli_module.write_text(
            None, "Created %s in %s:\n  %s\n" % (ticket_id, target, line)
        )
        return 0

    def command_ticket_list(args):
        config = cli_module._config(args)
        items, _diagnostics = cli_module._parse_or_exit(
            cli_module._ticket_paths(args), config
        )
        canonical = {}
        for field in (
            "tracker",
            "status",
            "priority",
            "severity",
            "assignee",
            "component",
            "version",
            "sprint",
            "project",
        ):
            value = getattr(args, field, None)
            if value:
                canonical["ticket_status" if field == "status" else field] = value
        if getattr(args, "open_only", False):
            canonical["open_only"] = True
        custom = parse_custom_field_assignments(
            getattr(args, "custom_filters", None), config=config, filter_only=True
        )
        definitions = custom_field_definitions(config, strict=True)
        has_fields = []
        for name in getattr(args, "has_custom_fields", None) or []:
            name = str(name).strip()
            if name not in definitions:
                raise ValueError("Unknown configured custom field %r." % name)
            if not definitions[name].get("filterable"):
                raise ValueError("Custom field %r is not filterable." % name)
            has_fields.append(name)
        rows = []
        for item in tickets.iter_tickets(items):
            summary = tickets.ticket_summary(
                item, config, key=cli_module.id_key_from_config(config)
            )
            if not tickets._matches_filters(summary, canonical):
                continue
            matched = True
            for name, wanted_values in custom.items():
                actual = [str(value) for value in item.details.get(name, [])]
                if not all(value in actual for value in wanted_values):
                    matched = False
                    break
            if matched and any(not item.details.get(name) for name in has_fields):
                matched = False
            if matched:
                rows.append(summary)
        rows.sort(key=lambda row: str(row["id"] or ""))
        if getattr(args, "json", False):
            cli_module.write_text(
                None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
            )
            return 0
        if not rows:
            cli_module.write_text(None, "No tickets.\n")
            return 0
        for row in rows:
            cli_module.write_text(
                None,
                "%-10s %-8s %-10s %-8s %-10s %s\n"
                % (
                    row["id"] or "-",
                    row["tracker"] or "-",
                    row["ticket_status"] or "-",
                    row["priority"] or "-",
                    row["assignee"] or "-",
                    row["title"],
                ),
            )
        return 0

    def command_ticket_show(args):
        config = cli_module._config(args)
        key = cli_module.id_key_from_config(config)
        items, _diagnostics = cli_module._parse_or_exit(
            cli_module._ticket_paths(args), config
        )
        target = None
        for item in items:
            if (
                tickets.is_ticket(item)
                and str(tickets.ticket_id_of(item, key)) == args.id
            ):
                target = item
                break
        if target is None:
            cli_module.sys.stderr.write("ERROR: Ticket %r not found.\n" % args.id)
            return 1
        view = tickets.ticket_view(target, config, items, key=key)
        if getattr(args, "json", False):
            cli_module.write_text(
                None, json.dumps(view, ensure_ascii=False, indent=2) + "\n"
            )
            return 0
        summary = view["summary"]
        cli_module.write_text(None, "%s  %s\n" % (summary["id"], summary["title"]))
        cli_module.write_text(
            None,
            "  tracker=%s status=%s (%s) priority=%s severity=%s\n"
            % (
                summary["tracker"],
                summary["ticket_status"],
                summary["status"],
                summary["priority"],
                summary["severity"],
            ),
        )
        cli_module.write_text(
            None,
            "  assignee=%s reporter=%s project=%s component=%s version=%s sprint=%s\n"
            % (
                summary["assignee"],
                summary["reporter"],
                summary["project"],
                summary["component"],
                summary["version"],
                summary["sprint"],
            ),
        )
        if summary["watchers"]:
            cli_module.write_text(
                None, "  watchers: %s\n" % ", ".join(summary["watchers"])
            )
        if view["custom_fields"]:
            cli_module.write_text(None, "  custom fields:\n")
            for name, value in view["custom_fields"].items():
                rendered = ", ".join(value) if isinstance(value, list) else value
                cli_module.write_text(None, "    %s: %s\n" % (name, rendered))
        if view["relations"]:
            cli_module.write_text(None, "  relations:\n")
            for relation, targets in view["relations"].items():
                cli_module.write_text(
                    None, "    %s: %s\n" % (relation, ", ".join(targets))
                )
        if view["incoming_links"]:
            cli_module.write_text(None, "  referenced by:\n")
            for row in view["incoming_links"]:
                cli_module.write_text(
                    None,
                    "    %s <- %s %s\n"
                    % (row["relation"], row["source_id"] or "?", row["source_title"]),
                )
        return 0

    cli_module.command_ticket_new = command_ticket_new
    cli_module.command_ticket_list = command_ticket_list
    cli_module.command_ticket_show = command_ticket_show
    for name in (
        "command_ticket_edit",
        "command_ticket_assign",
        "command_ticket_close",
        "command_ticket_reopen",
        "command_ticket_link",
        "command_ticket_unlink",
    ):
        current = getattr(cli_module, name)
        _ORIGINALS[name] = current
        setattr(cli_module, name, _config_scoped_command(cli_module, current))
    cli_module.build_parser = build_parser


def _patch_capabilities():
    from . import safety_foundation, surface_runtime

    if "custom_surface_capability_document_for" in _ORIGINALS:
        return
    original_for = surface_runtime.capability_document_for
    original_base = safety_foundation.capability_document
    _ORIGINALS["custom_surface_capability_document_for"] = original_for
    _ORIGINALS["custom_base_capability_document"] = original_base

    def enrich(data, config=None):
        result = OrderedDict(data)
        result["ticket_custom_fields"] = ticket_custom_field_contract(config)
        return result

    def capability_document_for(
        surface,
        read_only=False,
        authentication="token",
        writable_targets=None,
        config=None,
    ):
        return enrich(
            original_for(
                surface,
                read_only=read_only,
                authentication=authentication,
                writable_targets=writable_targets,
                config=config,
            ),
            config=config,
        )

    def capability_document(
        read_only=False, authentication="token", writable_targets=None, config=None
    ):
        return enrich(
            original_base(
                read_only=read_only,
                authentication=authentication,
                writable_targets=writable_targets,
                config=config,
            ),
            config=config,
        )

    surface_runtime.capability_document_for = capability_document_for
    safety_foundation.capability_document = capability_document


def install_ticket_custom_fields():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_ticket_core()
    _patch_revision_validation()
    _patch_cli()
    _patch_capabilities()
    _INSTALLED = True
