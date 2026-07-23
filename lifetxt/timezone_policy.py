"""Shared timezone interpretation and boundary helpers.

The legacy parser preserves authored offsets but historically compares aware values
in the host timezone.  This module supplies an explicit policy context so CLI, Web,
MCP, timer, notification, and completion code can use the documented precedence
without changing the authored representation.
"""

from __future__ import unicode_literals

import contextlib
import contextvars
import datetime
import re

from .safety_foundation import resolve_timezone_policy
from .timeutil import parse_date, parse_datetime


UTC = datetime.timezone.utc
_TIME_RE = re.compile(
    r"^(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:?\d{2})?$"
)
_TIMEZONE_CONTEXT = contextvars.ContextVar("lifetxt_timezone", default=None)
_CLOCK_CONTEXT = contextvars.ContextVar("lifetxt_clock", default=None)


class TimezonePolicyError(ValueError):
    """Raised when an authored value cannot be interpreted under the policy."""


@contextlib.contextmanager
def timezone_context(name):
    """Temporarily make ``name`` the comparison/display timezone."""
    token = _TIMEZONE_CONTEXT.set(name)
    try:
        yield name
    finally:
        _TIMEZONE_CONTEXT.reset(token)


@contextlib.contextmanager
def clock_context(value):
    """Temporarily provide a deterministic clock value or zero-argument callable."""
    token = _CLOCK_CONTEXT.set(value)
    try:
        yield value
    finally:
        _CLOCK_CONTEXT.reset(token)


def current_timezone_name(default="local"):
    return _TIMEZONE_CONTEXT.get() or default


def resolve_timezone_name(config=None, text="", cli_timezone=None):
    report = resolve_timezone_policy(config or {}, text=text, cli_timezone=cli_timezone)
    if not report.get("valid"):
        raise TimezonePolicyError(
            "Invalid timezone %r from %s: %s"
            % (report.get("timezone"), report.get("source"), report.get("error"))
        )
    return report["timezone"]


def timezone_info(name=None):
    """Return a tzinfo for an IANA name or the host-local timezone."""
    value = str(name or current_timezone_name()).strip()
    if value.lower() in ("local", "host"):
        return datetime.datetime.now().astimezone().tzinfo
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(value)
    except Exception as exc:
        raise TimezonePolicyError("Invalid timezone %r: %s" % (value, exc))


def classify_wall_time(value, timezone_name=None):
    """Classify a naive wall datetime as valid, ambiguous, or nonexistent."""
    if not isinstance(value, datetime.datetime):
        raise TypeError("classify_wall_time expects datetime.")
    naive = value.replace(tzinfo=None)
    zone = timezone_info(timezone_name)
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)
    first_valid = _roundtrip_wall(first, zone) == naive
    second_valid = _roundtrip_wall(second, zone) == naive
    if not first_valid and not second_valid:
        state = "nonexistent"
    elif first_valid and second_valid and first.utcoffset() != second.utcoffset():
        state = "ambiguous"
    else:
        state = "valid"
    return {
        "state": state,
        "timezone": str(timezone_name or current_timezone_name()),
        "fold0_offset": _offset_text(first.utcoffset()),
        "fold1_offset": _offset_text(second.utcoffset()),
        "fold0_valid": first_valid,
        "fold1_valid": second_valid,
    }


def localize_datetime(value, timezone_name=None, fold_policy="error", gap_policy="error"):
    """Attach policy timezone to a naive datetime with explicit DST behavior.

    ``fold_policy`` is ``error``, ``earlier`` or ``later``. ``gap_policy`` is
    ``error``, ``next`` or ``previous``. Gap adjustment is bounded to three hours.
    """
    if not isinstance(value, datetime.datetime):
        raise TypeError("localize_datetime expects datetime.")
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(timezone_info(timezone_name))
    naive = value.replace(tzinfo=None)
    zone = timezone_info(timezone_name)
    classification = classify_wall_time(naive, timezone_name)
    state = classification["state"]
    if state == "valid":
        candidate = naive.replace(tzinfo=zone, fold=0)
        if not classification["fold0_valid"]:
            candidate = naive.replace(tzinfo=zone, fold=1)
        return candidate
    if state == "ambiguous":
        if fold_policy == "error":
            raise TimezonePolicyError(
                "Ambiguous local datetime %s in %s; choose fold_policy=earlier or later."
                % (naive.isoformat(), timezone_name or current_timezone_name())
            )
        if fold_policy not in ("earlier", "later"):
            raise TimezonePolicyError("Unknown fold_policy: %s" % fold_policy)
        fold = 0 if fold_policy == "earlier" else 1
        return naive.replace(tzinfo=zone, fold=fold)
    if gap_policy == "error":
        raise TimezonePolicyError(
            "Nonexistent local datetime %s in %s; choose gap_policy=next or previous."
            % (naive.isoformat(), timezone_name or current_timezone_name())
        )
    if gap_policy not in ("next", "previous"):
        raise TimezonePolicyError("Unknown gap_policy: %s" % gap_policy)
    direction = 1 if gap_policy == "next" else -1
    probe = naive
    for _minute in range(180):
        probe += datetime.timedelta(minutes=direction)
        report = classify_wall_time(probe, timezone_name)
        if report["state"] != "nonexistent":
            fold = "earlier" if fold_policy == "error" else fold_policy
            return localize_datetime(
                probe,
                timezone_name=timezone_name,
                fold_policy=fold,
                gap_policy="error",
            )
    raise TimezonePolicyError("Could not resolve timezone gap within three hours.")


