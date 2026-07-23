import calendar
import json
import re
from collections import OrderedDict
from datetime import datetime, time, timedelta

from .links import dependency_blockers_by_item
from .model import (
    VALID_STATUSES,
    VALID_TYPES,
    normalize_status,
    normalize_type,
)
from .serializer import item_to_line
from .timezone_policy import local_now_naive
from .timeutil import (
    parse_date,
    parse_date_or_datetime,
    parse_datetime,
    parse_time,
    format_datetime as format_life_datetime,
)


OPEN_STATUSES = ("[ ]", "[/]", "[>]", "[?]")
_DURATION_RE = re.compile(r"^(\d+)([a-z]*)$")

_POINT_KEYS = ("due", "do", "moved_to", "notify_at")
_MAX_REPEAT_MATCHES = 1000
_RRULE_PREFIX = "RRULE:"
_RRULE_FREQ_TO_REPEAT = {
    "DAILY": "daily",
    "WEEKLY": "weekly",
    "MONTHLY": "monthly",
    "YEARLY": "yearly",
}
_RRULE_WEEKDAYS = {
    "MO": 0,
    "TU": 1,
    "WE": 2,
    "TH": 3,
    "FR": 4,
    "SA": 5,
    "SU": 6,
}
_TABLE_COLUMNS = (
    ("when", "when"),
    ("key", "key"),
    ("line_text", "line"),
    ("type", "type"),
    ("status", "status"),
    ("blocked_text", "blocked"),
    ("title", "title"),
)


def parse_agenda_range(
    start_text=None,
    end_text=None,
    around_text=None,
    window_text="1h",
    now=None,
):
    """Parse CLI range options into half-open start/end datetimes."""
    if now is None:
        now = local_now_naive().replace(second=0, microsecond=0)

    if (start_text or end_text) and around_text:
        raise ValueError("Use either --from/--to or --around, not both.")
    if start_text or end_text:
        if not (start_text and end_text):
            raise ValueError("--from and --to must be used together.")
        start = _parse_range_boundary(start_text, is_end=False, now=now)
        end = _parse_range_boundary(end_text, is_end=True, now=now)
    else:
        center = _parse_around_value(around_text or "now", now)
        window = parse_duration(window_text)
        start = center - window
        end = center + window

    if end < start:
        raise ValueError("Range end must not be earlier than range start.")
    return start, end


def parse_duration(value):
    text = str(value or "").strip().lower()
    match = _DURATION_RE.match(text)
    if not match:
        raise ValueError("Duration must look like 30m, 2h, 1d, 1w, 1mo, or 1y.")
    amount = int(match.group(1))
    unit = match.group(2) or "m"
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return timedelta(seconds=amount)
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return timedelta(minutes=amount)
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return timedelta(hours=amount)
    if unit in ("d", "day", "days"):
        return timedelta(days=amount)
    if unit in ("w", "week", "weeks"):
        return timedelta(weeks=amount)
    if unit in ("mo", "mon", "month", "months"):
        return timedelta(days=30 * amount)
    if unit in ("y", "yr", "yrs", "year", "years"):
        return timedelta(days=365 * amount)
    raise ValueError("Unsupported duration unit %r." % unit)


def parse_optional_time_range(after_text=None, before_text=None, now=None):
    if now is None:
        now = local_now_naive().replace(second=0, microsecond=0)
    range_start = None
    range_end = None
    if after_text:
        range_start = _parse_range_boundary(after_text, is_end=False, now=now)
    if before_text:
        range_end = _parse_range_boundary(before_text, is_end=True, now=now)
    if range_start and range_end and range_end < range_start:
        raise ValueError("Time filter end must not be earlier than start.")
    return range_start, range_end


def agenda_records(items, range_start, range_end):
    records = []
    blockers_by_item = dependency_blockers_by_item(items)
    for item in items:
        matches = item_time_matches(item, range_start, range_end)
        if not matches:
            continue
        blockers = blockers_by_item.get(id(item), [])
        primary = matches[0]
        record = OrderedDict()
        record["when"] = format_match_time(primary)
        record["key"] = primary["key"]
        if item.line is not None:
            record["line"] = item.line
        record["status"] = item.status
        record["type"] = item.kind
        record["blocked"] = bool(blockers)
        if blockers:
            record["blocked_by"] = blockers
        record["title"] = item.title
        record["matches"] = matches
        record["details"] = _copy_details(item.details)
        record["text"] = _item_line_text(item)
        record["generated"] = bool("occurrence_index" in primary or "repeat" in primary)
        source_ids = item.details.get("id", [])
        if source_ids:
            record["source_id"] = str(source_ids[0])
        # Carry the originating file so callers can edit the record they are
        # looking at. webapp.py already reads record["source"], and without it
        # every agenda row is read-only in the TUI.
        item_source = getattr(item, "source", None)
        if item_source:
            record["source"] = item_source
        occurrence_start = primary.get("start")
        occurrence_end = primary.get("end")
        if occurrence_start:
            record["occurrence_start"] = occurrence_start
        if occurrence_end:
            record["occurrence_end"] = occurrence_end
        if "occurrence_index" in primary:
            record["occurrence_index"] = primary["occurrence_index"]
        if "repeat" in primary:
            record["repeat_rule"] = primary["repeat"]
        records.append(record)
    records.sort(key=_record_sort_key)
    return records


