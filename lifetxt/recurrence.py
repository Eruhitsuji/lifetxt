"""Expanding recurrence rules into concrete occurrences.

`repeat:` accepts either a short name (`daily`, `weekly`, `monthly`, `yearly`)
or an iCalendar rule (`RRULE:FREQ=WEEKLY;BYDAY=MO,WE;INTERVAL=2`). Agenda
expansion, `complete` materialization, and the `rrule` command all need the
same answer for "when does this happen next", so the generator lives here.

The supported subset is deliberately closed and dependency-free:

* `FREQ` — DAILY, WEEKLY, MONTHLY, YEARLY
* `INTERVAL`, `COUNT`, `UNTIL`
* `BYDAY` — plain (`MO,WE`) and positional (`1MO`, `-1FR`)
* `BYMONTHDAY` — including negative offsets from the end of the month
* `BYMONTH`

Anything outside that subset is reported rather than silently ignored, because
a rule that is quietly dropped produces a schedule the user never asked for.
"""

import calendar
from collections import OrderedDict
from datetime import date, datetime, time, timedelta


RRULE_PREFIX = "RRULE:"

FREQ_NAMES = OrderedDict(
    [("DAILY", "daily"), ("WEEKLY", "weekly"), ("MONTHLY", "monthly"), ("YEARLY", "yearly")]
)
NAME_TO_FREQ = OrderedDict((value, key) for key, value in FREQ_NAMES.items())

WEEKDAY_CODES = OrderedDict(
    [("MO", 0), ("TU", 1), ("WE", 2), ("TH", 3), ("FR", 4), ("SA", 5), ("SU", 6)]
)
WEEKDAY_NAMES = dict((value, key) for key, value in WEEKDAY_CODES.items())

#: Parts we understand. Anything else is reported by `unsupported_parts`.
SUPPORTED_PARTS = ("FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY", "BYMONTH", "WKST")

#: Hard ceiling so a rule with no COUNT or UNTIL cannot spin forever.
DEFAULT_MAX_OCCURRENCES = 500
SAFETY_ITERATIONS = 100000


class RecurrenceError(ValueError):
    """Raised when a rule cannot be parsed or expanded."""


def parse_rule(value, interval=None, count=None, until=None):
    """Parse a repeat value into a normalized rule dictionary.

    ``interval``/``count``/``until`` are the item's sibling details, used when
    the rule itself does not carry them.
    """
    text = str(value or "").strip()
    if not text:
        raise RecurrenceError("Empty repeat value.")

    if not text.upper().startswith(RRULE_PREFIX):
        name = text.lower()
        if name not in NAME_TO_FREQ:
            raise RecurrenceError(
                "Unknown repeat %r. Use daily, weekly, monthly, yearly, or an RRULE." % text
            )
        return _rule(
            label=text,
            freq=NAME_TO_FREQ[name],
            interval=interval or 1,
            count=count,
            until=until,
        )

    parts = parse_rrule_parts(text)
    freq = str(parts.get("FREQ", "")).upper()
    if freq not in FREQ_NAMES:
        raise RecurrenceError(
            "RRULE needs FREQ=DAILY, WEEKLY, MONTHLY, or YEARLY; got %r." % (parts.get("FREQ") or "")
        )

    rule = _rule(
        label=text,
        freq=freq,
        interval=_positive_int(parts.get("INTERVAL"), interval or 1),
        count=_positive_int(parts.get("COUNT"), count),
        until=_parse_until(parts.get("UNTIL")) or until,
        byday=_parse_byday(parts.get("BYDAY")),
        bymonthday=_parse_int_list(parts.get("BYMONTHDAY"), "BYMONTHDAY", 1, 31, allow_negative=True),
        bymonth=_parse_int_list(parts.get("BYMONTH"), "BYMONTH", 1, 12),
    )
    rule["unsupported"] = [key for key in parts if key.upper() not in SUPPORTED_PARTS]
    return rule


def _rule(label, freq, interval=1, count=None, until=None, byday=(), bymonthday=(), bymonth=()):
    return OrderedDict(
        [
            ("label", label),
            ("freq", freq),
            ("name", FREQ_NAMES[freq]),
            ("interval", max(1, int(interval or 1))),
            ("count", count),
            ("until", until),
            ("byday", tuple(byday)),
            ("bymonthday", tuple(bymonthday)),
            ("bymonth", tuple(bymonth)),
            ("unsupported", []),
        ]
    )


def parse_rrule_parts(value):
    text = str(value or "").strip()
    if text.upper().startswith(RRULE_PREFIX):
        text = text[len(RRULE_PREFIX):]
    parts = OrderedDict()
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise RecurrenceError("RRULE part %r is not KEY=VALUE." % chunk)
        key, _, part_value = chunk.partition("=")
        parts[key.strip().upper()] = part_value.strip()
    return parts


