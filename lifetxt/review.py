"""Review aggregation shared by the CLI, Web API, Web UI, and MCP server.

`resolve_review_range` turns week/month/from/to selectors into a concrete
date window, and `build_review` aggregates completed tasks, habit
completion, journal entries, mood trend, and elapsed time for that window.
The CLI `review` command, `GET /api/review`, and the MCP `get_review` tool
all produce the same result shape from these two functions.
"""

import calendar
import datetime

from .timezone_policy import today as timezone_today

from .stats import longest_streak_days, streak_days
from .timeutil import parse_elapsed

OPEN_TASK_STATUSES = ("[ ]", "[/]", "[>]", "[?]")
NAMED_REVIEW_RANGES = ("last-week", "last-month", "year")


def parse_date_only(value):
    """Parse the YYYY-MM-DD prefix of a date or datetime string, or None."""
    s = str(value)
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        try:
            return datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
        except (ValueError, IndexError):
            pass
    return None


def latest_item_date(item):
    """Return the most recent parsed date from common date detail keys."""
    best = None
    for key in ("updated", "created", "done", "do", "due", "on"):
        for val in item.details.get(key, []):
            parsed = parse_date_only(str(val))
            if parsed and (best is None or parsed > best):
                best = parsed
    return best


def resolve_named_review_range(selector, year=None, today=None):
    """Resolve last-week, last-month, or year through the shared range rules.

    This is the single public implementation used by the Web request adapter,
    MCP, and future CLI/TUI saved ranges.  It delegates final validation and
    date-window construction to :func:`resolve_review_range`.
    """
    today = today or timezone_today()
    selector = str(selector or "").strip().lower()
    if selector not in NAMED_REVIEW_RANGES:
        raise ValueError(
            "Unknown review range %r. Use %s."
            % (selector, ", ".join(NAMED_REVIEW_RANGES))
        )
    if selector == "last-week":
        current_monday = today - datetime.timedelta(days=today.weekday())
        start = current_monday - datetime.timedelta(days=7)
        end = current_monday - datetime.timedelta(days=1)
        return resolve_review_range(
            from_date=start.isoformat(),
            to_date=end.isoformat(),
            today=today,
        )
    if selector == "last-month":
        first_this_month = today.replace(day=1)
        previous = first_this_month - datetime.timedelta(days=1)
        return resolve_review_range(
            month="%04d-%02d" % (previous.year, previous.month),
            today=today,
        )
    selected_year = today.year if year in (None, "") else int(year)
    if selected_year < 1 or selected_year > 9999:
        raise ValueError("Review year must be between 1 and 9999.")
    return resolve_review_range(
        from_date="%04d-01-01" % selected_year,
        to_date="%04d-12-31" % selected_year,
        today=today,
    )


def resolve_review_range(week=False, month=None, from_date=None, to_date=None, today=None):
    """Return the (start, end) date window for a review.

    Selector precedence matches the CLI flags: week, then month, then
    from/to with current-week-start and today as fallbacks. Raises
    ValueError for malformed month or date values.
    """
    today = today or timezone_today()
    if week:
        start = today - datetime.timedelta(days=today.weekday())
        return start, start + datetime.timedelta(days=6)
    if month:
        try:
            year_s, month_s = str(month).split("-")
            year_i, month_i = int(year_s), int(month_s)
            start = datetime.date(year_i, month_i, 1)
        except (ValueError, AttributeError):
            raise ValueError("Invalid month %r. Use YYYY-MM." % (month,))
        return start, datetime.date(year_i, month_i, calendar.monthrange(year_i, month_i)[1])
    start = parse_date_only(from_date) if from_date else None
    end = parse_date_only(to_date) if to_date else None
    if from_date and start is None:
        raise ValueError("Invalid from date %r. Use YYYY-MM-DD." % (from_date,))
    if to_date and end is None:
        raise ValueError("Invalid to date %r. Use YYYY-MM-DD." % (to_date,))
    if start is None:
        start = today - datetime.timedelta(days=today.weekday())
    if end is None:
        end = today
    return start, end


