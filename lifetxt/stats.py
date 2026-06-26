import json
import sys
from collections import OrderedDict
from datetime import date, timedelta

from .model import normalize_type
from .parser import parse_text
from .timeutil import parse_date, parse_date_or_datetime


SPARK = "._-="
MISSING = " "
MOOD_VALUES = {"bad": 1, "neutral": 2, "ok": 2, "good": 3, "great": 4}


def cmd_stats(args):
    start, end = stats_range(args.start, args.end)
    items = load_items(args.paths)
    kind = normalize_type(args.kind) if args.kind else None
    if kind:
        items = [item for item in items if item.kind == kind]
    if args.project:
        items = [item for item in items if args.project in item.details.get("project", [])]
    buckets = make_buckets(start, end, args.group)
    data = build_stats(items, start, end, args.group, buckets)
    if args.format == "json":
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(format_stats(data))
    return 0


def stats_range(start_text=None, end_text=None, today=None):
    if today is None:
        today = date.today()
    if end_text:
        end_date = _parse_date_only(end_text)
    else:
        end_date = today
    if start_text:
        start_date = _parse_date_only(start_text)
    else:
        start_date = end_date - timedelta(days=29)
    if end_date < start_date:
        raise ValueError("--to must not be earlier than --from.")
    return start_date, end_date


def build_stats(items, start, end, group, buckets=None):
    if buckets is None:
        buckets = make_buckets(start, end, group)
    tasks = [item for item in items if item.kind == "T" and item_in_date_range(item, start, end)]
    done_tasks = [item for item in tasks if item.status == "[x]"]
    overdue = [item for item in tasks if item.status != "[x]" and _is_overdue(item, end)]
    by_project = project_stats(tasks)
    habits = habit_stats([item for item in items if item.kind == "H"], start, end, buckets)
    mood = mood_stats([item for item in items if item.kind == "J"], buckets)
    data = OrderedDict()
    data["range"] = OrderedDict([("from", start.isoformat()), ("to", end.isoformat()), ("group", group)])
    data["tasks"] = OrderedDict(
        [
            ("done", len(done_tasks)),
            ("total", len(tasks)),
            ("rate", _rate(len(done_tasks), len(tasks))),
            ("overdue", len(overdue)),
            ("buckets", task_bucket_stats(tasks, buckets)),
        ]
    )
    data["habits"] = habits
    data["mood"] = mood
    data["by_project"] = by_project
    data["journal_entries"] = len([item for item in items if item.kind == "J" and item_in_date_range(item, start, end)])
    return data


def format_stats(data):
    lines = []
    lines.append("lifetxt stats  %s - %s" % (data["range"]["from"], data["range"]["to"]))
    lines.append("=" * 39)
    tasks = data["tasks"]
    lines.append("")
    lines.append("Tasks")
    lines.append(
        "  done   %s / %s  (%s%%)  %s"
        % (tasks["done"], tasks["total"], tasks["rate"], progress_bar(tasks["rate"]))
    )
    lines.append("  overdue  %s" % tasks["overdue"])
    if tasks.get("buckets") and len(tasks["buckets"]) > 1:
        lines.append("  buckets")
        for bucket in tasks["buckets"]:
            lines.append(
                "    %s  done %s / %s  overdue %s"
                % (
                    bucket_label(bucket),
                    bucket["done"],
                    bucket["total"],
                    bucket["overdue"],
                )
            )
    lines.append("")
    lines.append("Habits")
    if data["habits"]:
        for habit in data["habits"]:
            lines.append("  %-20s streak %3sd  %s" % (habit["title"], habit["streak"], habit["sparkline"]))
    else:
        lines.append("  No habit data.")
    lines.append("")
    lines.append("Mood")
    mood = data["mood"]
    if mood["counts"]:
        counts = "  " + "  ".join("%s %sd" % (key, value) for key, value in mood["counts"].items())
        lines.append(counts)
        lines.append("  %s" % mood["sparkline"])
    else:
        lines.append("  No mood data.")
    lines.append("")
    lines.append("By project")
    if data["by_project"]:
        for project, values in data["by_project"].items():
            lines.append(
                "  %-12s done %s / %s  (%s%%)"
                % (project or "(none)", values["done"], values["total"], values["rate"])
            )
    else:
        lines.append("  No project data.")
    lines.append("")
    lines.append("Journal entries  %s entries" % data["journal_entries"])
    return "\n".join(lines).rstrip() + "\n"


def progress_bar(rate, width=28):
    filled = int((rate * width) / 100)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def sparkline(values):
    if not values:
        return ""
    present = [value for value in values if value is not None]
    if not present:
        return MISSING * len(values)
    low = min(present)
    high = max(present)
    chars = []
    for value in values:
        if value is None:
            chars.append(MISSING)
        elif high == low:
            chars.append(SPARK[-1])
        else:
            index = int(round((value - low) * (len(SPARK) - 1) / float(high - low)))
            chars.append(SPARK[index])
    return "".join(chars)


