"""Shorthand notations shared by the CLI, TUI, Web UI, and MCP.

Two kinds of shorthand live here, both deliberately small and explicit:

* Capture sigils. ``Buy milk @home #errand !high ^tomorrow`` expands into
  ``project:home tag:errand priority:high due:2026-07-20`` so a capture does not
  need one flag per field.
* Relative date tokens. ``today``, ``tomorrow``, weekday names, ``next_week``,
  and ``+3d`` / ``-1w`` offsets resolve to ISO dates.

Both are closed sets. Anything unrecognized is left alone rather than guessed
at, so a title that merely contains an ``@`` keeps it and an unknown date token
fails loudly at the caller instead of silently writing an unparseable value.
"""

import datetime
import re


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# Sigil -> detail key. Kept tiny on purpose; every addition is a character a
# title can no longer start a word with.
SIGILS = (
    ("@", "project"),
    ("#", "tag"),
    ("!", "priority"),
    ("^", "due"),
)

SIGIL_CHARS = "".join(sigil for sigil, _key in SIGILS)

# A sigil token is a whole whitespace-delimited word: one sigil character plus
# a value. This is what keeps "mail me at a@b.com" and "10 ^ 2" intact.
_SIGIL_TOKEN = re.compile(r"^([%s])([^\s]+)$" % re.escape(SIGIL_CHARS))

_OFFSET = re.compile(r"^([+-])(\d+)([dwmy]?)$", re.IGNORECASE)


class ShorthandError(ValueError):
    """Raised when a shorthand token is recognized but cannot be resolved."""


def resolve_date_token(value, today=None, strict=False):
    """Resolve a relative date token to an ISO date string.

    Recognizes ``today``, ``tomorrow``, ``yesterday``, weekday names (the next
    occurrence), ``next_WEEKDAY`` (always next week), ``next_week``, and signed
    offsets such as ``+3d``, ``-1w``, ``+2m``, ``+1y``.

    Unrecognized values are returned unchanged so existing ISO dates pass
    through. With ``strict=True`` an unrecognized value raises instead, which
    callers use when the value must be a real date.
    """
    if today is None:
        today = datetime.date.today()
    raw = str(value if value is not None else "").strip()
    text = raw.lower()
    if not text:
        if strict:
            raise ShorthandError("Empty date value.")
        return raw

    if text == "today":
        return today.isoformat()
    if text == "tomorrow":
        return (today + datetime.timedelta(days=1)).isoformat()
    if text == "yesterday":
        return (today - datetime.timedelta(days=1)).isoformat()
    if text == "next_week":
        return (today + datetime.timedelta(days=(7 - today.weekday()) % 7 or 7)).isoformat()

    if text in WEEKDAYS:
        return (today + datetime.timedelta(days=_days_ahead(today, WEEKDAYS[text]))).isoformat()
    if text.startswith("next_") and text[5:] in WEEKDAYS:
        return (today + datetime.timedelta(days=_days_ahead(today, WEEKDAYS[text[5:]]) + 7)).isoformat()

    match = _OFFSET.match(text)
    if match:
        sign, amount, unit = match.group(1), int(match.group(2)), (match.group(3) or "d").lower()
        if sign == "-":
            amount = -amount
        return _shift(today, amount, unit).isoformat()

    if strict and not _looks_like_date(raw):
        raise ShorthandError(
            "%r is not a date. Use YYYY-MM-DD, today, tomorrow, yesterday, a weekday, "
            "next_week, or an offset such as +3d, -1w, +2m." % raw
        )
    return raw


def _days_ahead(today, target_weekday):
    days = target_weekday - today.weekday()
    return days + 7 if days <= 0 else days


def _shift(today, amount, unit):
    if unit == "d":
        return today + datetime.timedelta(days=amount)
    if unit == "w":
        return today + datetime.timedelta(weeks=amount)
    if unit == "y":
        return _add_months(today, amount * 12)
    return _add_months(today, amount)


def _add_months(date, months):
    total = date.month - 1 + months
    year = date.year + total // 12
    month = total % 12 + 1
    # Clamp so that adding a month to the 31st lands on the last valid day.
    day = min(date.day, _days_in_month(year, month))
    return datetime.date(year, month, day)


def _days_in_month(year, month):
    if month == 12:
        return 31
    return (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day


def _looks_like_date(value):
    from .timeutil import parse_date_or_datetime

    try:
        return parse_date_or_datetime(value) is not None
    except Exception:
        return False


def parse_capture(text, today=None, strict_dates=True):
    """Split capture sigils out of a title.

    Returns ``(title, details)`` where details maps a detail key to a list of
    values, matching the shape used by :class:`lifetxt.model.Item`.

    Only whole whitespace-delimited words are treated as sigils, and a token
    can be escaped with a backslash to keep it in the title.
    """
    details = {}
    kept = []
    for token in str(text or "").split(" "):
        if not token:
            kept.append(token)
            continue
        if token.startswith("\\") and len(token) > 1 and token[1] in SIGIL_CHARS:
            kept.append(token[1:])
            continue
        match = _SIGIL_TOKEN.match(token)
        if not match:
            kept.append(token)
            continue
        sigil, value = match.group(1), match.group(2)
        key = dict(SIGILS)[sigil]
        if key == "due":
            value = resolve_date_token(value, today=today, strict=strict_dates)
        details.setdefault(key, []).append(value)

    title = " ".join(part for part in kept if part != "").strip()
    return title, details


def describe_sigils():
    """Human-readable reference used by help output and docs."""
    return (
        ("@NAME", "project:NAME"),
        ("#NAME", "tag:NAME"),
        ("!VALUE", "priority:VALUE"),
        ("^DATE", "due:DATE (accepts relative tokens)"),
    )


def describe_date_tokens():
    return (
        ("today / tomorrow / yesterday", "the obvious calendar day"),
        ("monday .. sunday", "the next occurrence of that weekday"),
        ("next_monday .. next_sunday", "that weekday next week"),
        ("next_week", "the coming Monday"),
        ("+3d / -1w / +2m / +1y", "signed offsets in days, weeks, months, years"),
    )