def _parse_byday(value):
    """Parse BYDAY into ``(position, weekday)`` pairs; position 0 means every."""
    if not value:
        return ()
    entries = []
    for token in str(value).split(","):
        token = token.strip().upper()
        if not token:
            continue
        position = 0
        code = token
        if len(token) > 2:
            prefix, code = token[:-2], token[-2:]
            try:
                position = int(prefix)
            except ValueError:
                raise RecurrenceError("BYDAY entry %r is not a weekday." % token)
            if position == 0:
                raise RecurrenceError("BYDAY position in %r must not be zero." % token)
        if code not in WEEKDAY_CODES:
            raise RecurrenceError("BYDAY entry %r is not a weekday code." % token)
        entries.append((position, WEEKDAY_CODES[code]))
    return tuple(entries)


def _parse_int_list(value, name, low, high, allow_negative=False):
    if not value:
        return ()
    numbers = []
    for token in str(value).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            number = int(token)
        except ValueError:
            raise RecurrenceError("%s entry %r is not a number." % (name, token))
        magnitude = abs(number)
        if number == 0 or magnitude < low or magnitude > high:
            raise RecurrenceError("%s entry %r is out of range." % (name, token))
        if number < 0 and not allow_negative:
            raise RecurrenceError("%s does not accept negative values." % name)
        numbers.append(number)
    return tuple(sorted(set(numbers)))


def _parse_until(value):
    text = str(value or "").strip()
    if not text:
        return None
    cleaned = text.rstrip("Zz")
    # A date-only UNTIL covers that whole day. Treating it as midnight would
    # drop an occurrence that happens later on the final day.
    for pattern, whole_day in (
        ("%Y%m%dT%H%M%S", False),
        ("%Y-%m-%dT%H:%M:%S", False),
        ("%Y-%m-%dT%H:%M", False),
        ("%Y%m%d", True),
        ("%Y-%m-%d", True),
    ):
        try:
            parsed = datetime.strptime(cleaned, pattern)
        except ValueError:
            continue
        if whole_day:
            return parsed.replace(hour=23, minute=59, second=59)
        return parsed
    raise RecurrenceError("UNTIL value %r is not a date or datetime." % value)


def _positive_int(value, default):
    if value is None or value == "":
        return default
    try:
        number = int(str(value).strip())
    except ValueError:
        raise RecurrenceError("Expected a whole number, got %r." % value)
    if number <= 0:
        raise RecurrenceError("Expected a positive number, got %r." % value)
    return number


# ---------------------------------------------------------------------------
# expansion
# ---------------------------------------------------------------------------


def expand(rule, start, after=None, before=None, limit=None):
    """Occurrences of ``rule`` anchored at ``start``.

    Bounded by the rule's own COUNT/UNTIL, by ``before``, and by ``limit``.
    A rule with none of those still stops at DEFAULT_MAX_OCCURRENCES rather
    than running forever.
    """
    if isinstance(rule, str):
        rule = parse_rule(rule)
    start = _as_datetime(start)
    if start is None:
        raise RecurrenceError("Expansion needs a start date.")
    after = _as_datetime(after)
    before = _as_datetime(before)

    ceiling = rule["count"] or limit or DEFAULT_MAX_OCCURRENCES
    if limit:
        ceiling = min(ceiling, limit)

    results = []
    emitted = 0
    for moment in _candidates(rule, start):
        if rule["until"] is not None and moment > rule["until"]:
            break
        if before is not None and moment > before:
            break
        # COUNT counts from the series start, not from `after`, so a windowed
        # view still reflects where the series really ends.
        emitted += 1
        if rule["count"] is not None and emitted > rule["count"]:
            break
        if after is not None and moment < after:
            if emitted >= SAFETY_ITERATIONS:
                break
            continue
        results.append(moment)
        if len(results) >= ceiling:
            break
    return results


def _candidates(rule, start):
    """Yield every moment the rule matches, in order, from ``start``."""
    name = rule["name"]
    interval = rule["interval"]
    byday = rule["byday"]
    bymonthday = rule["bymonthday"]
    bymonth = rule["bymonth"]
    moment_time = start.time()

    if name == "daily":
        current = start
        guard = 0
        while guard < SAFETY_ITERATIONS:
            guard += 1
            if _matches_filters(current, byday, bymonthday, bymonth):
                yield current
            current = current + timedelta(days=interval)
        return

    if name == "weekly":
        if byday:
            week_start = start.date() - timedelta(days=start.weekday())
            guard = 0
            while guard < SAFETY_ITERATIONS:
                guard += 1
                for _position, weekday in sorted(set(byday)):
                    moment = datetime.combine(week_start + timedelta(days=weekday), moment_time)
                    if moment >= start and _matches_month(moment, bymonth):
                        yield moment
                week_start = week_start + timedelta(weeks=interval)
            return
        current = start
        guard = 0
        while guard < SAFETY_ITERATIONS:
            guard += 1
            if _matches_month(current, bymonth):
                yield current
            current = current + timedelta(weeks=interval)
        return

    if name == "monthly":
        year, month = start.year, start.month
        guard = 0
        while guard < SAFETY_ITERATIONS:
            guard += 1
            if not bymonth or month in bymonth:
                for moment in _month_occurrences(year, month, start, rule, moment_time):
                    if moment >= start:
                        yield moment
            year, month = _shift_month(year, month, interval)
        return

    if name == "yearly":
        # Stepping 12 months at a time would never leave the anchor's month,
        # so BYMONTH would silently never match. Walk the year's months.
        year = start.year
        months = tuple(sorted(bymonth)) if bymonth else (start.month,)
        guard = 0
        while guard < SAFETY_ITERATIONS:
            guard += 1
            for month in months:
                for moment in _month_occurrences(year, month, start, rule, moment_time):
                    if moment >= start:
                        yield moment
            year += interval
        return

    raise RecurrenceError("Unsupported frequency %r." % name)