def filter_items(
    items,
    open_only=False,
    statuses=None,
    kinds=None,
    projects=None,
    tags=None,
    tag_all=None,
    exclude_tags=None,
    users=None,
    persons=None,
    owners=None,
    assignees=None,
    attendees=None,
    senders=None,
    recipients=None,
    teams=None,
    detail_filters=None,
    text=None,
    range_start=None,
    range_end=None,
    user_aliases=None,
    team_members=None,
    team_aliases=None,
    tag_aliases=None,
):
    statuses = _normalize_status_filter(statuses)
    kinds = _normalize_type_filter(kinds)
    projects = _normalize_filter_values(projects)
    tags = _normalize_filter_values(tags, tag_aliases)
    tag_all = _normalize_filter_groups(tag_all, tag_aliases)
    exclude_tags = _normalize_filter_values(exclude_tags, tag_aliases)
    users = _normalize_filter_values(users, user_aliases)
    persons = _normalize_filter_values(persons)
    owners = _normalize_filter_values(owners)
    assignees = _normalize_filter_values(assignees)
    attendees = _normalize_filter_values(attendees)
    senders = _normalize_filter_values(senders)
    recipients = _normalize_filter_values(recipients)
    teams = _normalize_filter_values(teams, team_aliases)
    details = _parse_detail_filters(detail_filters)
    text = text.lower() if text else None

    if range_start is None and range_end is not None:
        range_start = datetime.min
    if range_start is not None and range_end is None:
        range_end = datetime.max

    filtered = []
    for item in items:
        if open_only and item.status not in OPEN_STATUSES:
            continue
        if statuses and item.status not in statuses:
            continue
        if kinds and item.kind not in kinds:
            continue
        if projects and not _item_has_any_detail(item, "project", projects):
            continue
        if tags and not _item_has_any_detail(item, "tag", tags):
            continue
        if tag_all and not _item_matches_all_detail_groups(item, "tag", tag_all):
            continue
        if exclude_tags and _item_has_any_detail(item, "tag", exclude_tags):
            continue
        if users and not _item_has_any_user(item, users, user_aliases):
            continue
        if persons and not _item_has_any_detail(item, "person", persons):
            continue
        if owners and not _item_has_any_detail(item, "owner", owners):
            continue
        if assignees and not _item_has_any_detail(item, "assignee", assignees):
            continue
        if attendees and not _item_has_any_detail(item, "attendee", attendees):
            continue
        if senders and not _item_has_any_detail(item, "sender", senders):
            continue
        if recipients and not _item_has_any_detail(item, "recipient", recipients):
            continue
        if teams and not _item_has_any_team(item, teams, team_members):
            continue
        if details and not _item_matches_detail_filters(item, details):
            continue
        if text and text not in _item_search_text(item).lower():
            continue
        if range_start is not None and not item_time_matches(item, range_start, range_end):
            continue
        filtered.append(item)
    return filtered


def filter_agenda_records(
    records,
    open_only=False,
    statuses=None,
    kinds=None,
    projects=None,
    tags=None,
    tag_all=None,
    exclude_tags=None,
    users=None,
    persons=None,
    owners=None,
    assignees=None,
    attendees=None,
    senders=None,
    recipients=None,
    teams=None,
    detail_filters=None,
    text=None,
    blocked=None,
    user_aliases=None,
    team_members=None,
    team_aliases=None,
    tag_aliases=None,
):
    statuses = _normalize_status_filter(statuses)
    kinds = _normalize_type_filter(kinds)
    projects = _normalize_filter_values(projects)
    tags = _normalize_filter_values(tags, tag_aliases)
    tag_all = _normalize_filter_groups(tag_all, tag_aliases)
    exclude_tags = _normalize_filter_values(exclude_tags, tag_aliases)
    users = _normalize_filter_values(users, user_aliases)
    persons = _normalize_filter_values(persons)
    owners = _normalize_filter_values(owners)
    assignees = _normalize_filter_values(assignees)
    attendees = _normalize_filter_values(attendees)
    senders = _normalize_filter_values(senders)
    recipients = _normalize_filter_values(recipients)
    teams = _normalize_filter_values(teams, team_aliases)
    details = _parse_detail_filters(detail_filters)
    text = text.lower() if text else None

    filtered = []
    for record in records:
        if open_only and record["status"] not in OPEN_STATUSES:
            continue
        if statuses and record["status"] not in statuses:
            continue
        if kinds and record["type"] not in kinds:
            continue
        if projects and not _record_has_any_detail(record, "project", projects):
            continue
        if tags and not _record_has_any_detail(record, "tag", tags):
            continue
        if tag_all and not _record_matches_all_detail_groups(record, "tag", tag_all):
            continue
        if exclude_tags and _record_has_any_detail(record, "tag", exclude_tags):
            continue
        if users and not _record_has_any_user(record, users, user_aliases):
            continue
        if persons and not _record_has_any_detail(record, "person", persons):
            continue
        if owners and not _record_has_any_detail(record, "owner", owners):
            continue
        if assignees and not _record_has_any_detail(record, "assignee", assignees):
            continue
        if attendees and not _record_has_any_detail(record, "attendee", attendees):
            continue
        if senders and not _record_has_any_detail(record, "sender", senders):
            continue
        if recipients and not _record_has_any_detail(record, "recipient", recipients):
            continue
        if teams and not _record_has_any_team(record, teams, team_members):
            continue
        if details and not _record_matches_detail_filters(record, details):
            continue
        if text and text not in _record_search_text(record).lower():
            continue
        if blocked is True and not record.get("blocked"):
            continue
        if blocked is False and record.get("blocked"):
            continue
        filtered.append(record)
    return filtered


