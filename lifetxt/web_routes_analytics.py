"""Read-only analytics routes registered by :mod:`lifetxt.webapp`.

FastAPI is imported inside :func:`register_analytics_routes` so importing the
module does not change the dependency-free core import policy.
"""

from datetime import timedelta

from .stats import MOOD_VALUES, item_completion_dates, item_date_value
from .stats import make_buckets, project_stats, stats_range, streak_days
from .stats import task_bucket_stats


def register_analytics_routes(app, read_life_inputs, elapsed_to_minutes):
    """Attach chart and summary routes to ``app`` without changing contracts."""
    from fastapi import Query

    @app.get("/api/chart/tasks")
    def chart_tasks(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        group="daily",
        project=None,
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        tasks = [item for item in items if item.kind == "T"]
        if project:
            tasks = [
                item for item in tasks if project in item.details.get("project", [])
            ]
        bucket_stats = task_bucket_stats(tasks, make_buckets(s, e, group))
        labels = [
            b["from"] if b["from"] == b["to"] else "%s/%s" % (b["from"], b["to"])
            for b in bucket_stats
        ]
        return {
            "labels": labels,
            "datasets": [
                {"label": "done", "data": [b["done"] for b in bucket_stats]},
                {"label": "total", "data": [b["total"] for b in bucket_stats]},
                {"label": "overdue", "data": [b["overdue"] for b in bucket_stats]},
            ],
            "range": {"from": s.isoformat(), "to": e.isoformat(), "group": group},
        }

    @app.get("/api/chart/habits")
    def chart_habits(
        start=Query(None, alias="from"), end=Query(None, alias="to"), group="daily"
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        habit_items = [item for item in items if item.kind == "H"]
        buckets = make_buckets(s, e, group)
        labels = [
            b[0].isoformat()
            if b[0] == b[1]
            else "%s/%s" % (b[0].isoformat(), b[1].isoformat())
            for b in buckets
        ]
        datasets = []
        for habit in habit_items:
            dates = item_completion_dates(habit)
            data = []
            for bucket_start, bucket_end in buckets:
                count = sum(
                    1
                    for offset in range((bucket_end - bucket_start).days + 1)
                    if bucket_start + timedelta(days=offset) in dates
                )
                data.append(count)
            bucket_size = (
                max(1, (buckets[0][1] - buckets[0][0]).days + 1) if buckets else 1
            )
            datasets.append(
                {
                    "label": habit.title,
                    "streak": streak_days(dates, e),
                    "data": data,
                    "bucket_size": bucket_size,
                }
            )
        datasets.sort(key=lambda data: (-data["streak"], data["label"]))
        return {
            "labels": labels,
            "datasets": datasets,
            "range": {"from": s.isoformat(), "to": e.isoformat(), "group": group},
        }

    @app.get("/api/chart/mood")
    def chart_mood(
        start=Query(None, alias="from"), end=Query(None, alias="to"), group="daily"
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        journal_items = [item for item in items if item.kind == "J"]
        buckets = make_buckets(s, e, group)
        labels = [
            b[0].isoformat()
            if b[0] == b[1]
            else "%s/%s" % (b[0].isoformat(), b[1].isoformat())
            for b in buckets
        ]
        counts = {}
        data = []
        for bucket_start, bucket_end in buckets:
            bucket_values = []
            for item in journal_items:
                item_date = item_date_value(item)
                if (
                    item_date is None
                    or item_date < bucket_start
                    or item_date > bucket_end
                ):
                    continue
                mood_val = (
                    item.details.get("mood", [""])[0].lower()
                    if item.details.get("mood")
                    else ""
                )
                if mood_val:
                    counts[mood_val] = counts.get(mood_val, 0) + 1
                if mood_val in MOOD_VALUES:
                    bucket_values.append(MOOD_VALUES[mood_val])
            data.append(
                round(sum(bucket_values) / len(bucket_values), 2)
                if bucket_values
                else None
            )
        return {
            "labels": labels,
            "datasets": [{"label": "mood", "data": data}],
            "mood_scale": MOOD_VALUES,
            "counts": counts,
            "range": {"from": s.isoformat(), "to": e.isoformat(), "group": group},
        }

    @app.get("/api/chart/elapsed")
    def chart_elapsed(
        start=Query(None, alias="from"), end=Query(None, alias="to"), project=None
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        elapsed_by_project = {}
        for item in items:
            item_date = item_date_value(item)
            if item_date is not None and (item_date < s or item_date > e):
                continue
            for elapsed_val in item.details.get("elapsed", []):
                minutes = elapsed_to_minutes(elapsed_val)
                if minutes is None:
                    continue
                for proj in item.details.get("project") or ["(none)"]:
                    if project and proj != project:
                        continue
                    elapsed_by_project[proj] = elapsed_by_project.get(proj, 0) + minutes
        sorted_projects = sorted(
            elapsed_by_project.items(), key=lambda entry: -entry[1]
        )
        return {
            "labels": [project for project, _ in sorted_projects],
            "datasets": [
                {
                    "label": "elapsed (min)",
                    "data": [value for _, value in sorted_projects],
                }
            ],
            "range": {"from": s.isoformat(), "to": e.isoformat()},
        }

    @app.get("/api/chart/habits-heatmap")
    def chart_habits_heatmap(
        start=Query(None, alias="from"), end=Query(None, alias="to")
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        result = []
        for item in (item for item in items if item.kind == "H"):
            dates = item_completion_dates(item)
            result.append(
                {
                    "title": item.title,
                    "dates": {date.isoformat(): 1 for date in dates if s <= date <= e},
                    "streak": streak_days(dates, e),
                }
            )
        result.sort(key=lambda entry: (-entry["streak"], entry["title"]))
        return {"habits": result, "range": {"from": s.isoformat(), "to": e.isoformat()}}

    @app.get("/api/stats/summary")
    def stats_summary(
        start=Query(None, alias="from"), end=Query(None, alias="to"), project=None
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        tasks = [item for item in items if item.kind == "T"]
        if project:
            tasks = [
                item for item in tasks if project in item.details.get("project", [])
            ]
        by_project = project_stats(tasks)
        by_type = {}
        by_status = {}
        for item in items:
            by_type[item.kind] = by_type.get(item.kind, 0) + 1
            by_status[item.status] = by_status.get(item.status, 0) + 1
        top_projects = sorted(by_project.items(), key=lambda entry: -entry[1]["total"])[
            :10
        ]
        return {
            "total": len(items),
            "by_type": by_type,
            "by_status": by_status,
            "by_project": [
                {
                    "project": key or "(none)",
                    "done": value["done"],
                    "total": value["total"],
                    "rate": value["rate"],
                }
                for key, value in top_projects
            ],
            "range": {"from": s.isoformat(), "to": e.isoformat()},
        }