def make_buckets(start, end, group):
    buckets = []
    current = start
    while current <= end:
        if group == "weekly":
            bucket_end = min(end, current + timedelta(days=6))
        elif group == "monthly":
            next_month = _add_month(current)
            bucket_end = min(end, next_month - timedelta(days=1))
        else:
            bucket_end = current
        buckets.append((current, bucket_end))
        current = bucket_end + timedelta(days=1)
    return buckets


def task_bucket_stats(tasks, buckets):
    result = []
    for bucket_start, bucket_end in buckets:
        bucket_tasks = []
        for item in tasks:
            item_date = item_date_value(item)
            if item_date is None:
                continue
            if bucket_start <= item_date <= bucket_end:
                bucket_tasks.append(item)
        done = len([item for item in bucket_tasks if item.status == "[x]"])
        overdue = len([item for item in bucket_tasks if item.status != "[x]" and _is_overdue(item, bucket_end)])
        result.append(
            OrderedDict(
                [
                    ("from", bucket_start.isoformat()),
                    ("to", bucket_end.isoformat()),
                    ("done", done),
                    ("total", len(bucket_tasks)),
                    ("rate", _rate(done, len(bucket_tasks))),
                    ("overdue", overdue),
                ]
            )
        )
    return result


def habit_stats(items, start, end, buckets=None):
    result = []
    if buckets is None:
        buckets = make_buckets(start, end, "daily")
    for item in items:
        dates = item_completion_dates(item)
        values = []
        for bucket_start, bucket_end in buckets:
            count = 0
            current = bucket_start
            while current <= bucket_end:
                if current in dates:
                    count += 1
                current += timedelta(days=1)
            values.append(count if count else None)
        result.append(
            OrderedDict(
                [
                    ("title", item.title),
                    ("streak", streak_days(dates, end)),
                    ("sparkline", sparkline(values)),
                ]
            )
        )
    result.sort(key=lambda row: (-row["streak"], row["title"]))
    return result


def mood_stats(items, buckets):
    counts = OrderedDict()
    values = []
    for bucket_start, bucket_end in buckets:
        bucket_values = []
        for item in items:
            item_date = item_date_value(item)
            if item_date is None or item_date < bucket_start or item_date > bucket_end:
                continue
            mood = item.details.get("mood", [""])[0].lower() if item.details.get("mood") else ""
            if mood:
                counts[mood] = counts.get(mood, 0) + 1
            if mood in MOOD_VALUES:
                bucket_values.append(MOOD_VALUES[mood])
        if bucket_values:
            values.append(sum(bucket_values) / float(len(bucket_values)))
        else:
            values.append(None)
    return OrderedDict([("counts", counts), ("sparkline", sparkline(values))])


def project_stats(tasks):
    result = OrderedDict()
    for item in tasks:
        projects = item.details.get("project") or [""]
        for project in projects:
            entry = result.setdefault(project, OrderedDict([("done", 0), ("total", 0), ("rate", 0)]))
            entry["total"] += 1
            if item.status == "[x]":
                entry["done"] += 1
    for values in result.values():
        values["rate"] = _rate(values["done"], values["total"])
    return result


def bucket_label(bucket):
    if bucket["from"] == bucket["to"]:
        return bucket["from"]
    return "%s..%s" % (bucket["from"], bucket["to"])


def item_completion_dates(item):
    dates = set()
    for value in item.details.get("done", []):
        parsed = _date_from_value(value)
        if parsed:
            dates.add(parsed)
    if not dates and item.status == "[x]":
        item_date = item_date_value(item)
        if item_date:
            dates.add(item_date)
    return dates


def streak_days(dates, end):
    count = 0
    current = end
    while current in dates:
        count += 1
        current -= timedelta(days=1)
    return count


def item_in_date_range(item, start, end):
    item_date = item_date_value(item)
    if item_date is None:
        return True
    return start <= item_date <= end


def item_date_value(item):
    for key in ("done", "on", "due", "do", "from", "created", "updated"):
        for value in item.details.get(key, []):
            parsed = _date_from_value(value)
            if parsed:
                return parsed
    return None


def load_items(paths):
    items = []
    for path in paths:
        with open(path, "r", encoding="utf-8-sig") as handle:
            path_items, diagnostics = parse_text(handle.read())
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
        if errors:
            raise ValueError(errors[0].format())
        items.extend(path_items)
    return items


def _is_overdue(item, today):
    for value in item.details.get("due", []):
        parsed = _date_from_value(value)
        if parsed and parsed < today:
            return True
    return False


def _date_from_value(value):
    parsed_date = parse_date(value)
    if parsed_date:
        return parsed_date
    parsed = parse_date_or_datetime(value, is_end=False)
    if parsed:
        return parsed.date()
    return None


def _parse_date_only(value):
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError("Expected YYYY-MM-DD: %s" % value)
    return parsed


def _rate(done, total):
    if not total:
        return 0
    return int(round((done * 100.0) / total))


def _add_month(value):
    year = value.year
    month = value.month + 1
    if month > 12:
        year += 1
        month = 1
    return date(year, month, 1)