def item_time_matches(item, range_start, range_end):
    matches = []
    if item.details.get("repeat"):
        _add_repeat_matches(matches, item, range_start, range_end)
    else:
        _add_from_to_matches(matches, item, range_start, range_end)
        _add_detail_range_matches(
            matches,
            item,
            "notify_from",
            "notify_to",
            "notify_from/to",
            range_start,
            range_end,
        )
        _add_point_key_matches(matches, item, range_start, range_end)
        _add_at_matches(matches, item, range_start, range_end)
        _add_on_matches(matches, item, range_start, range_end)
    matches.sort(key=_match_sort_key)
    return matches


def format_agenda_table(records, width=None):
    if not records:
        return "No agenda items found.\n"

    if width is None:
        try:
            import shutil as _shutil
            width = _shutil.get_terminal_size((80, 24)).columns
        except Exception:
            width = 80

    # Compact single-line format for narrow terminals (< 80 cols)
    if width < 80:
        lines = []
        for record in records:
            when = _table_cell(record.get("when", ""))
            status = _table_cell(record.get("status", ""))
            title = record.get("title", "")
            # Truncate title to fit remaining width
            max_title = max(10, width - len(when) - len(status) - 4)
            if len(title) > max_title:
                title = title[: max_title - 3] + "..."
            lines.append("%s %s %s" % (when, status, title))
        return "\n".join(lines) + "\n"

    rows = []
    for record in records:
        row = OrderedDict()
        for key, _heading in _TABLE_COLUMNS:
            if key == "line_text":
                value = record.get("line", "")
            elif key == "blocked_text":
                value = "yes" if record.get("blocked") else ""
            else:
                value = record.get(key, "")
            row[key] = _table_cell(value)
        rows.append(row)

    widths = []
    for key, heading in _TABLE_COLUMNS:
        col_width = len(heading)
        for row in rows:
            col_width = max(col_width, len(row[key]))
        widths.append(col_width)

    lines = []
    lines.append(_format_table_row([heading for _key, heading in _TABLE_COLUMNS], widths))
    lines.append(_format_table_row(["-" * w for w in widths], widths))
    for row in rows:
        lines.append(
            _format_table_row(
                [row[key] for key, _heading in _TABLE_COLUMNS],
                widths,
            )
        )
    return "\n".join(lines) + "\n"


def agenda_records_to_json(records, pretty=False):
    indent = 2 if pretty else None
    return json.dumps(
        records,
        ensure_ascii=False,
        indent=indent,
        separators=None if pretty else (",", ":"),
    )


def agenda_records_to_jsonl(records):
    lines = []
    for record in records:
        lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def agenda_records_to_life(records):
    return "\n".join([record["text"] for record in records])


def format_range_label(range_start, range_end):
    return "%s..%s" % (_format_datetime(range_start), _format_datetime(range_end))


def _add_from_to_matches(matches, item, range_start, range_end):
    starts = item.details.get("from", [])
    ends = item.details.get("to", [])
    for index, start_text in enumerate(starts):
        start = _parse_datetime_value(start_text)
        if start is None:
            continue
        end = None
        if index < len(ends):
            end = _parse_datetime_value(ends[index])
        elif len(ends) == 1:
            end = _parse_datetime_value(ends[0])
        if end is None and item.kind != "S":
            end = start
        key = "from/to" if end and end != start else "from"
        _add_match(matches, key, start, end, range_start, range_end)

    if starts:
        return

    for end_text in ends:
        end = _parse_datetime_value(end_text)
        if end is not None:
            _add_match(matches, "to", end, end, range_start, range_end)


def _add_detail_range_matches(
    matches,
    item,
    start_key,
    end_key,
    range_key,
    range_start,
    range_end,
):
    starts = item.details.get(start_key, [])
    ends = item.details.get(end_key, [])
    for index, start_text in enumerate(starts):
        start_span = _parse_date_or_datetime_span(start_text)
        if start_span is None:
            continue
        start = start_span[0]
        end = None
        if index < len(ends):
            end_span = _parse_date_or_datetime_span(ends[index])
            if end_span is not None:
                end = end_span[1]
        elif len(ends) == 1:
            end_span = _parse_date_or_datetime_span(ends[0])
            if end_span is not None:
                end = end_span[1]
        key = range_key if end and end != start else start_key
        _add_match(matches, key, start, end, range_start, range_end)

    if starts:
        return

    for end_text in ends:
        end_span = _parse_date_or_datetime_span(end_text)
        if end_span is not None:
            _add_match(matches, end_key, end_span[0], end_span[1], range_start, range_end)


def _add_point_key_matches(matches, item, range_start, range_end):
    for key in _POINT_KEYS:
        for value in item.details.get(key, []):
            span = _parse_date_or_datetime_span(value)
            if span is not None:
                _add_match(matches, key, span[0], span[1], range_start, range_end)


