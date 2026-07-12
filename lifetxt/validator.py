import re
from datetime import datetime

from .ids import id_value_is_safe
from .model import (
    DATE_KEYS,
    DATE_OR_DATETIME_KEYS,
    DATETIME_KEYS,
    Diagnostic,
    DURATION_KEYS,
    KNOWN_KEYS,
    RECOMMENDED_KEYS_BY_TYPE,
    REFERENCE_KEYS,
    SIMPLE_REPEAT_VALUES,
    STATUS_STATE_VALUES,
    TIME_OR_DATETIME_KEYS,
    VALID_STATUSES,
    VALID_TYPES,
)
from .timeutil import normalize_duration
from .timeutil import (
    is_date,
    is_datetime,
    is_time,
    parse_date_or_datetime,
    parse_datetime,
)


_KEY_STYLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RRULE_PREFIX = "RRULE:"
_SUPPORTED_RRULE_KEYS = set(("FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY"))
_SUPPORTED_RRULE_FREQS = set(("DAILY", "WEEKLY", "MONTHLY", "YEARLY"))
_SUPPORTED_RRULE_BYDAY_FREQS = set(("DAILY", "WEEKLY"))
_RRULE_WEEKDAYS = set(("MO", "TU", "WE", "TH", "FR", "SA", "SU"))
_DURATION_VALUE_RE = re.compile(r"^\d+(?:h(?:\d+m)?|m)$|^\d+$")


def validate_item(item):
    diagnostics = []

    if item.status not in VALID_STATUSES:
        diagnostics.append(
            Diagnostic(
                "error",
                "E101",
                "Invalid status %r." % item.status,
                item.line,
                1,
            )
        )

    if item.kind not in VALID_TYPES:
        diagnostics.append(
            Diagnostic(
                "error",
                "E102",
                "Invalid type %r." % item.kind,
                item.line,
            )
        )

    if item.status == "[N]" and item.kind not in ("N", "J"):
        diagnostics.append(
            Diagnostic(
                "warning",
                "W101",
                "The [N] status is recommended only with note type N or journal type J.",
                item.line,
            )
        )

    if item.kind in ("N", "J") and item.status != "[N]":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W102",
                "Note type N and journal type J are recommended to use status [N].",
                item.line,
            )
        )

    if item.status == "[x]" and "done" not in item.details and item.kind != "S":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W103",
                "Completed items should usually include done:DATE.",
                item.line,
            )
        )

    if item.status != "[x]" and "done" in item.details:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W104",
                "done: is usually used with completed status [x].",
                item.line,
            )
        )

    known_keys = set(KNOWN_KEYS)
    if item.kind in RECOMMENDED_KEYS_BY_TYPE:
        recommended = set(RECOMMENDED_KEYS_BY_TYPE[item.kind])
    else:
        recommended = set()

    for key, values in item.details.items():
        if not _KEY_STYLE_RE.match(key):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W105",
                    "Detail key %r does not follow lowercase_snake_case style." % key,
                    item.line,
                )
            )

        if (
            item.kind in RECOMMENDED_KEYS_BY_TYPE
            and key not in recommended
            and key not in known_keys
        ):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W106",
                    "Detail key %r is custom for type %s; it will be preserved."
                    % (key, item.kind),
                    item.line,
                )
            )

        for value in values:
            diagnostics.extend(_validate_value(item, key, value))

    diagnostics.extend(_validate_event_range(item))
    diagnostics.extend(_validate_status_item(item))
    diagnostics.extend(_validate_message_item(item))
    return diagnostics


