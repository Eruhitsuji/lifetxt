import re
from datetime import datetime, time


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
DATETIME_SECONDS_FORMAT = "%Y-%m-%dT%H:%M:%S"
DATETIME_FRACTION_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
TIME_FORMAT = "%H:%M"
TIME_SECONDS_FORMAT = "%H:%M:%S"
TIME_FRACTION_FORMAT = "%H:%M:%S.%f"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:?\d{2})?$"
)
TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:?\d{2})?$")


class LifeDateTime(datetime):
    """Datetime that keeps authored offsets without breaking legacy comparisons.

    lifetxt historically converted offset-aware values to the host's local time
    and removed ``tzinfo`` during parsing.  That made ordering work with naive
    values, but destroyed the original offset before callers could serialize or
    inspect it.  ``LifeDateTime`` preserves ``tzinfo`` and applies the old local
    naive normalization only when an ordering comparison or datetime subtraction
    mixes aware and naive values.

    Equality intentionally retains Python's normal datetime semantics: an aware
    value is not equal to a naive value merely because their local wall-clock
    representations happen to match.
    """

    def _comparison_value(self):
        return comparison_datetime(self)

    def __lt__(self, other):
        if isinstance(other, datetime):
            return self._comparison_value() < comparison_datetime(other)
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, datetime):
            return self._comparison_value() <= comparison_datetime(other)
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, datetime):
            return self._comparison_value() > comparison_datetime(other)
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, datetime):
            return self._comparison_value() >= comparison_datetime(other)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, datetime):
            return self._comparison_value() - comparison_datetime(other)
        result = datetime.__sub__(self, other)
        if isinstance(result, datetime) and not isinstance(result, LifeDateTime):
            return _life_datetime(result)
        return result

    def __rsub__(self, other):
        if isinstance(other, datetime):
            return comparison_datetime(other) - self._comparison_value()
        return NotImplemented


def is_date(value):
    return parse_date(value) is not None


def is_datetime(value):
    return parse_datetime(value) is not None


def is_time(value):
    return parse_time(value) is not None