def _add_at_matches(matches, item, range_start, range_end):
    at_values = item.details.get("at", [])
    if not at_values:
        return

    on_dates = _item_on_dates(item)
    for value in at_values:
        point = _parse_datetime_value(value)
        if point is not None:
            _add_match(matches, "at", point, point, range_start, range_end)
            continue

        at_time = _parse_time_value(value)
        if at_time is None:
            continue
        if on_dates:
            candidate_dates = on_dates
        elif _is_unbounded_range(range_start, range_end):
            continue
        elif (range_end.date() - range_start.date()).days > 366:
            candidate_dates = [_first_matching_date_for_time(range_start, at_time)]
        else:
            candidate_dates = _range_dates(range_start, range_end)
        for candidate_date in candidate_dates:
            point = datetime.combine(candidate_date, at_time)
            _add_match(matches, "at", point, point, range_start, range_end)


def _add_on_matches(matches, item, range_start, range_end):
    for value in item.details.get("on", []):
        span = _parse_date_span(value)
        if span is not None:
            _add_match(matches, "on", span[0], span[1], range_start, range_end)


def next_repeat_occurrence(item, repeat_base, completion_date):
    """Compute the next occurrence for a repeat-enabled item's instance completion.

    Shared by the CLI `complete` command and the MCP `complete_item` tool so
    both surfaces materialize the next occurrence identically.

    Returns (anchor_key, next_datetime_or_None, rule). anchor_key is 'due' or
    'do', whichever the item carries. next_datetime is None when the repeat
    series has reached its `until` bound (no new occurrence should be added).
    Raises ValueError (fail-loud) when the repeat rule cannot be resolved,
    when repeat_base is invalid, or when repeat_base:due lacks a due/do value.
    """
    repeat_value = _first_detail_value(item, "repeat")
    rule = _repeat_rule(item, repeat_value)
    if rule is None:
        raise ValueError(
            "Unrecognized repeat:%s value; cannot materialize the next occurrence." % repeat_value
        )

    repeat_base = str(repeat_base or "due").strip().lower()
    if repeat_base not in ("due", "done"):
        raise ValueError("repeat_base must be 'due' or 'done', got %r." % repeat_base)

    anchor_key = "due" if item.details.get("due") else ("do" if item.details.get("do") else "due")

    if repeat_base == "due":
        due_values = item.details.get(anchor_key)
        if not due_values:
            raise ValueError(
                "repeat_base:due requires a due: (or do:) value on the item. "
                "Set repeat_base:done or add a due date."
            )
        anchor = parse_date_or_datetime(due_values[0], is_end=False)
        if anchor is None:
            raise ValueError("Could not parse %s:%s for repeat calculation." % (anchor_key, due_values[0]))
    else:
        anchor = datetime.combine(completion_date, time())

    next_dt = _next_occurrence_after(item, anchor, rule)
    if next_dt is None:
        return anchor_key, None, rule
    until = rule.get("until")
    if until is not None and next_dt > until:
        return anchor_key, None, rule
    return anchor_key, next_dt, rule


def _next_occurrence_after(item, anchor, rule):
    """First occurrence strictly after the anchor.

    Simple rules keep the original arithmetic; anything with BYDAY,
    BYMONTHDAY, or BYMONTH goes through the shared expander, which is the only
    place that knows how those interact.
    """
    from .recurrence import RecurrenceError, rule_for_item, expand

    # Decide from the shared parse, not from this module's rule: the local
    # BYDAY parser drops positional forms such as 1MO, so relying on it would
    # quietly fall back to plain month arithmetic and land on the wrong day.
    try:
        expanded_rule = rule_for_item(item)
    except RecurrenceError as exc:
        raise ValueError(str(exc))
    if expanded_rule is None or not (
        expanded_rule["byday"] or expanded_rule["bymonthday"] or expanded_rule["bymonth"]
    ):
        return _next_repeat_datetime(anchor, rule["repeat"], rule["interval"])

    try:
        series_start = _series_start(item, anchor)
        upcoming = expand(
            expanded_rule,
            series_start,
            after=anchor + timedelta(minutes=1),
            limit=1,
        )
    except RecurrenceError as exc:
        raise ValueError(str(exc))
    return upcoming[0] if upcoming else None


def _series_start(item, anchor):
    """Anchor the expansion at the item's own start so BYDAY phases line up."""
    for key in ("due", "do", "from"):
        values = item.details.get(key)
        if values:
            parsed = parse_date_or_datetime(values[0], is_end=False)
            if parsed is not None:
                return min(parsed, anchor)
    return anchor