def _validate_value(item, key, value):
    diagnostics = []
    if key in DATE_KEYS:
        if not is_date(value):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W201",
                    "%s: should use YYYY-MM-DD." % key,
                    item.line,
                )
            )
    elif key in DATETIME_KEYS:
        if not is_datetime(value):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W202",
                    "%s: should use YYYY-MM-DDTHH:MM, optionally with :SS, fractional seconds, and timezone." % key,
                    item.line,
                )
            )
    elif key in DATE_OR_DATETIME_KEYS:
        if not (is_date(value) or is_datetime(value)):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W203",
                    "%s: should use YYYY-MM-DD or YYYY-MM-DDTHH:MM, optionally with :SS, fractional seconds, and timezone." % key,
                    item.line,
                )
            )
    elif key in TIME_OR_DATETIME_KEYS:
        if not (is_time(value) or is_datetime(value)):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W204",
                    "%s: should use HH:MM, HH:MM:SS, fractional seconds, optional timezone, or YYYY-MM-DDTHH:MM." % key,
                    item.line,
                )
            )
    elif key == "id" or key in REFERENCE_KEYS:
        if not id_value_is_safe(value):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W214",
                    "%s: should be a compact ASCII token without spaces or quotes." % key,
                    item.line,
                )
            )
    elif key == "repeat":
        if value not in SIMPLE_REPEAT_VALUES and not value.startswith("RRULE:"):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W205",
                    "repeat: should usually be daily, weekly, monthly, yearly, weekdays, or RRULE:...",
                    item.line,
                )
            )
        elif value.startswith("RRULE:"):
            diagnostics.extend(_validate_rrule_value(item, value))
    elif key in ("interval", "count"):
        if not _is_positive_integer(value):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W219",
                    "%s: should be a positive integer." % key,
                    item.line,
                )
            )
    elif key in DURATION_KEYS:
        normalized = normalize_duration(value)
        if str(normalized) == str(value) and not _duration_like(value):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W226",
                    "%s: duration %r is not recognized; use forms like 25m, 1h30m, or 90." % (key, value),
                    item.line,
                )
            )
            return diagnostics
        if str(normalized) != str(value):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W222",
                    "%s: duration %r should be in compact form; use %r." % (key, value, normalized),
                    item.line,
                )
            )
    elif key == "state":
        if value not in STATUS_STATE_VALUES:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W207",
                    "state: should usually be one of: %s."
                    % ", ".join(STATUS_STATE_VALUES),
                    item.line,
                )
            )
    return diagnostics


def _validate_rrule_value(item, value):
    diagnostics = []
    parts = _parse_rrule_parts(value)
    freq = parts.get("FREQ")

    if not freq:
        diagnostics.append(_rrule_warning(item, "RRULE is missing FREQ."))
    elif freq not in _SUPPORTED_RRULE_FREQS:
        diagnostics.append(
            _rrule_warning(
                item,
                "RRULE FREQ=%s is stored but not expanded by the dependency-free core." % freq,
            )
        )

    unsupported = sorted(set(parts.keys()) - _SUPPORTED_RRULE_KEYS)
    if unsupported:
        diagnostics.append(
            _rrule_warning(
                item,
                "RRULE keys are stored but not expanded by the dependency-free core: %s."
                % ", ".join(unsupported),
            )
        )

    if "INTERVAL" in parts and not _is_positive_integer(parts["INTERVAL"]):
        diagnostics.append(_rrule_warning(item, "RRULE INTERVAL should be a positive integer."))

    if "COUNT" in parts and not _is_positive_integer(parts["COUNT"]):
        diagnostics.append(_rrule_warning(item, "RRULE COUNT should be a positive integer."))

    if "UNTIL" in parts and not _is_rrule_until(parts["UNTIL"]):
        diagnostics.append(
            _rrule_warning(
                item,
                "RRULE UNTIL should use life.txt datetime syntax or iCalendar basic date/datetime.",
            )
        )

    if "BYDAY" in parts:
        byday_warning = _rrule_byday_warning(freq, parts["BYDAY"])
        if byday_warning:
            diagnostics.append(_rrule_warning(item, byday_warning))

    return diagnostics


def _parse_rrule_parts(value):
    text = str(value or "")
    if text.startswith(_RRULE_PREFIX):
        text = text[len(_RRULE_PREFIX):]
    parts = {}
    for raw_part in text.split(";"):
        if "=" not in raw_part:
            continue
        key, raw_value = raw_part.split("=", 1)
        key = key.strip().upper()
        if key:
            parts[key] = raw_value.strip().upper()
    return parts


def _is_rrule_until(value):
    if parse_date_or_datetime(value, is_end=True) is not None:
        return True
    text = str(value or "").strip().upper()
    if re.match(r"^\d{8}$", text):
        fmt = "%Y%m%d"
    elif re.match(r"^\d{8}T\d{6}Z$", text):
        fmt = "%Y%m%dT%H%M%SZ"
    elif re.match(r"^\d{8}T\d{6}[+-]\d{4}$", text):
        fmt = "%Y%m%dT%H%M%S%z"
    elif re.match(r"^\d{8}T\d{6}$", text):
        fmt = "%Y%m%dT%H%M%S"
    else:
        return False
    try:
        datetime.strptime(text, fmt)
    except ValueError:
        return False
    return True


