"""Generic, configuration-backed typed custom fields for ordinary life.txt
records (#596).

``lifetxt/ticket_custom_fields.py`` (``ticketing.custom_fields``) is scoped
to ``record:ticket`` items and ticket workflow/role/privacy semantics. This
module is its smallest generic counterpart: a top-level ``custom_fields``
registry that lets a user declare typed metadata for ordinary T/E/D/R/H/N/S/
M/J records without turning life.txt's open custom-key model into a closed
schema. Both registries share one typed-value implementation
(``lifetxt/custom_field_primitives.py``); this module owns only the generic
definition shape (kinds/projects/filterable applicability -- no trackers,
roles, or privacy levels) and its own bounded ``CF0xx`` diagnostics.

``record:ticket`` items are never governed by this registry, and a generic
definition never reinterprets or overrides ``ticketing.custom_fields``.
"""

from __future__ import unicode_literals

import re
from collections import OrderedDict

from .custom_field_primitives import (
    SUPPORTED_TYPES,
    decimal_text,
    definition_boolean,
    definition_decimal,
    definition_integer,
    normalize_typed_value,
    string_list,
)
from .model import KNOWN_KEYS, VALID_TYPES, Diagnostic


_DEFINITION_KEYS = frozenset(
    (
        "type",
        "label",
        "description",
        "repeatable",
        "required",
        "enum",
        "values",
        "minimum",
        "maximum",
        "min_length",
        "max_length",
        "pattern",
        "kinds",
        "projects",
        "filterable",
    )
)
_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_W106_KEY_RE = re.compile(r"^Detail key '([^']+)' is custom for type ")
_HINT = "Fix the top-level custom_fields configuration."


def _reserved_names():
    return set(KNOWN_KEYS) | {"record"}


def _registry_diagnostic(code, message, field=None):
    row = OrderedDict(
        (
            ("severity", "error"),
            ("code", code),
            ("message", message),
            ("hint", _HINT),
        )
    )
    if field is not None:
        row["field"] = str(field)
    return row


def _bool_metadata(raw, field, key, diagnostics, default=False):
    return definition_boolean(
        raw,
        key,
        field,
        diagnostics,
        default=default,
        diag=lambda message, _fld: _registry_diagnostic(
            "CF001", "Custom field " + message, field
        ),
    )


def _decimal_metadata(raw, field, key, diagnostics):
    return definition_decimal(
        raw,
        key,
        field,
        diagnostics,
        diag=lambda message, _fld: _registry_diagnostic(
            "CF001", "Custom field " + message, field
        ),
    )


def _integer_metadata(raw, field, key, diagnostics):
    return definition_integer(
        raw,
        key,
        field,
        diagnostics,
        diag=lambda message, _fld: _registry_diagnostic(
            "CF001", "Custom field " + message, field
        ),
    )


def _kind_list(raw, field, diagnostics):
    values = string_list(raw)
    if not values:
        return None
    normalized = [str(value).strip().upper() for value in values]
    invalid = sorted(set(normalized) - set(VALID_TYPES))
    if invalid:
        diagnostics.append(
            _registry_diagnostic(
                "CF001",
                "Custom field %r has invalid kinds: %s. Use one of: %s."
                % (field, ", ".join(invalid), ", ".join(VALID_TYPES)),
                field,
            )
        )
    return [value for value in normalized if value in VALID_TYPES] or None


