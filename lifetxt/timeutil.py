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


def parse_datetime(value):
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
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
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
        return datetime.combine(parsed_date, time(23, 59, 59))
    return datetime.combine(parsed_date, time(0, 0, 0))


def format_datetime(value):
    if getattr(value, "microsecond", 0):
        text = value.strftime(DATETIME_FRACTION_FORMAT)
        return text.rstrip("0").rstrip(".")
    if getattr(value, "second", 0):
        return value.strftime(DATETIME_SECONDS_FORMAT)
    return value.strftime(DATETIME_FORMAT)


def _normalize_timezone(value):
    text = value
    if text.endswith("Z"):
        return text[:-1] + "+0000"
    if len(text) >= 6 and text[-6] in ("+", "-") and text[-3] == ":":
        return text[:-3] + text[-2:]
    return text