def format_review_elapsed(minutes):
    """Format elapsed minutes the way the review report does (1h5m, 45m)."""
    if minutes >= 60:
        return "%dh%dm" % (minutes // 60, minutes % 60)
    return "%dm" % minutes


def build_review(items, start, end, project=None, id_key="id", today=None):
    """Aggregate a review report dict for items inside the date window."""
    today = today or timezone_today()
    if project:
        items = [i for i in items if project in [str(v) for v in i.details.get("project", [])]]

    completed_tasks = []
    open_tasks = 0
    habits = {}
    journal_entries = []
    moods = []
    elapsed_by_project = {}

    for item in items:
        if item.kind == "T":
            if item.status == "[x]":
                done_dates = [parse_date_only(str(v)) for v in item.details.get("done", [])]
                if any(d and start <= d <= end for d in done_dates):
                    completed_tasks.append(item)
            elif item.status in OPEN_TASK_STATUSES:
                open_tasks += 1

        elif item.kind == "H":
            bucket = habits.setdefault(item.title, {"done": 0, "open": 0, "dates": set()})
            if item.status == "[x]":
                bucket["done"] += 1
            elif item.status in ("[ ]", "[/]"):
                bucket["open"] += 1
            # Collect per-day completion dates so real streaks can be derived
            # instead of the earlier placeholder that reported no streaks.
            done_dates = [parse_date_only(str(v)) for v in item.details.get("done", [])]
            for d in done_dates:
                if d is not None:
                    bucket["dates"].add(d)
            if item.status == "[x]" and not done_dates:
                item_date = latest_item_date(item)
                if item_date is not None:
                    bucket["dates"].add(item_date)

        elif item.kind == "J":
            j_date = latest_item_date(item) or today
            if start <= j_date <= end:
                body_vals = item.details.get("body", [])
                excerpt = str(body_vals[0])[:200] if body_vals else ""
                journal_entries.append((j_date, item.title, excerpt))
                mood_vals = item.details.get("mood", [])
                if mood_vals:
                    moods.append((j_date, str(mood_vals[0])))

        elapsed_vals = item.details.get("elapsed", [])
        if elapsed_vals:
            minutes = parse_elapsed(str(elapsed_vals[0]))
            if minutes:
                proj = str(item.details.get("project", ["(no project)"])[0])
                elapsed_by_project[proj] = elapsed_by_project.get(proj, 0) + minutes

    def first_detail(item, key):
        values = item.details.get(key, [])
        return str(values[0]) if values else ""

    return {
        "range": "%s to %s" % (start.isoformat(), end.isoformat()),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "completed_tasks": len(completed_tasks),
        "open_tasks": open_tasks,
        "completed": [
            {
                "title": t.title,
                "done": first_detail(t, "done"),
                "project": first_detail(t, "project"),
                "id": first_detail(t, id_key),
            }
            for t in completed_tasks
        ],
        "habits": {
            title: {
                "done": h["done"],
                "open": h["open"],
                "completion_rate": (
                    round(h["done"] / (h["done"] + h["open"]) * 100)
                    if (h["done"] + h["open"] > 0) else 0
                ),
                "current_streak": streak_days(h["dates"], today),
                "longest_streak": longest_streak_days(h["dates"]),
            }
            for title, h in habits.items()
        },
        "journals": len(journal_entries),
        "journal_entries": [
            {"date": d.isoformat(), "title": t, "excerpt": e}
            for d, t, e in sorted(journal_entries)
        ],
        "mood_trend": [
            {"date": d.isoformat(), "mood": m} for d, m in sorted(moods)
        ],
        "elapsed_by_project": {
            proj: format_review_elapsed(m)
            for proj, m in sorted(elapsed_by_project.items(), key=lambda x: -x[1])
        },
    }