def interpret_datetime(value, timezone_name=None, fold_policy="error", gap_policy="error"):
    """Parse/interpret a datetime, preserving explicit offsets and localizing naive values."""
    parsed = value
    if isinstance(value, str):
        parsed = parse_datetime(value)
    if not isinstance(parsed, datetime.datetime):
        raise TimezonePolicyError("Invalid datetime value: %r" % value)
    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        return parsed.astimezone(timezone_info(timezone_name))
    return localize_datetime(parsed, timezone_name, fold_policy, gap_policy)


def convert_datetime(value, timezone_name=None, source_timezone=None, fold_policy="error", gap_policy="error"):
    """Convert ``value`` from its offset/source timezone into ``timezone_name``."""
    parsed = value if isinstance(value, datetime.datetime) else parse_datetime(value)
    if not isinstance(parsed, datetime.datetime):
        raise TimezonePolicyError("Invalid datetime value: %r" % value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = localize_datetime(parsed, source_timezone or timezone_name, fold_policy, gap_policy)
    return parsed.astimezone(timezone_info(timezone_name))


def interpret_time(value, anchor_date=None, timezone_name=None, fold_policy="error", gap_policy="error"):
    """Interpret a time-only value on ``anchor_date`` without discarding offsets."""
    if isinstance(anchor_date, str):
        anchor_date = parse_date(anchor_date)
    anchor_date = anchor_date or today(timezone_name)
    if not isinstance(anchor_date, datetime.date):
        raise TimezonePolicyError("Invalid anchor date: %r" % anchor_date)
    if isinstance(value, datetime.time):
        parsed_time = value
    else:
        match = _TIME_RE.match(str(value or ""))
        if not match:
            raise TimezonePolicyError("Invalid time value: %r" % value)
        hour, minute, second, fraction, offset = match.groups()
        microsecond = int((fraction or "0").ljust(6, "0"))
        tz = _offset_timezone(offset)
        parsed_time = datetime.time(
            int(hour), int(minute), int(second or 0), microsecond, tzinfo=tz
        )
    combined = datetime.datetime.combine(anchor_date, parsed_time)
    if parsed_time.tzinfo is not None:
        return combined.astimezone(timezone_info(timezone_name))
    return localize_datetime(combined, timezone_name, fold_policy, gap_policy)


def date_boundaries(value, timezone_name=None):
    """Return timezone-aware inclusive day boundaries for a date."""
    parsed = parse_date(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime.date):
        raise TimezonePolicyError("Invalid date value: %r" % value)
    start = localize_datetime(datetime.datetime.combine(parsed, datetime.time.min), timezone_name)
    end = localize_datetime(
        datetime.datetime.combine(parsed, datetime.time(23, 59, 59, 999999)),
        timezone_name,
    )
    return start, end


def comparison_datetime(value, timezone_name=None):
    """Return configured-zone wall time for legacy naive comparisons."""
    if not isinstance(value, datetime.datetime):
        raise TypeError("comparison_datetime expects datetime.")
    if value.tzinfo is not None and value.utcoffset() is not None:
        local = value.astimezone(timezone_info(timezone_name))
    else:
        local = value
    return datetime.datetime(
        local.year,
        local.month,
        local.day,
        local.hour,
        local.minute,
        local.second,
        local.microsecond,
        fold=getattr(local, "fold", 0),
    )


def now(timezone_name=None):
    source = _CLOCK_CONTEXT.get()
    if source is None:
        return datetime.datetime.now(timezone_info(timezone_name))
    value = source() if callable(source) else source
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        value = datetime.datetime.combine(value, datetime.time.min)
    if not isinstance(value, datetime.datetime):
        raise TypeError("clock_context expects a date, datetime, or callable returning one.")
    zone = timezone_info(timezone_name)
    if value.tzinfo is None or value.utcoffset() is None:
        return localize_datetime(value, timezone_name, fold_policy="earlier", gap_policy="next")
    return value.astimezone(zone)


def today(timezone_name=None):
    return now(timezone_name).date()


def utcnow():
    return now("UTC")


def local_now_naive(timezone_name=None):
    return now(timezone_name).replace(tzinfo=None)


def policy_report(config=None, text="", cli_timezone=None, sample=None, fold_policy="error", gap_policy="error"):
    base = resolve_timezone_policy(config or {}, text=text, cli_timezone=cli_timezone)
    result = dict(base)
    result.update(
        {
            "fold_policy": fold_policy,
            "gap_policy": gap_policy,
            "naive_values": "interpreted as wall time in the resolved timezone",
            "aware_values": "converted to the resolved timezone for comparison/display",
            "time_only_values": "anchored to an explicit date before conversion",
        }
    )
    if sample:
        try:
            interpreted = interpret_datetime(sample, base["timezone"], fold_policy, gap_policy)
            result["sample"] = {
                "input": sample,
                "output": interpreted.isoformat(),
                "classification": classify_wall_time(
                    interpreted.replace(tzinfo=None), base["timezone"]
                )["state"],
            }
        except Exception as exc:
            result["sample"] = {"input": sample, "error": str(exc)}
    return result


def _roundtrip_wall(value, zone):
    converted = value.astimezone(UTC).astimezone(zone)
    return converted.replace(tzinfo=None)


def _offset_text(value):
    if value is None:
        return None
    seconds = int(value.total_seconds())
    sign = "+" if seconds >= 0 else "-"
    seconds = abs(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return "%s%02d:%02d" % (sign, hours, minutes)


def _offset_timezone(value):
    if not value:
        return None
    if value == "Z":
        return UTC
    compact = value.replace(":", "")
    sign = 1 if compact[0] == "+" else -1
    hours = int(compact[1:3])
    minutes = int(compact[3:5])
    return datetime.timezone(sign * datetime.timedelta(hours=hours, minutes=minutes))