def _add_repeat_matches(matches, item, range_start, range_end):
    repeat_value = _first_detail_value(item, "repeat")
    rule = _repeat_rule(item, repeat_value)
    if rule is None:
        return

    anchor = _repeat_anchor(item, range_start, range_end)
    if anchor is None:
        return

    key, anchor_start, anchor_end = anchor
    if anchor_end is None:
        anchor_end = anchor_start
    if anchor_end < anchor_start:
        anchor_end = anchor_start

    repeat_name = rule["repeat"]
    interval = rule["interval"]
    count = rule["count"]
    until = rule["until"]
    effective_start = anchor_start if range_start == datetime.min else range_start
    effective_end = range_end
    if range_end == datetime.max:
        effective_end = effective_start + timedelta(days=366)
    if until is not None and until < effective_end:
        effective_end = until

    if _add_shared_rrule_matches(
        matches,
        item,
        key,
        anchor_start,
        anchor_end,
        effective_end,
        range_start,
        range_end,
        rule["label"],
    ):
        return

    byday = rule.get("byday")
    if byday:
        _add_rrule_byday_matches(
            matches,
            key,
            anchor_start,
            anchor_end,
            repeat_name,
            byday,
            interval,
            count,
            until,
            effective_end,
            range_start,
            range_end,
            rule["label"],
        )
        return

    current, occurrence_index = _align_repeat_start(
        repeat_name,
        anchor_start,
        anchor_end,
        interval,
        effective_start,
        count,
    )
    emitted = 0
    while current <= effective_end and emitted < _MAX_REPEAT_MATCHES:
        if count is not None and occurrence_index > count:
            break
        if until is not None and current > until:
            break

        current_end = current + (anchor_end - anchor_start)
        _add_match(
            matches,
            "repeat:%s" % key,
            current,
            current_end,
            range_start,
            range_end,
            repeat=rule["label"],
            occurrence_index=occurrence_index,
        )
        emitted += 1

        next_current = _next_repeat_datetime(current, repeat_name, interval)
        if next_current <= current:
            break
        current = next_current
        occurrence_index += 1


def _repeat_rule(item, repeat_value):
    if repeat_value in ("daily", "weekly", "monthly", "yearly", "weekdays"):
        return OrderedDict(
            [
                ("label", repeat_value),
                ("repeat", repeat_value),
                ("interval", _positive_int_detail(item, "interval", 1)),
                ("count", _positive_int_detail(item, "count", None)),
                ("until", _repeat_until(item)),
                ("byday", ()),
            ]
        )

    text = str(repeat_value or "")
    if not text.upper().startswith(_RRULE_PREFIX):
        return None

    parts = _parse_rrule_parts(text)
    repeat_name = _RRULE_FREQ_TO_REPEAT.get(parts.get("FREQ", ""))
    if repeat_name is None:
        return None

    byday = _parse_rrule_byday(parts.get("BYDAY"))
    if byday and repeat_name not in ("daily", "weekly"):
        return None

    return OrderedDict(
        [
            ("label", text),
            ("repeat", repeat_name),
            ("interval", _positive_int_text(parts.get("INTERVAL"), _positive_int_detail(item, "interval", 1))),
            ("count", _positive_int_text(parts.get("COUNT"), _positive_int_detail(item, "count", None))),
            ("until", _parse_rrule_until(parts.get("UNTIL")) or _repeat_until(item)),
            ("byday", byday),
        ]
    )


def _parse_rrule_parts(value):
    text = str(value or "")
    if text.upper().startswith(_RRULE_PREFIX):
        text = text[len(_RRULE_PREFIX):]
    parts = OrderedDict()
    for raw_part in text.split(";"):
        if "=" not in raw_part:
            continue
        key, raw_value = raw_part.split("=", 1)
        key = key.strip().upper()
        if key:
            parts[key] = raw_value.strip().upper()
    return parts


def _parse_rrule_byday(value):
    if not value:
        return ()
    weekdays = []
    for raw_part in str(value).split(","):
        code = raw_part.strip().upper()
        # Ignore positional BYDAY forms such as 1MO or -1FR in the dependency-free subset.
        if len(code) != 2:
            return ()
        weekday = _RRULE_WEEKDAYS.get(code)
        if weekday is None:
            return ()
        if weekday not in weekdays:
            weekdays.append(weekday)
    return tuple(sorted(weekdays))


