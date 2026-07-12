import hashlib
import json
import sys
import time
from collections import OrderedDict
from datetime import datetime

from .agenda import parse_duration
from .atomic import atomic_write_json
from .serializer import item_to_line
from .timeutil import format_datetime as format_life_datetime, parse_date_or_datetime, parse_datetime


NOTIFIABLE_STATUSES = ("[ ]", "[/]", "[>]", "[?]")


def notification_records(
    items,
    recipient=None,
    now=None,
    lookahead="0m",
    grace="2m",
):
    if now is None:
        now = datetime.now().replace(second=0, microsecond=0)
    if recipient is None:
        recipient = "self"

    start = now - _safe_duration(grace, "2m")
    end = now + _safe_duration(lookahead, "0m")

    records = []
    for item in items:
        if item.kind != "M":
            continue
        if item.status not in NOTIFIABLE_STATUSES:
            continue
        if recipient and recipient not in item.details.get("recipient", []):
            continue
        if _notification_suppressed(item, now):
            continue

        matches = _notification_matches(item, start, now, end)
        for match in matches:
            records.append(_notification_record(item, match))

    records.sort(key=lambda record: (record.get("when", ""), record.get("id", "")))
    return records


def records_to_json(records, pretty=False):
    return json.dumps(
        records,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )


def records_to_jsonl(records):
    return "\n".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    )


def format_notification_table(records):
    if not records:
        return "No notifications found.\n"

    columns = (
        ("when", "when"),
        ("sender", "sender"),
        ("recipients", "recipients"),
        ("status", "status"),
        ("title", "title"),
    )
    rows = []
    for record in records:
        row = OrderedDict()
        for key, _heading in columns:
            value = record.get(key, "")
            if isinstance(value, list):
                value = ",".join(value)
            row[key] = str(value)
        rows.append(row)

    widths = []
    for key, heading in columns:
        width = len(heading)
        for row in rows:
            width = max(width, len(row[key]))
        widths.append(width)

    lines = []
    lines.append(_format_row([heading for _key, heading in columns], widths))
    lines.append(_format_row(["-" * width for width in widths], widths))
    for row in rows:
        lines.append(_format_row([row[key] for key, _heading in columns], widths))
    return "\n".join(lines) + "\n"


def format_notification_email(records, recipient=None):
    lines = ["lifetxt notifications", ""]
    if recipient:
        lines.append("Recipient: %s" % recipient)
    lines.append("Count: %d" % len(records))
    if not records:
        lines.append("")
        lines.append("No notifications found.")
        return "\n".join(lines) + "\n"

    lines.append("")
    for index, record in enumerate(records, start=1):
        lines.append("%d. %s" % (index, record.get("title", "")))
        lines.append("   When: %s" % record.get("when", ""))
        if record.get("until"):
            lines.append("   Until: %s" % record.get("until", ""))
        if record.get("sender"):
            lines.append("   From: %s" % record.get("sender", ""))
        recipients = record.get("recipients") or []
        if recipients:
            lines.append("   To: %s" % ", ".join(str(value) for value in recipients))
        if record.get("id"):
            lines.append("   ID: %s" % record.get("id"))
        if record.get("source") or record.get("line"):
            source = record.get("source") or ""
            line = record.get("line") or ""
            lines.append("   Source: %s%s" % (source, (":%s" % line) if line else ""))
        body = str(record.get("body") or "").strip()
        if body:
            lines.append("   Body: %s" % body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def notification_email_subject(records, base="lifetxt notifications"):
    count = len(records or [])
    suffix = "1 due message" if count == 1 else "%d due messages" % count
    return "%s: %s" % (base or "lifetxt notifications", suffix)


def notify_desktop(record):
    title = "life.txt"
    message = "%s\n%s" % (record.get("title", ""), record.get("body", ""))
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
            return True
        except Exception:
            return False
    return False


def watch_notifications(
    load_records,
    interval_seconds=30,
    desktop=False,
    deliver=None,
    once=False,
    output=None,
    state_file=None,
):
    if output is None:
        output = sys.stdout
    state = load_notification_state(state_file)
    seen = set(state.get("seen", {}).keys())
    while True:
        records = load_records()
        emitted = []
        for record in records:
            key = record.get("notification_id")
            if key in seen:
                continue
            seen.add(key)
            emitted.append(record)
            output.write(_watch_line(record) + "\n")
            output.flush()
            if desktop:
                notify_desktop(record)
        if emitted and deliver:
            deliver(emitted)
        if emitted and state_file:
            mark_notifications_seen(state, emitted)
            save_notification_state(state_file, state)
        if once:
            return 0
        time.sleep(max(1, int(interval_seconds)))


def load_notification_state(path):
    if not path:
        return _empty_state()
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle, object_pairs_hook=OrderedDict)
    except (OSError, ValueError):
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    seen = data.get("seen")
    if isinstance(seen, list):
        data["seen"] = OrderedDict((str(value), OrderedDict()) for value in seen)
    elif not isinstance(seen, dict):
        data["seen"] = OrderedDict()
    data.setdefault("version", 1)
    return data


