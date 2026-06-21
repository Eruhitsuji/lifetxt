import re

from .ids import id_value_is_safe
from .model import (
    DATE_KEYS,
    DATE_OR_DATETIME_KEYS,
    DATETIME_KEYS,
    Diagnostic,
    KNOWN_KEYS,
    RECOMMENDED_KEYS_BY_TYPE,
    SIMPLE_REPEAT_VALUES,
    STATUS_STATE_VALUES,
    TIME_OR_DATETIME_KEYS,
    VALID_STATUSES,
    VALID_TYPES,
)
from .timeutil import (
    is_date,
    is_datetime,
    is_time,
    parse_date_or_datetime,
    parse_datetime,
)


_KEY_STYLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


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

    if item.status == "[N]" and item.kind != "N":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W101",
                "The [N] status is recommended only with note type N.",
                item.line,
            )
        )

    if item.kind == "N" and item.status != "[N]":
        diagnostics.append(
            Diagnostic(
                "warning",
                "W102",
                "Note type N is recommended to use status [N].",
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
                    "%s: should use YYYY-MM-DDTHH:MM, optionally with :SS and timezone." % key,
                    item.line,
                )
            )
    elif key in DATE_OR_DATETIME_KEYS:
        if not (is_date(value) or is_datetime(value)):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W203",
                    "%s: should use YYYY-MM-DD or YYYY-MM-DDTHH:MM, optionally with :SS and timezone." % key,
                    item.line,
                )
            )
    elif key in TIME_OR_DATETIME_KEYS:
        if not (is_time(value) or is_datetime(value)):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W204",
                    "%s: should use HH:MM, HH:MM:SS, or YYYY-MM-DDTHH:MM with optional seconds/timezone." % key,
                    item.line,
                )
            )
    elif key in ("id", "parent"):
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
                    "repeat: should usually be daily, weekly, monthly, yearly, or RRULE:...",
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
                        "Status item from: must use YYYY-MM-DDTHH:MM with optional seconds/timezone.",
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
                        "Status item to: must use YYYY-MM-DDTHH:MM with optional seconds/timezone.",
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