def _rrule_byday_warning(freq, value):
    if freq and freq not in _SUPPORTED_RRULE_BYDAY_FREQS:
        return "RRULE BYDAY is expanded only for FREQ=DAILY or FREQ=WEEKLY."
    for raw_part in str(value or "").split(","):
        code = raw_part.strip().upper()
        if not code:
            return "RRULE BYDAY should list weekday codes such as MO,WE,FR."
        if len(code) != 2 or code not in _RRULE_WEEKDAYS:
            return (
                "RRULE BYDAY supports only plain weekday codes such as MO,WE,FR; "
                "positional values such as 1MO are stored but not expanded."
            )
    return None


def _rrule_warning(item, message):
    return Diagnostic(
        "warning",
        "W223",
        message,
        item.line,
    )


def _validate_event_range(item):
    if item.kind != "E":
        return []
    if "from" not in item.details or "to" not in item.details:
        return []
    start = item.details["from"][0]
    end = item.details["to"][0]
    if not (is_datetime(start) and is_datetime(end)):
        return []
    if parse_datetime(end) < parse_datetime(start):
        return [
            Diagnostic(
                "warning",
                "W206",
                "Event to: datetime is earlier than from: datetime.",
                item.line,
            )
        ]
    return []


def _validate_status_item(item):
    if item.kind != "S":
        return []

    diagnostics = []
    has_from = "from" in item.details
    has_to = "to" in item.details

    if not has_from:
        diagnostics.append(
            Diagnostic(
                "error",
                "E201",
                "Status items require from:YYYY-MM-DDTHH:MM.",
                item.line,
            )
        )
    else:
        for value in item.details["from"]:
            if not is_datetime(value):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E202",
                        "Status item from: must use YYYY-MM-DDTHH:MM with optional seconds, fractional seconds, and timezone.",
                        item.line,
                    )
                )

    if "state" not in item.details:
        diagnostics.append(
            Diagnostic(
                "error",
                "E203",
                "Status items require state:VALUE.",
                item.line,
            )
        )

    if has_to:
        for value in item.details["to"]:
            if not is_datetime(value):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E204",
                        "Status item to: must use YYYY-MM-DDTHH:MM with optional seconds, fractional seconds, and timezone.",
                        item.line,
                    )
                )

    if has_to and item.status != "[x]":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W208",
                "Status items with to: are recommended to use completed status [x].",
                item.line,
            )
        )

    if not has_to and item.status != "[/]":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W209",
                "Current status items without to: are recommended to use in-progress status [/].",
                item.line,
            )
        )

    return diagnostics


def _is_positive_integer(value):
    try:
        return int(str(value)) > 0
    except (TypeError, ValueError):
        return False


def _duration_like(value):
    return bool(_DURATION_VALUE_RE.match(str(value or "").strip().lower()))


def _validate_message_item(item):
    if item.kind != "M":
        return []

    diagnostics = []
    if "sender" not in item.details:
        diagnostics.append(
            Diagnostic(
                "error",
                "E205",
                "Message items require sender:PERSON.",
                item.line,
            )
        )

    if "recipient" not in item.details:
        diagnostics.append(
            Diagnostic(
                "error",
                "E206",
                "Message items require recipient:PERSON. Repeat recipient: for multiple recipients.",
                item.line,
            )
        )

    has_notify_from = "notify_from" in item.details
    has_notify_to = "notify_to" in item.details
    if has_notify_from != has_notify_to:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W210",
                "Notification periods should usually include both notify_from: and notify_to:.",
                item.line,
            )
        )

    if has_notify_from and has_notify_to:
        start = item.details["notify_from"][0]
        end = item.details["notify_to"][0]
        parsed_start = parse_date_or_datetime(start, is_end=False)
        parsed_end = parse_date_or_datetime(end, is_end=True)
        if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W211",
                    "Message notify_to: is earlier than notify_from:.",
                    item.line,
                )
            )

    if item.status == "[N]":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W212",
                "Message type M is recommended to use workflow statuses, not [N].",
                item.line,
            )
        )

    return diagnostics