def _parse_rrule_until(value):
    if not value:
        return None

    parsed = parse_date_or_datetime(value, is_end=True)
    if parsed is not None:
        return parsed

    text = str(value).strip().upper()
    try:
        if re.match(r"^\d{8}$", text):
            parsed_date = datetime.strptime(text, "%Y%m%d").date()
            return datetime.combine(parsed_date, time(23, 59, 59))
        if re.match(r"^\d{8}T\d{6}Z$", text):
            return datetime.strptime(text[:-1] + "+0000", "%Y%m%dT%H%M%S%z").astimezone().replace(tzinfo=None)
        if re.match(r"^\d{8}T\d{6}[+-]\d{4}$", text):
            return datetime.strptime(text, "%Y%m%dT%H%M%S%z").astimezone().replace(tzinfo=None)
        if re.match(r"^\d{8}T\d{6}$", text):
            return datetime.strptime(text, "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    return None


def _positive_int_text(value, default):
    if value is None:
        return default
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return default
    return number


def _add_shared_rrule_matches(
    matches,
    item,
    key,
    anchor_start,
    anchor_end,
    effective_end,
    range_start,
    range_end,
    repeat_label,
):
    """Expand a BY*-bearing RRULE with the shared recurrence engine.

    The local parser understands only plain BYDAY, so positional forms such as
    1MO or -1FR, plus BYMONTHDAY and BYMONTH, used to be dropped and the series
    silently collapsed to the anchor. Returns False when the rule is outside
    the shared subset so the caller can keep its own arithmetic.
    """
    from .recurrence import RecurrenceError, expand, rule_for_item

    try:
        rule = rule_for_item(item)
    except RecurrenceError:
        return False
    if rule is None or not (rule["byday"] or rule["bymonthday"] or rule["bymonth"]):
        return False

    duration = anchor_end - anchor_start
    try:
        occurrences = expand(
            rule,
            anchor_start,
            before=effective_end,
            limit=_MAX_REPEAT_MATCHES,
        )
    except RecurrenceError:
        return False

    emitted = 0
    for occurrence_index, current in enumerate(occurrences, 1):
        current_end = current + duration
        _add_match(
            matches,
            "repeat:%s" % key,
            current,
            current_end,
            range_start,
            range_end,
            repeat=repeat_label,
            occurrence_index=occurrence_index,
        )
        if _overlaps(current, current_end, range_start, range_end):
            emitted += 1
            if emitted >= _MAX_REPEAT_MATCHES:
                break
    return True


def _add_rrule_byday_matches(
    matches,
    key,
    anchor_start,
    anchor_end,
    repeat_name,
    byday,
    interval,
    count,
    until,
    effective_end,
    range_start,
    range_end,
    repeat_label,
):
    duration = anchor_end - anchor_start
    emitted = 0
    occurrence_index = 1
    for current in _rrule_byday_candidates(
        anchor_start,
        repeat_name,
        byday,
        interval,
    ):
        if current > effective_end:
            break
        if count is not None and occurrence_index > count:
            break
        if until is not None and current > until:
            break

        current_end = current + duration
        _add_match(
            matches,
            "repeat:%s" % key,
            current,
            current_end,
            range_start,
            range_end,
            repeat=repeat_label,
            occurrence_index=occurrence_index,
        )
        if _overlaps(current, current_end, range_start, range_end):
            emitted += 1
            if emitted >= _MAX_REPEAT_MATCHES:
                break
        occurrence_index += 1


def _rrule_byday_candidates(anchor_start, repeat_name, byday, interval):
    if repeat_name == "daily":
        current = anchor_start
        while True:
            if current >= anchor_start and current.weekday() in byday:
                yield current
            current = current + timedelta(days=interval)

    elif repeat_name == "weekly":
        anchor_week_start = anchor_start.date() - timedelta(days=anchor_start.weekday())
        week_start = anchor_week_start
        while True:
            for weekday in byday:
                candidate = datetime.combine(
                    week_start + timedelta(days=weekday),
                    anchor_start.time(),
                )
                if candidate >= anchor_start:
                    yield candidate
            week_start = week_start + timedelta(weeks=interval)


def _repeat_anchor(item, range_start, range_end):
    starts = item.details.get("from", [])
    ends = item.details.get("to", [])
    for index, start_text in enumerate(starts):
        start = _parse_datetime_value(start_text)
        if start is None:
            continue
        end = None
        if index < len(ends):
            end = _parse_datetime_value(ends[index])
        elif len(ends) == 1:
            end = _parse_datetime_value(ends[0])
        if end is None:
            end = start
        return "from/to" if end != start else "from", start, end

    at_values = item.details.get("at", [])
    for value in at_values:
        point = _parse_datetime_value(value)
        if point is not None:
            return "at", point, point

        at_time = _parse_time_value(value)
        if at_time is None:
            continue
        on_dates = _item_on_dates(item)
        if not on_dates and _is_unbounded_range(range_start, range_end):
            return None
        anchor_date = on_dates[0] if on_dates else _first_matching_date_for_time(range_start, at_time)
        point = datetime.combine(anchor_date, at_time)
        return "at", point, point

    for value in item.details.get("on", []):
        span = _parse_date_span(value)
        if span is not None:
            return "on", span[0], span[1]

    for key in _POINT_KEYS:
        for value in item.details.get(key, []):
            span = _parse_date_or_datetime_span(value)
            if span is not None:
                return key, span[0], span[1]

    return None


def _align_repeat_start(repeat_value, anchor_start, anchor_end, interval, range_start, count):
    occurrence_index = 1
    duration = anchor_end - anchor_start
    target = range_start - duration
    if target <= anchor_start:
        return anchor_start, occurrence_index

    if repeat_value == "daily":
        step_seconds = timedelta(days=interval).total_seconds()
        skipped = max(0, int((target - anchor_start).total_seconds() // step_seconds) - 1)
        if count is not None and skipped >= count:
            return anchor_start + timedelta(days=interval * skipped), skipped + 1
        return anchor_start + timedelta(days=interval * skipped), skipped + 1

    if repeat_value == "weekly":
        step_seconds = timedelta(weeks=interval).total_seconds()
        skipped = max(0, int((target - anchor_start).total_seconds() // step_seconds) - 1)
        if count is not None and skipped >= count:
            return anchor_start + timedelta(weeks=interval * skipped), skipped + 1
        return anchor_start + timedelta(weeks=interval * skipped), skipped + 1

    current = anchor_start
    while current < target:
        if count is not None and occurrence_index >= count:
            break
        next_current = _next_repeat_datetime(current, repeat_value, interval)
        if next_current <= current:
            break
        current = next_current
        occurrence_index += 1
    return current, occurrence_index


def _next_repeat_datetime(value, repeat_value, interval):
    if repeat_value == "daily":
        return value + timedelta(days=interval)
    if repeat_value == "weekly":
        return value + timedelta(weeks=interval)
    if repeat_value == "monthly":
        return _add_months(value, interval)
    if repeat_value == "yearly":
        return _add_years(value, interval)
    if repeat_value == "weekdays":
        current = value
        advanced = 0
        while advanced < interval:
            current = current + timedelta(days=1)
            if current.weekday() < 5:
                advanced += 1
        return current
    return value


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _add_years(value, years):
    year = value.year + years
    day = min(value.day, calendar.monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def _repeat_until(item):
    for value in item.details.get("until", []):
        parsed = parse_date_or_datetime(value, is_end=True)
        if parsed is not None:
            return parsed
    return None


def _positive_int_detail(item, key, default):
    value = _first_detail_value(item, key)
    if value is None:
        return default
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return default
    return number


def _first_detail_value(item, key):
    values = item.details.get(key)
    if values:
        return values[0]
    return None


def _add_match(matches, key, start, end, range_start, range_end, repeat=None, occurrence_index=None):
    if start is None:
        return
    if _overlaps(start, end, range_start, range_end):
        match = OrderedDict()
        match["key"] = key
        match["start"] = _format_datetime(start)
        if end is not None and end != start:
            match["end"] = _format_datetime(end)
        elif end is None:
            match["end"] = ""
        if repeat is not None:
            match["repeat"] = repeat
        if occurrence_index is not None:
            match["occurrence_index"] = occurrence_index
        matches.append(match)


def _overlaps(start, end, range_start, range_end):
    if end is None:
        return start < range_end
    if end == start:
        return range_start <= start < range_end
    return start < range_end and end > range_start


def _is_unbounded_range(range_start, range_end):
    return range_start == datetime.min or range_end == datetime.max


def _parse_range_boundary(value, is_end, now):
    if str(value).strip().lower() == "now":
        return now
    parsed_date = parse_date(value)
    if parsed_date is not None:
        if is_end:
            return datetime.combine(parsed_date, time(0, 0, 0)) + timedelta(days=1)
        return datetime.combine(parsed_date, time(0, 0, 0))
    parsed = _parse_datetime_value(value)
    if parsed is None:
        raise ValueError(
            "Datetime must be now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM with optional seconds, fractional seconds, and timezone."
        )
    return parsed


def _parse_around_value(value, now):
    if str(value).strip().lower() == "now":
        return now
    parsed_date = parse_date(value)
    if parsed_date is not None:
        return datetime.combine(parsed_date, time(12, 0))
    parsed = _parse_datetime_value(value)
    if parsed is None:
        raise ValueError(
            "--around must be now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM with optional seconds, fractional seconds, and timezone."
        )
    return parsed


def _parse_date_or_datetime_span(value):
    start = parse_date_or_datetime(value, is_end=False)
    if start is None:
        return None
    end = parse_date_or_datetime(value, is_end=True)
    return start, end


def _parse_date_span(value):
    parsed = parse_date(value)
    if parsed is None:
        return None
    return datetime.combine(parsed, time(0, 0, 0)), datetime.combine(parsed, time(23, 59, 59))


def _parse_datetime_value(value):
    return parse_datetime(value)


def _parse_time_value(value):
    return parse_time(value)


def _item_on_dates(item):
    dates = []
    for value in item.details.get("on", []):
        parsed = parse_date(value)
        if parsed is None:
            continue
        dates.append(parsed)
    return dates


def _first_matching_date_for_time(range_start, at_time):
    candidate_date = range_start.date()
    point = datetime.combine(candidate_date, at_time)
    if point < range_start:
        candidate_date = candidate_date + timedelta(days=1)
    return candidate_date


def _range_dates(range_start, range_end):
    current = range_start.date()
    last = range_end.date()
    values = []
    while current <= last:
        values.append(current)
        current = current + timedelta(days=1)
    return values


def _match_sort_key(match):
    return (_parse_datetime_value(match["start"]) or datetime.max, match["key"])


def _record_sort_key(record):
    primary = record["matches"][0]
    start = _parse_datetime_value(primary["start"]) or datetime.max
    return (start, record.get("line", 0), record["type"], record["title"])


def format_match_time(match):
    if "end" in match and match["end"]:
        return "%s..%s" % (match["start"], match["end"])
    if "end" in match and match["end"] == "":
        return "%s.." % match["start"]
    return match["start"]


def _format_datetime(value):
    return format_life_datetime(value)


def _copy_details(details):
    copied = OrderedDict()
    for key, values in details.items():
        copied[key] = list(values)
    return copied


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"


def _table_cell(value):
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def _normalize_filter_values(values, aliases=None):
    normalized = []
    for raw in values or []:
        for value in str(raw).split(","):
            value = value.strip()
            if not value:
                continue
            for expanded in _expand_filter_value(value, aliases):
                if expanded and expanded not in normalized:
                    normalized.append(expanded)
    return tuple(normalized)


def _normalize_filter_groups(values, aliases=None):
    groups = []
    for raw in values or []:
        for value in str(raw).split(","):
            value = value.strip()
            if not value:
                continue
            expanded = []
            for entry in _expand_filter_value(value, aliases):
                if entry and entry not in expanded:
                    expanded.append(entry)
            if expanded:
                groups.append(tuple(expanded))
    return tuple(groups)


def _expand_filter_value(value, aliases):
    values = [value]
    if isinstance(aliases, dict):
        if value in aliases:
            values.extend(aliases.get(value) or [])
        else:
            for canonical, alias_values in aliases.items():
                all_values = [canonical] + list(alias_values or [])
                if value in all_values:
                    values.extend(all_values)
                    break
    return values


def _normalize_status_filter(values):
    normalized = []
    for value in _normalize_filter_values(values):
        status = normalize_status(value)
        if status not in VALID_STATUSES:
            raise ValueError("Invalid status filter %r." % value)
        if status not in normalized:
            normalized.append(status)
    return tuple(normalized)


def _normalize_type_filter(values):
    normalized = []
    for value in _normalize_filter_values(values):
        kind = normalize_type(value)
        if kind not in VALID_TYPES:
            raise ValueError("Invalid type filter %r." % value)
        if kind not in normalized:
            normalized.append(kind)
    return tuple(normalized)


def _parse_detail_filters(values):
    filters = []
    for raw in values or []:
        text = str(raw).strip()
        if not text:
            continue
        if "=" in text:
            key, value = text.split("=", 1)
            filters.append((key.strip(), value.strip()))
        elif ":" in text:
            key, value = text.split(":", 1)
            filters.append((key.strip(), value.strip()))
        else:
            filters.append((text, None))
    return tuple(filters)


def _record_has_any_detail(record, key, values):
    details = record.get("details", {})
    record_values = details.get(key, [])
    if key == "person" and not record_values and record.get("type") == "S":
        record_values = ["self"]
    for value in values:
        if value in record_values:
            return True
    return False


def _record_matches_all_detail_groups(record, key, groups):
    details = record.get("details", {})
    record_values = details.get(key, [])
    for group in groups:
        if not any(value in record_values for value in group):
            return False
    return True


def _item_has_any_detail(item, key, values):
    item_values = item.details.get(key, [])
    if key == "person" and not item_values and item.kind == "S":
        item_values = ["self"]
    for value in values:
        if value in item_values:
            return True
    return False


def _item_matches_all_detail_groups(item, key, groups):
    item_values = item.details.get(key, [])
    for group in groups:
        if not any(value in item_values for value in group):
            return False
    return True


def _item_has_any_user(item, values, aliases=None):
    item_values = _item_user_values(item)
    expanded = set()
    for value in item_values:
        expanded.update(_expand_filter_value(value, aliases))
    return any(value in expanded for value in values)


def _record_has_any_user(record, values, aliases=None):
    record_values = _record_user_values(record)
    expanded = set()
    for value in record_values:
        expanded.update(_expand_filter_value(value, aliases))
    return any(value in expanded for value in values)


def _item_has_any_team(item, values, team_members=None):
    item_teams = set(item.details.get("team", []) + item.details.get("group", []))
    if any(value in item_teams for value in values):
        return True
    if not isinstance(team_members, dict):
        return False
    item_users = set(_item_user_values(item))
    for team in values:
        members = set(team_members.get(team, []))
        if members and item_users.intersection(members):
            return True
    return False


def _record_has_any_team(record, values, team_members=None):
    details = record.get("details", {})
    record_teams = set(details.get("team", []) + details.get("group", []))
    if any(value in record_teams for value in values):
        return True
    if not isinstance(team_members, dict):
        return False
    record_users = set(_record_user_values(record))
    for team in values:
        members = set(team_members.get(team, []))
        if members and record_users.intersection(members):
            return True
    return False


def _item_user_values(item):
    values = []
    for key in ("user", "person", "owner", "assignee", "attendee", "sender", "recipient"):
        values.extend(item.details.get(key, []))
    if item.kind == "S" and not item.details.get("person"):
        values.append("self")
    return values


def _record_user_values(record):
    details = record.get("details", {})
    values = []
    for key in ("user", "person", "owner", "assignee", "attendee", "sender", "recipient"):
        values.extend(details.get(key, []))
    if record.get("type") == "S" and not details.get("person"):
        values.append("self")
    return values


def _record_matches_detail_filters(record, filters):
    details = record.get("details", {})
    for key, value in filters:
        if not key:
            return False
        if key not in details:
            return False
        if value is not None and value not in details.get(key, []):
            return False
    return True


def _item_matches_detail_filters(item, filters):
    for key, value in filters:
        if not key:
            return False
        if key not in item.details:
            return False
        if value is not None and value not in item.details.get(key, []):
            return False
    return True


def _record_search_text(record):
    parts = [
        record.get("status", ""),
        record.get("type", ""),
        record.get("title", ""),
        record.get("text", ""),
    ]
    for values in record.get("details", {}).values():
        parts.extend(values)
    return " ".join(parts)


def _item_search_text(item):
    parts = [
        item.status,
        item.kind,
        item.title,
        _item_line_text(item),
        item_to_line(item),
    ]
    for values in item.details.values():
        parts.extend(values)
    return " ".join(parts)


def _item_line_text(item):
    if getattr(item, "source_text", None):
        return item.source_text
    return item_to_line(item)