def save_notification_state(path, state):
    if not path:
        return
    atomic_write_json(path, state)


def mark_notifications_seen(state, records, now=None):
    if now is None:
        now = datetime.now().replace(second=0, microsecond=0)
    seen = state.setdefault("seen", OrderedDict())
    for record in records:
        key = record.get("notification_id")
        if not key:
            continue
        seen[key] = OrderedDict(
            [
                ("seen_at", _format_datetime(now)),
                ("id", record.get("id", "")),
                ("title", record.get("title", "")),
                ("when", record.get("when", "")),
            ]
        )


def _notification_matches(item, start, now, end):
    matches = []
    for value in item.details.get("notify_at", []):
        point = parse_datetime(value)
        if point is not None and start <= point <= end:
            matches.append(("notify_at", point, point))

    starts = item.details.get("notify_from", [])
    ends = item.details.get("notify_to", [])
    for index, raw_start in enumerate(starts):
        period_start = parse_datetime(raw_start)
        if period_start is None:
            continue
        period_end = None
        if index < len(ends):
            period_end = parse_datetime(ends[index])
        elif len(ends) == 1:
            period_end = parse_datetime(ends[0])
        if period_end is None:
            period_end = period_start
        if period_start <= now <= period_end or _overlaps(period_start, period_end, start, end):
            matches.append(("notify_from/to", period_start, period_end))

    return matches


def _notification_suppressed(item, now):
    if item.details.get("ack"):
        return True
    for value in item.details.get("snooze_until", []):
        snooze_until = parse_date_or_datetime(value)
        if snooze_until is not None and snooze_until > now:
            return True
    return False


def _notification_record(item, match):
    key, start, end = match
    details = _copy_details(item.details)
    line_text = getattr(item, "source_text", None) or item_to_line(item)
    item_id = _first(details, "id")
    notification_id = item_id or _fallback_id(item, line_text)

    record = OrderedDict()
    record["notification_id"] = "%s:%s:%s" % (
        notification_id,
        key,
        _format_datetime(start),
    )
    if item_id:
        record["id"] = item_id
    record["when"] = _format_datetime(start)
    if end is not None and end != start:
        record["until"] = _format_datetime(end)
    record["key"] = key
    if item.line is not None:
        record["line"] = item.line
    record["source"] = getattr(item, "source", None)
    record["status"] = item.status
    record["type"] = item.kind
    record["title"] = item.title
    record["body"] = _first(details, "body") or _first(details, "note") or line_text
    record["sender"] = _first(details, "sender") or ""
    record["recipients"] = list(details.get("recipient", []))
    record["details"] = details
    record["text"] = line_text
    return record


def _safe_duration(value, default):
    try:
        return parse_duration(value)
    except ValueError:
        return parse_duration(default)


def _format_datetime(value):
    return format_life_datetime(value)


def _overlaps(start, end, range_start, range_end):
    return start <= range_end and end >= range_start


def _copy_details(details):
    copied = OrderedDict()
    for key, values in details.items():
        copied[key] = list(values)
    return copied


def _first(details, key):
    values = details.get(key)
    if values:
        return values[0]
    return None


def _fallback_id(item, line_text):
    if item.line is not None and getattr(item, "source", None):
        return "%s:%s" % (item.source, item.line)
    if item.line is not None:
        return "line:%s" % item.line
    digest = hashlib.sha256(line_text.encode("utf-8")).hexdigest()[:16]
    return "sha256:%s" % digest


def _empty_state():
    return OrderedDict([("version", 1), ("seen", OrderedDict())])


def _format_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"


def _watch_line(record):
    return "[%s] %s -> %s: %s" % (
        record.get("when", ""),
        record.get("sender", ""),
        ",".join(record.get("recipients", [])),
        record.get("title", ""),
    )