def custom_field_registry_report(config=None):
    """Return normalized generic custom-field definitions plus registry
    diagnostics for the top-level ``custom_fields`` configuration object."""
    raw_registry = (config or {}).get("custom_fields")
    definitions = OrderedDict()
    diagnostics = []
    if raw_registry in (None, ""):
        return OrderedDict(
            (
                ("schema", "generic-custom-field-registry-v1.schema.json"),
                ("valid", True),
                ("definitions", definitions),
                ("diagnostics", diagnostics),
            )
        )
    if not isinstance(raw_registry, dict):
        diagnostics.append(
            _registry_diagnostic(
                "CF001", "custom_fields must be an object keyed by field name."
            )
        )
        return OrderedDict(
            (
                ("schema", "generic-custom-field-registry-v1.schema.json"),
                ("valid", False),
                ("definitions", definitions),
                ("diagnostics", diagnostics),
            )
        )

    reserved = _reserved_names()
    for raw_name, raw_definition in raw_registry.items():
        name = str(raw_name).strip()
        if not _FIELD_NAME_RE.match(name):
            diagnostics.append(
                _registry_diagnostic(
                    "CF002",
                    "Invalid custom field name %r; use letters, digits, underscore, dot, or hyphen."
                    % name,
                    name,
                )
            )
        if name in reserved:
            diagnostics.append(
                _registry_diagnostic(
                    "CF003",
                    "Custom field %r conflicts with a known life.txt detail key."
                    % name,
                    name,
                )
            )
        if isinstance(raw_definition, str):
            raw_definition = {"type": raw_definition}
        if not isinstance(raw_definition, dict):
            diagnostics.append(
                _registry_diagnostic(
                    "CF001",
                    "Custom field %r definition must be an object or type string."
                    % name,
                    name,
                )
            )
            continue
        unknown = sorted(set(raw_definition) - _DEFINITION_KEYS)
        if unknown:
            diagnostics.append(
                _registry_diagnostic(
                    "CF001",
                    "Custom field %r has unknown metadata keys: %s."
                    % (name, ", ".join(unknown)),
                    name,
                )
            )

        field_type = str(raw_definition.get("type") or "string").strip().lower()
        if field_type not in SUPPORTED_TYPES:
            diagnostics.append(
                _registry_diagnostic(
                    "CF004",
                    "Custom field %r has unsupported type %r; use one of: %s."
                    % (name, field_type, ", ".join(SUPPORTED_TYPES)),
                    name,
                )
            )
            field_type = "string"

        repeatable = _bool_metadata(
            raw_definition.get("repeatable"), name, "repeatable", diagnostics
        )
        required = _bool_metadata(
            raw_definition.get("required"), name, "required", diagnostics
        )
        filterable = _bool_metadata(
            raw_definition.get("filterable"), name, "filterable", diagnostics
        )

        enum_values = raw_definition.get("enum")
        if enum_values is None:
            enum_values = raw_definition.get("values")
        enum_values = string_list(enum_values)
        if field_type == "enum" and not enum_values:
            diagnostics.append(
                _registry_diagnostic(
                    "CF001",
                    "Enum custom field %r requires a non-empty enum or values list."
                    % name,
                    name,
                )
            )

        minimum = _decimal_metadata(
            raw_definition.get("minimum"), name, "minimum", diagnostics
        )
        maximum = _decimal_metadata(
            raw_definition.get("maximum"), name, "maximum", diagnostics
        )
        if minimum is not None and maximum is not None and minimum > maximum:
            diagnostics.append(
                _registry_diagnostic(
                    "CF001",
                    "Custom field %r minimum is greater than maximum." % name,
                    name,
                )
            )
        min_length = _integer_metadata(
            raw_definition.get("min_length"), name, "min_length", diagnostics
        )
        max_length = _integer_metadata(
            raw_definition.get("max_length"), name, "max_length", diagnostics
        )
        if (
            min_length is not None
            and max_length is not None
            and min_length > max_length
        ):
            diagnostics.append(
                _registry_diagnostic(
                    "CF001",
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
                    _registry_diagnostic(
                        "CF001",
                        "Custom field %r pattern is invalid: %s." % (name, exc),
                        name,
                    )
                )

        kinds = _kind_list(raw_definition.get("kinds"), name, diagnostics)
        projects = string_list(raw_definition.get("projects")) or None

        definitions[name] = OrderedDict(
            (
                ("type", field_type),
                ("label", str(raw_definition.get("label") or name)),
                ("description", str(raw_definition.get("description") or "")),
                ("repeatable", repeatable),
                ("required", required),
                ("filterable", filterable),
                ("enum", enum_values),
                ("minimum", None if minimum is None else decimal_text(minimum)),
                ("maximum", None if maximum is None else decimal_text(maximum)),
                ("min_length", min_length),
                ("max_length", max_length),
                ("pattern", pattern),
                ("kinds", kinds),
                ("projects", projects),
            )
        )

    return OrderedDict(
        (
            ("schema", "generic-custom-field-registry-v1.schema.json"),
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


def filterable_field_names(config=None):
    """Field names declared ``filterable: true`` in the active ``custom_fields``
    registry -- the only ones the shared Query engine recognizes dynamically."""
    definitions = custom_field_definitions(config)
    return frozenset(
        name for name, definition in definitions.items() if definition["filterable"]
    )


def _record_marker(item):
    values = getattr(item, "details", {}).get("record") or []
    return str(values[0]).lower() if values else None


def field_applies(definition, item):
    """Whether a normalized generic field definition applies to ``item``.

    ``record:ticket`` items are always excluded: those remain governed by
    ``ticketing.custom_fields`` only.
    """
    if _record_marker(item) == "ticket":
        return False
    kinds = definition.get("kinds")
    if kinds and item.kind not in kinds:
        return False
    projects = definition.get("projects")
    if projects:
        item_projects = {str(value) for value in item.details.get("project", [])}
        if not item_projects & set(projects):
            return False
    return True


def _w106_key(diagnostic):
    match = _W106_KEY_RE.match(str(getattr(diagnostic, "message", "")))
    return match.group(1) if match else None


def generic_custom_field_diagnostics(items, diagnostics, config=None):
    """Return ``diagnostics`` with the generic registry integrated.

    A declared, applicable field's own W106 "custom key" warning is removed
    (the field is recognized, not merely preserved); enum/range/length/
    pattern/repeatable/required violations are appended as new ``CF0xx``
    diagnostics; registry-definition errors (invalid metadata) are appended
    once. An undeclared key, or a declared field used outside its own
    ``kinds``/``projects`` applicability, is left completely untouched.
    """
    report = custom_field_registry_report(config)
    definitions = report["definitions"]

    result = list(diagnostics)
    for row in report["diagnostics"]:
        result.append(
            Diagnostic("error", row["code"], row["message"], hint=row["hint"])
        )
    if not definitions:
        return result

    applicable_keys_by_line = {}
    appended = []
    for item in items:
        applicable = OrderedDict(
            (name, definition)
            for name, definition in definitions.items()
            if field_applies(definition, item)
        )
        if not applicable:
            continue
        applicable_keys_by_line[item.line] = set(applicable)
        source = getattr(item, "source", None)
        for name, definition in applicable.items():
            values = item.details.get(name, [])
            if not values:
                if definition["required"]:
                    appended.append(
                        Diagnostic(
                            "error",
                            "CF008",
                            "Item is missing required custom field %r." % name,
                            item.line,
                            source=source,
                            hint=_HINT,
                        )
                    )
                continue
            if not definition["repeatable"] and len(values) > 1:
                appended.append(
                    Diagnostic(
                        "error",
                        "CF007",
                        "Custom field %r is not repeatable but has %d values."
                        % (name, len(values)),
                        item.line,
                        source=source,
                        hint=_HINT,
                    )
                )
            for value in values:
                try:
                    normalize_typed_value(value, definition)
                except ValueError as exc:
                    appended.append(
                        Diagnostic(
                            "error",
                            "CF006",
                            "Custom field %r value %r %s." % (name, value, exc),
                            item.line,
                            source=source,
                            hint=_HINT,
                        )
                    )

    filtered = []
    for diagnostic in result:
        code = str(getattr(diagnostic, "code", "")).upper()
        if code == "W106":
            key = _w106_key(diagnostic)
            line = getattr(diagnostic, "line", None)
            if key is not None and key in applicable_keys_by_line.get(line, ()):
                continue
        filtered.append(diagnostic)

    return filtered + appended