def parse_date(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        return None


def parse_iso_date(value):
    """Parse the ISO date subset supported by life.txt on Python 3.10+."""
    if not isinstance(value, str):
        return None
    return parse_date(value.strip())


def parse_datetime(value):
    """Parse a life.txt datetime without discarding an explicit UTC offset."""
    if not isinstance(value, str) or not DATETIME_RE.match(value):
        return None
    text = _normalize_timezone(value)
    formats = (
        DATETIME_FORMAT,
        DATETIME_SECONDS_FORMAT,
        DATETIME_FRACTION_FORMAT,
        DATETIME_FORMAT + "%z",
        DATETIME_SECONDS_FORMAT + "%z",
        DATETIME_FRACTION_FORMAT + "%z",
    )
    for fmt in formats:
        try:
            return LifeDateTime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_iso_datetime(value):
    """Parse the ISO datetime subset supported by life.txt on Python 3.10+."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    parsed = parse_datetime(text)
    if parsed is None and " " in text and "T" not in text:
        parsed = parse_datetime(text.replace(" ", "T", 1))
    if parsed is not None:
        return parsed
    parsed_date = parse_iso_date(text)
    if parsed_date is not None:
        return datetime.combine(parsed_date, time(0, 0, 0))
    return None


def parse_time(value):
    if not isinstance(value, str) or not TIME_RE.match(value):
        return None
    text = _normalize_timezone(value)
    formats = (
        TIME_FORMAT,
        TIME_SECONDS_FORMAT,
        TIME_FRACTION_FORMAT,
        TIME_FORMAT + "%z",
        TIME_SECONDS_FORMAT + "%z",
        TIME_FRACTION_FORMAT + "%z",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            anchored = datetime.combine(datetime.now().date(), parsed.timetz())
            return anchored.astimezone().time().replace(tzinfo=None)
        return parsed.time()
    return None


def parse_date_or_datetime(value, is_end=False):
    parsed = parse_datetime(value)
    if parsed is not None:
        return parsed
    parsed_date = parse_date(value)
    if parsed_date is None:
        return None
    if is_end:
        return LifeDateTime.combine(parsed_date, time(23, 59, 59))
    return LifeDateTime.combine(parsed_date, time(0, 0, 0))


def comparison_datetime(value):
    """Return a naive datetime suitable for legacy ordering and subtraction.

    Aware values are converted to the host's local timezone and then stripped of
    ``tzinfo``.  Naive values are copied unchanged.  This is deliberately a
    comparison-only representation; callers that display or serialize a value
    must keep the original aware datetime.
    """
    if not isinstance(value, datetime):
        raise TypeError("comparison_datetime expects a datetime value.")
    if _is_aware(value):
        local = value.astimezone()
        return datetime(
            local.year,
            local.month,
            local.day,
            local.hour,
            local.minute,
            local.second,
            local.microsecond,
            fold=getattr(local, "fold", 0),
        )
    return datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        fold=getattr(value, "fold", 0),
    )


def format_datetime(value):
    """Format a datetime while retaining seconds, fractions, and UTC offset."""
    if not isinstance(value, datetime):
        raise TypeError("format_datetime expects a datetime value.")
    if getattr(value, "microsecond", 0):
        text = value.strftime(DATETIME_FRACTION_FORMAT).rstrip("0").rstrip(".")
    elif getattr(value, "second", 0):
        text = value.strftime(DATETIME_SECONDS_FORMAT)
    else:
        text = value.strftime(DATETIME_FORMAT)
    return text + _format_timezone_offset(value)


def _life_datetime(value):
    if isinstance(value, LifeDateTime):
        return value
    return LifeDateTime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=value.tzinfo,
        fold=getattr(value, "fold", 0),
    )


def _is_aware(value):
    return value.tzinfo is not None and value.utcoffset() is not None


def _format_timezone_offset(value):
    if not _is_aware(value):
        return ""
    total_seconds = int(value.utcoffset().total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return "%s%02d:%02d" % (sign, hours, minutes)


def _normalize_timezone(value):
    text = value
    if text.endswith("Z"):
        return text[:-1] + "+0000"
    if len(text) >= 6 and text[-6] in ("+", "-") and text[-3] == ":":
        return text[:-3] + text[-2:]
    return text


_DURATION_VALUE_RE = re.compile(r"^\d+(?:h(?:\d+m)?|m)$|^\d+$")


def parse_elapsed(value):
    text = str(value or "").strip().lower()
    if not text:
        return 0
    if not _DURATION_VALUE_RE.match(text):
        raise ValueError(
            "Invalid elapsed duration %r. Use forms like 25m, 1h30m, or 90." % value
        )
    total = 0
    number = ""
    saw_unit = False
    for char in text:
        if char.isdigit():
            number += char
            continue
        if char == "h":
            total += int(number or "0") * 60
            number = ""
            saw_unit = True
            continue
        if char == "m":
            total += int(number or "0")
            number = ""
            saw_unit = True
            continue
        raise ValueError(
            "Invalid elapsed duration %r. Use forms like 25m, 1h30m, or 90." % value
        )
    if number and not saw_unit:
        total += int(number)
    return total


def format_elapsed(minutes):
    minutes = int(minutes or 0)
    hours = minutes // 60
    rest = minutes % 60
    if hours and rest:
        return "%dh%02dm" % (hours, rest)
    if hours:
        return "%dh" % hours
    return "%dm" % rest


def normalize_duration(value):
    """Return canonical compact form (e.g. 90m -> 1h30m, 60m -> 1h) or value unchanged if not parseable."""
    text = str(value or "").strip().lower()
    if not _DURATION_VALUE_RE.match(text):
        return value
    minutes = parse_elapsed(text)
    return format_elapsed(minutes)
