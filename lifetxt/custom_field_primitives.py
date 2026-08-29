"""Protocol-neutral typed-value primitives shared by every custom-field
registry (#596).

`lifetxt/ticket_custom_fields.py` (``ticketing.custom_fields``) and
`lifetxt/custom_fields.py` (the generic ``custom_fields`` registry for
ordinary records) both declare fields with a ``type`` plus bounded
constraint metadata (enum/minimum/maximum/length/pattern) and need to parse
a raw string value against that definition. This module is the single
authoritative implementation of that parsing and constraint evaluation, so
equivalent primitive inputs cannot drift between the two registries.
Ticket-specific concerns -- trackers, roles, privacy levels, ticket
diagnostic codes, ticket workflow behavior -- stay in the ticket layer and
have no presence here.
"""

from __future__ import unicode_literals

from decimal import Decimal, InvalidOperation

from .timeutil import parse_iso_date, parse_iso_datetime


#: Every primitive type either registry may declare for a field.
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


def string_list(value):
    """Normalize a raw config value (None/scalar/list) to a deduplicated,
    order-preserving list of non-empty strings."""
    if value in (None, ""):
        return []
    source = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
    result = []
    for entry in source:
        text = str(entry).strip()
        if text and text not in result:
            result.append(text)
    return result


def definition_boolean(raw, key, field, diagnostics, default=False, diag=None):
    """Coerce one boolean definition field, appending a diagnostic on a
    non-boolean value. ``diag`` builds the diagnostic row for the caller's
    own diagnostic shape (ticket TK006 vs. generic CF-series codes)."""
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    if diag is not None:
        diagnostics.append(
            diag("%r metadata %s must be a boolean." % (field, key), field)
        )
    return bool(default)


def definition_integer(raw, key, field, diagnostics, diag=None):
    if raw is None:
        return None
    if isinstance(raw, bool):
        if diag is not None:
            diagnostics.append(
                diag("%r metadata %s must be an integer." % (field, key), field)
            )
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        if diag is not None:
            diagnostics.append(
                diag("%r metadata %s must be an integer." % (field, key), field)
            )
        return None
    if value < 0:
        if diag is not None:
            diagnostics.append(
                diag("%r metadata %s must be zero or greater." % (field, key), field)
            )
        return None
    return value


def definition_decimal(raw, key, field, diagnostics, diag=None):
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        if diag is not None:
            diagnostics.append(
                diag("%r metadata %s must be a number." % (field, key), field)
            )
        return None


def decimal_text(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_boolean(value):
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return "true", Decimal(1)
    if text in ("0", "false", "no", "off"):
        return "false", Decimal(0)
    raise ValueError("must be true/false, yes/no, on/off, or 1/0")


def normalize_typed_value(value, definition):
    """Parse and validate one raw string value against a field definition.

    ``definition`` is a plain dict/mapping with at least ``type`` and,
    where applicable, ``enum``/``minimum``/``maximum``/``min_length``/
    ``max_length``/``pattern``. Returns the normalized (canonical string)
    value, or raises ``ValueError`` describing the violation -- the same
    contract every caller (ticket and generic) already relies on.
    """
    import re

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
        normalized = decimal_text(number)
        comparable = number
    elif field_type == "boolean":
        normalized, comparable = normalize_boolean(text)
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