def _month_occurrences(year, month, start, rule, moment_time):
    """Days matched inside one month, in order."""
    byday = rule["byday"]
    bymonthday = rule["bymonthday"]
    days_in_month = calendar.monthrange(year, month)[1]

    days = set()
    if bymonthday:
        for number in bymonthday:
            day = number if number > 0 else days_in_month + number + 1
            if 1 <= day <= days_in_month:
                days.add(day)
    if byday:
        for position, weekday in byday:
            matches = [
                day
                for day in range(1, days_in_month + 1)
                if date(year, month, day).weekday() == weekday
            ]
            if position == 0:
                days.update(matches)
            elif position > 0 and position <= len(matches):
                days.add(matches[position - 1])
            elif position < 0 and -position <= len(matches):
                days.add(matches[position])
    if not days:
        # No BYDAY/BYMONTHDAY: keep the anchor's day, clamped to short months.
        days.add(min(start.day, days_in_month))

    for day in sorted(days):
        yield datetime.combine(date(year, month, day), moment_time)


def _matches_filters(moment, byday, bymonthday, bymonth):
    if byday and not any(
        moment.weekday() == weekday for _position, weekday in byday
    ):
        return False
    if bymonthday:
        days_in_month = calendar.monthrange(moment.year, moment.month)[1]
        allowed = set()
        for number in bymonthday:
            allowed.add(number if number > 0 else days_in_month + number + 1)
        if moment.day not in allowed:
            return False
    return _matches_month(moment, bymonth)


def _matches_month(moment, bymonth):
    return not bymonth or moment.month in bymonth


def _shift_month(year, month, months):
    total = (year * 12 + (month - 1)) + months
    return total // 12, total % 12 + 1


def _as_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time())
    from .timeutil import parse_date_or_datetime

    parsed = parse_date_or_datetime(str(value), is_end=False)
    if parsed is None:
        raise RecurrenceError("%r is not a date or datetime." % value)
    return parsed


# ---------------------------------------------------------------------------
# description
# ---------------------------------------------------------------------------


def describe(rule):
    """A short human sentence for a rule, for previews and help output."""
    if isinstance(rule, str):
        rule = parse_rule(rule)
    interval = rule["interval"]
    name = rule["name"]
    unit = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}[name]
    if interval == 1:
        text = {"daily": "Every day", "weekly": "Every week",
                "monthly": "Every month", "yearly": "Every year"}[name]
    else:
        text = "Every %d %ss" % (interval, unit)

    if rule["byday"]:
        parts = []
        for position, weekday in rule["byday"]:
            label = calendar.day_name[weekday]
            if position:
                parts.append("%s %s" % (_ordinal(position), label))
            else:
                parts.append(label)
        text += " on " + ", ".join(parts)
    if rule["bymonthday"]:
        text += " on day " + ", ".join(
            _ordinal(number) if number > 0 else "%s from the end" % _ordinal(-number)
            for number in rule["bymonthday"]
        )
    if rule["bymonth"]:
        text += " in " + ", ".join(calendar.month_name[number] for number in rule["bymonth"])
    if rule["count"]:
        text += ", %d times" % rule["count"]
    if rule["until"]:
        text += ", until %s" % rule["until"].date().isoformat()
    return text


def _ordinal(number):
    magnitude = abs(int(number))
    if magnitude == 1 and number < 0:
        return "last"
    suffix = "th"
    if magnitude % 100 not in (11, 12, 13):
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(magnitude % 10, "th")
    return "%d%s" % (magnitude, suffix)


def rule_for_item(item):
    """Build a rule from an item's repeat: plus sibling interval/count/until."""
    values = item.details.get("repeat") or []
    if not values:
        return None
    return parse_rule(
        values[0],
        interval=_first_int(item, "interval"),
        count=_first_int(item, "count"),
        until=_first_until(item),
    )


def _first_int(item, key):
    values = item.details.get(key) or []
    if not values:
        return None
    try:
        return int(str(values[0]).strip())
    except ValueError:
        return None


def _first_until(item):
    values = item.details.get("until") or []
    if not values:
        return None
    return _as_datetime(values[0])
