import os
import tempfile
from collections import OrderedDict
from datetime import datetime

from .agenda import (
    agenda_records,
    filter_items,
    parse_duration,
    parse_agenda_range,
    parse_optional_time_range,
)
from .config import (
    config_notification_recipient,
    config_section,
    config_tag_aliases,
    config_team_aliases,
    config_team_members,
    config_user_aliases,
    config_user_name,
)
from .ids import (
    auto_ids_enabled,
    collect_item_ids,
    duplicate_id_diagnostics,
    ensure_item_id,
    id_key_from_config,
    id_prefix_for_item,
)
from .links import (
    build_id_index,
    dependency_blocker_records,
    item_id_values,
    link_records,
    reference_diagnostics,
)
from .stats import (
    MOOD_VALUES,
    build_stats,
    habit_stats,
    item_date_value,
    make_buckets,
    mood_stats,
    project_stats,
    stats_range,
    task_bucket_stats,
)
from .markdown import item_markdown_payload
from .model import Diagnostic, Item
from .notifier import notification_records
from .parser import parse_text
from .paths import expand_paths
from .serializer import item_from_dict, item_to_line
from .status_summary import latest_status_records
from .timeutil import format_datetime as format_life_datetime, parse_date_or_datetime
from .validator import validate_item


def create_app(paths=None, writable_path=None, config=None, read_only=False):
    try:
        from fastapi import Body, FastAPI, HTTPException, Query, Request
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Web dependencies are not installed. Run: pip install -r requirements-web.txt"
        ) from exc

    app = FastAPI(
        title="life.txt API",
        version="0.1.0",
        description="life.txt REST API" + (" — read-only demo" if read_only else ""),
    )
    app.state.paths = normalize_server_paths(paths)
    app.state.writable_path = writable_path or app.state.paths[0]
    app.state.config = config or {}
    app.state.read_only = read_only

    _READ_ONLY_ALLOWED_PATHS = frozenset({"/api/check-line", "/api/items/parse"})

    if read_only:
        @app.middleware("http")
        async def _read_only_guard(request: Request, call_next):
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if request.url.path not in _READ_ONLY_ALLOWED_PATHS:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "READ_ONLY",
                            "message": "This is a read-only demo instance. Write operations are disabled.",
                        },
                    )
            return await call_next(request)

    _api_token = (config or {}).get("api", {}).get("token") if config else None
    if _api_token:
        @app.middleware("http")
        async def _bearer_auth(request: Request, call_next):
            if request.url.path in ("/", "/api/health"):
                return await call_next(request)
            auth = request.headers.get("authorization", "")
            if auth != "Bearer " + _api_token:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "UNAUTHORIZED",
                        "message": "Authorization: Bearer TOKEN header required.",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return await call_next(request)

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request, exc):
        detail = exc.detail
        if isinstance(detail, list):
            payload = {
                "error": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "detail": detail,
            }
        elif isinstance(detail, dict) and "error" in detail:
            payload = detail
        else:
            code = "NOT_FOUND" if exc.status_code == 404 else "ERROR"
            payload = {
                "error": code,
                "message": str(detail) if detail is not None else "An error occurred.",
                "detail": None,
            }
        return JSONResponse(status_code=exc.status_code, content=payload)

    def raise_for_errors(diagnostics):
        if _has_error(diagnostics):
            raise HTTPException(
                status_code=400,
                detail=[diagnostic.to_dict() for diagnostic in diagnostics],
            )

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML_PAGE

    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "paths": app.state.paths,
            "writable_path": app.state.writable_path,
            "config_path": app.state.config.get("_path"),
            "user": config_user_name(app.state.config),
            "read_only": app.state.read_only,
        }

    @app.get("/api/config")
    def get_config():
        return {
            "paths": app.state.paths,
            "writable_path": app.state.writable_path,
            "user": config_user_name(app.state.config),
            "notifications": public_notification_config(app.state.config),
            "ids": public_id_config(app.state.config),
            "web": public_web_config(app.state.config),
            "git": public_git_config(app.state.config),
            "views": public_views_config(app.state.config),
            "users": public_users_config(app.state.config),
            "teams": public_teams_config(app.state.config),
            "tags": public_tags_config(app.state.config),
        }

    @app.get("/api/items")
    def get_items(
        open_only=False,
        blocked=False,
        status=None,
        kind=None,
        type_value=Query(None, alias="type"),
        project=None,
        tag=None,
        tag_all=None,
        exclude_tag=None,
        user=None,
        team=None,
        person=None,
        owner=None,
        assignee=None,
        attendee=None,
        sender=None,
        recipient=None,
        text=None,
        q=None,
        after=None,
        before=None,
        sort="line",
        order="asc",
        limit=None,
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        range_start, range_end = parse_optional_time_range(after, before)
        filtered = filter_items(
            items,
            open_only=open_only or bool(blocked and blocked != "false"),
            statuses=_csv_values(status),
            kinds=_csv_values(kind or type_value),
            projects=_csv_values(project),
            tags=_csv_values(tag),
            tag_all=_csv_values(tag_all),
            exclude_tags=_csv_values(exclude_tag),
            users=_csv_values(user),
            persons=_csv_values(person),
            owners=_csv_values(owner),
            assignees=_csv_values(assignee),
            attendees=_csv_values(attendee),
            senders=_csv_values(sender),
            recipients=_csv_values(recipient),
            teams=_csv_values(team),
            text=text or q,
            range_start=range_start,
            range_end=range_end,
            user_aliases=config_user_aliases(app.state.config),
            team_members=config_team_members(app.state.config),
            team_aliases=config_team_aliases(app.state.config),
            tag_aliases=config_tag_aliases(app.state.config),
        )
        if blocked and blocked != "false":
            key = id_key_from_config(app.state.config)
            blocker_records = dependency_blocker_records(items, key=key)
            blocked_item_ids = set(
                r["blocked_id"] for r in blocker_records if r.get("blocked_id")
            )
            blocked_lines = set(
                r["blocked_line"] for r in blocker_records if r.get("blocked_line") is not None
            )
            filtered = [
                item for item in filtered
                if (item.details.get(key) and str(item.details[key][0]) in blocked_item_ids)
                or (item.line is not None and item.line in blocked_lines)
            ]
        filtered = sort_items(filtered, sort, order)
        filtered = limit_items(filtered, limit)
        return items_response(
            filtered,
            diagnostics,
            app.state.writable_path,
            id_key_from_config(app.state.config),
        )

    @app.get("/api/links")
    def get_links(
        item_id=Query(None, alias="id"),
        direction="both",
        relation=None,
        limit=None,
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        records = link_records(
            items,
            key=id_key_from_config(app.state.config),
            focus_id=item_id,
            direction=direction,
            relations=_csv_values(relation),
        )
        records = limit_items(records, limit)
        return links_response(records, diagnostics)

    @app.post("/api/check-line")
    def check_line(payload=Body(...)):
        line = payload.get("line", "") if isinstance(payload, dict) else str(payload or "")
        if not str(line).strip():
            return {"ok": True, "item_count": 0, "diagnostics": []}
        text = str(line).rstrip("\n") + "\n"
        parsed_items, diagnostics = parse_text(text)
        has_error = any(d.severity == "error" for d in diagnostics)
        return {
            "ok": not has_error,
            "item_count": len(parsed_items),
            "diagnostics": [d.to_dict() for d in diagnostics],
        }

    @app.post("/api/items/parse")
    def parse_item_line(payload=Body(...)):
        line = payload.get("line", "") if isinstance(payload, dict) else str(payload or "")
        if not str(line).strip():
            return {"ok": True, "item_count": 0, "diagnostics": [], "items": []}
        text = str(line).rstrip("\n") + "\n"
        id_key = id_key_from_config(app.state.config)
        parsed_items, diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        has_error = any(d.severity == "error" for d in diagnostics)
        response_items = []
        for item in parsed_items:
            data = api_item(item, None, id_key)
            data["source"] = None
            data["editable"] = False
            data["generated"] = False
            response_items.append(data)
        return {
            "ok": not has_error,
            "item_count": len(parsed_items),
            "items": response_items,
            "diagnostics": [d.to_dict() for d in diagnostics],
        }

    @app.get("/api/graph")
    def get_graph(
        root=Query(None),
        depth=Query(None),
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        id_key = id_key_from_config(app.state.config)
        records = link_records(items, key=id_key)
        nodes_map = {}
        edges = []
        for rec in records:
            src_id = rec["source_id"] or rec["source_location"]
            tgt_id = rec["target_id"]
            if src_id not in nodes_map:
                nodes_map[src_id] = {
                    "id": src_id,
                    "title": rec["source_title"],
                    "status": rec["source_status"],
                    "type": rec["source_type"],
                    "missing": False,
                }
            else:
                nodes_map[src_id]["missing"] = False
            if tgt_id and tgt_id not in nodes_map:
                nodes_map[tgt_id] = {
                    "id": tgt_id,
                    "title": rec.get("target_title", tgt_id),
                    "status": rec.get("target_status", ""),
                    "type": rec.get("target_type", ""),
                    "missing": rec.get("status") == "missing",
                }
            edges.append({"source": src_id, "target": tgt_id, "relation": rec["relation"]})
        nodes = list(nodes_map.values())
        if root:
            nodes, edges = _subgraph(nodes, edges, root, depth)
        return {"nodes": nodes, "edges": edges}

    @app.get("/api/blockers")
    def get_blockers(
        item_id=Query(None, alias="id"),
        depth=Query(None),
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        key = id_key_from_config(app.state.config)
        if not item_id:
            raise HTTPException(status_code=422, detail="Query parameter 'id' is required.")
        focus = find_item_by_id(items, item_id, key=key)
        if focus is None:
            raise HTTPException(status_code=404, detail=f"No item with id {item_id!r}.")
        try:
            max_depth = max(1, min(int(depth), 10)) if depth is not None else 5
        except (TypeError, ValueError):
            max_depth = 5
        blocker_records = dependency_blocker_records(items, key=key)
        by_blocked_key = {}
        for rec in blocker_records:
            by_blocked_key.setdefault(rec["_blocked_item_key"], []).append(rec)
        chain = []
        visited = {id(focus)}
        frontier = [id(focus)]
        for level in range(1, max_depth + 1):
            next_frontier = []
            for item_key in frontier:
                for rec in by_blocked_key.get(item_key, []):
                    entry = {
                        k: v for k, v in rec.items() if not k.startswith("_")
                    }
                    entry["level"] = level
                    chain.append(entry)
                    blocker_key = rec["_blocker_item_key"]
                    if blocker_key not in visited:
                        visited.add(blocker_key)
                        next_frontier.append(blocker_key)
            if not next_frontier:
                break
            frontier = next_frontier
        return {
            "id": item_id,
            "blocked": any(entry["level"] == 1 for entry in chain),
            "count": len(chain),
            "chain": chain,
        }

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
            tasks = [item for item in tasks if project in item.details.get("project", [])]
        buckets = make_buckets(s, e, group)
        bucket_stats = task_bucket_stats(tasks, buckets)
        labels = [b["from"] if b["from"] == b["to"] else "%s/%s" % (b["from"], b["to"]) for b in bucket_stats]
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
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        group="daily",
    ):
        from .stats import item_completion_dates, streak_days as _streak
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        habit_items = [item for item in items if item.kind == "H"]
        buckets = make_buckets(s, e, group)
        labels = [b[0].isoformat() if b[0] == b[1] else "%s/%s" % (b[0].isoformat(), b[1].isoformat()) for b in buckets]
        datasets = []
        for habit in habit_items:
            dates = item_completion_dates(habit)
            data = []
            for bucket_start, bucket_end in buckets:
                count = 0
                d = bucket_start
                while d <= bucket_end:
                    if d in dates:
                        count += 1
                    d = d + __import__('datetime').timedelta(days=1)
                data.append(count)
            bucket_size = max(1, ((buckets[0][1] - buckets[0][0]).days + 1)) if buckets else 1
            datasets.append({
                "label": habit.title,
                "streak": _streak(dates, e),
                "data": data,
                "bucket_size": bucket_size,
            })
        datasets.sort(key=lambda d: (-d["streak"], d["label"]))
        return {
            "labels": labels,
            "datasets": datasets,
            "range": {"from": s.isoformat(), "to": e.isoformat(), "group": group},
        }

    @app.get("/api/chart/mood")
    def chart_mood(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        group="daily",
    ):
        from datetime import date as _date
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        journal_items = [item for item in items if item.kind == "J"]
        buckets = make_buckets(s, e, group)
        labels = [b[0].isoformat() if b[0] == b[1] else "%s/%s" % (b[0].isoformat(), b[1].isoformat()) for b in buckets]
        counts = {}
        data = []
        for bucket_start, bucket_end in buckets:
            bucket_values = []
            for item in journal_items:
                item_date = item_date_value(item)
                if item_date is None or item_date < bucket_start or item_date > bucket_end:
                    continue
                mood_val = item.details.get("mood", [""])[0].lower() if item.details.get("mood") else ""
                if mood_val:
                    counts[mood_val] = counts.get(mood_val, 0) + 1
                if mood_val in MOOD_VALUES:
                    bucket_values.append(MOOD_VALUES[mood_val])
            data.append(round(sum(bucket_values) / len(bucket_values), 2) if bucket_values else None)
        return {
            "labels": labels,
            "datasets": [{"label": "mood", "data": data}],
            "mood_scale": MOOD_VALUES,
            "counts": counts,
            "range": {"from": s.isoformat(), "to": e.isoformat(), "group": group},
        }

    @app.get("/api/chart/elapsed")
    def chart_elapsed(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        project=None,
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        elapsed_by_project = {}
        for item in items:
            item_date = item_date_value(item)
            if item_date is not None and (item_date < s or item_date > e):
                continue
            for elapsed_val in item.details.get("elapsed", []):
                minutes = _elapsed_to_minutes(elapsed_val)
                if minutes is None:
                    continue
                projects = item.details.get("project") or ["(none)"]
                for proj in projects:
                    if project and proj != project:
                        continue
                    elapsed_by_project[proj] = elapsed_by_project.get(proj, 0) + minutes
        sorted_projects = sorted(elapsed_by_project.items(), key=lambda x: -x[1])
        labels = [p for p, _ in sorted_projects]
        data = [v for _, v in sorted_projects]
        return {
            "labels": labels,
            "datasets": [{"label": "elapsed (min)", "data": data}],
            "range": {"from": s.isoformat(), "to": e.isoformat()},
        }

    @app.get("/api/chart/habits-heatmap")
    def chart_habits_heatmap(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
    ):
        from .stats import item_completion_dates, streak_days
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        habit_items = [item for item in items if item.kind == "H"]
        result = []
        for item in habit_items:
            dates = item_completion_dates(item)
            date_map = {d.isoformat(): 1 for d in dates if s <= d <= e}
            result.append({
                "title": item.title,
                "dates": date_map,
                "streak": streak_days(dates, e),
            })
        result.sort(key=lambda r: (-r["streak"], r["title"]))
        return {
            "habits": result,
            "range": {"from": s.isoformat(), "to": e.isoformat()},
        }

    def _git_guard(request):
        git_config = (app.state.config or {}).get("git", {})
        if not git_config.get("enable_api"):
            raise HTTPException(
                status_code=403,
                detail={"error": "FORBIDDEN", "message": "Git API is not enabled. Set git.enable_api: true in config.", "detail": None},
            )
        host = request.client.host if request.client else None
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(
                status_code=403,
                detail={"error": "FORBIDDEN", "message": "Git API is restricted to loopback access.", "detail": None},
            )

    def _run_git(cmd, cwd=None):
        import subprocess
        result = subprocess.run(
            cmd,
            cwd=cwd or os.path.dirname(os.path.abspath(app.state.writable_path)),
            capture_output=True,
            text=True,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "ok": result.returncode == 0,
        }

    @app.get("/api/git/status")
    def git_status(request: Request):
        _git_guard(request)
        return _run_git(["git", "status", "--short"])

    @app.post("/api/git/pull")
    def git_pull(request: Request):
        _git_guard(request)
        return _run_git(["git", "pull"])

    @app.post("/api/git/commit")
    def git_commit(request: Request, payload=Body(...)):
        _git_guard(request)
        message = payload.get("message", "") if isinstance(payload, dict) else ""
        if not message:
            raise HTTPException(
                status_code=400,
                detail={"error": "ERROR", "message": "commit message is required.", "detail": None},
            )
        writable = app.state.writable_path
        import subprocess
        cwd = os.path.dirname(os.path.abspath(writable))
        add_result = subprocess.run(["git", "add", os.path.abspath(writable)], cwd=cwd, capture_output=True, text=True)
        if add_result.returncode != 0:
            return {"stdout": add_result.stdout, "stderr": add_result.stderr, "exit_code": add_result.returncode, "ok": False}
        return _run_git(["git", "commit", "-m", message], cwd=cwd)

    @app.post("/api/git/push")
    def git_push(request: Request):
        _git_guard(request)
        return _run_git(["git", "push"])

    @app.get("/api/git/log")
    def git_log(request: Request, n: int = 5, count: bool = False):
        _git_guard(request)
        n = min(max(1, n), 50)
        result = _run_git(["git", "log", "--pretty=format:%H\t%s\t%ai", "-%d" % n])
        commits = []
        if result.get("ok") and result.get("stdout"):
            for line in result["stdout"].strip().splitlines():
                parts = line.split("\t", 2)
                if len(parts) >= 2:
                    commits.append({"hash": parts[0][:8], "message": parts[1], "date": parts[2] if len(parts) > 2 else ""})
        total = None
        if count:
            count_result = _run_git(["git", "rev-list", "--count", "HEAD"])
            if count_result.get("ok") and count_result.get("stdout"):
                try:
                    total = int(count_result["stdout"].strip())
                except ValueError:
                    pass
        return {"commits": commits, "ok": result.get("ok", False), "total": total}

    @app.get("/api/stats/summary")
    def stats_summary(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        project=None,
    ):
        from .stats import project_stats, stats_range as _sr
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = _sr(start, end)
        tasks = [item for item in items if item.kind == "T"]
        if project:
            tasks = [item for item in tasks if project in item.details.get("project", [])]
        by_project = project_stats(tasks)
        by_type = {}
        by_status = {}
        for item in items:
            by_type[item.kind] = by_type.get(item.kind, 0) + 1
            by_status[item.status] = by_status.get(item.status, 0) + 1
        top_projects = sorted(by_project.items(), key=lambda x: -x[1]["total"])[:10]
        return {
            "total": len(items),
            "by_type": by_type,
            "by_status": by_status,
            "by_project": [{"project": k or "(none)", "done": v["done"], "total": v["total"], "rate": v["rate"]} for k, v in top_projects],
            "range": {"from": s.isoformat(), "to": e.isoformat()},
        }

    @app.get("/api/review")
    def get_review(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        week=False,
        month=None,
        project=None,
    ):
        from .review import build_review, resolve_review_range

        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        try:
            range_start, range_end = resolve_review_range(
                week=week, month=month, from_date=start, to_date=end
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return build_review(
            items,
            range_start,
            range_end,
            project=project,
            id_key=id_key_from_config(app.state.config),
        )

    @app.get("/api/agenda")
    def get_agenda(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        around=None,
        window="1h",
        open_only=False,
        status=None,
        kind=None,
        type_value=Query(None, alias="type"),
        project=None,
        tag=None,
        tag_all=None,
        exclude_tag=None,
        user=None,
        team=None,
        person=None,
        owner=None,
        assignee=None,
        attendee=None,
        sender=None,
        recipient=None,
        text=None,
        q=None,
        limit=None,
        blocked=None,
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        range_start, range_end = parse_agenda_range(start, end, around, window)
        records = agenda_records(items, range_start, range_end)
        record_items = []
        for record in records:
            item = Item(
                record["status"],
                record["type"],
                record["title"],
                record["details"],
                record.get("line"),
                record.get("text"),
            )
            item.source = record.get("source")
            record_items.append((record, item))
        filtered_items = filter_items(
            [entry[1] for entry in record_items],
            open_only=open_only,
            statuses=_csv_values(status),
            kinds=_csv_values(kind or type_value),
            projects=_csv_values(project),
            tags=_csv_values(tag),
            tag_all=_csv_values(tag_all),
            exclude_tags=_csv_values(exclude_tag),
            users=_csv_values(user),
            persons=_csv_values(person),
            owners=_csv_values(owner),
            assignees=_csv_values(assignee),
            attendees=_csv_values(attendee),
            senders=_csv_values(sender),
            recipients=_csv_values(recipient),
            teams=_csv_values(team),
            text=text or q,
            user_aliases=config_user_aliases(app.state.config),
            team_members=config_team_members(app.state.config),
            team_aliases=config_team_aliases(app.state.config),
            tag_aliases=config_tag_aliases(app.state.config),
        )
        filtered_ids = set(id(item) for item in filtered_items)
        filtered_records = [
            record for record, item in record_items if id(item) in filtered_ids
        ]
        key = id_key_from_config(app.state.config)
        blocked_by_id = {}
        blocked_by_line = {}
        for rec in dependency_blocker_records(items, key=key):
            info = {
                "id": rec["blocker_id"],
                "title": rec["blocker_title"],
                "status": rec["blocker_status"],
                "relation": rec["relation"],
            }
            if rec.get("blocked_id"):
                blocked_by_id.setdefault(str(rec["blocked_id"]), []).append(info)
            if rec.get("blocked_line") is not None:
                blocked_by_line.setdefault(
                    (rec.get("blocked_source"), rec["blocked_line"]), []
                ).append(info)
        for record in filtered_records:
            record_id = None
            details = record.get("details") or {}
            if details.get(key):
                record_id = str(details[key][0])
            blockers = blocked_by_id.get(record_id) if record_id else None
            if blockers is None:
                blockers = blocked_by_line.get(
                    (record.get("source"), record.get("line"))
                )
            record["blocked"] = bool(blockers)
            record["blocked_by"] = blockers or []
        blocked_mode = str(blocked or "").strip().lower()
        if blocked_mode in ("only", "true", "1"):
            filtered_records = [r for r in filtered_records if r["blocked"]]
        elif blocked_mode in ("hide", "none"):
            filtered_records = [r for r in filtered_records if not r["blocked"]]
        filtered_records = limit_items(filtered_records, limit)
        return {"count": len(filtered_records), "records": filtered_records}

    @app.get("/api/status")
    def get_status(person=None, active=False):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        # Untyped query params arrive as raw strings, so "?active=false" must
        # not be treated as truthy.
        active_only = str(active).lower() in ("1", "true", "yes", "on")
        records = latest_status_records(items, person=person, active_only=active_only)
        return {"count": len(records), "records": records}

    @app.get("/api/notifications")
    def get_notifications(recipient=None, lookahead=None, grace=None, limit=None):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        notification_config = config_section(app.state.config, "notifications")
        records = notification_records(
            items,
            recipient=recipient or config_notification_recipient(app.state.config),
            lookahead=lookahead or notification_config.get("lookahead") or "0m",
            grace=grace or notification_config.get("grace") or "2m",
        )
        records = limit_items(records, limit)
        return {"count": len(records), "records": records}

    @app.get("/api/messages")
    def get_messages(
        open_only=False,
        status=None,
        sender=None,
        recipient=None,
        project=None,
        tag=None,
        tag_all=None,
        exclude_tag=None,
        user=None,
        team=None,
        text=None,
        q=None,
        after=None,
        before=None,
        sort="time",
        order="asc",
        limit=None,
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        range_start, range_end = parse_optional_time_range(after, before)
        filtered = filter_items(
            items,
            open_only=open_only,
            statuses=_csv_values(status),
            kinds=("M",),
            projects=_csv_values(project),
            tags=_csv_values(tag),
            tag_all=_csv_values(tag_all),
            exclude_tags=_csv_values(exclude_tag),
            users=_csv_values(user),
            senders=_csv_values(sender),
            recipients=_csv_values(recipient),
            teams=_csv_values(team),
            text=text or q,
            range_start=range_start,
            range_end=range_end,
            user_aliases=config_user_aliases(app.state.config),
            team_members=config_team_members(app.state.config),
            team_aliases=config_team_aliases(app.state.config),
            tag_aliases=config_tag_aliases(app.state.config),
        )
        filtered = sort_items(filtered, sort, order)
        filtered = limit_items(filtered, limit)
        return items_response(
            filtered,
            diagnostics,
            app.state.writable_path,
            id_key_from_config(app.state.config),
        )

    @app.get("/api/messages/id/{message_id}")
    def get_message_by_id(message_id):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        try:
            item = find_item_by_id(
                items,
                message_id,
                kind="M",
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        if item is None:
            raise HTTPException(status_code=404, detail="Message id:%s was not found." % message_id)
        return {
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            )
        }

    @app.put("/api/messages/id/{message_id}")
    def update_message_by_id(message_id, payload=Body(...)):
        try:
            item = update_item_by_id_in_file(
                app.state.writable_path,
                message_id,
                payload,
                kind="M",
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "id": message_id,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.delete("/api/messages/id/{message_id}")
    def delete_message_by_id(message_id):
        try:
            deleted = delete_item_by_id_from_file(
                app.state.writable_path,
                message_id,
                kind="M",
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {"id": message_id, "deleted": deleted}

    @app.post("/api/messages/id/{message_id}/ack")
    def ack_message_by_id(message_id, payload=Body(None)):
        try:
            item = ack_message_in_file(
                app.state.writable_path,
                message_id,
                payload,
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "id": message_id,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.post("/api/messages/id/{message_id}/snooze")
    def snooze_message_by_id(message_id, payload=Body(None)):
        try:
            item = snooze_message_in_file(
                app.state.writable_path,
                message_id,
                payload,
                app.state.config,
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "id": message_id,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.get("/api/messages/thread/{thread_id}")
    def get_message_thread(thread_id, limit=None):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        thread = []
        for item in items:
            if item.kind != "M":
                continue
            item_id_key = id_key_from_config(app.state.config)
            if thread_id in item.details.get(item_id_key, []) or thread_id in item.details.get("parent", []):
                thread.append(item)
        thread = sort_items(thread, "time", "asc")
        thread = limit_items(thread, limit)
        return items_response(
            thread,
            diagnostics,
            app.state.writable_path,
            id_key_from_config(app.state.config),
        )

    @app.post("/api/messages/id/{message_id}/reply", status_code=201)
    def reply_to_message(message_id, payload=Body(...)):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        try:
            original = find_item_by_id(
                items,
                message_id,
                kind="M",
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        if original is None:
            raise HTTPException(status_code=404, detail="Message id:%s was not found." % message_id)
        try:
            item = message_reply_from_payload(original, message_id, payload, app.state.config)
            assign_auto_id_from_paths(
                item,
                app.state.config,
                auto_id_paths(app.state.paths, app.state.writable_path),
            )
            line = append_item_to_file(app.state.writable_path, item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "line": line,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.post("/api/messages", status_code=201)
    def create_message(payload=Body(...)):
        try:
            item = message_item_from_payload(payload, app.state.config)
            assign_auto_id_from_paths(
                item,
                app.state.config,
                auto_id_paths(app.state.paths, app.state.writable_path),
            )
            line = append_item_to_file(app.state.writable_path, item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "line": line,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.post("/api/items", status_code=201)
    def create_item(payload=Body(...)):
        try:
            item = item_from_payload(payload)
            assign_auto_id_from_paths(
                item,
                app.state.config,
                auto_id_paths(app.state.paths, app.state.writable_path),
            )
            line = append_item_to_file(app.state.writable_path, item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "line": line,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.post("/api/items/raw", status_code=201)
    def create_item_raw(payload=Body(...)):
        raw = payload.get("line", "") if isinstance(payload, dict) else str(payload or "")
        raw = str(raw).strip()
        if not raw:
            raise HTTPException(status_code=400, detail={"error": "ERROR", "message": "line is required.", "detail": None})
        text = raw.rstrip("\n") + "\n"
        parsed_items, diagnostics = parse_text(text)
        has_error = any(d.severity == "error" for d in diagnostics)
        if has_error or not parsed_items:
            raise HTTPException(
                status_code=422,
                detail={"error": "VALIDATION_ERROR", "message": diagnostics[0].message if diagnostics else "Could not parse line.", "detail": [d.to_dict() for d in diagnostics]},
            )
        writable = app.state.writable_path
        if not writable:
            raise HTTPException(status_code=403, detail={"error": "READONLY", "message": "No writable file configured.", "detail": None})
        ensure_parent_dir(writable)
        existing = read_text(writable) if os.path.exists(writable) else ""
        prefix = "\n" if existing and not existing.endswith(("\n", "\r")) else ""
        write_text(writable, existing + prefix + raw + "\n")
        line_no = len(existing.splitlines()) + 1
        return {
            "line": line_no,
            "item": api_item(parsed_items[0], writable, id_key_from_config(app.state.config)),
        }

    @app.get("/api/items/id/{item_id}")
    def get_item_by_id(item_id):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        try:
            item = find_item_by_id(
                items,
                item_id,
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        if item is None:
            raise HTTPException(status_code=404, detail="Item id:%s was not found." % item_id)
        return {
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            )
        }

    @app.put("/api/items/id/{item_id}")
    def update_item_by_id(item_id, payload=Body(...)):
        try:
            item = update_item_by_id_in_file(
                app.state.writable_path,
                item_id,
                payload,
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "id": item_id,
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.delete("/api/items/id/{item_id}")
    def delete_item_by_id(item_id):
        try:
            deleted = delete_item_by_id_from_file(
                app.state.writable_path,
                item_id,
                key=id_key_from_config(app.state.config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {"id": item_id, "deleted": deleted}

    @app.get("/api/items/{line_no}")
    def get_item_by_line(line_no: int):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        matches = [i for i in items if i.line == line_no]
        if not matches:
            raise HTTPException(status_code=404, detail="No item at line %d." % line_no)
        return {
            "item": api_item(
                matches[0],
                app.state.writable_path,
                id_key_from_config(app.state.config),
            )
        }

    @app.put("/api/items/{line_no}")
    def update_item(line_no, payload=Body(...)):
        try:
            item = update_item_in_file(app.state.writable_path, int(line_no), payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {
            "line": int(line_no),
            "item": api_item(
                item,
                app.state.writable_path,
                id_key_from_config(app.state.config),
            ),
        }

    @app.delete("/api/items/{line_no}")
    def delete_item(line_no):
        try:
            deleted = delete_item_from_file(app.state.writable_path, int(line_no))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {"line": int(line_no), "deleted": deleted}

    return app


def normalize_server_paths(paths):
    if paths is None:
        return ["life.txt"]
    if isinstance(paths, str):
        paths = [paths]
    paths = list(paths)
    return expand_paths(paths or ["life.txt"], stdin_when_empty=False) or ["life.txt"]


def auto_id_paths(paths, writable_path=None):
    candidates = normalize_server_paths(paths)
    if writable_path:
        candidates.append(writable_path)

    normalized = []
    seen = set()
    for path in candidates:
        key = os.path.abspath(path)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return normalized


def read_life_inputs(paths, config=None):
    normalized = normalize_server_paths(paths)
    include_source = len(normalized) > 1
    id_key = id_key_from_config(config or {})
    items = []
    diagnostics = []
    for path in normalized:
        text = read_text(path)
        path_items, path_diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        generated = is_generated_path(path, config)
        for item in path_items:
            item.generated = generated
        if include_source:
            for item in path_items:
                item.source = path
            for diagnostic in path_diagnostics:
                diagnostic.source = path
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
    diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
    diagnostics.extend(reference_diagnostics(items, key=id_key))
    return items, diagnostics


def is_generated_path(path, config=None):
    if not path:
        return False
    targets = []
    sync = config_section(config or {}, "sync_ics")
    output = sync.get("output")
    if output:
        targets.append(output)
    generated_paths = sync.get("generated_paths") or []
    if isinstance(generated_paths, str):
        generated_paths = [generated_paths]
    for value in generated_paths:
        if value:
            targets.append(value)
    abs_path = os.path.abspath(path)
    return any(os.path.abspath(target) == abs_path for target in targets)


def items_response(items, diagnostics, writable_path, id_key="id"):
    return {
        "count": len(items),
        "items": [api_item(item, writable_path, id_key) for item in items],
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def links_response(records, diagnostics):
    return {
        "count": len(records),
        "records": records,
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def public_notification_config(config):
    notifications = config_section(config, "notifications")
    return {
        "enabled": bool(notifications.get("enabled", True)),
        "recipient": config_notification_recipient(config),
        "lookahead": notifications.get("lookahead", "0m"),
        "grace": notifications.get("grace", "2m"),
        "poll_seconds": int(notifications.get("poll_seconds") or 30),
        "state_file": notifications.get("state_file", ""),
        "snooze_default": notifications.get("snooze_default", "10m"),
        "web": bool(notifications.get("web", True)),
    }


def public_id_config(config):
    return {
        "auto": auto_ids_enabled(config),
        "key": id_key_from_config(config),
    }


WEB_THEME_KEYS = (
    "bg",
    "panel",
    "panel_2",
    "soft",
    "ink",
    "muted",
    "line",
    "line_strong",
    "accent",
    "accent_hover",
    "accent_soft",
    "accent_ink",
    "danger",
    "danger_soft",
    "warn",
    "warn_soft",
    "ok",
    "ok_soft",
    "info",
    "info_soft",
    "violet",
    "violet_soft",
    "shadow_1",
    "shadow_2",
    "shadow_3",
    "r_sm",
    "r_md",
    "r_lg",
)

DEFAULT_DASHBOARD_CARDS = ("today", "needs_attention", "completions", "projects")
KNOWN_DASHBOARD_CARDS = set(DEFAULT_DASHBOARD_CARDS)


def _int_or_default(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value):
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _nested_or_dotted(section, key):
    nested = section.get(key)
    data = OrderedDict()
    if isinstance(nested, dict):
        data.update(nested)
    prefix = key + "."
    for raw_key, value in section.items():
        if isinstance(raw_key, str) and raw_key.startswith(prefix):
            data[raw_key[len(prefix) :]] = value
    return data


def public_web_theme_config(web):
    theme = _nested_or_dotted(web, "theme")
    result = OrderedDict()
    for key in WEB_THEME_KEYS:
        if key in theme and str(theme[key]).strip():
            result[key] = str(theme[key]).strip()
    return result


def public_web_dashboard_config(web):
    dashboard = _nested_or_dotted(web, "dashboard")
    cards = _string_list(dashboard.get("cards"))
    cards = [card for card in cards if card in KNOWN_DASHBOARD_CARDS]
    if not cards:
        cards = list(DEFAULT_DASHBOARD_CARDS)
    limits = dashboard.get("limits")
    if not isinstance(limits, dict):
        limits = {}
    result_limits = OrderedDict()
    for card in DEFAULT_DASHBOARD_CARDS:
        raw = limits.get(card)
        if raw is None:
            raw = dashboard.get("limit." + card)
        value = _int_or_default(raw, 0)
        if value > 0:
            result_limits[card] = value
    return {"cards": cards, "limits": result_limits}


def public_web_config(config):
    web = config_section(config, "web")
    return {
        "display_refresh": _int_or_default(web.get("display_refresh"), 60),
        "notification_poll_seconds": _int_or_default(web.get("notification_poll_seconds"), 30),
        "notification_lookahead": web.get("notification_lookahead", "0m"),
        "default_limit": web.get("default_limit", ""),
        "default_sort": web.get("default_sort", "line"),
        "default_order": web.get("default_order", "asc"),
        "due_soon_days": _int_or_default(web.get("due_soon_days"), 3),
        "theme": public_web_theme_config(web),
        "dashboard": public_web_dashboard_config(web),
    }


def public_git_config(config):
    git = config_section(config, "git")
    return {
        "enable_api": bool(git.get("enable_api")),
        "ui_poll": bool(git.get("ui_poll", True)),
        "ui_poll_seconds": int(git.get("ui_poll_seconds") or 60),
    }


def public_views_config(config):
    views = config_section(config, "views")
    data = OrderedDict()
    for name, values in views.items():
        if isinstance(values, dict):
            data[str(name)] = OrderedDict((str(key), str(value)) for key, value in values.items())
    return data


def public_users_config(config):
    data = OrderedDict()
    for name, aliases in config_user_aliases(config).items():
        data[str(name)] = {"aliases": list(aliases)}
    return data


def public_teams_config(config):
    data = OrderedDict()
    members = config_team_members(config)
    aliases = config_team_aliases(config)
    for name, values in members.items():
        data[str(name)] = {
            "members": list(values),
            "aliases": list(aliases.get(name, [name])),
        }
    return data


def public_tags_config(config):
    data = OrderedDict()
    for name, aliases in config_tag_aliases(config).items():
        data[str(name)] = list(aliases)
    return data


def sort_items(items, sort_key="line", order="asc"):
    reverse = str(order).lower() in ("desc", "descending", "-1")
    key_name = str(sort_key or "line").lower().replace("-", "_")
    supported = {
        "line",
        "status",
        "type",
        "kind",
        "title",
        "source",
        "time",
        "due",
        "from",
        "to",
        "notify_at",
        "notify_from",
        "notify_to",
        "on",
        "updated",
        "created",
    }
    if key_name not in supported:
        key_name = "line"
    keyed = [(sort_key_for_item(item, key_name), item) for item in items]
    present = [entry for entry in keyed if entry[0][0] == 0]
    missing = [entry for entry in keyed if entry[0][0] != 0]
    present.sort(key=lambda entry: entry[0], reverse=reverse)
    missing.sort(key=lambda entry: entry[0])
    return [entry[1] for entry in present + missing]


def limit_items(items, limit):
    if limit in (None, ""):
        return items
    try:
        amount = int(limit)
    except (TypeError, ValueError):
        return items
    if amount < 0:
        return items
    return items[:amount]


def sort_key_for_item(item, key_name):
    if key_name == "line":
        return (0, item.line if item.line is not None else 999999999)
    if key_name == "status":
        return (0, item.status or "", item.line or 0)
    if key_name in ("type", "kind"):
        return (0, item.kind or "", item.line or 0)
    if key_name == "title":
        return (0, item.title.lower(), item.line or 0)
    if key_name == "source":
        return (0, getattr(item, "source", "") or "", item.line or 0)
    if key_name == "time":
        return _detail_sort_key(
            item,
            (
                "from",
                "notify_at",
                "notify_from",
                "due",
                "do",
                "on",
                "at",
                "to",
                "notify_to",
                "updated",
                "created",
            ),
        )
    return _detail_sort_key(item, (key_name,))


def _detail_sort_key(item, keys):
    for key in keys:
        values = item.details.get(key)
        if values:
            parsed = parse_date_or_datetime(values[0])
            if parsed is not None:
                return (0, format_life_datetime(parsed), item.line or 0)
            return (0, values[0], item.line or 0)
    return (1, "", item.line or 0)


def api_item(item, writable_path=None, id_key="id"):
    data = item.to_dict()
    if item.details.get(id_key):
        data["id"] = item.details[id_key][0]
    data["line"] = item.line
    data["source"] = getattr(item, "source", None)
    data["text"] = getattr(item, "source_text", None) or item_to_line(item)
    data["generated"] = bool(getattr(item, "generated", False))
    data["editable"] = is_editable(item, writable_path)
    data["markdown"] = item_markdown_payload(item)
    return data


def is_editable(item, writable_path):
    if getattr(item, "generated", False):
        return False
    if item.line is None:
        return False
    source = getattr(item, "source", None)
    if source is None:
        return True
    if writable_path is None:
        return False
    return os.path.abspath(source) == os.path.abspath(writable_path)


def item_from_payload(payload):
    item = item_from_dict(payload)
    diagnostics = validate_item(item)
    if _has_error(diagnostics):
        raise ValueError([diagnostic.to_dict() for diagnostic in diagnostics])
    return item


def assign_auto_id_from_paths(item, config=None, paths=None, now=None):
    if not auto_ids_enabled(config or {}):
        return None
    items, _diagnostics = read_life_inputs(paths, config)
    return assign_auto_id(item, config=config, existing_items=items, now=now)


def assign_auto_id(item, config=None, existing_items=None, now=None):
    config = config or {}
    if not auto_ids_enabled(config):
        return None
    key = id_key_from_config(config)
    if item.details.get(key):
        return item.details[key][0]
    existing = collect_item_ids(existing_items or [], key=key)
    return ensure_item_id(
        item,
        existing_ids=existing,
        key=key,
        prefix=id_prefix_for_item(item, config),
        now=now,
    )


def message_item_from_payload(payload, config=None):
    if not isinstance(payload, dict):
        raise ValueError("Message payload must be an object.")

    details = OrderedDict()
    for key, values in (payload.get("details") or {}).items():
        if isinstance(values, list):
            details[key] = list(values)
        else:
            details[key] = [values]

    for key in (
        "sender",
        "recipient",
        "user",
        "team",
        "group",
        "notify_at",
        "notify_from",
        "notify_to",
        "ack",
        "snooze_until",
        "channel",
        "service",
        "priority",
        "project",
        "tag",
        "note",
        "body",
        "url",
        "id",
        "parent",
        "ref",
        "depends_on",
        "blocks",
        "related",
        "created",
        "updated",
    ):
        if key in payload:
            _append_payload_values(details, key, payload[key])

    if "recipients" in payload:
        _append_payload_values(details, "recipient", payload["recipients"])

    if "sender" not in details:
        sender = config_section(config or {}, "message").get("default_sender")
        if not sender:
            sender = config_user_name(config or {})
        if sender:
            details["sender"] = [str(sender)]

    if "channel" not in details:
        channel = config_section(config or {}, "message").get("default_channel")
        if channel:
            details["channel"] = [str(channel)]

    title = payload.get("title", payload.get("body"))
    data = {
        "status": payload.get("status", "[ ]"),
        "type": "M",
        "title": title,
        "details": details,
    }
    return item_from_payload(data)


def message_reply_from_payload(original, original_id, payload, config=None):
    if not isinstance(payload, dict):
        raise ValueError("Message reply payload must be an object.")
    data = dict(payload)
    details = OrderedDict()
    for key, values in (payload.get("details") or {}).items():
        details[key] = list(values) if isinstance(values, list) else [values]
    details.setdefault("parent", []).append(original_id)

    if "recipient" not in data and "recipients" not in data and "recipient" not in details:
        sender = original.details.get("sender", [])
        if sender:
            details["recipient"] = [sender[0]]

    data["details"] = details
    return message_item_from_payload(data, config=config)


def _append_payload_values(details, key, raw_value):
    if raw_value is None:
        return
    if isinstance(raw_value, (list, tuple)):
        values = raw_value
    else:
        values = [raw_value]
    for value in values:
        if value is not None and value != "":
            details.setdefault(key, []).append(value)


def find_item_by_id(items, item_id, kind=None, key="id"):
    matches = []
    for item in items:
        if kind is not None and item.kind != kind:
            continue
        if item_id in item.details.get(key, []):
            matches.append(item)
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError("Multiple items found with id:%s." % item_id)
    return matches[0]


def append_item_to_file(path, item):
    line = item_to_line(item)
    ensure_parent_dir(path)
    existing = ""
    if os.path.exists(path):
        existing = read_text(path)
    prefix = "\n" if existing and not existing.endswith(("\n", "\r")) else ""
    write_text(path, existing + prefix + line + "\n")
    return len(existing.splitlines()) + 1


def update_item_in_file(path, line_no, payload):
    text = read_text(path)
    raw_lines = text.splitlines(True)
    if line_no < 1 or line_no > len(raw_lines):
        raise ValueError("Line %s is out of range." % line_no)
    original_item = _find_item_starting_at_line(text, line_no)
    if original_item is None:
        raise ValueError("Line %s is not a valid life.txt item." % line_no)
    updated = merge_item_payload(original_item, payload)
    line = item_to_line(updated)
    parsed_items, diagnostics = parse_text(line + "\n")
    parsed = parsed_items[0] if parsed_items else None
    if parsed is None:
        diagnostics.append(Diagnostic("error", "E301", "Updated item did not parse."))
    if _has_error(diagnostics):
        raise ValueError([diagnostic.to_dict() for diagnostic in diagnostics])
    start = original_item.line - 1
    end = getattr(original_item, "end_line", original_item.line) or original_item.line
    _body, ending = split_line_ending(raw_lines[end - 1])
    replacement = _with_line_ending(line, ending).splitlines(True)
    raw_lines[start:end] = replacement
    write_text(path, "".join(raw_lines))
    updated.line = line_no
    updated.end_line = line_no + len(line.splitlines()) - 1
    updated.source_text = line
    return updated


def update_item_by_id_in_file(path, item_id, payload, kind=None, key="id"):
    line_no, _item = find_item_line_by_id(path, item_id, kind=kind, key=key)
    return update_item_in_file(path, line_no, payload)


def ack_message_in_file(path, message_id, payload=None, now=None, key="id"):
    payload = payload if isinstance(payload, dict) else {}
    value = payload.get("ack") or payload.get("at") or _format_now(now)
    return patch_item_details_by_id_in_file(
        path,
        message_id,
        {
            "ack": [value],
            "snooze_until": None,
            "updated": [value],
        },
        kind="M",
        key=key,
    )


def snooze_message_in_file(path, message_id, payload=None, config=None, now=None, key="id"):
    payload = payload if isinstance(payload, dict) else {}
    until = payload.get("snooze_until") or payload.get("until")
    if not until:
        duration = payload.get("duration")
        if not duration:
            duration = config_section(config or {}, "notifications").get("snooze_default")
        duration = duration or "10m"
        until = _format_datetime(_now(now) + parse_duration(duration))
    return patch_item_details_by_id_in_file(
        path,
        message_id,
        {
            "ack": None,
            "snooze_until": [until],
            "updated": [_format_now(now)],
        },
        kind="M",
        key=key,
    )


def patch_item_details_by_id_in_file(path, item_id, detail_updates, kind=None, key="id"):
    line_no, item = find_item_line_by_id(path, item_id, kind=kind, key=key)
    details = OrderedDict()
    for key, values in item.details.items():
        details[key] = list(values)
    for key, values in detail_updates.items():
        if values is None:
            details.pop(key, None)
            continue
        if isinstance(values, (list, tuple)):
            details[key] = [str(value) for value in values]
        else:
            details[key] = [str(values)]
    return update_item_in_file(
        path,
        line_no,
        {
            "status": item.status,
            "type": item.kind,
            "title": item.title,
            "details": details,
        },
    )


def delete_item_from_file(path, line_no):
    text = read_text(path)
    raw_lines = text.splitlines(True)
    if line_no < 1 or line_no > len(raw_lines):
        raise ValueError("Line %s is out of range." % line_no)
    item = _find_item_starting_at_line(text, line_no)
    if item is None:
        raise ValueError("Line %s is not a valid life.txt item." % line_no)
    start = item.line - 1
    end = getattr(item, "end_line", item.line) or item.line
    del raw_lines[start:end]
    write_text(path, "".join(raw_lines))
    return item_to_line(item)


def delete_item_by_id_from_file(path, item_id, kind=None, key="id"):
    line_no, _item = find_item_line_by_id(path, item_id, kind=kind, key=key)
    return delete_item_from_file(path, line_no)


def find_item_line_by_id(path, item_id, kind=None, key="id"):
    text = read_text(path)
    items, _diagnostics = parse_text(text)
    matches = []
    for item in items:
        if kind is not None and item.kind != kind:
            continue
        if item_id in item.details.get(key, []):
            matches.append((item.line, item))
    if not matches:
        raise ValueError("No writable item found with id:%s." % item_id)
    if len(matches) > 1:
        raise ValueError("Multiple writable items found with id:%s." % item_id)
    return matches[0]


def _find_item_starting_at_line(text, line_no):
    items, _diagnostics = parse_text(text)
    for item in items:
        if item.line == line_no:
            return item
    return None


def _with_line_ending(text, ending):
    if text.endswith(("\n", "\r")):
        return text
    return text + ending


def merge_item_payload(item, payload):
    data = item.to_dict()
    for key in ("status", "type", "title"):
        if key in payload:
            data[key] = payload[key]
    if "kind" in payload:
        data["type"] = payload["kind"]
    if "details" in payload:
        data["details"] = payload["details"]
    return item_from_payload(data)


def read_text(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def write_text(path, text):
    ensure_parent_dir(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    handle = None
    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=directory,
            prefix=".lifetxt-",
            suffix=".tmp",
        )
        temp_path = handle.name
        handle.write(text)
        handle.close()
        os.replace(temp_path, path)
    finally:
        if handle is not None and not handle.closed:
            handle.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def ensure_parent_dir(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def split_line_ending(line):
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def _now(value=None):
    if value is None:
        value = datetime.now()
    return value.replace(second=0, microsecond=0)


def _format_now(value=None):
    return format_life_datetime(_now(value))


def _format_datetime(value):
    return format_life_datetime(value)


def _subgraph(nodes, edges, root, depth):
    try:
        max_depth = int(depth) if depth is not None else None
    except (TypeError, ValueError):
        max_depth = None
    if max_depth is not None:
        max_depth = max(0, min(max_depth, 10))
    node_ids = {n["id"] for n in nodes}
    if root not in node_ids:
        return [], []
    reachable = set()
    queue = [(root, 0)]
    while queue:
        current, d = queue.pop(0)
        if current in reachable:
            continue
        reachable.add(current)
        if max_depth is not None and d >= max_depth:
            continue
        for edge in edges:
            if edge["source"] == current and edge["target"] not in reachable:
                queue.append((edge["target"], d + 1))
            if edge["target"] == current and edge["source"] not in reachable:
                queue.append((edge["source"], d + 1))
    filtered_nodes = [n for n in nodes if n["id"] in reachable]
    filtered_edges = [e for e in edges if e["source"] in reachable and e["target"] in reachable]
    return filtered_nodes, filtered_edges


def _elapsed_to_minutes(value):
    import re
    text = str(value).strip()
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", text)
    if m and (m.group(1) or m.group(2)):
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        return hours * 60 + minutes
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


def _csv_values(value):
    if value is None:
        return None
    values = []
    if isinstance(value, (list, tuple)):
        source_values = value
    else:
        source_values = [value]
    for raw in source_values:
        for part in str(raw).split(","):
            part = part.strip()
            if part:
                values.append(part)
    return values or None


def _has_error(diagnostics):
    for diagnostic in diagnostics:
        if isinstance(diagnostic, Diagnostic) and diagnostic.severity == "error":
            return True
    return False


def error_detail(exc):
    if exc.args:
        return exc.args[0]
    return str(exc)


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>life.txt</title>
  <style>
    :root {
      /* surfaces */
      --bg: #f1f4f2;
      --panel: #ffffff;
      --panel-2: #f7faf8;
      --soft: #ecf2ee;
      /* text */
      --ink: #17201b;
      --muted: #5d6b63;
      /* lines */
      --line: #dfe6e1;
      --line-strong: #c2cdc6;
      /* brand + semantic */
      --accent: #0e7a65;
      --accent-hover: #0a6252;
      --accent-soft: #e0f0ea;
      --accent-ink: #ffffff;
      --danger: #b23c2e;
      --danger-soft: #fbeae7;
      --warn: #9a5b04;
      --warn-soft: #fdf3de;
      --ok: #1a7a45;
      --ok-soft: #e2f5e9;
      --info: #175f9e;
      --info-soft: #e4eefa;
      --violet: #6d4fc4;
      --violet-soft: #ece6fa;
      /* elevation */
      --shadow-1: 0 1px 2px rgba(16, 26, 21, .06);
      --shadow-2: 0 4px 18px rgba(16, 26, 21, .10);
      --shadow-3: 0 18px 48px rgba(16, 26, 21, .20);
      /* radii */
      --r-sm: .45rem;
      --r-md: .7rem;
      --r-lg: 1rem;
      /* type + motion */
      --font-ui: "Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI", "Hiragino Sans", "Noto Sans JP", sans-serif;
      --font-mono: Consolas, "Cascadia Mono", "Courier New", monospace;
      --t-fast: .12s ease;
      --t-med: .2s ease;
      /* layout */
      --topbar-h: 3.6rem;
      /* legacy aliases (older rules reference these names) */
      --text: var(--ink);
      --text-muted: var(--muted);
      --border: var(--line);
    }
    [data-theme="dark"] {
      --bg: #101512;
      --panel: #1a211d;
      --panel-2: #1f2722;
      --soft: #232c26;
      --ink: #e3e9e5;
      --muted: #93a099;
      --line: #2a332d;
      --line-strong: #3e4a43;
      --accent: #43c3a3;
      --accent-hover: #5cd8b8;
      --accent-soft: #17342b;
      --accent-ink: #07231b;
      --danger: #ef8677;
      --danger-soft: #3a211d;
      --warn: #e5b566;
      --warn-soft: #37301c;
      --ok: #6fd394;
      --ok-soft: #1c3325;
      --info: #7cb7ec;
      --info-soft: #1d2d3e;
      --violet: #ab93e8;
      --violet-soft: #2b2440;
      --shadow-1: 0 1px 2px rgba(0, 0, 0, .35);
      --shadow-2: 0 4px 18px rgba(0, 0, 0, .45);
      --shadow-3: 0 18px 48px rgba(0, 0, 0, .6);
    }
    * { box-sizing: border-box; }
    html { scrollbar-color: var(--line-strong) transparent; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: var(--bg);
      font-family: var(--font-ui);
      font-size: 15px;
      line-height: 1.45;
    }
    ::selection { background: var(--accent-soft); }
    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 999px; border: 2px solid transparent; background-clip: content-box; }
    ::-webkit-scrollbar-track { background: transparent; }
    /* ── App shell: sticky topbar ── */
    header {
      position: sticky;
      top: 0;
      z-index: 150;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
      min-height: var(--topbar-h);
      padding: .45rem clamp(.75rem, 3vw, 1.5rem);
      background: color-mix(in srgb, var(--panel) 86%, transparent);
      -webkit-backdrop-filter: blur(10px);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--line);
    }
    @supports not (background: color-mix(in srgb, red 50%, blue)) {
      header { background: var(--panel); }
    }
    .brand { display: flex; align-items: center; gap: .6rem; min-width: 0; flex: 1 1 16rem; }
    .brand-mark {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 2.1rem;
      height: 2.1rem;
      flex-shrink: 0;
      border-radius: .65rem;
      background: linear-gradient(135deg, var(--accent), var(--accent-hover));
      color: #fff;
      font-size: 1.15rem;
      font-weight: 800;
      box-shadow: var(--shadow-1);
    }
    h1 { margin: 0; font-size: 1.15rem; letter-spacing: -.02em; line-height: 1.2; white-space: nowrap; }
    .subtitle { margin: 0; color: var(--muted); font-size: .72rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: clamp(12rem, 24vw, 22rem); }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 1.1rem;
      max-width: 1360px;
      margin: 0 auto;
      padding: 1.1rem clamp(.75rem, 3vw, 1.5rem) 2.5rem;
    }
    section {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--r-lg);
      overflow: hidden;
      box-shadow: var(--shadow-1);
    }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: .75rem;
      padding: .8rem 1rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    h2 { margin: 0; font-size: .8rem; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); display: flex; align-items: center; gap: .4rem; }
    h2 .h2-icon { font-size: .95rem; line-height: 1; }
    .toolbar, .actions {
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      align-items: center;
    }
    header > .toolbar {
      flex: 1 1 22rem;
      justify-content: flex-end;
      min-width: 0;
    }
    /* ── Form controls ── */
    input, select, textarea, button {
      max-width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: var(--r-sm);
      padding: .5rem .65rem;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
      transition: border-color var(--t-fast), box-shadow var(--t-fast), background var(--t-fast);
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
    input:disabled, select:disabled, textarea:disabled {
      color: var(--muted);
      background: var(--soft);
    }
    select { cursor: pointer; }
    textarea {
      width: 100%;
      min-height: 8rem;
      resize: vertical;
      font-family: var(--font-mono);
      font-size: .9rem;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: var(--accent-ink);
      font-weight: 650;
    }
    button:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
    button:active { transform: translateY(1px); }
    button.secondary { background: var(--panel); color: var(--accent); }
    button.secondary:hover { background: var(--accent-soft); border-color: var(--accent); }
    button.danger { background: var(--panel); border-color: var(--danger); color: var(--danger); }
    button.danger:hover { background: var(--danger-soft); }
    button:disabled { cursor: not-allowed; opacity: .55; transform: none; }
    .help-target,
    .field-help {
      position: relative;
    }
    .ui-help-tooltip {
      position: fixed;
      z-index: 900;
      max-width: min(20rem, calc(100vw - 1rem));
      padding: .55rem .65rem;
      border: 1px solid var(--line-strong);
      border-radius: var(--r-md);
      background: var(--ink);
      color: var(--panel);
      box-shadow: var(--shadow-2);
      font-size: .78rem;
      font-weight: 500;
      line-height: 1.35;
      text-align: left;
      opacity: 0;
      pointer-events: none;
      transform: translateY(-.12rem);
      transition: opacity var(--t-fast), transform var(--t-fast);
    }
    .ui-help-tooltip.visible {
      opacity: 1;
      transform: translateY(0);
    }
    .field-label {
      display: grid;
      gap: .25rem;
    }
    .field-label-head {
      display: flex;
      align-items: center;
      gap: .35rem;
    }
    .field-help {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.15rem;
      height: 1.15rem;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      color: var(--accent);
      background: var(--panel);
      font-size: .72rem;
      font-weight: 800;
      cursor: help;
    }
    .editor-help-strip {
      padding: .55rem .7rem;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--info-soft);
      color: var(--info);
      font-size: .84rem;
    }
    .content, .stack { display: grid; gap: .6rem; padding: 1rem; }
    /* ── Items secondary control strip ── */
    .items-controls {
      display: flex;
      gap: .45rem;
      flex-wrap: wrap;
      align-items: center;
      padding: .55rem 1rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .items-controls select, .items-controls input {
      font-size: .82rem;
      padding: .3rem .5rem;
    }
    .items-controls #limit { max-width: 5rem; }
    .search-wrap {
      position: relative;
      display: flex;
      align-items: center;
      gap: .35rem;
      min-width: 0;
    }
    .search-wrap .search-icon {
      position: absolute;
      left: .55rem;
      font-size: .8rem;
      opacity: .55;
      pointer-events: none;
    }
    .search-wrap input { padding-left: 1.85rem; min-width: 11rem; }
    /* ── Item cards ── */
    .item {
      display: grid;
      grid-template-columns: auto auto auto minmax(0, 1fr) auto;
      gap: .55rem;
      align-items: start;
      width: 100%;
      padding: .7rem .8rem;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel);
      text-align: left;
      color: inherit;
      transition: border-color var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
    }
    .item:hover { border-color: var(--line-strong); box-shadow: var(--shadow-2); }
    .item.selected { border-color: var(--accent); background: var(--panel-2); box-shadow: inset 3px 0 0 var(--accent); }
    .item:active { transform: none; }
    .item-check { opacity: 0; cursor: pointer; width: 1rem; height: 1rem; align-self: center; transition: opacity var(--t-fast); accent-color: var(--accent); }
    .item:hover .item-check, .item.bulk-selected .item-check { opacity: 1; }
    .item.bulk-selected { border-color: var(--accent); background: var(--accent-soft); }
    .bulk-toolbar {
      display: none;
      align-items: center;
      gap: .5rem;
      padding: .5rem .75rem;
      background: var(--accent-soft);
      border: 1px solid var(--accent);
      border-radius: var(--r-md);
      margin-bottom: .5rem;
      flex-wrap: wrap;
      animation: fadeSlideIn .16s ease;
    }
    .bulk-toolbar.visible { display: flex; }
    .bulk-toolbar-count { font-size: .85rem; font-weight: 700; color: var(--accent); margin-right: auto; }
    .title { font-weight: 650; overflow-wrap: anywhere; line-height: 1.35; }
    .meta { color: var(--muted); font-size: .82rem; overflow-wrap: anywhere; margin-top: .12rem; }
    @keyframes fadeSlideIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
    /* ── Skeleton loading ── */
    .skeleton-row {
      height: 3.4rem;
      border-radius: var(--r-md);
      border: 1px solid var(--line);
      background: linear-gradient(90deg, var(--panel) 25%, var(--soft) 45%, var(--panel) 65%);
      background-size: 220% 100%;
      animation: shimmer 1.1s linear infinite;
    }
    @keyframes shimmer { from { background-position: 160% 0; } to { background-position: -60% 0; } }
    /* ── Empty state ── */
    .empty-state {
      display: grid;
      justify-items: center;
      gap: .5rem;
      padding: 2.2rem 1rem;
      text-align: center;
      color: var(--muted);
    }
    .empty-state .empty-icon { font-size: 2rem; opacity: .75; }
    .empty-state .empty-title { font-weight: 700; color: var(--ink); }
    .empty-state .empty-hint { font-size: .84rem; max-width: 26rem; }
    .empty-actions {
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: .45rem;
      margin-top: .2rem;
    }
    /* ── Back to top ── */
    #back-to-top {
      position: fixed;
      bottom: 1.4rem;
      left: 1.4rem;
      z-index: 300;
      display: none;
      width: 2.6rem;
      height: 2.6rem;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      box-shadow: var(--shadow-2);
      font-size: 1.05rem;
      padding: 0;
    }
    #back-to-top.visible { display: inline-flex; }
    /* ── Density: compact ── */
    .density-compact .content, .density-compact .stack { gap: .35rem; padding: .65rem; }
    .density-compact .item { padding: .42rem .6rem; gap: .45rem; border-radius: var(--r-sm); }
    .density-compact .item .body-preview { display: none; }
    .density-compact .meta { font-size: .76rem; }
    .density-compact .title { font-size: .92rem; }
    .density-compact .section-head { padding: .55rem .8rem; }
    /* ── Reduced motion ── */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
    }
    .markdown {
      overflow-wrap: anywhere;
    }
    .markdown p,
    .markdown ul,
    .markdown ol,
    .markdown pre {
      margin: .35rem 0 0;
    }
    .markdown ul,
    .markdown ol {
      padding-left: 1.25rem;
    }
    .markdown code {
      padding: .05rem .25rem;
      border-radius: .25rem;
      background: var(--soft);
      font-family: Consolas, "Courier New", monospace;
      font-size: .9em;
    }
    .markdown pre {
      max-width: 100%;
      overflow: auto;
      padding: .5rem;
      border-radius: .45rem;
      background: var(--soft);
    }
    .markdown table {
      width: 100%;
      margin: .45rem 0 0;
      border-collapse: collapse;
      font-size: .9rem;
      overflow-wrap: normal;
    }
    .markdown th,
    .markdown td {
      padding: .35rem .45rem;
      border: 1px solid var(--line);
      vertical-align: top;
    }
    .markdown th {
      background: var(--soft);
      font-weight: 700;
    }
    .markdown a { color: var(--accent); }
    .body-preview {
      margin-top: .35rem;
      color: var(--ink);
      font-size: .9rem;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 1.5rem;
      padding: .12rem .5rem;
      border-radius: 999px;
      background: var(--soft);
      border: 1px solid var(--line);
      font-family: var(--font-mono);
      font-size: .78rem;
      white-space: nowrap;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      min-height: 1.5rem;
      padding: .12rem .55rem;
      border-radius: 999px;
      font-family: var(--font-mono);
      font-size: .78rem;
      white-space: nowrap;
      font-weight: 700;
    }
    .status-open   { background: var(--info-soft); color: var(--info); }
    .status-active { background: var(--warn-soft); color: var(--warn); }
    .status-done   { background: var(--ok-soft); color: var(--ok); text-decoration: line-through; opacity: .75; }
    .status-cancel { background: var(--soft); color: var(--muted); text-decoration: line-through; opacity: .75; }
    .status-defer  { background: var(--violet-soft); color: var(--violet); }
    .status-maybe  { background: var(--danger-soft); color: var(--danger); }
    .status-note   { background: var(--soft); color: var(--muted); }
    .type-badge {
      display: inline-flex;
      align-items: center;
      min-height: 1.5rem;
      padding: .12rem .5rem;
      border-radius: .4rem;
      font-size: .74rem;
      font-weight: 800;
      white-space: nowrap;
      letter-spacing: .04em;
    }
    .type-T { background: #e3f1fc; color: #145a86; }
    .type-E { background: #f9e7fc; color: #6d1a82; }
    .type-D { background: #fce5e5; color: #8f1d1d; }
    .type-R { background: #fcf1e2; color: #7d4b03; }
    .type-H { background: #e2fcee; color: #16603a; }
    .type-N { background: #eef0ef; color: #57605a; }
    .type-S { background: #e6edfc; color: #1d3a8f; }
    .type-M { background: #fcece2; color: #82441d; }
    .type-J { background: #fbfbdf; color: #63630a; }
    [data-theme="dark"] .type-T { background: rgba(64, 146, 210, .18); color: #8ec4ee; }
    [data-theme="dark"] .type-E { background: rgba(190, 92, 214, .18); color: #dea7ee; }
    [data-theme="dark"] .type-D { background: rgba(224, 90, 90, .18); color: #f0a2a2; }
    [data-theme="dark"] .type-R { background: rgba(224, 160, 60, .18); color: #ecc78f; }
    [data-theme="dark"] .type-H { background: rgba(70, 200, 130, .18); color: #93e2b6; }
    [data-theme="dark"] .type-N { background: rgba(150, 160, 155, .18); color: #b8c1bb; }
    [data-theme="dark"] .type-S { background: rgba(100, 130, 230, .18); color: #a9bcf2; }
    [data-theme="dark"] .type-M { background: rgba(220, 130, 70, .18); color: #eab894; }
    [data-theme="dark"] .type-J { background: rgba(200, 200, 80, .18); color: #d9d98f; }
    .item.overdue   { border-left: 3px solid var(--danger); }
    .item.due-soon  { border-left: 3px solid #e67e22; }
    /* ── Stats summary as stat chips ── */
    .stats-summary {
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      align-items: flex-start;
      padding: .6rem 1rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
      font-size: .82rem;
    }
    .stats-count {
      display: flex;
      gap: .35rem;
      align-items: baseline;
      padding: .25rem .7rem;
      border: 1px solid var(--line);
      border-radius: var(--r-sm);
      background: var(--panel);
    }
    .stats-count .n { font-weight: 800; font-size: 1.02rem; font-variant-numeric: tabular-nums; }
    .stats-count.overdue-count .n { color: var(--danger); }
    .filter-chips {
      display: flex;
      flex-wrap: wrap;
      gap: .4rem;
      padding: .5rem 1rem;
      border-bottom: 1px solid var(--line);
      min-height: 0;
    }
    .filter-chips:empty { display: none; }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: .3rem;
      padding: .2rem .6rem;
      border-radius: 999px;
      background: var(--accent-soft);
      border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
      color: var(--accent);
      font-size: .8rem;
      font-weight: 600;
    }
    .chip button {
      background: none;
      border: none;
      padding: 0;
      color: var(--accent);
      font-size: .9rem;
      line-height: 1;
      cursor: pointer;
      font-weight: 700;
    }
    .chip button:hover { background: none; color: var(--danger); }
    .chart-panel {
      position: relative;
      height: 200px;
    }
    .chart-tabs { display: flex; gap: .25rem; padding: .5rem 1rem; border-bottom: 1px solid var(--line); overflow-x: auto; }
    .chart-tab {
      padding: .25rem .7rem;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
      font-size: .8rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .chart-tab:hover { border-color: var(--accent); color: var(--accent); background: var(--panel); }
    .chart-tab.active { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
    .quick-add-bar {
      display: flex;
      gap: .4rem;
      padding: .55rem 1rem;
      border-bottom: 1px solid var(--line);
      background: var(--accent-soft);
      animation: fadeSlideIn .16s ease;
    }
    .quick-add-bar input {
      flex: 1;
    }
    .quick-add-bar .hint {
      color: var(--muted);
      font-size: .78rem;
      align-self: center;
      white-space: nowrap;
    }
    .quick-add-bar input.ok  { border-color: #86efac; }
    .quick-add-bar input.err { border-color: #fca5a5; }
    .quick-add-bar .check-msg { font-size: .78rem; align-self: center; }
    .quick-add-bar .check-msg.ok  { color: #166534; }
    .quick-add-bar .check-msg.err { color: #991b1b; }
    .type-hints {
      padding: .3rem .65rem .3rem;
      font-size: .78rem;
      color: var(--muted);
      background: var(--soft);
      border-radius: .35rem;
      margin: .2rem 0;
    }
    .detail-drawer {
      align-items: center;
      justify-content: center;
      padding: clamp(.75rem, 3vw, 2rem);
    }
    .detail-modal {
      width: min(900px, 96vw);
      max-height: min(90vh, 900px);
      background: var(--panel);
      border: 1px solid var(--line);
      border-top: 3px solid var(--accent);
      border-radius: var(--r-lg);
      box-shadow: var(--shadow-3);
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      overflow: hidden;
      animation: fadeSlideIn .18s ease;
    }
    .drawer-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: .8rem 1.1rem;
      border-bottom: 1px solid var(--line);
      gap: .5rem;
      background: var(--panel);
      z-index: 1;
      flex-wrap: wrap;
    }
    .drawer-head h3 { margin: 0; font-size: .95rem; order: 0; flex: 1 1 calc(100% - 3.2rem); line-height: 1.45; }
    .drawer-head .drawer-close-btn { order: 1; }
    #drawer-head-btns { order: 2; flex: 1 1 100%; }
    .drawer-body { padding: 1rem 1.1rem; display: grid; gap: 1rem; overflow-y: auto; min-height: 0; }
    .drawer-fields { display: grid; gap: .4rem; }
    .drawer-field { display: grid; grid-template-columns: 7rem 1fr; gap: .5rem; font-size: .88rem; }
    .drawer-field .key { color: var(--muted); }
    .drawer-field .val { overflow-wrap: anywhere; }
    .drawer-section-title {
      font-size: .78rem;
      font-weight: 700;
      letter-spacing: .06em;
      text-transform: uppercase;
      color: var(--muted);
      margin: .2rem 0 .1rem;
    }
    .drawer-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
    .drawer-link { color: var(--accent); text-decoration: underline; cursor: pointer; font-size: .88rem; }
    .incoming-link-row { font-size: .88rem; padding: .25rem 0; border-bottom: 1px solid var(--line); }
    .incoming-link-row:last-child { border-bottom: none; }
    #toast-container {
      position: fixed;
      bottom: 1.5rem;
      right: 1.5rem;
      z-index: 500;
      display: flex;
      flex-direction: column;
      gap: .5rem;
      pointer-events: none;
    }
    .toast {
      display: flex;
      align-items: center;
      padding: .65rem 1rem;
      border-radius: var(--r-md);
      background: var(--panel);
      border: 1px solid var(--line);
      border-left-width: 4px;
      box-shadow: var(--shadow-2);
      font-size: .88rem;
      color: var(--ink);
      max-width: 360px;
      pointer-events: auto;
      animation: toastIn .2s cubic-bezier(.2, .8, .3, 1);
    }
    .toast::before { margin-right: .5rem; font-weight: 800; }
    .toast.success { border-left-color: var(--ok); }
    .toast.success::before { content: "✓"; color: var(--ok); }
    .toast.error   { border-left-color: var(--danger); }
    .toast.error::before { content: "✕"; color: var(--danger); }
    .toast.warning { border-left-color: var(--warn); }
    .toast.warning::before { content: "⚠"; color: var(--warn); }
    .toast.info    { border-left-color: var(--info); }
    .toast.info::before { content: "ℹ"; color: var(--info); }
    @keyframes toastIn { from { opacity: 0; transform: translateY(10px) scale(.98); } to { opacity: 1; transform: none; } }
    .git-badge {
      padding: .22rem .6rem;
      border-radius: 999px;
      font-size: .76rem;
      font-weight: 700;
      cursor: pointer;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .git-clean    { background: var(--ok-soft); color: var(--ok); }
    .git-modified { background: var(--warn-soft); color: var(--warn); }
    .git-error    { background: var(--danger-soft); color: var(--danger); }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(10, 16, 13, .5);
      -webkit-backdrop-filter: blur(3px);
      backdrop-filter: blur(3px);
      z-index: 550;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .modal-backdrop.open { display: flex; }
    body.modal-open { overflow: hidden; }
    .modal {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--r-lg);
      padding: 1.5rem 1.75rem;
      max-width: 520px;
      width: 92vw;
      max-height: 82vh;
      overflow-y: auto;
      box-shadow: var(--shadow-3);
      animation: fadeSlideIn .18s ease;
    }
    .modal h3 { margin: 0 0 1rem; }
    .modal table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    .modal td { padding: .3rem .5rem; border-bottom: 1px solid var(--line); }
    .modal td:first-child { color: var(--muted); width: 7rem; white-space: nowrap; }
    .notif-permission { display: flex; align-items: center; gap: .4rem; font-size: .82rem; padding: .5rem 1rem; border-bottom: 1px solid var(--line); }
    .notif-perm-granted { color: var(--ok); }
    .notif-perm-denied  { color: var(--danger); }
    .notif-perm-default { color: var(--warn); }
    mark { background: #ffec8a; color: #3d3200; border-radius: .2rem; padding: 0 .1rem; }
    [data-theme="dark"] mark { background: #6b5d13; color: #ffe9a3; }
    /* ── Button active state ─────────────────────────────────────── */
    .secondary.btn-active {
      background: var(--accent-soft); border-color: var(--accent); color: var(--accent); font-weight: 700;
    }
    /* ── Dependency graph rows ───────────────────────────────────── */
    .dep-graph { display: grid; gap: .3rem; }
    .dep-group-label { font-size: .73rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-top: .15rem; }
    .dep-row { display: flex; align-items: center; gap: .35rem; padding: .3rem .45rem; border-radius: var(--r-sm); background: var(--panel-2); border: 1px solid var(--line); transition: border-color var(--t-fast); }
    .dep-row:hover { border-color: var(--accent); }
    .dep-arrow { font-weight: 700; font-size: .9rem; min-width: 1.2rem; text-align: center; }
    .dep-out { color: var(--info); }
    .dep-in  { color: var(--violet); }
    .dep-rel { font-size: .72rem; color: var(--muted); min-width: 5.5rem; }
    .dep-missing { color: #9ca3af; font-style: italic; font-size: .85rem; }
    a.drawer-link { color: var(--accent); text-decoration: none; font-size: .88rem; }
    a.drawer-link:hover { text-decoration: underline; }
    .graph-toolbar { display: flex; gap: .35rem; align-items: center; padding: .65rem 1rem; border-bottom: 1px solid var(--line); }
    .graph-toolbar input { min-width: 0; flex: 1; font-size: .82rem; }
    .graph-panel { min-height: 12rem; padding: .75rem 1rem; overflow: auto; }
    .graph-svg { width: 100%; height: auto; max-height: 22rem; border: 1px solid var(--line); border-radius: .55rem; background: linear-gradient(180deg, var(--panel), var(--soft)); }
    .graph-edge { stroke: #94a3b8; stroke-width: 1.4; marker-end: url(#arrow); opacity: .8; }
    .graph-edge-label { fill: var(--muted); font-size: 9px; pointer-events: none; }
    .graph-node { cursor: pointer; }
    .graph-node circle { stroke: var(--panel); stroke-width: 2; filter: drop-shadow(0 1px 2px rgba(0,0,0,.14)); }
    .graph-node text { fill: var(--ink); font-size: 10px; font-weight: 700; pointer-events: none; }
    .graph-node:hover circle { stroke: var(--accent); stroke-width: 3; }
    .drawer-graph-mini { margin-bottom: .55rem; }
    .drawer-graph-mini .graph-svg { max-height: 11rem; }
    .message-thread { display: grid; gap: .35rem; }
    .message-thread-row { border: 1px solid var(--line); border-radius: .45rem; padding: .45rem .55rem; background: var(--bg); font-size: .84rem; }
    .message-thread-row.current { border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }
    .message-thread-meta { color: var(--muted); font-size: .74rem; margin-top: .15rem; }
    /* ── Status quick-filter bar ──────────────────────────────────── */
    .filter-bar { display: flex; gap: .3rem; flex-wrap: wrap; padding: .55rem 1rem; border-bottom: 1px solid var(--line); margin: 0; background: var(--panel); }
    .filter-btn { padding: .24rem .7rem; border-radius: 999px; font-size: .78rem; font-weight: 600; border: 1px solid var(--line); background: var(--panel-2); cursor: pointer; color: var(--muted); transition: background var(--t-fast), border-color var(--t-fast), color var(--t-fast); }
    .filter-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--panel); }
    .filter-btn.active { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); font-weight: 700; }
    /* ── Ref links in item rows ───────────────────────────────────── */
    .ref-link { display: inline-block; color: var(--accent); font-size: .75rem; border: 1px solid currentColor; border-radius: .25rem; padding: 0 .3rem; margin-left: .15rem; cursor: pointer; opacity: .85; }
    .ref-link:hover { opacity: 1; text-decoration: underline; }
    .parent-indicator { font-size: .73rem; color: var(--muted); margin-left: .3rem; }
    /* ── Notification state badges ────────────────────────────────── */
    .notif-state { display: inline-block; font-size: .72rem; font-weight: 600; padding: .1rem .5rem; border-radius: 999px; margin-left: .4rem; vertical-align: middle; }
    .notif-state-ack      { background: var(--ok-soft); color: var(--ok); }
    .notif-state-snoozed  { background: var(--warn-soft); color: var(--warn); }
    .notif-state-pending  { background: var(--info-soft); color: var(--info); }
    /* ── Habit heatmap ────────────────────────────────────────────── */
    .heatmap-section { display: grid; gap: .9rem; }
    .heatmap-habit { }
    .heatmap-title { font-size: .82rem; font-weight: 600; margin-bottom: .3rem; display: flex; align-items: center; gap: .5rem; }
    .heatmap-streak { font-size: .72rem; color: var(--muted); font-weight: 400; }
    .heatmap-grid { display: grid; grid-template-columns: repeat(53, 1fr); gap: 2px; }
    .heatmap-cell { width: 100%; aspect-ratio: 1; border-radius: 2px; background: var(--line); title: ""; }
    .heatmap-cell.done { background: #22c55e; }
    .heatmap-cell.today { outline: 1.5px solid var(--accent); }
    .heatmap-month-labels { display: flex; font-size: .65rem; color: var(--muted); margin-bottom: .15rem; }
    /* ── Search result count ──────────────────────────────────────── */
    #search-count { font-size: .77rem; color: var(--muted); margin-left: .35rem; white-space: nowrap; }
    /* ── Dark mode toggle button ─────────────────────────────────── */
    #dark-btn { font-size:.85rem; padding:.25rem .5rem; }
    /* ── Heatmap tooltip ─────────────────────────────────────────── */
    .hm-tooltip { position:fixed; background:rgba(0,0,0,.78); color:#fff; font-size:.75rem; padding:.25rem .55rem; border-radius:.3rem; pointer-events:none; z-index:9999; display:none; }
    /* ── Context menu ────────────────────────────────────────────── */
    #ctx-menu { position:fixed; background:var(--panel); border:1px solid var(--line); border-radius:var(--r-md); box-shadow:var(--shadow-3); z-index:9998; display:none; min-width:11rem; padding:.3rem; animation: fadeSlideIn .12s ease; }
    .ctx-item { padding:.42rem .7rem; font-size:.85rem; cursor:pointer; white-space:nowrap; border-radius:var(--r-sm); }
    .ctx-item:hover { background:var(--accent-soft); color:var(--accent); }
    .ctx-sep { border:none; border-top:1px solid var(--line); margin:.25rem .3rem; }
    /* ── Project stats mini-table ────────────────────────────────── */
    .proj-stats-table { width:100%; font-size:.78rem; border-collapse:collapse; margin-top:.5rem; }
    .proj-stats-table th { text-align:left; color:var(--muted); font-weight:500; padding:.1rem .3rem; }
    .proj-stats-table td { padding:.1rem .3rem; vertical-align:middle; }
    .proj-stats-bar { display:block; height:.4rem; background:var(--accent); border-radius:.2rem; min-width:2px; }
    /* ── Agenda badge ────────────────────────────────────────────── */
    .overdue-badge { display:inline-flex; align-items:center; justify-content:center; background:var(--danger); color:#fff; border-radius:.9rem; font-size:.7rem; min-width:1.3rem; height:1.3rem; padding:0 .35rem; margin-left:.4rem; font-weight:600; }
    .agenda-limit-ctrl { display:flex; align-items:center; gap:.25rem; margin-left:auto; font-size:.75rem; color:var(--text-muted); }
    .agenda-limit-ctrl input[type="number"] { font-size:.75rem; padding:.1rem .2rem; border:1px solid var(--border); border-radius:.25rem; background:var(--bg); color:var(--text); text-align:center; }
    .agenda-limit-ctrl input[type="number"]:focus { outline:1px solid var(--accent); }
    /* ── Drawer copy ID button ───────────────────────────────────── */
    #drawer-copy-id { font-size:.75rem; padding:.15rem .45rem; }
    /* ── Drawer raw line section ─────────────────────────────────── */
    .drawer-raw-details { margin:.4rem 0; font-size:.82rem; }
    .drawer-raw-details summary { cursor:pointer; color:var(--muted); font-size:.78rem; padding:.15rem 0; }
    .drawer-raw-pre { font-family:monospace; font-size:.77rem; white-space:pre-wrap; background:var(--soft); border-radius:.3rem; padding:.4rem .6rem; margin:.3rem 0 0; word-break:break-all; }
    /* ── Drawer close button (fixed top-right, always visible) ──── */
    .drawer-close-btn { flex-shrink:0; background:none; border:1px solid var(--line); border-radius:.3rem; cursor:pointer; font-size:.95rem; padding:.18rem .52rem; color:var(--muted); line-height:1; margin-left:.25rem; }
    .drawer-close-btn:hover { background:var(--soft); color:var(--text); }
    /* ── Drawer inline edit form ─────────────────────────────────── */
    .drawer-edit-form { display:grid; gap:.75rem; }
    .drawer-edit-form label { display:grid; gap:.25rem; font-size:.85rem; color:var(--muted); }
    .drawer-edit-form input, .drawer-edit-form select { width:100%; box-sizing:border-box; }
    .drawer-edit-form textarea { width:100%; box-sizing:border-box; min-height:6rem; font-family:monospace; font-size:.82rem; resize:vertical; }
    /* ── Single-content pages: exactly one visible at a time ────── */
    .page { display: none; }
    .page.page-active { display: block; animation: fadeSlideIn .14s ease; }
    /* ── View tab bar ────────────────────────────────────────────── */
    .workspace-tabs {
      display: flex;
      gap: .3rem;
      align-items: center;
      overflow-x: auto;
      scrollbar-width: thin;
      padding-bottom: .05rem;
    }
    .header-workspace-tabs {
      order: 3;
      flex: 1 1 100%;
      justify-content: flex-start;
      padding: .42rem .5rem;
      border: 1px solid var(--line);
      border-radius: var(--r-lg);
      background: var(--panel-2);
      box-shadow: var(--shadow-1);
    }
    .workspace-tab {
      display: inline-flex;
      align-items: center;
      gap: .3rem;
      white-space: nowrap;
      border: 1px solid var(--line-strong);
      background: var(--panel);
      color: var(--muted);
      border-radius: 999px;
      padding: .38rem .72rem;
      font-size: .82rem;
      font-weight: 700;
    }
    .workspace-tab:hover { color: var(--accent); background: var(--accent-soft); border-color: var(--accent); }
    .workspace-tab.active { color: var(--accent-ink); background: var(--accent); border-color: var(--accent); }
    .skip-link {
      position: fixed;
      top: .75rem;
      left: .75rem;
      z-index: 1000;
      transform: translateY(-160%);
      padding: .45rem .7rem;
      border: 1px solid var(--accent);
      border-radius: 999px;
      background: var(--panel);
      color: var(--accent);
      box-shadow: var(--shadow-2);
      font-weight: 800;
      text-decoration: none;
    }
    .skip-link:focus { transform: translateY(0); outline: 2px solid var(--accent); outline-offset: 2px; }
    .view-guide {
      max-width: 1360px;
      margin: .85rem auto 0;
      padding: 0 1rem;
    }
    .view-guide-card {
      display: flex;
      align-items: center;
      gap: .8rem;
      flex-wrap: wrap;
      padding: .8rem .95rem;
      border: 1px solid var(--line);
      border-radius: var(--r-lg);
      background: color-mix(in srgb, var(--panel) 92%, var(--soft));
      box-shadow: var(--shadow-1);
    }
    .view-guide-chip {
      display: inline-flex;
      align-items: center;
      min-height: 1.6rem;
      padding: .12rem .55rem;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: .74rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .05em;
    }
    .view-guide-copy { min-width: min(100%, 26rem); flex: 1 1 20rem; }
    .view-guide-title { font-weight: 800; color: var(--ink); line-height: 1.2; }
    .view-guide-desc { color: var(--muted); font-size: .86rem; margin-top: .12rem; }
    .view-guide-actions { display: flex; gap: .4rem; flex-wrap: wrap; justify-content: flex-end; }
    .view-guide-actions button { padding: .34rem .6rem; font-size: .78rem; }
    .display-mode .view-guide,
    .kiosk-mode .view-guide { display: none; }
    /* ── Dashboard view ──────────────────────────────────────────── */
    .dashboard-body { display: grid; gap: 1rem; padding: 1rem; }
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
      gap: .7rem;
    }
    .kpi-tile {
      display: grid;
      justify-items: start;
      gap: .1rem;
      padding: .8rem .95rem;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel-2);
      color: var(--ink);
      text-align: left;
      cursor: pointer;
      transition: border-color var(--t-fast), box-shadow var(--t-fast), transform var(--t-fast);
    }
    .kpi-tile:hover { border-color: var(--accent); box-shadow: var(--shadow-2); background: var(--panel); }
    .kpi-icon { font-size: .95rem; opacity: .8; }
    .kpi-n { font-size: 1.7rem; font-weight: 800; line-height: 1.1; font-variant-numeric: tabular-nums; }
    .kpi-label { font-size: .74rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .kpi-tile.kpi-danger .kpi-n { color: var(--danger); }
    .kpi-tile.kpi-warn .kpi-n { color: var(--warn); }
    .kpi-tile.kpi-ok .kpi-n { color: var(--ok); }
    .dash-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1rem;
    }
    .dash-card {
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel);
      padding: .85rem 1rem;
      min-width: 0;
    }
    .dash-card.card-hidden { display: none; }
    .dash-card-title {
      font-size: .78rem;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: .6rem;
    }
    .dash-list { display: grid; gap: .35rem; }
    .dash-row {
      display: flex;
      align-items: center;
      gap: .45rem;
      padding: .3rem .4rem;
      border-radius: var(--r-sm);
      font-size: .88rem;
      min-width: 0;
    }
    .dash-row:hover { background: var(--panel-2); }
    .dash-row-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    a.dash-row-title { cursor: pointer; }
    .dash-row-title.review-click {
      border: 0;
      background: transparent;
      color: var(--accent);
      padding: 0;
      text-align: left;
      font-weight: 650;
      text-decoration: underline;
      cursor: pointer;
    }
    /* ── Focus view ──────────────────────────────────────────────── */
    .focus-body { max-width: 46rem; margin: 0 auto; width: 100%; }
    .focus-list { display: grid; gap: .45rem; padding: .35rem 0 1rem; }
    .focus-group-label {
      margin-top: .8rem;
      font-size: .78rem;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .focus-group-label.focus-overdue { color: var(--danger); }
    .focus-row {
      display: flex;
      align-items: center;
      gap: .8rem;
      padding: .7rem .85rem;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel);
      transition: border-color var(--t-fast), box-shadow var(--t-fast);
    }
    .focus-row:hover { border-color: var(--line-strong); box-shadow: var(--shadow-1); }
    .focus-check {
      flex-shrink: 0;
      width: 1.5rem;
      height: 1.5rem;
      padding: 0;
      border-radius: 999px;
      border: 2px solid var(--line-strong);
      background: var(--panel);
      cursor: pointer;
      transition: border-color var(--t-fast), background var(--t-fast);
    }
    .focus-check:hover { border-color: var(--ok); background: var(--ok-soft); }
    .focus-check:disabled { opacity: .4; cursor: not-allowed; }
    .focus-row-main { flex: 1; min-width: 0; cursor: pointer; }
    .focus-row-title { font-size: 1.02rem; font-weight: 650; line-height: 1.35; overflow-wrap: anywhere; }
    .focus-row-meta { display: flex; align-items: center; gap: .4rem; margin-top: .15rem; font-size: .78rem; color: var(--muted); }
    .focus-readonly { opacity: .75; }
    .focus-quick-add {
      display: flex;
      gap: .45rem;
      align-items: center;
      padding: .35rem 0 .2rem;
    }
    .focus-quick-add input { flex: 1; min-width: 0; }
    .focus-event-time { font-variant-numeric: tabular-nums; }
    /* ── Review view ─────────────────────────────────────────────── */
    .review-body { display: grid; gap: 1rem; padding: 1rem; }
    .review-range-bar { display: flex; gap: .35rem; flex-wrap: wrap; align-items: center; }
    .review-range-btn {
      font-size: .78rem;
      padding: .24rem .65rem;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
      cursor: pointer;
      transition: border-color var(--t-fast), background var(--t-fast), color var(--t-fast);
    }
    .review-range-btn:hover { border-color: var(--line-strong); color: var(--ink); }
    .review-range-btn.active {
      background: var(--accent-soft);
      border-color: var(--accent);
      color: var(--accent);
      font-weight: 700;
    }
    .review-filter-input {
      min-width: 8.5rem;
      font-size: .78rem;
      padding: .3rem .55rem;
      border-radius: 999px;
    }
    .review-habit-bar {
      flex: 0 0 70px;
      height: 6px;
      border-radius: 3px;
      background: var(--soft);
      overflow: hidden;
    }
    .review-habit-bar > span { display: block; height: 100%; background: var(--ok); border-radius: 3px; }
    .review-excerpt { font-size: .78rem; color: var(--muted); margin-top: .1rem; overflow-wrap: anywhere; }
    .review-mood-row { flex-wrap: wrap; }
    .review-num { color: var(--muted); font-size: .78rem; font-variant-numeric: tabular-nums; }
    /* ── Presence (Status & Team views) ──────────────────────────── */
    .presence-dot {
      width: .72rem;
      height: .72rem;
      border-radius: 50%;
      display: inline-block;
      flex-shrink: 0;
      background: var(--info);
      box-shadow: 0 0 0 2px var(--panel);
    }
    .presence-dot.p-available { background: var(--ok); }
    .presence-dot.p-busy { background: var(--danger); }
    .presence-dot.p-away { background: var(--warn); }
    .presence-dot.p-focus { background: var(--violet); }
    .presence-dot.p-off { background: transparent; border: 2px solid var(--muted); box-shadow: none; }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
      gap: .8rem;
    }
    .team-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
      gap: .8rem;
      padding: 1rem;
    }
    .person-card {
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel);
      padding: .8rem .95rem;
      display: grid;
      gap: .45rem;
      align-content: start;
      min-width: 0;
    }
    .person-card.presence-ended { opacity: .72; }
    .person-head { display: flex; align-items: center; gap: .5rem; min-width: 0; }
    .person-name {
      font-weight: 750;
      font-size: 1rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .presence-state-badge {
      margin-left: auto;
      font-size: .7rem;
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
      padding: .12rem .5rem;
      border-radius: 999px;
      background: var(--soft);
      color: var(--muted);
      white-space: nowrap;
    }
    .presence-state-badge.p-available { background: var(--ok-soft); color: var(--ok); }
    .presence-state-badge.p-busy { background: var(--danger-soft); color: var(--danger); }
    .presence-state-badge.p-away { background: var(--warn-soft); color: var(--warn); }
    .presence-state-badge.p-focus { background: var(--violet-soft); color: var(--violet); }
    .presence-state-badge.p-unknown { background: var(--info-soft); color: var(--info); }
    .person-status-title { font-size: .9rem; overflow-wrap: anywhere; }
    .person-meta { font-size: .76rem; color: var(--muted); display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
    .person-workload { display: flex; gap: .35rem; flex-wrap: wrap; }
    .person-card-actions {
      display: flex;
      gap: .35rem;
      flex-wrap: wrap;
      margin-top: .1rem;
    }
    .person-card-action {
      justify-self: start;
      padding: .26rem .55rem;
      font-size: .76rem;
    }
    .person-msgs { display: grid; gap: .25rem; border-top: 1px dashed var(--line); padding-top: .45rem; }
    .person-msg {
      font-size: .8rem;
      display: flex;
      gap: .4rem;
      align-items: baseline;
      cursor: pointer;
      border-radius: var(--r-sm);
      padding: .15rem .3rem;
      min-width: 0;
    }
    .person-msg:hover { background: var(--panel-2); }
    .person-msg-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    /* ── Timeline view ───────────────────────────────────────────── */
    .timeline-body { max-width: 52rem; margin: 0 auto; width: 100%; padding: 0 1rem 1.2rem; }
    .tl-controls { display: flex; gap: .35rem; padding: .8rem 0 .4rem; flex-wrap: wrap; align-items: center; }
    .tl-empty-actions {
      display: flex;
      gap: .45rem;
      justify-content: center;
      flex-wrap: wrap;
      margin-top: .75rem;
    }
    .tl-empty-range {
      margin-top: .4rem;
      color: var(--muted);
      font-size: .78rem;
      font-family: var(--font-mono);
    }
    .tl-day-head {
      font-size: .8rem;
      font-weight: 800;
      letter-spacing: .05em;
      text-transform: uppercase;
      color: var(--muted);
      margin: 1rem 0 .35rem;
      padding-left: 4.4rem;
    }
    .tl-row { display: flex; gap: .7rem; align-items: stretch; min-width: 0; }
    .tl-time {
      flex: 0 0 3.2rem;
      text-align: right;
      font-size: .78rem;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      padding-top: .55rem;
      white-space: nowrap;
    }
    .tl-rail { flex: 0 0 .9rem; position: relative; display: flex; justify-content: center; }
    .tl-rail::before { content: ""; position: absolute; top: 0; bottom: 0; width: 2px; background: var(--line); }
    .tl-node {
      position: relative;
      z-index: 1;
      width: .8rem;
      height: .8rem;
      margin-top: .62rem;
      border-radius: 50%;
      background: var(--accent);
      border: 2px solid var(--panel-2);
    }
    .tl-node.t-T { background: #4092d2; }
    .tl-node.t-E { background: #be5cd6; }
    .tl-node.t-D { background: #e05a5a; }
    .tl-node.t-R { background: #e0a03c; }
    .tl-node.t-H { background: #46c882; }
    .tl-node.t-N { background: #96a09b; }
    .tl-node.t-S { background: #6482e6; }
    .tl-node.t-M { background: #dc8246; }
    .tl-node.t-J { background: #c8c850; }
    .tl-card {
      flex: 1;
      min-width: 0;
      margin: .18rem 0;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel);
      padding: .5rem .7rem;
      cursor: pointer;
      transition: border-color var(--t-fast), box-shadow var(--t-fast);
    }
    .tl-card:hover { border-color: var(--line-strong); box-shadow: var(--shadow-1); }
    .tl-card.tl-static { cursor: default; }
    .tl-card-title { font-weight: 650; overflow-wrap: anywhere; }
    .tl-card-meta { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; margin-top: .15rem; font-size: .76rem; color: var(--muted); }
    .tl-past .tl-card { opacity: .78; }
    .tl-now { display: flex; align-items: center; gap: .5rem; margin: .3rem 0; }
    .tl-now-label { flex: 0 0 3.2rem; text-align: right; font-size: .72rem; font-weight: 800; color: var(--danger); }
    .tl-now-line { flex: 1; height: 2px; background: var(--danger); border-radius: 1px; position: relative; }
    .tl-now-line::before {
      content: "";
      position: absolute;
      left: -.1rem;
      top: -3px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--danger);
    }
    /* ── Record editor modal ─────────────────────────────────────── */
    .editor-modal { max-width: 560px; }
    .editor-modal-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: .5rem;
      margin-bottom: 1rem;
    }
    .editor-modal-head h3 { margin: 0; font-size: 1rem; }
    /* ── Chart group buttons ─────────────────────────────────────── */
    .chart-group-bar { display:flex; gap:.25rem; padding:.25rem 1rem; border-bottom:1px solid var(--line); }
    .chart-group-btn { font-size:.73rem; font-weight:600; padding:.15rem .55rem; border:1px solid var(--line); border-radius:999px; background:var(--panel-2); cursor:pointer; color:var(--muted); }
    .chart-group-btn:hover { border-color:var(--accent); color:var(--accent); background:var(--panel); }
    .chart-group-btn.active { background:var(--accent); color:var(--accent-ink); border-color:var(--accent); }
    /* ── Notification inline snooze ──────────────────────────────── */
    .snooze-inline { display:inline-flex; gap:.25rem; align-items:center; margin-left:.25rem; }
    .snooze-inline input { width:4.5rem; font-size:.77rem; padding:.1rem .35rem; border:1px solid var(--line); border-radius:.3rem; background:var(--bg); }
    /* ── Git log in modal ───────────────────────────────────────── */
    .git-log-entry { display:flex; gap:.5rem; font-size:.77rem; padding:.15rem 0; border-bottom:1px dashed var(--line); }
    .git-log-hash { font-family:monospace; color:var(--muted); min-width:4.5rem; }
    .git-log-msg { flex:1; }
    /* ── Editor import raw ───────────────────────────────────────── */
    #import-raw-row { display:none; margin-top:.5rem; }
    #import-raw-input { width:100%; font-family:monospace; font-size:.8rem; }
    /* ── Heatmap month labels ────────────────────────────────────── */
    .heatmap-months { display:grid; grid-template-columns:repeat(53,1fr); gap:2px; margin-bottom:.2rem; }
    .heatmap-month-cell { font-size:.6rem; color:var(--muted); text-align:center; }
    .source { color: var(--muted); font-size: .74rem; white-space: nowrap; font-family: var(--font-mono); opacity: .85; }
    form.stack { grid-template-columns: 1fr 1fr; }
    form.stack label, form.stack textarea, form.stack .actions, .wide { grid-column: 1 / -1; }
    label { display: grid; gap: .3rem; color: var(--muted); font-size: .82rem; }
    label.inline {
      display: inline-flex;
      align-items: center;
      gap: .35rem;
      min-height: 2.35rem;
      color: var(--ink);
      font-size: .95rem;
    }
    label.inline input { width: auto; }
    label > input, label > select { color: var(--ink); font-size: .95rem; }
    .empty, .note { color: var(--muted); }
    .diagnostic {
      margin: .75rem 1rem 0;
      padding: .65rem;
      border: 1px solid var(--danger);
      border-radius: var(--r-sm);
      color: var(--danger);
      background: var(--danger-soft);
      font-family: var(--font-mono);
      font-size: .86rem;
    }
    .diagnostic.warning {
      border-color: var(--warn);
      color: var(--warn);
      background: var(--warn-soft);
    }
    .parse-preview {
      margin-top: .35rem;
      padding: .5rem .6rem;
      border: 1px dashed var(--line);
      border-radius: var(--r-sm);
      background: var(--panel-2);
      color: var(--muted);
      font-size: .78rem;
      line-height: 1.45;
    }
    .parse-preview.ok { border-color: var(--ok); color: var(--ok); background: var(--ok-soft); }
    .parse-preview.err { border-color: var(--danger); color: var(--danger); background: var(--danger-soft); }
    .parse-preview.warn { border-color: var(--warn); color: var(--warn); background: var(--warn-soft); }
    .occurrence-badge {
      display: inline-flex;
      margin-left: .35rem;
      padding: .08rem .36rem;
      border-radius: 999px;
      background: #e0f2fe;
      color: #0369a1;
      font-size: .68rem;
      font-weight: 700;
      vertical-align: middle;
    }
    .message-reply-form {
      margin-top: .55rem;
      display: grid;
      gap: .35rem;
    }
    .message-reply-form textarea {
      width: 100%;
      min-height: 4.5rem;
      resize: vertical;
    }
    .notification-row {
      padding: .65rem;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel-2);
    }
    .display-mode {
      background:
        radial-gradient(circle at top left, rgba(14, 122, 101, .12), transparent 28rem),
        linear-gradient(180deg, #f8f3e8 0%, #eef4ee 100%);
      color: #17201b;
      font-size: clamp(18px, 1.4vw, 28px);
    }
    .display-mode header {
      max-width: none;
      padding: 1.2rem 2rem;
      position: static;
      background: color-mix(in srgb, #fffaf0 84%, transparent);
      -webkit-backdrop-filter: none;
      backdrop-filter: none;
      border-bottom: 1px solid #decfb7;
    }
    .display-mode .header-workspace-tabs, .kiosk-mode .header-workspace-tabs { display: none; }
    .display-mode #back-to-top, .kiosk-mode #back-to-top { display: none !important; }
    .display-mode .brand-mark { background: linear-gradient(135deg, #0e7a65, #86b85b); }
    .display-mode h1 { font-size: clamp(2.6rem, 6vw, 5rem); color: #15231d; }
    .display-mode .subtitle { color: #6b6254; }
    .display-mode main {
      max-width: none;
      grid-template-columns: minmax(0, 1fr);
      padding: 0 2rem 2rem;
    }
    .display-mode section,
    .display-mode .item {
      background: #fffdf6;
      border-color: #decfb7;
    }
    .display-mode .section-head {
      background: #fbf4e7;
      border-color: #decfb7;
    }
    .display-mode main .toolbar,
    .display-mode section .toolbar { display: none; }
    .display-mode header .toolbar > *:not(#display-exit-btn) { display: none; }
    .display-mode #display-exit-btn {
      display: inline-flex !important;
      background: #fffdf6;
      border-color: #b9a98d;
      color: #0e7a65;
    }
    .display-mode .pill {
      background: #e4f1e9;
      color: #0b604f;
    }
    .display-mode .meta,
    .display-mode .source,
    .display-mode .empty,
    .display-mode .note { color: #6b6254; }
    [data-theme="dark"] body.display-mode {
      background: #0f1412;
      color: #edf4ef;
    }
    [data-theme="dark"] body.display-mode header {
      background: transparent;
      border-bottom: none;
    }
    [data-theme="dark"] body.display-mode .brand-mark { background: #23322d; }
    [data-theme="dark"] body.display-mode h1 { color: #edf4ef; }
    [data-theme="dark"] body.display-mode .subtitle { color: #aebbb4; }
    [data-theme="dark"] body.display-mode section,
    [data-theme="dark"] body.display-mode .item {
      background: #151c19;
      border-color: #31413b;
    }
    [data-theme="dark"] body.display-mode .section-head {
      background: #151c19;
      border-color: #31413b;
    }
    [data-theme="dark"] body.display-mode #display-exit-btn {
      background: #23322d;
      border-color: #31413b;
      color: #edf4ef;
    }
    [data-theme="dark"] body.display-mode .pill {
      background: #23322d;
      color: #edf4ef;
    }
    [data-theme="dark"] body.display-mode .meta,
    [data-theme="dark"] body.display-mode .source,
    [data-theme="dark"] body.display-mode .empty,
    [data-theme="dark"] body.display-mode .note { color: #aebbb4; }
    /* ── Kiosk mode (bulletin board / 掲示板) — high-contrast light theme ── */
    .kiosk-mode {
      background: #f5f7f6;
      color: #111714;
      font-size: clamp(15px, 1.05vw, 20px);
      overflow: hidden;
    }
    .kiosk-mode header {
      max-width: none;
      padding: .65rem 2rem;
      border-bottom: 2px solid #1a7a4a;
      background: #1a7a4a;
      -webkit-backdrop-filter: none;
      backdrop-filter: none;
      color: #fff;
    }
    .kiosk-mode .brand-mark { background: rgba(255,255,255,.18); box-shadow: none; }
    .kiosk-mode .subtitle { display: none; }
    .kiosk-mode h1 { font-size: clamp(1.3rem, 2.2vw, 2.4rem); color: #fff; }
    .kiosk-mode .subtitle { display: none; }
    .kiosk-mode header .toolbar { gap: .5rem; }
    .kiosk-mode header .toolbar > *:not(#kiosk-clock):not(#kiosk-exit-btn) { display: none; }
    .kiosk-mode #kiosk-clock {
      display: flex !important;
      align-items: center;
      gap: .5rem;
      font-size: clamp(1rem, 1.8vw, 1.8rem);
      font-variant-numeric: tabular-nums;
      color: #d0f5e4;
      font-weight: 700;
      letter-spacing: .05em;
    }
    .kiosk-mode #kiosk-exit-btn {
      display: inline-flex !important;
      background: rgba(255,255,255,.15);
      border-color: rgba(255,255,255,.4);
      color: #fff;
    }
    .kiosk-mode #kiosk-exit-btn:hover { background: rgba(255,255,255,.28); }
    .kiosk-mode main {
      max-width: none;
      grid-template-columns: 1fr;
      padding: 0;
      height: calc(100vh - 3.5rem);
      overflow: hidden;
    }
    .kiosk-mode .toolbar { display: none; }
    .kiosk-mode .item-section { overflow: hidden; background: transparent; border: none; box-shadow: none; }
    .kiosk-mode .item-section .section-head { display: none; }
    .kiosk-mode .items-controls, .kiosk-mode .filter-bar,
    .kiosk-mode .stats-summary, .kiosk-mode .filter-chips,
    .kiosk-mode .bulk-toolbar { display: none; }
    .display-mode .items-controls, .display-mode .filter-bar { display: none; }
    .kiosk-mode #items {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
      gap: .75rem;
      padding: .75rem 1.25rem;
      height: calc(100vh - 3.8rem);
      overflow-y: auto;
      overflow-x: hidden;
      scrollbar-width: thin;
      scrollbar-color: #b2d8c4 transparent;
    }
    .kiosk-mode .item {
      background: #fff;
      border: 1.5px solid #c5e0d0;
      border-radius: .55rem;
      padding: .85rem 1rem;
      font-size: clamp(12px, .88vw, 16px);
      display: flex;
      flex-direction: column;
      gap: .35rem;
      cursor: default;
      box-shadow: 0 1px 4px rgba(0,0,0,.07);
      animation: kiosk-card-in .28s ease both;
    }
    .kiosk-mode .item:nth-child(2n) { animation-delay: .04s; }
    .kiosk-mode .item:nth-child(3n) { animation-delay: .08s; }
    .kiosk-mode .item:hover { border-color: #1a7a4a; }
    .kiosk-mode .item .status-badge { font-weight: 700; }
    .kiosk-mode .item .title { font-weight: 700; color: #0d2b1a; font-size: 1em; }
    .kiosk-mode .item .meta { font-size: .8em; color: #4a7a5e; }
    .kiosk-mode .item .source { display: none; }
    .kiosk-mode .item-check { display: none !important; }
    .kiosk-mode .item.kiosk-changed {
      border-color: #f59e0b;
      box-shadow: 0 0 0 3px rgba(245, 158, 11, .25), 0 1px 6px rgba(0,0,0,.1);
      animation: kiosk-change-pulse 1.4s ease both;
    }
    .kiosk-mode .kiosk-progress-bar {
      position: fixed;
      bottom: 0; left: 0; right: 0;
      height: 4px;
      background: #c5e0d0;
    }
    .kiosk-mode .kiosk-progress-bar::after {
      content: "";
      display: block;
      height: 100%;
      background: #1a7a4a;
      animation: kiosk-progress var(--kiosk-interval, 60s) linear infinite;
    }
    @keyframes kiosk-progress {
      from { width: 0 } to { width: 100% }
    }
    @keyframes kiosk-card-in {
      from { opacity: 0; transform: translateY(10px) scale(.98); }
      to { opacity: 1; transform: none; }
    }
    @keyframes kiosk-change-pulse {
      0% { transform: scale(.985); background: #fff7ed; }
      35% { transform: scale(1.012); background: #fff; }
      100% { transform: none; background: #fff; }
    }
    /* ── Item grouping headers ── */
    .group-header {
      display: flex;
      align-items: center;
      gap: .45rem;
      margin: .35rem 0 -.2rem;
      font-size: .78rem;
      font-weight: 700;
      letter-spacing: .05em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .group-header::after { content: ""; flex: 1; border-top: 1px solid var(--line); }
    .group-header .n { font-weight: 600; color: var(--muted); text-transform: none; letter-spacing: 0; }
    /* ── Keyboard focus (j/k navigation) ── */
    .item.kb-focus { outline: 2px solid var(--accent); outline-offset: 1px; }
    /* ── Inline status cycling ── */
    .status-badge.clickable { cursor: pointer; }
    .status-badge.clickable:hover { box-shadow: 0 0 0 2px var(--accent); }
    /* ── Relative due labels ── */
    .due-rel { margin-left: .4rem; font-size: .78rem; font-weight: 700; color: var(--muted); white-space: nowrap; }
    .due-rel.overdue { color: var(--danger); }
    .due-rel.due-soon { color: #b45309; }
    [data-theme="dark"] .due-rel.due-soon { color: #fbbf24; }
    /* ── Undo toast ── */
    .toast .undo-btn {
      margin-left: .75rem;
      padding: .15rem .6rem;
      font-size: .8rem;
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      border-radius: .35rem;
    }
    .modal-hint { margin: -.35rem 0 .85rem; color: var(--muted); font-size: .86rem; }
    .undo-history-list { display: grid; gap: .45rem; }
    .undo-history-row {
      display: flex;
      align-items: center;
      gap: .6rem;
      padding: .55rem .65rem;
      border: 1px solid var(--line);
      border-radius: var(--r-md);
      background: var(--panel-2);
    }
    .undo-history-row .undo-history-label { flex: 1; min-width: 0; overflow-wrap: anywhere; }
    .undo-history-row .undo-history-time {
      color: var(--muted);
      font-size: .76rem;
      white-space: nowrap;
    }
    /* ── Blocked badges (items + agenda) ── */
    .blocked-badge {
      display: inline-flex;
      align-items: center;
      margin-left: .35rem;
      padding: .08rem .38rem;
      border-radius: 999px;
      background: #fee2e2;
      color: #991b1b;
      font-size: .7rem;
      font-weight: 700;
      cursor: help;
      vertical-align: middle;
    }
    [data-theme="dark"] .blocked-badge { background: #4c1d1d; color: #fca5a5; }
    .agenda-blocked-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    /* ── Blocker chain ("Why blocked") in drawer ── */
    .blocker-chain { display: grid; gap: .3rem; margin-bottom: .6rem; }
    .blocker-chain-row {
      display: flex;
      align-items: center;
      gap: .4rem;
      padding: .3rem .45rem;
      border-radius: .35rem;
      border: 1px solid #fca5a5;
      background: #fff8f8;
      font-size: .85rem;
    }
    [data-theme="dark"] .blocker-chain-row { background: #2d1f1f; border-color: #7f3535; }
    /* ── Graph layout buttons + export ── */
    .graph-layout-bar { display: flex; gap: .3rem; align-items: center; flex-wrap: wrap; }
    .graph-layout-btn, .graph-export-btn {
      padding: .18rem .5rem;
      font-size: .74rem;
      border-radius: .35rem;
      border: 1px solid var(--line-strong);
      background: var(--panel);
      color: var(--muted);
      cursor: pointer;
      font-weight: 600;
    }
    .graph-layout-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    .graph-node.missing circle { fill: var(--panel); stroke: #9ca3af; stroke-dasharray: 4 3; }
    .graph-node.missing text { font-style: italic; fill: #9ca3af; }
    /* ── est/elapsed progress bar (drawer) ── */
    .progress-wrap { display: grid; gap: .25rem; }
    .progress-track { height: .55rem; border-radius: 999px; background: var(--soft); overflow: hidden; border: 1px solid var(--line); }
    .progress-fill { height: 100%; background: var(--accent); border-radius: 999px; transition: width .2s; }
    .progress-fill.over { background: var(--danger); }
    .progress-label { font-size: .78rem; color: var(--muted); }
    /* ── Drawer due quick actions ── */
    .due-quick-bar { display: flex; gap: .3rem; flex-wrap: wrap; align-items: center; }
    .due-quick-bar button { padding: .18rem .55rem; font-size: .76rem; }
    /* ── Command palette ── */
    .cmdk-backdrop {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 20, 18, .45);
      z-index: 600;
      align-items: flex-start;
      justify-content: center;
      padding-top: 12vh;
    }
    .cmdk-backdrop.open { display: flex; }
    .cmdk {
      width: min(560px, 92vw);
      background: var(--panel);
      border: 1px solid var(--line-strong);
      border-radius: .7rem;
      box-shadow: 0 12px 48px rgba(0,0,0,.28);
      overflow: hidden;
    }
    .cmdk input {
      width: 100%;
      border: none;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      padding: .8rem 1rem;
      font-size: 1rem;
      background: var(--panel);
      color: var(--ink);
      outline: none;
    }
    .cmdk-list { max-height: 46vh; overflow-y: auto; padding: .35rem; }
    .cmdk-row {
      display: flex;
      align-items: center;
      gap: .55rem;
      padding: .5rem .65rem;
      border-radius: .45rem;
      cursor: pointer;
      font-size: .9rem;
    }
    .cmdk-row.focus, .cmdk-row:hover { background: var(--soft); }
    .cmdk-row .cmdk-kind {
      font-size: .7rem;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .05em;
      min-width: 3.4rem;
    }
    .cmdk-section {
      padding: .55rem .65rem .18rem;
      color: var(--muted);
      font-size: .68rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .08em;
      border-top: 1px solid var(--line);
    }
    .cmdk-section:first-child { border-top: none; }
    .cmdk-empty { padding: .8rem 1rem; color: var(--muted); font-size: .88rem; }
    /* ── Print stylesheet ── */
    @media print {
      header .toolbar, .detail-drawer, #toast-container, #ctx-menu,
      .filter-bar, .quick-add-bar, .bulk-toolbar, .modal-backdrop, .cmdk-backdrop,
      .item-check, .section-head .toolbar, #read-only-banner,
      .header-workspace-tabs, .items-controls, #back-to-top, .brand-mark { display: none !important; }
      header { position: static; border-bottom: 1px solid #ccc; }
      body { background: #fff; color: #000; font-size: 12px; }
      main { display: block; max-width: none; padding: 0; }
      section { border: none; }
      .item { border: none; border-bottom: 1px solid #ccc; border-radius: 0; break-inside: avoid; }
      .item.overdue, .item.due-soon { border-left: 3px solid #888; }
    }
    @media (max-width: 1080px) {
      .subtitle { display: none; }
      .header-workspace-tabs { order: 3; flex: 1 1 100%; }
      header > .toolbar {
        flex: 1 1 100%;
        justify-content: flex-start;
      }
    }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .workspace-tabs { justify-content: flex-start; }
      .dash-grid { grid-template-columns: 1fr; }
      .display-mode main { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      header { flex-wrap: wrap; align-items: center; }
      main, header { padding-left: .75rem; padding-right: .75rem; }
      .section-head { align-items: stretch; flex-direction: column; }
      .toolbar > *, .actions > *, .section-head button { flex: 1 1 100%; }
      .search-wrap { flex: 1 1 100%; }
      .search-wrap input { width: 100%; }
      .items-controls > * { flex: 1 1 40%; }
      .workspace-tabs { margin-inline: -.15rem; }
      .workspace-tab { padding: .32rem .6rem; font-size: .78rem; }
      .view-guide { padding: 0 .75rem; }
      .view-guide-card { align-items: stretch; }
      .view-guide-actions { justify-content: stretch; }
      .view-guide-actions button { flex: 1 1 8rem; }
      .kpi-row { grid-template-columns: repeat(2, 1fr); }
      .review-range-bar > * { flex: 1 1 100%; }
      .item { grid-template-columns: auto auto auto minmax(0, 1fr) auto; }
      .item-check { display: none; }
      .source { grid-column: 1 / -1; }
      form.stack { grid-template-columns: 1fr; }
      .detail-drawer { padding: .5rem; }
      .detail-modal { width: 100%; max-height: 96vh; border-radius: var(--r-md); }
      #back-to-top { bottom: 1rem; left: 1rem; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#workspace">Skip to content</a>
  <div id="read-only-banner" style="display:none;background:#d97706;color:#fff;text-align:center;font-size:.78rem;padding:.25rem .75rem;letter-spacing:.02em;">
    ⚠️ Read-only demo — write operations are disabled.
  </div>
  <header>
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">✓</span>
      <div>
        <h1>life.txt</h1>
        <p class="subtitle">Plain text tasks, schedule, presence, and notes.</p>
      </div>
    </div>
    <div class="toolbar">
      <button id="new-item-btn" class="help-target" data-workspace="new" data-help="Create a life.txt record. Pick a status, type, title, and detail keys; press n to open this editor from the keyboard." onclick="newItem()" title="Create a new record (n)">＋ New</button>
      <button id="dark-btn" class="secondary" onclick="toggleDarkMode()" title="Toggle dark mode (d)">🌙</button>
      <button id="density-btn" class="secondary" onclick="toggleDensity()" title="Toggle compact density">▤</button>
      <button id="fullscreen-btn" class="secondary" onclick="toggleFullscreen()" title="Toggle fullscreen (f)">⛶</button>
      <button id="notif-btn" class="secondary" onclick="toggleNotifPanel()" title="Open notifications / enable browser alerts">Notifications</button>
      <button id="refresh-btn" class="secondary" onclick="triggerRefresh()" title="Refresh (r)">Refresh</button>
      <button class="secondary" onclick="openCmdk()" title="Command palette (Ctrl+K)">⌘</button>
      <button class="secondary" onclick="openHelpModal()" title="Keyboard shortcuts (?)">?</button>
      <button id="git-status-badge" class="git-badge" style="display:none" onclick="openGitModal()"></button>
      <button id="display-exit-btn" class="secondary" style="display:none" onclick="switchWorkspace('')" title="Exit display mode">Exit Display</button>
      <span id="kiosk-clock" style="display:none"></span>
      <button id="kiosk-exit-btn" class="secondary" style="display:none" onclick="toggleKioskMode()" title="Exit kiosk mode (Esc)">✕ Exit</button>
    </div>
    <nav class="workspace-tabs header-workspace-tabs" id="workspace-tabs" aria-label="Views" role="tablist">
      <button type="button" class="workspace-tab" data-view="dashboard" onclick="switchWorkspace('dashboard')">🏠 Dashboard</button>
      <button type="button" class="workspace-tab" data-view="" onclick="switchWorkspace('')">📋 Items</button>
      <button type="button" class="workspace-tab" data-view="agenda" onclick="switchWorkspace('agenda')">📅 Agenda</button>
      <button type="button" class="workspace-tab" data-view="timeline" onclick="switchWorkspace('timeline')">🕒 Timeline</button>
      <button type="button" class="workspace-tab" data-view="focus" onclick="switchWorkspace('focus')">🎯 Focus</button>
      <button type="button" class="workspace-tab" data-view="review" onclick="switchWorkspace('review')">📝 Review</button>
      <button type="button" class="workspace-tab" data-view="messages" onclick="switchWorkspace('messages')">💬 Messages</button>
      <button type="button" class="workspace-tab" data-view="team" onclick="switchWorkspace('team')">🟢 Team</button>
      <button type="button" class="workspace-tab" data-view="status" onclick="switchWorkspace('status')">👥 Status</button>
      <button type="button" class="workspace-tab" data-view="notifications" onclick="switchWorkspace('notifications')">🔔 Notifications</button>
      <button type="button" class="workspace-tab" data-view="stats" onclick="switchWorkspace('stats')">📊 Stats</button>
      <button type="button" class="workspace-tab" data-view="graph" onclick="switchWorkspace('graph')">🕸️ Graph</button>
      <button type="button" class="workspace-tab" data-view="display" onclick="switchWorkspace('display')" title="Open a read-focused wall display mode">🪧 Display</button>
      <button type="button" class="workspace-tab" data-view="kiosk" onclick="switchWorkspace('kiosk')">🖥️ Kiosk</button>
    </nav>
  </header>
  <div id="view-guide" class="view-guide" aria-live="polite"></div>
  <main id="workspace" tabindex="-1">
    <section class="item-section page" data-page="items">
      <div class="section-head">
        <h2><span class="h2-icon" aria-hidden="true">📋</span><span id="items-heading-label">Items</span></h2>
        <div class="toolbar">
          <div class="search-wrap">
            <span class="search-icon" aria-hidden="true">🔍</span>
            <input id="search" placeholder="Search (/)" list="tag-suggestions" autocomplete="off">
            <span id="search-count"></span>
          </div>
          <label class="inline"><input id="open-only" type="checkbox"> Open</label>
          <button onclick="loadItems()">Apply</button>
        </div>
      </div>
      <div class="items-controls">
          <select id="kind" title="Filter by type">
            <option value="">All types</option>
            <option value="T">Task</option>
            <option value="E">Event</option>
            <option value="D">Deadline</option>
            <option value="R">Reminder</option>
            <option value="H">Habit</option>
            <option value="N">Note</option>
            <option value="S">Status</option>
            <option value="M">Message</option>
            <option value="J">Journal</option>
          </select>
          <select id="sort" title="Sort by">
            <option value="line">Line</option>
            <option value="time">Time</option>
            <option value="title">Title</option>
            <option value="type">Type</option>
            <option value="status">Status</option>
            <option value="source">Source</option>
          </select>
          <select id="order" title="Sort order">
            <option value="asc">Asc</option>
            <option value="desc">Desc</option>
          </select>
          <select id="group-by" title="Group items" onchange="loadItems()">
            <option value="">No grouping</option>
            <option value="project">Group: Project</option>
            <option value="type">Group: Type</option>
            <option value="status">Group: Status</option>
            <option value="source">Group: Source</option>
          </select>
          <input id="limit" inputmode="numeric" placeholder="Limit" title="Max rows">
          <select id="export-select" title="Download the currently filtered items" onchange="if(this.value){exportItems(this.value);this.value='';}" style="margin-left:auto">
            <option value="">⇩ Export…</option>
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
            <option value="markdown">Markdown</option>
          </select>
      </div>
      <div class="quick-add-bar" id="quick-add-bar" style="display:none">
        <input id="quick-line" placeholder="[ ] T My_task  due:tomorrow  project:work" autocomplete="off" onkeydown="if((e=event).key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();quickAddLine();}">
        <span id="quick-check-msg" class="check-msg"></span>
        <button onclick="quickAddLine()">Add</button>
        <span class="hint" style="font-size:.73rem;color:var(--muted)">Ctrl+↵</span>
        <span class="hint">q or Escape to close</span>
      </div>
      <div class="filter-bar" id="status-filter-bar">
        <button class="filter-btn" data-status="" onclick="setStatusFilter('')">All</button>
        <button class="filter-btn" data-status="[ ]" onclick="toggleStatusFilter('[ ]')">○ Open</button>
        <button class="filter-btn" data-status="[/]" onclick="toggleStatusFilter('[/]')">◑ In Progress</button>
        <button class="filter-btn" data-status="[x]" onclick="toggleStatusFilter('[x]')">✓ Done</button>
        <button class="filter-btn" data-status="[-]" onclick="toggleStatusFilter('[-]')">✕ Cancelled</button>
        <button class="filter-btn" data-status="__blocked__" onclick="toggleBlockedFilter()" title="Items blocked by open dependencies">⚡ Blocked</button>
      </div>
      <div id="filter-chips" class="filter-chips"></div>
      <div id="stats-summary" class="stats-summary" style="display:none"></div>
      <div id="diagnostics"></div>
      <div id="bulk-toolbar" class="bulk-toolbar">
        <span id="bulk-count" class="bulk-toolbar-count">0 selected</span>
        <button class="secondary" onclick="bulkMarkDone()" title="Mark selected as done">✓ Done</button>
        <select id="bulk-status-select" title="Set status of selected items" onchange="if(this.value){bulkSetStatus(this.value);this.value='';}">
          <option value="">Set status…</option>
          <option value="[ ]">○ Open</option>
          <option value="[/]">◑ In Progress</option>
          <option value="[x]">✓ Done</option>
          <option value="[-]">✕ Cancelled</option>
          <option value="[>]">→ Deferred</option>
        </select>
        <button class="secondary" onclick="bulkSetProject()" title="Set project on selected items">Set project…</button>
        <button class="danger" onclick="bulkDelete()" title="Delete selected">Delete</button>
        <button class="secondary" onclick="bulkClearSelection()" title="Clear selection">✕ Clear</button>
      </div>
      <div id="items" class="content"></div>
    </section>
    <section class="dashboard-section page" data-page="dashboard">
      <div class="section-head">
        <h2><span class="h2-icon" aria-hidden="true">🏠</span>Dashboard<span id="dash-date" style="margin-left:.5rem;font-weight:400;text-transform:none;letter-spacing:0"></span></h2>
        <button class="secondary" onclick="loadDashboard()" title="Refresh dashboard">↺</button>
      </div>
      <div class="section-body dashboard-body">
        <div id="dash-kpis" class="kpi-row"><div class="empty">Loading…</div></div>
        <div class="dash-grid" id="dash-grid">
          <div class="dash-card" data-dashboard-card="today">
            <div class="dash-card-title">📅 Today</div>
            <div id="dash-today" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
          <div class="dash-card" data-dashboard-card="needs_attention">
            <div class="dash-card-title">⚠️ Needs attention</div>
            <div id="dash-overdue" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
          <div class="dash-card" data-dashboard-card="completions">
            <div class="dash-card-title">📈 Completions (last 14 days)</div>
            <div class="chart-panel" style="height:180px"><canvas id="dash-chart"></canvas></div>
          </div>
          <div class="dash-card" data-dashboard-card="projects">
            <div class="dash-card-title">📁 Projects</div>
            <div id="dash-projects" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
        </div>
      </div>
    </section>
    <section class="focus-section page" data-page="focus">
      <div class="section-head">
        <h2><span class="h2-icon" aria-hidden="true">🎯</span>Focus<span id="focus-date" style="margin-left:.5rem;font-weight:400;text-transform:none;letter-spacing:0"></span></h2>
        <button class="secondary" onclick="loadFocus()" title="Refresh focus list">↺</button>
      </div>
      <div class="section-body focus-body">
        <div class="focus-quick-add">
          <input id="focus-quick-title" placeholder="Add a task due today… (Enter)" autocomplete="off"
                 onkeydown="if(event.key==='Enter'){event.preventDefault();focusQuickAdd();}">
          <button onclick="focusQuickAdd()">Add</button>
        </div>
        <div id="focus-list" class="focus-list"><div class="empty">Loading…</div></div>
      </div>
    </section>
    <section class="review-section page" data-page="review">
      <div class="section-head">
        <h2><span class="h2-icon" aria-hidden="true">📝</span>Review<span id="review-range-label" style="margin-left:.5rem;font-weight:400;text-transform:none;letter-spacing:0"></span></h2>
        <button class="secondary" onclick="loadReview()" title="Refresh review">↺</button>
      </div>
      <div class="section-body review-body">
        <div class="review-range-bar" id="review-range-bar" role="group" aria-label="Review range">
          <button type="button" class="review-range-btn active" data-range="week" onclick="setReviewRange('week')">This week</button>
          <button type="button" class="review-range-btn" data-range="last-week" onclick="setReviewRange('last-week')">Last week</button>
          <button type="button" class="review-range-btn" data-range="month" onclick="setReviewRange('month')">This month</button>
          <button type="button" class="review-range-btn" data-range="last-month" onclick="setReviewRange('last-month')">Last month</button>
          <input id="review-project" class="review-filter-input" placeholder="Project" autocomplete="off">
          <input id="review-from" class="review-filter-input" type="date" title="Review start date">
          <input id="review-to" class="review-filter-input" type="date" title="Review end date">
          <button type="button" class="secondary" onclick="setReviewCustom()">Apply</button>
          <button type="button" class="secondary" onclick="copyReviewMarkdown()">Copy Markdown</button>
        </div>
        <div id="review-kpis" class="kpi-row"><div class="empty">Loading…</div></div>
        <div class="dash-grid">
          <div class="dash-card">
            <div class="dash-card-title">✅ Completed</div>
            <div id="review-completed" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
          <div class="dash-card">
            <div class="dash-card-title">🔁 Habits</div>
            <div id="review-habits" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
          <div class="dash-card">
            <div class="dash-card-title">📓 Journal &amp; mood</div>
            <div id="review-journal" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
          <div class="dash-card">
            <div class="dash-card-title">⏱️ Elapsed by project</div>
            <div id="review-elapsed" class="dash-list"><div class="empty">Loading…</div></div>
          </div>
        </div>
      </div>
    </section>
    <section class="stats-section page" data-page="stats">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">📊</span>Statistics</h2>
          <button class="secondary" onclick="refreshCharts()" title="Refresh statistics">↺</button>
        </div>
        <div class="section-body">
          <div class="chart-tabs">
            <button class="chart-tab active" onclick="showChart('tasks', this)">Tasks</button>
            <button class="chart-tab" onclick="showChart('habits', this)">Habits</button>
            <button class="chart-tab" onclick="showChart('habits-heatmap', this)">Heatmap</button>
            <button class="chart-tab" onclick="showChart('mood', this)">Mood</button>
            <button class="chart-tab" onclick="showChart('elapsed', this)">Elapsed</button>
          </div>
          <div class="chart-group-bar" id="chart-group-bar" style="display:none">
            <button class="chart-group-btn active" onclick="setChartGroup('daily',this)">Daily</button>
            <button class="chart-group-btn" onclick="setChartGroup('weekly',this)">Weekly</button>
            <button class="chart-group-btn" onclick="setChartGroup('monthly',this)">Monthly</button>
            <button class="chart-group-btn" onclick="exportChartCsv()" style="margin-left:auto" title="Download chart data as CSV">&#x2193; CSV</button>
          </div>
          <div id="chart-container" style="padding:.75rem 1rem">
            <div class="chart-panel"><canvas id="main-chart"></canvas></div>
          </div>
          <div style="padding:.25rem 1rem 0;display:flex;gap:.4rem;align-items:center;flex-wrap:wrap">
            <label style="font-size:.76rem;color:var(--muted)">From<input type="date" id="breakdown-from" oninput="loadStatsBreakdown()" style="margin-left:.3rem;font-size:.76rem;padding:.12rem .3rem"></label>
            <label style="font-size:.76rem;color:var(--muted)">To<input type="date" id="breakdown-to" oninput="loadStatsBreakdown()" style="margin-left:.3rem;font-size:.76rem;padding:.12rem .3rem"></label>
            <button class="secondary" style="font-size:.74rem;padding:.12rem .4rem" onclick="document.getElementById('breakdown-from').value='';document.getElementById('breakdown-to').value='';loadStatsBreakdown()">All</button>
          </div>
          <div id="stats-breakdown" style="padding:.5rem 1rem 1rem;display:grid;grid-template-columns:1fr 1fr;gap:.75rem"></div>
        </div>
      </section>
      <section class="graph-section page" data-page="graph">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">🕸️</span>Graph</h2>
          <button class="secondary" onclick="loadGraphPanel()" title="Refresh dependency graph">Refresh</button>
        </div>
        <div class="section-body">
          <div class="graph-toolbar">
            <input id="graph-root" placeholder="Root id (optional)" autocomplete="off">
            <input id="graph-depth" placeholder="Depth" inputmode="numeric" style="max-width:4.2rem">
            <button class="secondary" onclick="loadGraphPanel()">Apply</button>
          </div>
          <div class="graph-layout-bar" style="padding:.45rem 1rem;border-bottom:1px solid var(--line)">
            <button class="graph-layout-btn" data-layout="ring" onclick="setGraphLayout('ring')" title="Ring layout (focus in center)">Ring</button>
            <button class="graph-layout-btn" data-layout="lr" onclick="setGraphLayout('lr')" title="Layered left-to-right">LR</button>
            <button class="graph-layout-btn" data-layout="tb" onclick="setGraphLayout('tb')" title="Layered top-to-bottom">TB</button>
            <span style="flex:1"></span>
            <button class="graph-export-btn" onclick="exportGraphSvg()" title="Download graph as SVG">⇩ SVG</button>
            <button class="graph-export-btn" onclick="exportGraphPng()" title="Download graph as PNG">⇩ PNG</button>
          </div>
          <div id="graph-panel" class="graph-panel"><div class="empty">Open this panel to load the ID graph.</div></div>
        </div>
      </section>
      <section class="agenda-section page" data-page="agenda">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">📅</span>Agenda<span id="agenda-overdue-badge" class="overdue-badge" style="display:none"></span></h2>
          <button id="agenda-blocked-btn" class="secondary agenda-blocked-btn" style="font-size:.72rem;padding:.18rem .5rem" onclick="toggleAgendaBlocked()" title="Cycle: show all / only blocked / hide blocked">⚡ All</button>
          <label class="agenda-limit-ctrl" title="Max agenda rows (0 = all)">
            <span class="agenda-limit-label">Rows</span>
            <input type="number" id="agenda-limit-spinner" min="0" max="100" step="1" value="8" style="width:3.2rem">
          </label>
        </div>
        <div class="section-body">
          <div id="agenda" class="stack"></div>
        </div>
      </section>
      <section class="status-section page" data-page="status">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">👥</span>Status</h2>
          <button id="status-active-btn" class="secondary" style="font-size:.72rem;padding:.18rem .5rem" onclick="toggleStatusActive()" title="Toggle between active-only and latest record for everyone">● Active only</button>
          <button class="secondary" onclick="loadStatus()" title="Refresh status">↺</button>
        </div>
        <div class="section-body">
          <div id="status" class="stack"></div>
        </div>
      </section>
      <section class="team-section page" data-page="team">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">🟢</span>Team</h2>
          <button class="secondary" onclick="loadTeam()" title="Refresh team board">↺</button>
        </div>
        <div class="section-body">
          <div id="team-board" class="team-grid"><div class="empty">Loading…</div></div>
        </div>
      </section>
      <section class="timeline-section page" data-page="timeline">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">🕒</span>Timeline<span id="tl-range-label" style="margin-left:.5rem;font-weight:400;text-transform:none;letter-spacing:0"></span></h2>
          <button class="secondary" onclick="loadTimeline()" title="Refresh timeline">↺</button>
        </div>
        <div class="section-body timeline-body">
          <div class="tl-controls" role="group" aria-label="Timeline range">
            <button type="button" class="review-range-btn active" data-range="today" onclick="setTimelineRange('today')">Today</button>
            <button type="button" class="review-range-btn" data-range="24h" onclick="setTimelineRange('24h')">Next 24h</button>
            <button type="button" class="review-range-btn" data-range="week" onclick="setTimelineRange('week')">Week</button>
          </div>
          <div id="timeline"><div class="empty">Loading…</div></div>
        </div>
      </section>
      <section class="notifications-section page" data-page="notifications">
        <div class="section-head">
          <h2><span class="h2-icon" aria-hidden="true">🔔</span>Notifications</h2>
          <div id="notif-permission-badge"></div>
        </div>
        <div class="section-body">
          <div id="notif-permission-bar" class="notif-permission" style="display:none"></div>
          <div id="notifications" class="stack"></div>
        </div>
      </section>
  </main>
  <!-- Record editor modal -->
  <div id="editor-modal" class="modal-backdrop" onclick="if(event.target===this)closeEditorModal()">
    <div class="modal editor-modal" role="dialog" aria-modal="true" aria-labelledby="editor-heading">
      <div class="editor-modal-head">
        <h3 id="editor-heading">New Record</h3>
        <button type="button" class="drawer-close-btn" onclick="closeEditorModal()" title="Close (Esc)">✕</button>
      </div>
      <form class="stack" onsubmit="saveItem(event)">
        <div class="editor-help-strip wide">Hover or focus the ? badges for field help. Type-specific suggested detail keys appear above the Details box.</div>
        <label class="field-label">
          <span class="field-label-head"><span>Status</span><span class="field-help" tabindex="0" data-help="Workflow state: [ ] open, [/] active, [x] done, [-] cancelled, [>] deferred, [?] maybe, [N] note.">?</span></span>
          <select id="edit-status">
            <option>[ ]</option><option>[/]</option><option>[x]</option>
            <option>[-]</option><option>[>]</option><option>[?]</option><option>[N]</option>
          </select>
        </label>
        <label class="field-label">
          <span class="field-label-head"><span>Type</span><span class="field-help" tabindex="0" data-help="Record kind: T task, E event, D deadline, R reminder, H habit, N note, S presence status, M message, J journal.">?</span></span>
          <select id="edit-type" aria-describedby="type-hints">
            <option>T</option><option>E</option><option>D</option><option>R</option>
            <option>H</option><option>N</option><option>S</option><option>M</option><option>J</option>
          </select>
        </label>
        <label class="wide field-label">
          <span class="field-label-head"><span>Title</span><span class="field-help" tabindex="0" data-help="Short human-readable record text. Use quotes in raw life.txt if the title contains spaces.">?</span></span>
          <input id="edit-title" required>
        </label>
        <label class="wide field-label">
          <span class="field-label-head"><span>Details</span><span class="field-help" tabindex="0" data-help="One key:value per line. Repeat the same key for multiple values. Use body: or | continuation lines for longer text.">?</span></span>
          <div id="type-hints" class="type-hints" style="display:none"></div>
          <textarea id="edit-details" placeholder="due:2026-06-12&#10;project:research"></textarea>
        </label>
        <div id="editor-note" class="note wide">Create a new record or select an editable row.</div>
        <div id="import-raw-row">
          <label class="wide" style="margin-top:.35rem">Import raw line
            <input id="import-raw-input" placeholder="[ ] T Task_title due:2026-06-28 project:work" autocomplete="off">
          </label>
          <div id="import-raw-preview" class="parse-preview" style="display:none"></div>
          <div class="actions" style="margin-top:.25rem">
            <button type="button" onclick="importRawLine()">Import</button>
            <button type="button" class="secondary" onclick="toggleImportRaw(false)">Cancel</button>
          </div>
        </div>
        <div class="actions">
          <button id="save-button">Create</button>
          <button id="delete-button" class="danger" type="button" onclick="deleteSelected()" disabled>Delete</button>
          <button type="button" class="secondary" onclick="toggleImportRaw()" title="Paste a raw life.txt line to populate the form">Import raw</button>
        </div>
      </form>
    </div>
  </div>
  <!-- Detail modal -->
  <div id="detail-drawer" class="modal-backdrop detail-drawer" role="presentation" onclick="if(event.target===this)closeDrawer()">
    <div class="detail-modal" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <div class="drawer-head">
        <h3 id="drawer-title">Record Detail</h3>
        <div id="drawer-head-btns" style="display:flex;gap:.35rem;flex-wrap:wrap;align-items:center">
          <button class="secondary" onclick="drawerMarkDone()" id="drawer-done-btn" disabled>Done</button>
          <button class="secondary" id="drawer-edit-btn" onclick="drawerEdit()">Edit</button>
          <button class="secondary" id="drawer-copy-id" onclick="drawerCopyId()" title="Copy item ID to clipboard" style="display:none">Copy ID</button>
          <button class="secondary" id="drawer-share-btn" onclick="drawerShareLink()" title="Copy deep link to this item">Share</button>
          <button class="secondary" onclick="drawerCopyMarkdown()" title="Copy item as Markdown">MD</button>
          <button class="danger" onclick="drawerDelete()" id="drawer-delete-btn" disabled>Delete</button>
        </div>
        <button class="drawer-close-btn" onclick="closeDrawer()" title="Close (Esc)">✕</button>
      </div>
      <div class="drawer-body" id="drawer-body"></div>
    </div>
  </div>

  <!-- Command palette -->
  <div class="cmdk-backdrop" id="cmdk-backdrop" onclick="if(event.target===this)closeCmdk()">
    <div class="cmdk" role="dialog" aria-label="Command palette">
      <input id="cmdk-input" placeholder="Type a command or search items…" autocomplete="off">
      <div id="cmdk-list" class="cmdk-list"></div>
    </div>
  </div>

  <!-- Toast container -->
  <div id="toast-container" aria-live="polite" aria-atomic="true" role="status"></div>
  <div id="hm-tooltip" class="hm-tooltip"></div>
  <div id="ui-help-tooltip" class="ui-help-tooltip" role="tooltip" aria-hidden="true"></div>
  <button id="back-to-top" class="secondary" onclick="window.scrollTo({top:0,behavior:'smooth'})" title="Back to top">↑</button>
  <!-- Context menu -->
  <div id="ctx-menu" role="menu" aria-label="Item context menu">
    <div class="ctx-item" onclick="ctxMarkDone()" id="ctx-done">Mark Done</div>
    <div class="ctx-item" onclick="ctxCopyTitle()">Copy Title</div>
    <div class="ctx-item" onclick="ctxCopyId()">Copy ID</div>
    <div class="ctx-item" onclick="ctxCopyLineNumber()">Copy Line Number</div>
    <div class="ctx-item" onclick="ctxShareLink()">Copy Link</div>
    <div class="ctx-item" onclick="ctxShowRawPath()">Show File Path</div>
    <div class="ctx-item" onclick="ctxDuplicate()">Duplicate</div>
    <hr class="ctx-sep">
    <div class="ctx-item" onclick="ctxOpenDrawer()">Open Detail</div>
    <div class="ctx-item" onclick="ctxEdit()">Edit</div>
  </div>
  <!-- Tag datalist for quick filter -->
  <datalist id="tag-suggestions"></datalist>

  <!-- Keyboard Help Modal -->
  <div class="modal-backdrop" id="help-modal" onclick="if(event.target===this)closeHelpModal()">
    <div class="modal">
      <h3>Keyboard shortcuts</h3>
      <table>
        <tr><td>/</td><td>Focus search</td></tr>
        <tr><td>Ctrl+K</td><td>Command palette (actions + jump to item)</td></tr>
        <tr><td>j / k</td><td>Move keyboard focus down / up in item list</td></tr>
        <tr><td>Enter</td><td>Open focused item in detail modal</td></tr>
        <tr><td>x</td><td>Toggle bulk selection on focused item</td></tr>
        <tr><td>n</td><td>New item (opens the record editor)</td></tr>
        <tr><td>q</td><td>Toggle quick-add bar</td></tr>
        <tr><td>r</td><td>Refresh current view</td></tr>
        <tr><td>s</td><td>Go to Stats view</td></tr>
        <tr><td>d</td><td>Toggle dark mode</td></tr>
        <tr><td>f</td><td>Toggle fullscreen</td></tr>
        <tr><td>Ctrl+K display</td><td>Open or toggle Display mode</td></tr>
        <tr><td>g</td><td>Jump to line number (opens detail modal)</td></tr>
        <tr><td>Shift+K</td><td>Toggle kiosk mode</td></tr>
        <tr><td>Esc</td><td>Close modal / palette / blur input</td></tr>
        <tr><td>[ / ]</td><td>Prev / next item in detail modal</td></tr>
        <tr><td>&lt; / &gt;</td><td>Prev / next status filter</td></tr>
        <tr><td>?</td><td>Show / hide this help</td></tr>
      </table>
      <div class="actions" style="margin-top:1rem"><button onclick="closeHelpModal()">Close</button></div>
    </div>
  </div>

  <!-- Undo history modal -->
  <div class="modal-backdrop" id="undo-modal" onclick="if(event.target===this)closeUndoHistoryModal()">
    <div class="modal">
      <h3>Undo history</h3>
      <p class="modal-hint">The browser keeps the last five undoable actions from this session.</p>
      <div id="undo-history-list" class="undo-history-list"></div>
      <div class="actions" style="margin-top:1rem">
        <button class="secondary" onclick="closeUndoHistoryModal()">Close</button>
      </div>
    </div>
  </div>

  <!-- Git commit/push modal -->
  <div class="modal-backdrop" id="git-modal" onclick="if(event.target===this)closeGitModal()">
    <div class="modal">
      <h3 id="git-modal-title">Git</h3>
      <div id="git-modal-body" style="display:grid;gap:.75rem">
        <pre id="git-status-output" style="font-size:.78rem;color:var(--muted);background:var(--bg);border:1px solid var(--line);border-radius:.35rem;padding:.4rem .7rem;min-height:2rem;max-height:8rem;overflow:auto;white-space:pre-wrap">Loading…</pre>
        <label>Commit message
          <input id="git-commit-msg" placeholder="Update life.txt">
        </label>
        <div class="actions">
          <button onclick="gitCommit()">Commit</button>
          <button class="secondary" onclick="gitPull()">Pull</button>
          <button class="secondary" onclick="gitPush()">Push</button>
          <button class="secondary" onclick="closeGitModal()">Cancel</button>
        </div>
        <pre id="git-output" style="font-size:.78rem;color:var(--muted);white-space:pre-wrap;display:none"></pre>
      </div>
    </div>
  </div>

  <script>
    let currentItems = [];
    let selectedItem = null;
    let bulkSelectedLines = new Set();
    let refreshTimer = null;
    let notificationTimer = null;
    let browserNotificationsEnabled = false;
    let seenNotifications = new Set();
    let appConfig = {};
    let graphLoaded = false;
    let _kioskDefaultTitle = null;
    let _kioskLastFingerprints = null;
    let _lastFocusedBeforeModal = null;
    const RECENT_ITEMS_STORAGE_KEY = "lifetxt_recent_items";
    const DASHBOARD_CARDS = ["today", "needs_attention", "completions", "projects"];
    const THEME_TOKEN_KEYS = new Set([
      "bg", "panel", "panel_2", "soft", "ink", "muted", "line", "line_strong",
      "accent", "accent_hover", "accent_soft", "accent_ink",
      "danger", "danger_soft", "warn", "warn_soft",
      "ok", "ok_soft", "info", "info_soft", "violet", "violet_soft",
      "shadow_1", "shadow_2", "shadow_3", "r_sm", "r_md", "r_lg",
    ]);

    async function api(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }
    function cssVarName(configKey) {
      return "--" + String(configKey || "").replace(/_/g, "-");
    }
    function applyConfiguredTheme() {
      const theme = appConfig?.web?.theme || {};
      for (const [key, value] of Object.entries(theme)) {
        if (!THEME_TOKEN_KEYS.has(key) || !String(value || "").trim()) continue;
        document.documentElement.style.setProperty(cssVarName(key), String(value).trim());
      }
    }
    function configuredDashboardCards() {
      const raw = appConfig?.web?.dashboard?.cards;
      const list = Array.isArray(raw)
        ? raw.map(String)
        : String(raw || "").split(",").map(part => part.trim());
      const cards = list.filter(card => DASHBOARD_CARDS.includes(card));
      return cards.length ? cards : DASHBOARD_CARDS.slice();
    }
    function applyConfiguredDashboard() {
      const grid = document.getElementById("dash-grid");
      if (!grid) return;
      const configured = configuredDashboardCards();
      const enabled = new Set(configured);
      const byName = {};
      grid.querySelectorAll("[data-dashboard-card]").forEach(card => {
        byName[card.dataset.dashboardCard] = card;
        card.classList.toggle("card-hidden", !enabled.has(card.dataset.dashboardCard));
      });
      for (const name of configured) {
        if (byName[name]) grid.appendChild(byName[name]);
      }
    }
    function dashboardLimit(cardName, fallback) {
      const raw = appConfig?.web?.dashboard?.limits?.[cardName];
      const n = Number(raw);
      return Number.isFinite(n) && n > 0 ? n : fallback;
    }
    function detailText(details) {
      return Object.entries(details || {}).flatMap(([key, values]) =>
        values.map(value => `${key}:${value}`)
      ).join(" ");
    }
    function itemStableKey(item) {
      const idKey = appConfig?.ids?.key || "id";
      return String(item?.id || item?.details?.[idKey]?.[0] || `${item?.source || ""}:${item?.line || ""}:${item?.title || ""}`);
    }
    function itemFingerprint(item) {
      return JSON.stringify({
        status: item?.status || "",
        type: item?.type || "",
        title: item?.title || "",
        details: item?.details || {},
        raw: item?.raw || "",
      });
    }
    function detailsToText(details) {
      const lines = [];
      for (const [key, values] of Object.entries(details || {})) {
        for (const value of values) {
          const text = String(value);
          if (key === "body" && text.includes("\n")) {
            const parts = text.split(/\n/);
            lines.push(`${key}:${parts.shift() || ""}`);
            for (const part of parts) lines.push(part ? `| ${part}` : "|");
          } else {
            lines.push(`${key}:${text}`);
          }
        }
      }
      return lines.join("\n");
    }
    function parseDetails(text) {
      const details = {};
      for (const line of text.split(/\n/)) {
        if (line.startsWith("|")) {
          if (!details.body || !details.body.length) details.body = [""];
          const value = line.startsWith("| ") ? line.slice(2) : line.slice(1);
          details.body[0] += `${details.body[0] ? "\n" : ""}${value}`;
          continue;
        }
        const trimmed = line.trim();
        if (!trimmed) continue;
        const colon = trimmed.indexOf(":");
        const equal = trimmed.indexOf("=");
        let index = -1;
        if (colon >= 0 && equal >= 0) index = Math.min(colon, equal);
        else index = Math.max(colon, equal);
        if (index <= 0) continue;
        const key = trimmed.slice(0, index).trim();
        const value = trimmed.slice(index + 1).trim();
        (details[key] ||= []).push(value);
      }
      return details;
    }
    function query() {
      return new URLSearchParams(window.location.search);
    }
    function firstParam(params, names, fallback = "") {
      for (const name of names) {
        const value = params.get(name);
        if (value !== null && value !== "") return value;
      }
      return fallback;
    }
    function boolParam(params, names) {
      const value = firstParam(params, names, "");
      return ["1", "true", "yes", "on", "open"].includes(value.toLowerCase());
    }
    function parseKioskFilter(value) {
      const result = {};
      if (!value) return result;
      const aliases = {type: "kind", q: "text", open: "open_only"};
      for (const part of String(value).split(/[;,]/)) {
        const trimmed = part.trim();
        if (!trimmed) continue;
        const idx = Math.max(trimmed.indexOf(":"), trimmed.indexOf("="));
        if (idx <= 0) continue;
        const rawKey = trimmed.slice(0, idx).trim();
        const key = aliases[rawKey] || rawKey;
        const val = trimmed.slice(idx + 1).trim();
        if (key && val) result[key] = val;
      }
      return result;
    }
    function applyKioskFilterParams(result, params) {
      if (!isKioskMode()) return;
      const filter = parseKioskFilter(firstParam(params, ["kiosk_filter"], ""));
      for (const [key, value] of Object.entries(filter)) {
        if (key === "open_only") {
          if (["1", "true", "yes", "on", "open"].includes(value.toLowerCase())) result.set("open_only", "true");
          continue;
        }
        if (!result.has(key)) result.set(key, value);
      }
    }
    // ── Single-content page router ─────────────────────────────────
    // Each view owns the whole screen: exactly one page section is shown.
    const PAGE_VIEWS = ["dashboard", "agenda", "timeline", "focus", "review", "messages", "team", "status", "notifications", "stats", "graph"];
    const VIEW_PAGE = {
      "": "items", "messages": "items", "kiosk": "items", "display": "items",
      "dashboard": "dashboard", "agenda": "agenda", "timeline": "timeline",
      "focus": "focus", "review": "review", "team": "team",
      "status": "status", "notifications": "notifications",
      "stats": "stats", "graph": "graph",
    };
    const VIEW_META = {
      "": {
        label: "Items",
        description: "Search, filter, edit, and bulk-manage life.txt records.",
        actions: [["New record", "newItem"], ["Quick add", "quickAdd"], ["Clear filters", "clearFilters"]],
      },
      dashboard: {
        label: "Dashboard",
        description: "A compact overview of open work, agenda pressure, messages, and presence.",
        actions: [["Open agenda", "agenda"], ["Open focus", "focus"], ["Refresh", "refresh"]],
      },
      agenda: {
        label: "Agenda",
        description: "Review dated work in the selected range, including blocked and upcoming records.",
        actions: [["Today", "agendaToday"], ["7 days", "agendaWeek"], ["Refresh", "refresh"]],
      },
      timeline: {
        label: "Timeline",
        description: "See dated records on a chronological board with empty-range guidance.",
        actions: [["Today", "timelineToday"], ["Next 24h", "timeline24h"], ["Week", "timelineWeek"]],
      },
      focus: {
        label: "Focus",
        description: "Prioritize open, actionable work and reduce noisy context while planning.",
        actions: [["Open tasks", "openTasks"], ["New record", "newItem"], ["Refresh", "refresh"]],
      },
      review: {
        label: "Review",
        description: "Summarize completed, carried, blocked, and planned work for a chosen period.",
        actions: [["This week", "reviewWeek"], ["Copy Markdown", "copyReview"], ["Refresh", "refresh"]],
      },
      messages: {
        label: "Messages",
        description: "Filter message records and manage notification-oriented conversations.",
        actions: [["New message", "newMessage"], ["Notifications", "notifications"], ["Clear filters", "clearFilters"]],
      },
      team: {
        label: "Team",
        description: "Combine presence, open workload, and recent messages per person.",
        actions: [["Status view", "status"], ["Messages", "messages"], ["Refresh", "refresh"]],
      },
      status: {
        label: "Status",
        description: "Show the latest presence state for each person or active status records only.",
        actions: [["Active only", "toggleStatusActive"], ["Team board", "team"], ["Refresh", "refresh"]],
      },
      notifications: {
        label: "Notifications",
        description: "Review pending notification records, acknowledge them, or request browser alerts.",
        actions: [["Enable alerts", "enableNotifications"], ["Messages", "messages"], ["Refresh", "refresh"]],
      },
      stats: {
        label: "Statistics",
        description: "Inspect charted trends for tasks, projects, messages, and journal fields.",
        actions: [["Refresh charts", "refreshCharts"], ["Dashboard", "dashboard"]],
      },
      graph: {
        label: "Graph",
        description: "Explore dependencies, references, parent-child links, and related records.",
        actions: [["Refresh graph", "refreshGraph"], ["Items", "items"]],
      },
      display: {
        label: "Display",
        description: "Read-focused wall display mode with editing controls hidden.",
        actions: [["Exit display", "items"]],
      },
      kiosk: {
        label: "Kiosk",
        description: "Always-on display mode with automatic refresh and compact controls.",
        actions: [["Exit kiosk", "items"]],
      },
    };
    const VIEW_ACTIONS = {
      newItem: () => newItem(),
      quickAdd: () => toggleQuickAdd(true),
      clearFilters: () => clearAllFilters(),
      refresh: () => triggerRefresh(),
      items: () => switchWorkspace(""),
      dashboard: () => switchWorkspace("dashboard"),
      agenda: () => switchWorkspace("agenda"),
      focus: () => switchWorkspace("focus"),
      review: () => switchWorkspace("review"),
      messages: () => switchWorkspace("messages"),
      team: () => switchWorkspace("team"),
      status: () => switchWorkspace("status"),
      notifications: () => switchWorkspace("notifications"),
      agendaToday: () => setAgendaQuickRange("today"),
      agendaWeek: () => setAgendaQuickRange("7d"),
      timelineToday: () => setTimelineRange("today"),
      timeline24h: () => setTimelineRange("24h"),
      timelineWeek: () => setTimelineRange("week"),
      openTasks: () => openTaskItems(),
      reviewWeek: () => setReviewRange("week"),
      copyReview: () => copyReviewMarkdown(),
      newMessage: () => {
        newItem();
        setTimeout(() => {
          const type = document.getElementById("edit-type");
          if (type) type.value = "M";
          updateTypeHints("M");
        }, 0);
      },
      toggleStatusActive: () => toggleStatusActive(),
      enableNotifications: () => enableBrowserNotifications(),
      refreshCharts: () => refreshStatsView(),
      refreshGraph: () => loadGraphPanel(),
    };
    function runViewGuideAction(action) {
      const fn = VIEW_ACTIONS[action];
      if (fn) fn();
    }
    function syncViewGuide() {
      const node = document.getElementById("view-guide");
      if (!node) return;
      const v = currentView();
      const meta = VIEW_META[v] || VIEW_META[""];
      const actions = (meta.actions || []).map(([label, action]) =>
        `<button type="button" class="secondary" onclick="runViewGuideAction(${escapeHtml(jsLiteral(action))})">${escapeHtml(label)}</button>`
      ).join("");
      node.innerHTML = `
        <div class="view-guide-card">
          <span class="view-guide-chip">${escapeHtml(v || "items")}</span>
          <div class="view-guide-copy">
            <div class="view-guide-title">${escapeHtml(meta.label)}</div>
            <div class="view-guide-desc">${escapeHtml(meta.description)}</div>
          </div>
          <div class="view-guide-actions">${actions}</div>
        </div>`;
    }
    function setupWorkspaceTabs() {
      const nav = document.getElementById("workspace-tabs");
      if (!nav) return;
      nav.setAttribute("role", "tablist");
      nav.addEventListener("keydown", (event) => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        const tabs = Array.from(nav.querySelectorAll(".workspace-tab[data-view]"));
        const current = tabs.indexOf(document.activeElement);
        if (current < 0 || !tabs.length) return;
        event.preventDefault();
        let next = current;
        if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else next = (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next].focus();
      });
    }
    function openTaskItems() {
      const params = query();
      params.delete("mode");
      params.delete("view");
      params.delete("workspace");
      params.delete("panel");
      params.set("kind", "T");
      params.set("open_only", "true");
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
    }
    function setAgendaQuickRange(range) {
      const params = query();
      params.delete("mode");
      params.set("view", "agenda");
      params.delete("from");
      params.delete("to");
      params.delete("around");
      params.delete("window");
      const today = new Date();
      if (range === "today") {
        params.set("from", _fmtDate(today));
        params.set("to", _fmtDate(today));
      } else {
        const end = new Date(today);
        end.setDate(end.getDate() + (range === "7d" ? 7 : 1));
        params.set("from", _fmtDate(today));
        params.set("to", _fmtDate(end));
      }
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadAgenda();
    }
    function refreshStatsView() {
      statsLoaded = true;
      loadChart(currentChartType);
      loadStatsBreakdown();
    }
    function switchWorkspace(view, historyMode = "push") {
      const params = query();
      params.delete("mode");
      params.delete("view");
      params.delete("workspace");
      params.delete("panel");
      if (view === "kiosk" || view === "display") params.set("mode", view);
      else if (view) params.set("view", view);
      const method = historyMode === "replace" ? "replaceState" : "pushState";
      history[method](null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      applyUrlToControls();
      refreshAll();
    }
    function switchView(view) { switchWorkspace(view); }
    function switchViewWorkspace(view, workspace) { switchWorkspace(view || workspace || ""); }
    function toggleDisplayMode() {
      switchWorkspace(isDisplayMode() ? "" : "display");
    }
    function syncViewTabs() {
      const v = currentView();
      document.querySelectorAll(".workspace-tab[data-view]").forEach(btn => {
        const active = (btn.dataset.view || "") === v;
        btn.classList.toggle("active", active);
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", active ? "true" : "false");
        btn.tabIndex = active ? 0 : -1;
      });
      const notifBtn = document.getElementById("notif-btn");
      if (notifBtn) notifBtn.classList.toggle("btn-active", v === "notifications");
    }
    function syncPages() {
      const page = VIEW_PAGE[currentView()] || "items";
      document.querySelectorAll("main .page").forEach(sec => {
        sec.classList.toggle("page-active", sec.dataset.page === page);
      });
      const label = document.getElementById("items-heading-label");
      if (label) label.textContent = currentView() === "messages" ? "Messages" : "Items";
    }
    function isDisplayMode() {
      const params = query();
      return firstParam(params, ["mode", "view"], "").toLowerCase() === "display";
    }
    function isKioskMode() {
      const params = query();
      return firstParam(params, ["mode", "view"], "").toLowerCase() === "kiosk";
    }
    function currentView() {
      const params = query();
      const value = firstParam(params, ["view", "mode"], "").toLowerCase();
      if (["display", "kiosk"].includes(value)) return value;
      if (PAGE_VIEWS.includes(value)) return value;
      // Back-compat: old ?workspace= / ?panel= parameters map onto page views.
      const ws = firstParam(params, ["workspace", "panel"], "").toLowerCase();
      if (PAGE_VIEWS.includes(ws)) return ws;
      return "";
    }
    window.addEventListener("popstate", () => {
      applyPresetToUrl();
      applyUrlToControls();
      refreshAll();
    });
    function applyPresetToUrl() {
      const params = query();
      // Support ?view=NAME as alias for ?preset=NAME (config-defined presets)
      const viewAlias = (params.get("view") || "").toLowerCase();
      if (viewAlias && !PAGE_VIEWS.includes(viewAlias) && !["display", "kiosk"].includes(viewAlias) && !params.get("preset")) {
        params.set("preset", params.get("view"));
        history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      }
      const presetName = params.get("preset");
      if (!presetName || params.get("_preset_applied") === presetName) return;
      const preset = getViewPreset(presetName);
      if (!preset) return;
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(preset)) {
        if (!next.has(key)) next.set(key, value);
      }
      next.set("_preset_applied", presetName);
      history.replaceState(null, "", `${location.pathname}?${next.toString()}`);
    }
    function applyUrlToControls() {
      const params = query();
      document.body.classList.toggle("display-mode", isDisplayMode());
      document.body.classList.toggle("kiosk-mode", isKioskMode());
      syncViewTabs();
      syncPages();
      syncViewGuide();
      _kioskApply();
      document.getElementById("search").value = firstParam(params, ["text", "q"], "");
      const fallbackKind = currentView() === "messages" ? "M" : "";
      const fallbackSort = currentView() === "messages" ? "time" : (appConfig?.web?.default_sort || "line");
      document.getElementById("kind").value = firstParam(params, ["kind", "type"], fallbackKind);
      document.getElementById("sort").value = firstParam(params, ["sort"], fallbackSort);
      document.getElementById("order").value = firstParam(params, ["order"], appConfig?.web?.default_order || "asc");
      document.getElementById("open-only").checked = boolParam(params, ["open", "open_only"]) || params.get("blocked") === "true";
      document.getElementById("limit").value = firstParam(params, ["limit"], appConfig?.web?.default_limit || "");
      const groupSel = document.getElementById("group-by");
      if (groupSel) groupSel.value = firstParam(params, ["group_by"], "");
      syncTimelineRange(firstParam(params, ["range", "timeline_range"], timelineRange));
      syncStatusFilterBarsFromUrl();
      configureAutoRefresh();
      configureNotificationPolling();
    }
    function configureAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const seconds = Number(firstParam(query(), ["refresh"], (isDisplayMode() || isKioskMode()) ? "60" : ""));
      if (Number.isFinite(seconds) && seconds > 0) {
        refreshTimer = setInterval(refreshAll, seconds * 1000);
      }
    }
    function configureNotificationPolling() {
      if (notificationTimer) clearInterval(notificationTimer);
      if (appConfig?.notifications?.enabled === false || appConfig?.notifications?.web === false) return;
      const fallback = appConfig?.web?.notification_poll_seconds || appConfig?.notifications?.poll_seconds || 30;
      const seconds = Number(firstParam(query(), ["notify_refresh"], String(fallback)));
      if (Number.isFinite(seconds) && seconds > 0) {
        notificationTimer = setInterval(loadNotifications, seconds * 1000);
      }
    }
    function itemQueryParams() {
      const params = query();
      const result = new URLSearchParams();
      const passthrough = [
        "status", "project", "tag", "tag_all", "exclude_tag", "user", "team",
        "person", "owner", "assignee", "attendee",
        "sender", "recipient", "after", "before"
      ];
      for (const key of passthrough) {
        if (params.has(key)) result.set(key, params.get(key));
      }
      const kind = document.getElementById("kind").value || firstParam(params, ["kind", "type"], "");
      const text = document.getElementById("search").value || firstParam(params, ["text", "q"], "");
      const limit = document.getElementById("limit").value || firstParam(params, ["limit"], "");
      result.set("sort", document.getElementById("sort").value || firstParam(params, ["sort"], "line"));
      result.set("order", document.getElementById("order").value || firstParam(params, ["order"], "asc"));
      if (kind) result.set("kind", kind);
      if (text) result.set("text", text);
      if (limit) result.set("limit", limit);
      if (document.getElementById("open-only").checked || boolParam(params, ["open", "open_only"])) {
        result.set("open_only", "true");
      }
      if (params.get("blocked") === "true") result.set("blocked", "true");
      applyKioskFilterParams(result, params);
      return result;
    }
    function updateUrlFromControls() {
      const current = query();
      const next = new URLSearchParams();
      for (const key of [
        "mode", "view", "refresh", "around", "window", "from", "to",
        "workspace", "panel", "theme",
        "kiosk_cols", "kiosk_filter", "kiosk_title",
        "status", "project", "tag", "tag_all", "exclude_tag", "user", "team",
        "person", "owner", "assignee", "attendee",
        "sender", "recipient", "after", "before"
      ]) {
        if (current.has(key)) next.set(key, current.get(key));
      }
      const text = document.getElementById("search").value;
      const kind = document.getElementById("kind").value;
      const limit = document.getElementById("limit").value;
      const groupBy = document.getElementById("group-by")?.value || "";
      if (text) next.set("text", text);
      if (kind) next.set("kind", kind);
      if (document.getElementById("open-only").checked) next.set("open_only", "true");
      if (limit) next.set("limit", limit);
      if (groupBy) next.set("group_by", groupBy);
      next.set("sort", document.getElementById("sort").value);
      next.set("order", document.getElementById("order").value);
      if (query().has("agenda_blocked")) next.set("agenda_blocked", query().get("agenda_blocked"));
      history.replaceState(null, "", `${location.pathname}?${next.toString()}`);
    }
    async function loadItems() {
      updateUrlFromControls();
      const params = itemQueryParams();
      if (!currentItems.length) {
        const root = document.getElementById("items");
        if (root && !root.querySelector(".item")) {
          root.innerHTML = `<div class="skeleton-row"></div>`.repeat(4);
        }
      }
      const data = await api(`/api/items?${params}`);
      currentItems = data.items;
      renderDiagnostics(data.diagnostics);
      renderItems(data.items);
      updateTagSuggestions(data.items);
      syncStatusFilterBtns();
      if (selectedItem) {
        const match = data.items.find(item => item.line === selectedItem.line && item.editable);
        if (match) selectItem(match);
      }
    }
    function renderDiagnostics(diagnostics) {
      document.getElementById("diagnostics").innerHTML = diagnostics
        .map(d => `<div class="diagnostic${d.severity === "warning" ? " warning" : ""}">${escapeHtml(d.severity)} ${escapeHtml(d.code)}: ${escapeHtml(d.message)}</div>`)
        .join("");
    }
    function safeMarkdownHtml(value, fallback = "") {
      return typeof value === "string" ? value : escapeHtml(fallback);
    }
    function firstMarkdownDetail(item, key) {
      const values = item?.markdown?.details?.[key];
      return Array.isArray(values) && values.length ? values[0] : "";
    }
    const STATUS_CLASS = {
      "[ ]": "status-open",
      "[/]": "status-active",
      "[x]": "status-done",
      "[-]": "status-cancel",
      "[>]": "status-defer",
      "[?]": "status-maybe",
      "[N]": "status-note",
    };
    const STATUS_LABEL = {
      "[ ]": "open", "[/]": "active", "[x]": "done",
      "[-]": "cancelled", "[>]": "deferred", "[?]": "maybe", "[N]": "note",
    };
    const ITEM_TYPE_NAMES = {
      T: "Task", H: "Habit", E: "Event", R: "Reminder",
      J: "Journal", S: "Status", M: "Message", N: "Note",
      G: "Goal", P: "Project", K: "Checklist", L: "Log",
    };
    function dueSoonDays() {
      return Number((appConfig?.web?.due_soon_days) ?? 3);
    }
    function itemDueSoonClass(item) {
      const dueVals = item?.details?.due;
      if (!dueVals || !dueVals.length) return "";
      const due = new Date(dueVals[0]);
      if (isNaN(due)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      const dueMid = new Date(due); dueMid.setHours(0,0,0,0);
      const diffDays = Math.floor((dueMid - today) / 86400000);
      if (diffDays < 0 && item.status !== "[x]" && item.status !== "[-]") return "overdue";
      if (diffDays >= 0 && diffDays <= dueSoonDays() && item.status !== "[x]" && item.status !== "[-]") return "due-soon";
      return "";
    }
    function renderSummary(items) {
      const el = document.getElementById("stats-summary");
      const total = items.length;
      const open = items.filter(i => !["[x]", "[-]"].includes(i.status)).length;
      const done = items.filter(i => i.status === "[x]").length;
      const overdue = items.filter(i => itemDueSoonClass(i) === "overdue").length;
      if (!total) { el.style.display = "none"; return; }
      el.style.display = "";
      el.innerHTML = `
        <div class="stats-count"><span class="n">${total}</span> total</div>
        <div class="stats-count"><span class="n">${open}</span> open</div>
        <div class="stats-count"><span class="n">${done}</span> done</div>
        <div class="stats-count overdue-count"><span class="n">${overdue}</span> overdue</div>
      `;
      // Build per-project mini-table from current items
      const projMap = {};
      for (const item of items) {
        if (item.type !== "T") continue;
        const projs = item?.details?.project?.length ? item.details.project : ["(none)"];
        for (const p of projs) {
          if (!projMap[p]) projMap[p] = {done: 0, total: 0};
          projMap[p].total++;
          if (item.status === "[x]") projMap[p].done++;
        }
      }
      const sorted = Object.entries(projMap).sort((a,b) => b[1].total - a[1].total).slice(0,6);
      if (!sorted.length) return;
      const maxT = Math.max(...sorted.map(([,v]) => v.total), 1);
      let table = `<div style="margin-top:.45rem;overflow-x:auto"><table class="proj-stats-table"><thead><tr><th>Project</th><th>✓</th><th>N</th><th></th></tr></thead><tbody>`;
      for (const [proj, v] of sorted) {
        const barW = Math.round(v.total / maxT * 56);
        const opacity = (0.4 + 0.6 * (v.done / Math.max(v.total, 1))).toFixed(2);
        table += `<tr><td>${escapeHtml(proj)}</td><td>${v.done}</td><td>${v.total}</td><td><span class="proj-stats-bar" style="width:${barW}px;opacity:${opacity}"></span></td></tr>`;
      }
      table += `</tbody></table></div>`;
      el.insertAdjacentHTML("beforeend", table);
    }
    function renderFilterChips() {
      const params = query();
      const el = document.getElementById("filter-chips");
      el.innerHTML = "";
      const filterKeys = [
        ["kind", "type"], ["status"], ["project"], ["tag"], ["user"], ["team"],
        ["person"], ["assignee"], ["owner"], ["after"], ["before"],
      ];
      const shown = new Set();
      for (const keys of filterKeys) {
        for (const k of keys) {
          if (shown.has(k)) break;
          const val = params.get(k);
          if (val) {
            shown.add(k);
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.innerHTML = `${escapeHtml(k)}:${escapeHtml(val)} <button title="Remove" onclick="removeFilter(${jsLiteral(k)})">×</button>`;
            el.appendChild(chip);
          }
        }
      }
      if (params.get("open_only") === "true") {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `open only <button title="Remove" onclick="removeFilter('open_only')">×</button>`;
        el.appendChild(chip);
      }
    }
    function removeFilter(key) {
      const params = query();
      params.delete(key);
      if (key === "open_only") document.getElementById("open-only").checked = false;
      if (key === "kind" || key === "type") document.getElementById("kind").value = "";
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadItems();
    }
    function groupKeyFor(item, groupBy) {
      if (groupBy === "project") return item?.details?.project?.[0] || "(no project)";
      if (groupBy === "type") return ITEM_TYPE_NAMES[item.type] || item.type || "(none)";
      if (groupBy === "status") return STATUS_LABEL[item.status] || item.status || "(none)";
      if (groupBy === "source") return item.source || "(unknown source)";
      return "";
    }
    function buildDueRelLabel(item) {
      const due = item?.details?.due?.[0];
      if (!due || ["[x]", "[-]"].includes(item.status)) return "";
      const d = new Date(due);
      if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      const dm = new Date(d); dm.setHours(0,0,0,0);
      const diff = Math.round((dm - today) / 86400000);
      let text, cls = "";
      if (diff < 0) { text = `${-diff}d overdue`; cls = "overdue"; }
      else if (diff === 0) { text = "due today"; cls = "due-soon"; }
      else if (diff <= dueSoonDays()) { text = `in ${diff}d`; cls = "due-soon"; }
      else if (diff <= 60) { text = `in ${diff}d`; }
      else return "";
      return `<span class="due-rel ${cls}">${escapeHtml(text)}</span>`;
    }
    function enhanceItemsEmptyState(hasFilters) {
      if (isKioskMode() || isDisplayMode()) return;
      const state = document.querySelector("#items .empty-state");
      if (!state) return;
      state.querySelectorAll(":scope > button, :scope > .empty-actions").forEach(el => el.remove());
      const actions = document.createElement("div");
      actions.className = "empty-actions";
      if (hasFilters) {
        actions.innerHTML =
          `<button type="button" class="secondary" onclick="clearAllFilters()">Clear filters</button>` +
          `<button type="button" onclick="newItem()">New record</button>`;
      } else {
        actions.innerHTML =
          `<button type="button" onclick="newItem()">New record</button>` +
          `<button type="button" class="secondary" onclick="toggleQuickAdd(true)">Quick add</button>` +
          `<button type="button" class="secondary" onclick="openCmdk()">Command palette</button>`;
      }
      state.appendChild(actions);
    }
    function renderItems(items) {
      const root = document.getElementById("items");
      const hasFilters = !!(document.getElementById("search").value.trim() ||
        query().get("status") || query().get("blocked") ||
        document.getElementById("kind").value || document.getElementById("open-only").checked);
      root.innerHTML = items.length ? "" : `
        <div class="empty-state">
          <div class="empty-icon" aria-hidden="true">${hasFilters ? "🔍" : "🌱"}</div>
          <div class="empty-title">${hasFilters ? "No items match the current filters" : "No items yet"}</div>
          <div class="empty-hint">${hasFilters
            ? "Try clearing the search text or status filters above."
            : "Add your first record with the quick-add bar (press q) or the New workspace."}</div>
          ${isKioskMode() || isDisplayMode() ? "" : (hasFilters
            ? `<button type="button" class="secondary" onclick="clearAllFilters()">Clear filters</button>`
            : `<button type="button" onclick="toggleQuickAdd(true)">＋ Quick add</button>`)}
        </div>`;
      if (!items.length) enhanceItemsEmptyState(hasFilters);
      renderSummary(items);
      renderFilterChips();
      updateSearchCount(items.length);
      const kioskNow = isKioskMode();
      const nextFingerprints = new Map();
      _kbIndex = -1;
      const groupBy = kioskNow ? "" : (document.getElementById("group-by")?.value || "");
      const appendItem = (item) => {
        const node = buildItemNode(item, kioskNow, nextFingerprints);
        root.appendChild(node);
      };
      if (groupBy) {
        const groups = new Map();
        for (const item of items) {
          const g = groupKeyFor(item, groupBy);
          if (!groups.has(g)) groups.set(g, []);
          groups.get(g).push(item);
        }
        for (const [name, groupItems] of groups) {
          root.insertAdjacentHTML(
            "beforeend",
            `<div class="group-header">${escapeHtml(name)} <span class="n">(${groupItems.length})</span></div>`
          );
          for (const item of groupItems) appendItem(item);
        }
      } else {
        for (const item of items) appendItem(item);
      }
      if (kioskNow) _kioskLastFingerprints = nextFingerprints;
      else _kioskLastFingerprints = null;
      const queryText = document.getElementById("search").value.trim();
      if (queryText) {
        root.querySelectorAll(".title.markdown, .meta, .body-preview").forEach(el => {
          el.innerHTML = highlightText(el.innerHTML, queryText);
        });
      }
    }
    function buildItemNode(item, kioskNow, nextFingerprints) {
        const titleHtml = safeMarkdownHtml(item?.markdown?.title, item.title);
        const previewHtml = firstMarkdownDetail(item, "body") || firstMarkdownDetail(item, "note");
        const preview = previewHtml ? `<div class="markdown body-preview">${previewHtml}</div>` : "";
        const occurrenceBadge = item.occurrence_start
          ? `<span class="occurrence-badge" title="${escapeHtml(item.occurrence_start)}">occurrence</span>`
          : "";
        const generatedBadge = item.generated && !item.occurrence_start
          ? `<span class="occurrence-badge" title="generated/read-only source file">generated</span>`
          : "";
        const statusCls = STATUS_CLASS[item.status] || "status-note";
        const statusLabel = STATUS_LABEL[item.status] || item.status;
        const typeCls = "type-" + (item.type || "N");
        const dueCls = itemDueSoonClass(item);
        const refLinks = buildRefLinksHtml(item.details);
        const parentInd = buildParentIndicator(item.details);
        const dueRel = buildDueRelLabel(item);
        const stableKey = itemStableKey(item);
        const fingerprint = itemFingerprint(item);
        nextFingerprints.set(stableKey, fingerprint);
        const node = document.createElement("button");
        node.type = "button";
        node.className = "item" + (dueCls ? " " + dueCls : "");
        if (kioskNow && _kioskLastFingerprints && _kioskLastFingerprints.get(stableKey) !== fingerprint) {
          node.classList.add("kiosk-changed");
        }
        if (selectedItem && item.line === selectedItem.line && item.editable === selectedItem.editable) {
          node.classList.add("selected");
        }
        const _bulkKey = String(item.line) + "|" + (item.source || "");
        node.addEventListener("click", (e) => {
          if (e.target.closest(".ref-link")) return;
          if (e.target.closest(".item-check")) return;
          selectItem(item);
          openDrawer(item);
        });
        node.addEventListener("contextmenu", (e) => openCtxMenu(e, item));
        const isBulkSelected = bulkSelectedLines.has(_bulkKey);
        if (isBulkSelected) node.classList.add("bulk-selected");
        node.innerHTML = `
          <input type="checkbox" class="item-check" title="Select for bulk action" ${isBulkSelected ? "checked" : ""}>
          <span class="status-badge ${statusCls}" title="${escapeHtml(item.status)}">${escapeHtml(statusLabel)}</span>
          <span class="type-badge ${typeCls}">${escapeHtml(item.type)}</span>
          <div>
            <div class="title markdown">${titleHtml}${parentInd}${occurrenceBadge}${generatedBadge}</div>
            <div class="meta">${escapeHtml(detailText(item.details))}${refLinks}${dueRel}</div>
            ${preview}
          </div>
          <span class="source">${escapeHtml(item.source || `line ${item.line || ""}`)}${item.generated ? " / generated" : ""}${item.editable ? "" : " / read-only"}</span>
        `;
        node.querySelector(".item-check").addEventListener("change", (ev) => {
          ev.stopPropagation();
          if (ev.target.checked) bulkSelectedLines.add(_bulkKey);
          else bulkSelectedLines.delete(_bulkKey);
          node.classList.toggle("bulk-selected", ev.target.checked);
          _updateBulkToolbar();
        });
        node.querySelector(".item-check").addEventListener("click", (ev) => {
          ev.stopPropagation();
        });
        const statusBadge = node.querySelector(".status-badge");
        if (statusBadge && item.editable && !kioskNow) {
          statusBadge.classList.add("clickable");
          statusBadge.title = `${item.status} — click to cycle status`;
          statusBadge.addEventListener("click", (ev) => {
            ev.stopPropagation();
            cycleItemStatus(item);
          });
        }
        node._lifetxtItem = item;
        return node;
    }

    // ── Inline status cycling on item rows ─────────────────────────
    const STATUS_INLINE_CYCLE = ["[ ]", "[/]", "[x]"];
    async function cycleItemStatus(item) {
      if (!item.editable) return;
      const idx = STATUS_INLINE_CYCLE.indexOf(item.status);
      const next = STATUS_INLINE_CYCLE[(idx + 1) % STATUS_INLINE_CYCLE.length];
      const line = item.line;
      const prevPayload = {status: item.status, type: item.type, title: item.title, details: item.details || {}};
      try {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, status: next}),
        });
        registerUndo(`Status changed to ${next}.`, async () => {
          await api(`/api/items/${line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await refreshAll();
      } catch(e) {
        showToast("Status change failed: " + (e.message || e), "error");
      }
    }

    // ── Keyboard focus navigation (j/k/x/Enter) ────────────────────
    let _kbIndex = -1;
    function _kbNodes() {
      return [...document.querySelectorAll("#items .item")];
    }
    function kbMove(delta) {
      const nodes = _kbNodes();
      if (!nodes.length) return;
      const next = _kbIndex === -1
        ? (delta > 0 ? 0 : nodes.length - 1)
        : Math.max(0, Math.min(nodes.length - 1, _kbIndex + delta));
      nodes.forEach(n => n.classList.remove("kb-focus"));
      _kbIndex = next;
      nodes[next].classList.add("kb-focus");
      nodes[next].scrollIntoView({block: "nearest", behavior: "smooth"});
    }
    function kbFocusedItem() {
      const nodes = _kbNodes();
      if (_kbIndex < 0 || _kbIndex >= nodes.length) return null;
      return nodes[_kbIndex]._lifetxtItem || null;
    }
    function kbActivate() {
      const item = kbFocusedItem();
      if (!item) return false;
      selectItem(item);
      openDrawer(item);
      return true;
    }
    function kbToggleSelect() {
      const nodes = _kbNodes();
      if (_kbIndex < 0 || _kbIndex >= nodes.length) return;
      const check = nodes[_kbIndex].querySelector(".item-check");
      if (check) check.click();
    }

    // ── Export filtered items (CSV / JSON / Markdown) ──────────────
    function exportItems(format) {
      const items = currentItems || [];
      if (!items.length) { showToast("No items to export.", "warning"); return; }
      let content, mime, ext;
      if (format === "json") {
        content = JSON.stringify(items.map(i => ({
          line: i.line, source: i.source, status: i.status, type: i.type,
          title: i.title, details: i.details || {},
        })), null, 2);
        mime = "application/json"; ext = "json";
      } else if (format === "markdown") {
        content = items.map(i => {
          const tick = i.status === "[x]" ? "x" : i.status === "[-]" ? "-" : " ";
          const due = i?.details?.due?.[0] ? ` (due: ${i.details.due[0]})` : "";
          const proj = i?.details?.project?.[0] ? ` [${i.details.project[0]}]` : "";
          return `- [${tick}] **${i.type}** ${i.title}${due}${proj}`;
        }).join("\n");
        mime = "text/markdown"; ext = "md";
      } else {
        const esc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
        const header = ["line", "source", "status", "type", "title", "due", "project", "tags", "details"].join(",");
        const rows = items.map(i => [
          i.line ?? "", i.source ?? "", i.status, i.type, i.title,
          i?.details?.due?.[0] || "",
          (i?.details?.project || []).join(";"),
          (i?.details?.tag || []).join(";"),
          detailText(i.details),
        ].map(esc).join(","));
        content = [header, ...rows].join("\n");
        mime = "text/csv"; ext = "csv";
      }
      const blob = new Blob([content], {type: mime});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `lifetxt-items-${new Date().toISOString().slice(0, 10)}.${ext}`;
      a.click();
      URL.revokeObjectURL(a.href);
      showToast(`Exported ${items.length} item(s) as ${ext.toUpperCase()}.`, "success");
    }

    // ── Undo for destructive actions ───────────────────────────────
    let _undoStack = [];
    let _undoSeq = 0;
    function registerUndo(message, undoFn) {
      const entry = {
        id: ++_undoSeq,
        message: String(message || "Undo action"),
        run: undoFn,
        createdAt: Date.now(),
      };
      _undoStack = [entry, ..._undoStack].slice(0, 5);
      renderUndoHistory();
      const container = document.getElementById("toast-container");
      const el = document.createElement("div");
      el.className = "toast success";
      const span = document.createElement("span");
      span.textContent = message;
      const btn = document.createElement("button");
      btn.className = "undo-btn";
      btn.textContent = "Undo";
      btn.addEventListener("click", async () => { el.remove(); await performUndo(entry.id); });
      el.append(span, btn);
      container.appendChild(el);
      setTimeout(() => el.remove(), 8000);
    }
    async function performUndo(entryId) {
      const idx = entryId == null ? 0 : _undoStack.findIndex(entry => entry.id === entryId);
      if (idx < 0 || !_undoStack[idx]) return;
      const [entry] = _undoStack.splice(idx, 1);
      renderUndoHistory();
      try {
        await entry.run();
        showToast("Undone.", "success");
        await refreshAll();
      } catch(e) {
        showToast("Undo failed: " + (e.message || e), "error");
      }
    }
    function openUndoHistoryModal() {
      renderUndoHistory();
      openManagedModal(document.getElementById("undo-modal"), "button");
    }
    function closeUndoHistoryModal() {
      closeManagedModal(document.getElementById("undo-modal"));
    }
    function renderUndoHistory() {
      const list = document.getElementById("undo-history-list");
      if (!list) return;
      if (!_undoStack.length) {
        list.innerHTML = `<div class="empty">No undoable actions in this session.</div>`;
        return;
      }
      list.innerHTML = _undoStack.map(entry => {
        const age = Math.max(0, Math.round((Date.now() - entry.createdAt) / 1000));
        const ageText = age < 60 ? `${age}s ago` : `${Math.floor(age / 60)}m ago`;
        return `<div class="undo-history-row">` +
          `<span class="undo-history-label">${escapeHtml(entry.message)}</span>` +
          `<span class="undo-history-time">${escapeHtml(ageText)}</span>` +
          `<button type="button" class="secondary" onclick="performUndo(${entry.id})">Undo</button>` +
          `</div>`;
      }).join("");
    }
    function _updateBulkToolbar() {
      const bar = document.getElementById("bulk-toolbar");
      const cnt = document.getElementById("bulk-count");
      if (!bar) return;
      const n = bulkSelectedLines.size;
      bar.classList.toggle("visible", n > 0);
      if (cnt) cnt.textContent = `${n} selected`;
    }
    function bulkClearSelection() {
      bulkSelectedLines.clear();
      renderItems(currentItems);
    }
    function _bulkTargets(extraFilter) {
      const keys = new Set(bulkSelectedLines);
      return currentItems.filter(i =>
        keys.has(String(i.line) + "|" + (i.source || "")) && i.editable && (!extraFilter || extraFilter(i))
      );
    }
    async function _bulkUpdateStatus(targets, statusValue, message) {
      const restores = [];
      let done = 0;
      for (const item of targets) {
        try {
          await api(`/api/items/${item.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ status: statusValue, type: item.type, title: item.title, details: item.details || {} }) });
          restores.push({line: item.line, payload: {status: item.status, type: item.type, title: item.title, details: item.details || {}}});
          done++;
        } catch(e) { /* skip */ }
      }
      bulkSelectedLines.clear();
      registerUndo(message.replace("{n}", String(done)), async () => {
        for (const r of restores) {
          await api(`/api/items/${r.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(r.payload) });
        }
      });
      await refreshAll();
    }
    async function bulkMarkDone() {
      const targets = _bulkTargets(i => !["[x]","[-]"].includes(i.status));
      if (!targets.length) { showToast("No editable open items selected.", "warning"); return; }
      await _bulkUpdateStatus(targets, "[x]", "Marked {n} item(s) done.");
    }
    async function bulkSetStatus(statusValue) {
      const targets = _bulkTargets(i => i.status !== statusValue);
      if (!targets.length) { showToast("No editable items selected (or already that status).", "warning"); return; }
      await _bulkUpdateStatus(targets, statusValue, `Set {n} item(s) to ${statusValue}.`);
    }
    async function bulkSetProject() {
      const targets = _bulkTargets();
      if (!targets.length) { showToast("No editable items selected.", "warning"); return; }
      const value = prompt(`Set project on ${targets.length} item(s) to (empty removes project):`);
      if (value === null) return;
      const proj = value.trim();
      const restores = [];
      let done = 0;
      for (const item of targets) {
        const details = JSON.parse(JSON.stringify(item.details || {}));
        if (proj) details.project = [proj];
        else delete details.project;
        try {
          await api(`/api/items/${item.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ status: item.status, type: item.type, title: item.title, details }) });
          restores.push({line: item.line, payload: {status: item.status, type: item.type, title: item.title, details: item.details || {}}});
          done++;
        } catch(e) { /* skip */ }
      }
      bulkSelectedLines.clear();
      registerUndo(proj ? `Set project:${proj} on ${done} item(s).` : `Removed project on ${done} item(s).`, async () => {
        for (const r of restores) {
          await api(`/api/items/${r.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(r.payload) });
        }
      });
      await refreshAll();
    }
    async function bulkDelete() {
      const targets = _bulkTargets();
      if (!targets.length) { showToast("No editable items selected.", "warning"); return; }
      if (!confirm(`Delete ${targets.length} item(s)?`)) return;
      targets.sort((a,b) => b.line - a.line);
      const rawLines = [];
      let done = 0;
      for (const item of targets) {
        try {
          await api(`/api/items/${item.line}`, { method: "DELETE" });
          if (item.text) rawLines.unshift(item.text);
          done++;
        }
        catch(e) { /* skip */ }
      }
      bulkSelectedLines.clear();
      registerUndo(`Deleted ${done} item(s).`, async () => {
        for (const line of rawLines) {
          await api("/api/items/raw", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({line}) });
        }
      });
      await refreshAll();
    }
    function openEditorModal() {
      openManagedModal(document.getElementById("editor-modal"), "#edit-title");
    }
    function closeEditorModal() {
      closeManagedModal(document.getElementById("editor-modal"));
    }
    function selectItem(item) {
      if (isDisplayMode()) return;
      selectedItem = item;
      document.getElementById("editor-heading").textContent = item.editable ? `Edit line ${item.line}` : "Read-only record";
      document.getElementById("edit-status").value = item.status;
      document.getElementById("edit-type").value = item.type;
      document.getElementById("edit-title").value = item.title;
      document.getElementById("edit-details").value = detailsToText(item.details);
      document.getElementById("save-button").textContent = "Save";
      document.getElementById("delete-button").disabled = !item.editable;
      document.getElementById("editor-note").textContent = item.editable
        ? "Editing the writable file. Save replaces this record line."
        : "This record comes from a read-only source.";
      setEditorDisabled(!item.editable);
      renderItems(currentItems);
    }
    function newItem() {
      openEditorModal();
      selectedItem = null;
      document.getElementById("editor-heading").textContent = "New Record";
      document.getElementById("edit-status").value = "[ ]";
      document.getElementById("edit-type").value = "T";
      document.getElementById("edit-title").value = "";
      document.getElementById("edit-details").value = "";
      document.getElementById("save-button").textContent = "Create";
      document.getElementById("delete-button").disabled = true;
      document.getElementById("editor-note").textContent = "Create a new record or select an editable row.";
      setEditorDisabled(false);
      renderItems(currentItems);
    }
    function setEditorDisabled(disabled) {
      for (const id of ["edit-status", "edit-type", "edit-title", "edit-details", "save-button"]) {
        document.getElementById(id).disabled = disabled;
      }
    }
    function editorPayload() {
      return {
        status: document.getElementById("edit-status").value,
        type: document.getElementById("edit-type").value,
        title: document.getElementById("edit-title").value,
        details: parseDetails(document.getElementById("edit-details").value),
      };
    }
    async function saveItem(event) {
      event.preventDefault();
      const payload = editorPayload();
      try {
        if (selectedItem && selectedItem.editable) {
          await api(`/api/items/${selectedItem.line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
          });
          showToast("Record saved.", "success");
        } else {
          await api("/api/items", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
          });
          showToast("Record created.", "success");
        }
      } catch(e) {
        showToast("Save failed: " + (e.message || e), "error");
        return;
      }
      closeEditorModal();
      selectedItem = null;
      await refreshAll();
    }
    async function deleteSelected() {
      if (!selectedItem || !selectedItem.editable) return;
      if (!confirm(`Delete line ${selectedItem.line}?`)) return;
      const rawLine = selectedItem.text;
      await api(`/api/items/${selectedItem.line}`, {method: "DELETE"});
      if (rawLine) {
        registerUndo("Item deleted.", async () => {
          await api("/api/items/raw", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({line: rawLine})});
        });
      }
      closeEditorModal();
      selectedItem = null;
      await refreshAll();
    }
    async function loadAgenda() {
      const params = query();
      const agendaParams = new URLSearchParams();
      for (const key of ["from", "to", "around", "window", "status", "kind", "type", "project", "tag", "tag_all", "exclude_tag", "user", "team", "person", "owner", "assignee", "attendee", "sender", "recipient", "text", "q", "limit"]) {
        if (params.has(key)) agendaParams.set(key, params.get(key));
      }
      if (!agendaParams.has("around") && !agendaParams.has("from")) agendaParams.set("around", "now");
      if (!agendaParams.has("window")) agendaParams.set("window", "1d");
      if (document.getElementById("open-only").checked || boolParam(params, ["open", "open_only"])) {
        agendaParams.set("open_only", "true");
      }
      const blockedMode = agendaBlockedMode();
      if (blockedMode) agendaParams.set("blocked", blockedMode);
      _syncAgendaBlockedBtn(blockedMode);
      const data = await api(`/api/agenda?${agendaParams}`);
      const node = document.getElementById("agenda");
      node.innerHTML = data.records.length ? "" : `<div class="empty">No agenda items.</div>`;
      const agendaLimitRaw = firstParam(query(), ["agenda_limit"], "8");
      const maxAgenda = Number(agendaLimitRaw);
      const unlimitedAgenda = agendaLimitRaw === "0" || maxAgenda === 0;
      const limit = unlimitedAgenda ? Infinity : (Number.isFinite(maxAgenda) && maxAgenda > 0 ? maxAgenda : 8);
      const shown = unlimitedAgenda ? data.records : data.records.slice(0, limit);
      for (const record of shown) {
        const dueCls = agendaDueSoonClass(record);
        const borderStyle = dueCls === "overdue" ? "border-left:3px solid #c0392b;" : dueCls === "due-soon" ? "border-left:3px solid #e67e22;" : "";
        const occ = record.occurrence_start || record.repeat_rule
          ? `<span class="occurrence-badge" title="${escapeHtml(record.repeat_rule || record.occurrence_start || "")}">occ #${escapeHtml(String(record.occurrence_index || 1))}</span>`
          : "";
        const blockedBadge = record.blocked
          ? `<span class="blocked-badge" title="Blocked by: ${escapeHtml((record.blocked_by || []).map(b => b.title || b.id).join(", "))}">⚡ blocked</span>`
          : "";
        const source = record.source_id ? `<div class="meta">source: ${escapeHtml(record.source_id)}</div>` : "";
        node.insertAdjacentHTML(
          "beforeend",
          `<div style="${borderStyle}padding-left:.45rem"><span class="pill">${escapeHtml(record.when)}</span>${occ}${blockedBadge}<div class="title">${escapeHtml(record.title)}</div>${source}</div>`
        );
      }
      if (!unlimitedAgenda && data.records.length > limit) {
        const remaining = data.records.length - limit;
        node.insertAdjacentHTML(
          "beforeend",
          `<div style="padding:.3rem .45rem"><a href="#" class="drawer-link" onclick="event.preventDefault();setAgendaLimit(0)">View all ${data.records.length} (${remaining} more)</a></div>`
        );
      }
      updateAgendaOverdueBadge(data.records);
    }
    // ── Presence rendering (Status & Team views) ───────────────────
    const PRESENCE_RULES = [
      [/^(available|free|online|in|open|active|here|present)$/, "p-available"],
      [/^(busy|meeting|call|working|occupied|class|lecture)$/, "p-busy"],
      [/^(focus|dnd|do[-_ ]?not[-_ ]?disturb|deep[-_ ]?work)$/, "p-focus"],
      [/^(away|afk|lunch|break|brb|idle|errand)$/, "p-away"],
      [/^(out|off|offline|gone|vacation|holiday|sick|absent|left)$/, "p-off"],
    ];
    function presenceClass(state, active) {
      if (active === false) return "p-off";
      const s = String(state || "").toLowerCase().trim();
      for (const [re, cls] of PRESENCE_RULES) if (re.test(s)) return cls;
      return "p-unknown";
    }
    function presenceDot(record) {
      const cls = presenceClass(record.state, record.active);
      const label = record.active === false ? "ended" : (record.state || "unknown");
      return `<span class="presence-dot ${cls}" role="img" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}"></span>`;
    }
    function presenceCard(record, extraHtml = "") {
      const cls = presenceClass(record.state, record.active);
      const started = record.from ? relativeTime(record.from) : "";
      const stateLabel = record.active === false
        ? (record.state ? `${record.state} · ended` : "ended")
        : (record.state || "—");
      return `<div class="person-card${record.active === false ? " presence-ended" : ""}">` +
        `<div class="person-head">${presenceDot(record)}` +
        `<span class="person-name">${escapeHtml(record.person)}</span>` +
        `<span class="presence-state-badge ${cls}">${escapeHtml(stateLabel)}</span></div>` +
        (record.title ? `<div class="person-status-title">${escapeHtml(record.title)}</div>` : "") +
        `<div class="person-meta">` +
        (record.from ? `<span title="${escapeHtml(record.from)}">started ${escapeHtml(started || record.from)}</span>` : "") +
        (record.to ? `<span title="${escapeHtml(record.to)}">until ${escapeHtml(record.to.replace("T", " "))}</span>` : "") +
        (record.service ? `<span class="pill">${escapeHtml(record.service)}</span>` : "") +
        `</div>` + extraHtml + `</div>`;
    }
    function openPersonItems(person) {
      const params = query();
      params.delete("mode");
      params.delete("view");
      params.delete("workspace");
      params.delete("panel");
      params.delete("person");
      params.delete("assignee");
      params.delete("sender");
      params.delete("recipient");
      params.set("user", String(person || ""));
      params.set("open_only", "true");
      if (!params.has("sort")) params.set("sort", "time");
      if (!params.has("order")) params.set("order", "asc");
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
    }
    function toggleStatusActive() {
      const params = query();
      const activeOnly = firstParam(params, ["active"], "true") !== "false";
      params.set("active", activeOnly ? "false" : "true");
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadStatus();
    }
    async function loadStatus() {
      const params = query();
      const statusParams = new URLSearchParams();
      const activeOnly = firstParam(params, ["active"], "true") !== "false";
      statusParams.set("active", activeOnly ? "true" : "false");
      if (params.has("person")) statusParams.set("person", params.get("person"));
      const btn = document.getElementById("status-active-btn");
      if (btn) btn.textContent = activeOnly ? "● Active only" : "◌ All latest";
      const data = await api(`/api/status?${statusParams}`);
      const node = document.getElementById("status");
      if (!data.records.length) {
        node.innerHTML = `<div class="empty">No ${activeOnly ? "active " : ""}status records.` +
          (activeOnly ? ` <a href="#" class="drawer-link" onclick="event.preventDefault();toggleStatusActive()">Show latest for everyone</a>` : "") +
          `</div>`;
        return;
      }
      node.innerHTML = `<div class="status-grid">` + data.records.map(r => presenceCard(r)).join("") + `</div>`;
    }

    // ── Team board (presence + messages + workload) ────────────────
    async function loadTeam() {
      const board = document.getElementById("team-board");
      if (!board) return;
      let statusData = {records: []}, msgs = [], openItems = [];
      try {
        [statusData, msgs, openItems] = await Promise.all([
          api("/api/status?active=false"),
          api("/api/messages?open_only=true&sort=time&order=desc").then(d => d.items || []).catch(() => []),
          api("/api/items?open_only=true").then(d => d.items || []).catch(() => []),
        ]);
      } catch(e) {
        board.innerHTML = `<div class="diagnostic">Team board error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const records = statusData.records || [];
      if (!records.length) {
        board.innerHTML = `<div class="empty-state"><div class="empty-icon" aria-hidden="true">🟢</div>` +
          `<div class="empty-title">No presence records yet</div>` +
          `<div class="empty-hint">Add a status record like<br><code>[/] S Working from:2026-07-07T09:00 state:busy person:alice</code><br>to put people on the board.</div></div>`;
        return;
      }
      const msgsFor = (person) => msgs.filter(m =>
        (m?.details?.recipient || []).map(String).includes(person)).slice(0, 3);
      const workloadFor = (person) => {
        const mine = openItems.filter(i => (i?.details?.assignee || []).map(String).includes(person));
        return {open: mine.length, overdue: mine.filter(i => itemDueSoonClass(i) === "overdue").length};
      };
      board.innerHTML = records.map(record => {
        const w = workloadFor(record.person);
        const personMsgs = msgsFor(record.person);
        let extra = "";
        if (w.open || w.overdue) {
          extra += `<div class="person-workload"><span class="pill">○ ${w.open} open</span>` +
            (w.overdue ? `<span class="pill" style="color:var(--danger)">⚠ ${w.overdue} overdue</span>` : "") +
            `</div>`;
        }
        if (personMsgs.length) {
          extra += `<div class="person-msgs">` + personMsgs.map(m =>
            `<div class="person-msg" onclick="openItemByLine(${Number(m.line)})" title="${escapeHtml(m.title)}">` +
            `<span aria-hidden="true">💬</span>` +
            `<span class="person-msg-title">${escapeHtml(m.title)}</span>` +
            `<span class="review-num" style="margin-left:auto">${escapeHtml(String(m?.details?.sender?.[0] || ""))}</span>` +
            `</div>`).join("") + `</div>`;
        }
        extra += `<div class="person-card-actions"><button type="button" class="secondary person-card-action" onclick="openPersonItems(${escapeHtml(jsLiteral(record.person))})">View items</button></div>`;
        return presenceCard(record, extra);
      }).join("");
    }

    // ── Timeline view (chronological board with a now line) ────────
    let timelineRange = "today";
    const TIMELINE_RANGES = new Set(["today", "24h", "week"]);
    function syncTimelineRange(range) {
      timelineRange = TIMELINE_RANGES.has(range) ? range : "today";
      document.querySelectorAll(".timeline-section .tl-controls .review-range-btn").forEach(btn =>
        btn.classList.toggle("active", btn.dataset.range === timelineRange));
    }
    function setTimelineRange(range) {
      syncTimelineRange(range);
      const params = query();
      params.set("view", "timeline");
      params.delete("mode");
      params.set("range", timelineRange);
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadTimeline();
    }
    function _tlIso(d) {
      const p = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    }
    function _tlComparable(value, endOfDay = false) {
      const text = String(value || "");
      if (!text) return "";
      if (text.length > 10) return text;
      return text + (endOfDay ? "T23:59" : "T00:00");
    }
    function _tlDisplayInfo(record, rangeStart, rangeEnd) {
      const primary = (record.matches || [])[0] || {};
      const originalStart = primary.start || record.when || "";
      const originalEnd = primary.end || "";
      const rangeStartIso = _tlComparable(rangeStart, false);
      const rangeEndIso = _tlComparable(rangeEnd, true);
      let when = originalStart || record.when || "";
      let clipped = false;
      if (originalStart && rangeStartIso && _tlComparable(originalStart, false) < rangeStartIso) {
        when = rangeStartIso;
        clipped = true;
      }
      if (when && rangeEndIso && _tlComparable(when, false) > rangeEndIso) {
        when = rangeEndIso;
      }
      return {when, originalStart, originalEnd, clipped};
    }
    function _tlNowLine() {
      const now = new Date();
      const p = (n) => String(n).padStart(2, "0");
      return `<div class="tl-now" aria-label="Current time"><span class="tl-now-label">${p(now.getHours())}:${p(now.getMinutes())}</span><span class="tl-now-line"></span></div>`;
    }
    function _timelineEmptyState(range, label, from, to) {
      const title = range === "today"
        ? "No dated records today"
        : range === "24h"
          ? "No dated records in the next 24 hours"
          : "No dated records this week";
      const hint = "Timeline only shows records with due:, do:, from:/to:, at:, on:, or notify_at: values inside the selected range.";
      const actions = range === "today"
        ? `<button type="button" onclick="setTimelineRange('24h')">Next 24h</button><button type="button" class="secondary" onclick="setTimelineRange('week')">This week</button>`
        : range === "24h"
          ? `<button type="button" onclick="setTimelineRange('week')">This week</button><button type="button" class="secondary" onclick="setTimelineRange('today')">Today</button>`
          : `<button type="button" onclick="setTimelineRange('today')">Today</button><button type="button" class="secondary" onclick="switchWorkspace('')">Go to Items</button>`;
      return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">🕒</div>` +
        `<div class="empty-title">${escapeHtml(title)}</div>` +
        `<div class="empty-hint">${escapeHtml(hint)}</div>` +
        `<div class="tl-empty-range">${escapeHtml(label)} / ${escapeHtml(from)} - ${escapeHtml(to)}</div>` +
        `<div class="tl-empty-actions">${actions}</div></div>`;
    }
    function _tlRow(record, nowIso, displayInfo) {
      const when = String(displayInfo?.when || record.when || "");
      const timed = when.length > 10;
      const time = timed ? when.slice(11, 16) : "all-day";
      const past = timed ? when < nowIso : when.slice(0, 10) < nowIso.slice(0, 10);
      const type = record.type || "N";
      const blockedBadge = record.blocked
        ? `<span class="blocked-badge" title="Blocked by: ${escapeHtml((record.blocked_by || []).map(b => b.title || b.id).join(", "))}">⚡ blocked</span>`
        : "";
      const occ = record.occurrence_start || record.repeat_rule
        ? `<span class="occurrence-badge" title="${escapeHtml(record.repeat_rule || record.occurrence_start || "")}">occ #${escapeHtml(String(record.occurrence_index || 1))}</span>`
        : "";
      const ongoing = displayInfo?.clipped
        ? `<span class="occurrence-badge" title="Started ${escapeHtml(displayInfo.originalStart || record.when || "")}${displayInfo.originalEnd ? ` / until ${escapeHtml(displayInfo.originalEnd)}` : ""}">ongoing</span>`
        : "";
      const proj = record.details?.project?.[0]
        ? `<span class="pill">${escapeHtml(String(record.details.project[0]))}</span>` : "";
      const clickable = Number.isInteger(record.line);
      return `<div class="tl-row${past ? " tl-past" : ""}">` +
        `<div class="tl-time">${escapeHtml(time)}</div>` +
        `<div class="tl-rail"><span class="tl-node t-${escapeHtml(type)}"></span></div>` +
        `<div class="tl-card${clickable ? "" : " tl-static"}"${clickable ? ` onclick="openItemByLine(${record.line})"` : ""}>` +
        `<div class="tl-card-title">${escapeHtml(record.title)}</div>` +
        `<div class="tl-card-meta">` +
        `<span class="type-badge type-${escapeHtml(type)}" style="font-size:.66rem;padding:.05rem .35rem;min-height:auto">${escapeHtml(type)}</span>` +
        (record.status ? `<span>${escapeHtml(record.status)}</span>` : "") +
        `${proj}${blockedBadge}${occ}${ongoing}</div></div></div>`;
    }
    async function loadTimeline() {
      const node = document.getElementById("timeline");
      if (!node) return;
      syncTimelineRange(firstParam(query(), ["range", "timeline_range"], timelineRange));
      const now = new Date();
      const nowIso = _tlIso(now);
      const today = _fmtDate(now);
      let from, to, label;
      if (timelineRange === "24h") {
        from = nowIso;
        to = _tlIso(new Date(now.getTime() + 24 * 3600 * 1000));
        label = "next 24 hours";
      } else if (timelineRange === "week") {
        const end = new Date(now); end.setDate(end.getDate() + 6);
        from = today;
        to = _fmtDate(end);
        label = `${today} to ${_fmtDate(end)}`;
      } else {
        from = today;
        to = today;
        label = now.toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"});
      }
      const rangeEl = document.getElementById("tl-range-label");
      if (rangeEl) rangeEl.textContent = label;
      let data;
      try {
        data = await api(`/api/agenda?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
      } catch(e) {
        node.innerHTML = `<div class="diagnostic">Timeline error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const records = (data.records || []).map(record => ({
        record,
        display: _tlDisplayInfo(record, from, to),
      })).sort((a, b) =>
        String(a.display.when || a.record.when || "").localeCompare(String(b.display.when || b.record.when || ""))
      );
      if (!records.length) {
        node.innerHTML = _timelineEmptyState(timelineRange, label, from, to);
        return;
      }
      const multiDay = timelineRange !== "today";
      const dayLabel = (d) => {
        const parsed = new Date(d + "T00:00");
        return isNaN(parsed) ? d : parsed.toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"});
      };
      let html = "";
      let lastDay = "";
      let nowInserted = false;
      for (const entry of records) {
        const record = entry.record;
        const when = String(entry.display.when || record.when || "");
        const day = when.slice(0, 10);
        const timed = when.length > 10;
        if (multiDay && day !== lastDay) {
          if (!nowInserted && lastDay === today) { html += _tlNowLine(); nowInserted = true; }
          html += `<div class="tl-day-head">${escapeHtml(dayLabel(day))}${day === today ? " · Today" : ""}</div>`;
          lastDay = day;
        }
        if (!nowInserted && day === today && timed && when > nowIso) {
          html += _tlNowLine();
          nowInserted = true;
        }
        html += _tlRow(record, nowIso, entry.display);
        if (!multiDay) lastDay = day;
      }
      if (!nowInserted && lastDay === today) html += _tlNowLine();
      node.innerHTML = html;
    }

    // ── Fullscreen ─────────────────────────────────────────────────
    function toggleFullscreen() {
      if (document.fullscreenElement) {
        document.exitFullscreen?.();
        return;
      }
      const target = document.documentElement;
      if (!target.requestFullscreen) {
        showToast("Fullscreen is not available in this browser.", "error");
        return;
      }
      target.requestFullscreen().catch(() => showToast("Fullscreen was blocked by the browser.", "error"));
    }
    document.addEventListener("fullscreenchange", () => {
      const active = !!document.fullscreenElement;
      document.body.classList.toggle("is-fullscreen", active);
      const btn = document.getElementById("fullscreen-btn");
      if (btn) {
        btn.textContent = active ? "⤢" : "⛶";
        btn.title = active ? "Exit fullscreen (f)" : "Toggle fullscreen (f)";
      }
    });
    async function loadConfig() {
      appConfig = await api("/api/config");
      applyConfiguredTheme();
      applyConfiguredDashboard();
    }
    async function loadNotifications() {
      if (appConfig?.notifications?.enabled === false || appConfig?.notifications?.web === false) {
        document.getElementById("notifications").innerHTML = `<div class="empty">Notifications disabled.</div>`;
        return;
      }
      const params = query();
      const notificationParams = new URLSearchParams();
      if (params.has("recipient")) notificationParams.set("recipient", params.get("recipient"));
      else if (params.has("person")) notificationParams.set("recipient", params.get("person"));
      const lookahead = firstParam(
        params,
        ["notify_lookahead"],
        appConfig?.web?.notification_lookahead || appConfig?.notifications?.lookahead || "0m"
      );
      if (lookahead) notificationParams.set("lookahead", lookahead);
      const data = await api(`/api/notifications?${notificationParams}`);
      window._lastNotifRecords = data.records || [];
      const node = document.getElementById("notifications");
      node.innerHTML = data.records.length ? "" : `<div class="empty">No notifications.</div>`;
      const snoozeDefault = appConfig?.notifications?.snooze_default || "10m";
      let notifIdx = 0;
      for (const record of data.records) {
        notifIdx++;
        const snoozeInputId = `snooze-input-${notifIdx}`;
        const snoozeRowId = `snooze-row-${notifIdx}`;
        const actions = record.id ? `
          <div class="actions" style="flex-wrap:wrap;gap:.3rem">
            <button class="secondary" type="button" onclick="ackMessage(${escapeHtml(jsLiteral(record.id))})">Ack</button>
            <button class="secondary" type="button" onclick="snoozeMessage(${escapeHtml(jsLiteral(record.id))}, ${escapeHtml(jsLiteral(snoozeDefault))})">Snooze ${escapeHtml(snoozeDefault)}</button>
            <button class="secondary" type="button" onclick="document.getElementById(${escapeHtml(jsLiteral(snoozeRowId))}).style.display=document.getElementById(${escapeHtml(jsLiteral(snoozeRowId))}).style.display===''?'none':''" style="font-size:.73rem">Custom…</button>
            <button class="secondary" type="button" onclick="retryBrowserNotification(${escapeHtml(jsLiteral(record.id || record.notification_id || ""))})" style="font-size:.73rem" title="Re-send browser notification">Retry</button>
          </div>
          <div id="${snoozeRowId}" class="snooze-inline" style="display:none">
            <input id="${snoozeInputId}" value="${escapeHtml(snoozeDefault)}" placeholder="30m / 1h / 2h">
            <button class="secondary" type="button" onclick="snoozeMessageCustom(${escapeHtml(jsLiteral(record.id))}, ${escapeHtml(jsLiteral(snoozeInputId))})">Go</button>
          </div>
        ` : "";
        const stateBadge = notifStateBadge(record);
        const relTime = record.when ? relativeTime(record.when) : "";
        const whenDisplay = relTime ? `${escapeHtml(record.when)} <span style="color:var(--muted);font-size:.8em">(${escapeHtml(relTime)})</span>` : escapeHtml(record.when);
        node.insertAdjacentHTML(
          "beforeend",
          `<div class="notification-row"><span class="pill">${whenDisplay}</span>${stateBadge}<div class="title">${escapeHtml(record.title)}</div><div class="meta">${escapeHtml(record.sender)} → ${escapeHtml((record.recipients || []).join(", "))}</div>${actions}</div>`
        );
        showBrowserNotification(record);
      }
    }
    async function ackMessage(id) {
      await api(`/api/messages/id/${encodeURIComponent(id)}/ack`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: "{}",
      });
      await refreshAll();
    }
    async function snoozeMessage(id, duration) {
      await api(`/api/messages/id/${encodeURIComponent(id)}/snooze`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({duration}),
      });
      await refreshAll();
    }
    async function enableBrowserNotifications() {
      if (!("Notification" in window)) {
        alert("This browser does not support notifications.");
        return;
      }
      const permission = await Notification.requestPermission();
      browserNotificationsEnabled = permission === "granted";
      updateNotifBtnLabel();
      updateNotifPermissionDisplay();
      if (browserNotificationsEnabled) await loadNotifications();
      else if (permission === "denied") showNotificationSettingsHelp();
    }
    function showBrowserNotification(record) {
      if (!browserNotificationsEnabled || !("Notification" in window) || Notification.permission !== "granted") return;
      const key = record.notification_id || record.id || record.text;
      if (seenNotifications.has(key)) return;
      seenNotifications.add(key);
      new Notification(record.title || "life.txt message", {
        body: `${record.sender || ""} -> ${(record.recipients || []).join(", ")}`,
        tag: key,
      });
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function jsLiteral(value) {
      return JSON.stringify(String(value ?? ""));
    }
    function focusableElements(container) {
      if (!container) return [];
      const selector = [
        "a[href]", "button:not([disabled])", "input:not([disabled])",
        "select:not([disabled])", "textarea:not([disabled])",
        "[tabindex]:not([tabindex='-1'])",
      ].join(",");
      return Array.from(container.querySelectorAll(selector))
        .filter(el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    }
    function syncBackgroundInert() {
      const hasOpenModal = !!document.querySelector(".modal-backdrop.open, .cmdk-backdrop.open");
      document.body.classList.toggle("modal-open", hasOpenModal);
      for (const el of [document.querySelector("header"), document.querySelector("main")]) {
        if (!el) continue;
        if (hasOpenModal) {
          el.setAttribute("inert", "");
          el.setAttribute("aria-hidden", "true");
        } else {
          el.removeAttribute("inert");
          el.removeAttribute("aria-hidden");
        }
      }
    }
    function openManagedModal(backdrop, focusSelector) {
      if (!backdrop) return;
      _lastFocusedBeforeModal = document.activeElement;
      backdrop.classList.add("open");
      syncBackgroundInert();
      window.setTimeout(() => {
        const target = focusSelector ? backdrop.querySelector(focusSelector) : null;
        const fallback = focusableElements(backdrop)[0];
        (target || fallback || backdrop).focus?.();
      }, 0);
    }
    function closeManagedModal(backdrop) {
      if (!backdrop) return;
      backdrop.classList.remove("open");
      syncBackgroundInert();
      const restore = _lastFocusedBeforeModal;
      _lastFocusedBeforeModal = null;
      const hiddenModal = restore?.closest?.(".modal-backdrop:not(.open), .cmdk-backdrop:not(.open)");
      if (restore && document.contains(restore) && !hiddenModal) {
        window.setTimeout(() => restore.focus?.(), 0);
      }
    }
    function activeModalBackdrop() {
      const open = Array.from(document.querySelectorAll(".modal-backdrop.open, .cmdk-backdrop.open"));
      return open.length ? open[open.length - 1] : null;
    }
    function trapModalFocus(event) {
      if (event.key !== "Tab") return false;
      const modal = activeModalBackdrop();
      if (!modal) return false;
      const focusables = focusableElements(modal);
      if (!focusables.length) {
        event.preventDefault();
        modal.focus?.();
        return true;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
        return true;
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
        return true;
      }
      return false;
    }
    async function refreshAll() {
      // Refresh only what the active view needs; notifications always poll so
      // browser alerts keep working from any view.
      const v = currentView();
      const tasks = [loadNotifications()];
      if (VIEW_PAGE[v] === "items" || v === "") tasks.push(loadItems());
      if (v === "agenda") tasks.push(loadAgenda());
      if (v === "timeline") tasks.push(loadTimeline());
      if (v === "status") tasks.push(loadStatus());
      if (v === "team") tasks.push(loadTeam());
      if (v === "dashboard") tasks.push(loadDashboard());
      if (v === "focus") tasks.push(loadFocus());
      if (v === "review") tasks.push(loadReview());
      if (v === "graph") tasks.push(loadGraphPanel());
      if (v === "stats") {
        statsLoaded = true;
        tasks.push(loadChart(currentChartType));
        tasks.push(loadStatsBreakdown());
      }
      await Promise.all(tasks);
    }

    // ── Quick-add bar ──────────────────────────────────────────────
    function toggleQuickAdd(show) {
      const bar = document.getElementById("quick-add-bar");
      bar.style.display = (show === undefined ? bar.style.display === "none" : show) ? "" : "none";
      if (bar.style.display !== "none") {
        document.getElementById("quick-line").focus();
        document.getElementById("quick-line").select();
      }
    }
    async function quickAddLine() {
      const input = document.getElementById("quick-line");
      const line = input.value.trim();
      if (!line) return;
      const msgEl = document.getElementById("quick-check-msg");
      try {
        await api("/api/items/raw", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        input.value = "";
        input.className = "";
        if (msgEl) { msgEl.textContent = ""; msgEl.className = "check-msg"; }
        toggleQuickAdd(false);
        showToast("Item added.", "success");
        await refreshAll();
      } catch(err) {
        input.classList.add("err");
        if (msgEl) { msgEl.textContent = err.message || "Invalid line"; msgEl.className = "check-msg err"; }
        showToast("Add failed: " + (err.message || "invalid"), "error");
      }
    }

    // ── Keyboard shortcuts ─────────────────────────────────────────
    document.addEventListener("keydown", function(e) {
      if (trapModalFocus(e)) return;
      const active = document.activeElement;
      const inInput = active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        openCmdk();
        return;
      }
      if (e.key === "Escape") {
        if (document.getElementById("cmdk-backdrop").classList.contains("open")) { closeCmdk(); return; }
        if (isKioskMode()) { toggleKioskMode(); return; }
        if (document.getElementById("help-modal").classList.contains("open")) { closeHelpModal(); return; }
        if (document.getElementById("undo-modal").classList.contains("open")) { closeUndoHistoryModal(); return; }
        if (document.getElementById("git-modal").classList.contains("open")) { closeGitModal(); return; }
        if (document.getElementById("editor-modal").classList.contains("open")) { closeEditorModal(); return; }
        if (document.getElementById("detail-drawer").classList.contains("open")) { closeDrawer(); return; }
        if (inInput) { active.blur(); return; }
        toggleQuickAdd(false);
        return;
      }
      if (inInput) return;
      if (e.key === "?") { e.preventDefault(); openHelpModal(); return; }
      if (e.key === "[" && document.getElementById("detail-drawer").classList.contains("open")) { e.preventDefault(); drawerPrev(); return; }
      if (e.key === "]" && document.getElementById("detail-drawer").classList.contains("open")) { e.preventDefault(); drawerNext(); return; }
      if (e.key === "<" || e.key === ",") { e.preventDefault(); cycleStatusFilter(-1); return; }
      if (e.key === ">" || e.key === ".") { e.preventDefault(); cycleStatusFilter(1); return; }
      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        newItem();
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        document.getElementById("search").focus();
        return;
      }
      if (e.key === "j") { e.preventDefault(); kbMove(1); return; }
      if (e.key === "k") { e.preventDefault(); kbMove(-1); return; }
      if (e.key === "Enter") {
        if (!document.getElementById("detail-drawer").classList.contains("open") && kbActivate()) e.preventDefault();
        return;
      }
      if (e.key === "x") { e.preventDefault(); kbToggleSelect(); return; }
      if (e.key === "q") { e.preventDefault(); toggleQuickAdd(); return; }
      if (e.key === "r" || e.key === "R") { e.preventDefault(); refreshAll(); return; }
      if (e.key === "s" || e.key === "S") { e.preventDefault(); toggleStats(); return; }
      if (e.key === "d" || e.key === "D") { e.preventDefault(); toggleDarkMode(); return; }
      if (e.key === "f" || e.key === "F") { e.preventDefault(); toggleFullscreen(); return; }
      if (e.key === "g" || e.key === "G") { e.preventDefault(); jumpToLine(); return; }
      if (e.key === "K") { e.preventDefault(); toggleKioskMode(); return; }
    });

    // ── Command palette (Ctrl+K) ───────────────────────────────────
    let _cmdkIndex = 0;
    let _cmdkEntries = [];
    function fuzzyMatch(text, queryText) {
      const textLower = String(text || "").toLowerCase();
      const queryLower = String(queryText || "").toLowerCase();
      if (!queryLower) return true;
      if (textLower.includes(queryLower)) return true;
      let j = 0;
      for (let i = 0; i < textLower.length && j < queryLower.length; i++) {
        if (textLower[i] === queryLower[j]) j++;
      }
      return j === queryLower.length;
    }
    function recentItemKey(item) {
      return itemStableKey(item);
    }
    function loadRecentItems() {
      try {
        const raw = localStorage.getItem(RECENT_ITEMS_STORAGE_KEY);
        const rows = raw ? JSON.parse(raw) : [];
        return Array.isArray(rows) ? rows : [];
      } catch(_) {
        return [];
      }
    }
    function rememberRecentItem(item) {
      if (!item) return;
      try {
        const key = recentItemKey(item);
        const row = {
          key,
          line: item.line,
          source: item.source || "",
          title: item.title || "",
          type: item.type || "",
          opened_at: Date.now(),
        };
        const next = [row, ...loadRecentItems().filter(r => r.key !== key)].slice(0, 8);
        localStorage.setItem(RECENT_ITEMS_STORAGE_KEY, JSON.stringify(next));
      } catch(_) {}
    }
    const CMDK_ACTIONS = [
      {label: "New item", run: newItem},
      {label: "Go to Dashboard", run: () => switchWorkspace("dashboard")},
      {label: "Go to Items", run: () => switchWorkspace("")},
      {label: "Go to Agenda", run: () => switchWorkspace("agenda")},
      {label: "Go to Timeline", run: () => switchWorkspace("timeline")},
      {label: "Go to Focus", run: () => switchWorkspace("focus")},
      {label: "Go to Review", run: () => switchWorkspace("review")},
      {label: "Go to Messages", run: () => switchWorkspace("messages")},
      {label: "Go to Team", run: () => switchWorkspace("team")},
      {label: "Go to Status", run: () => switchWorkspace("status")},
      {label: "Toggle fullscreen", run: () => toggleFullscreen()},
      {label: "Go to Notifications", run: () => switchWorkspace("notifications")},
      {label: "Go to Stats", run: () => switchWorkspace("stats")},
      {label: "Go to Graph", run: () => switchWorkspace("graph")},
      {label: "Go to Display mode", run: () => switchWorkspace("display")},
      {label: "Toggle quick-add bar", run: () => toggleQuickAdd(true)},
      {label: "Refresh all", run: refreshAll},
      {label: "Toggle dark mode", run: toggleDarkMode},
      {label: "Toggle display mode", run: toggleDisplayMode},
      {label: "Toggle kiosk mode", run: toggleKioskMode},
      {label: "Toggle agenda blocked filter", run: toggleAgendaBlocked},
      {label: "Show undo history", run: openUndoHistoryModal},
      {label: "Export items as CSV", run: () => exportItems("csv")},
      {label: "Export items as JSON", run: () => exportItems("json")},
      {label: "Export items as Markdown", run: () => exportItems("markdown")},
      {label: "Jump to line number", run: jumpToLine},
      {label: "Keyboard shortcuts help", run: openHelpModal},
    ];
    function openCmdk() {
      const backdrop = document.getElementById("cmdk-backdrop");
      const input = document.getElementById("cmdk-input");
      backdrop.classList.add("open");
      syncBackgroundInert();
      input.value = "";
      renderCmdk("");
      input.focus();
    }
    function closeCmdk() {
      document.getElementById("cmdk-backdrop").classList.remove("open");
      syncBackgroundInert();
    }
    function renderCmdk(qText) {
      const list = document.getElementById("cmdk-list");
      const q = String(qText || "").trim().toLowerCase();
      const idKey = appConfig?.ids?.key || "id";
      const actions = CMDK_ACTIONS.filter(a => fuzzyMatch(a.label, q));
      const items = q
        ? (currentItems || []).filter(i =>
            fuzzyMatch(i.title || "", q) ||
            fuzzyMatch(String(i?.details?.[idKey]?.[0] || i?.id || ""), q)
          ).slice(0, 8)
        : [];
      const recent = q ? [] : loadRecentItems()
        .map(r => (currentItems || []).find(i => recentItemKey(i) === r.key) || r)
        .filter(Boolean)
        .slice(0, 6);
      _cmdkEntries = [
        ...recent.map(i => ({kind: i.type || "recent", label: i.title || "(untitled)", hint: i?.details?.[idKey]?.[0] || (i.line ? `line ${i.line}` : "recent"), section: "Recently Opened", run: () => {
          const live = (currentItems || []).find(x => recentItemKey(x) === (i.key || recentItemKey(i)));
          if (live) { selectItem(live); openDrawer(live); }
          else if (i.line) openItemByLine(Number(i.line));
        }})),
        ...items.map(i => ({kind: i.type || "item", label: i.title, hint: i?.details?.[idKey]?.[0] || `line ${i.line}`, section: "Items", run: () => { selectItem(i); openDrawer(i); }})),
        ...actions.map(a => ({kind: "action", label: a.label, hint: "", section: "Actions", run: a.run})),
      ];
      _cmdkIndex = 0;
      if (!_cmdkEntries.length) {
        list.innerHTML = `<div class="cmdk-empty">No matches.</div>`;
        return;
      }
      list.innerHTML = "";
      let lastSection = "";
      _cmdkEntries.forEach((entry, i) => {
        if (entry.section && entry.section !== lastSection) {
          const section = document.createElement("div");
          section.className = "cmdk-section";
          section.textContent = entry.section;
          list.appendChild(section);
          lastSection = entry.section;
        }
        const row = document.createElement("div");
        row.className = "cmdk-row" + (i === _cmdkIndex ? " focus" : "");
        row.innerHTML = `<span class="cmdk-kind">${escapeHtml(entry.kind)}</span><span>${escapeHtml(entry.label)}</span>` +
          (entry.hint ? `<span style="margin-left:auto;color:var(--muted);font-size:.78rem">${escapeHtml(entry.hint)}</span>` : "");
        row.addEventListener("click", () => { closeCmdk(); entry.run(); });
        list.appendChild(row);
      });
    }
    function _cmdkMoveFocus(delta) {
      if (!_cmdkEntries.length) return;
      _cmdkIndex = (_cmdkIndex + delta + _cmdkEntries.length) % _cmdkEntries.length;
      const rows = document.querySelectorAll("#cmdk-list .cmdk-row");
      rows.forEach((row, i) => row.classList.toggle("focus", i === _cmdkIndex));
      if (rows[_cmdkIndex]) rows[_cmdkIndex].scrollIntoView({block: "nearest"});
    }
    document.addEventListener("DOMContentLoaded", () => {
      const input = document.getElementById("cmdk-input");
      if (!input) return;
      input.addEventListener("input", () => renderCmdk(input.value));
      input.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); _cmdkMoveFocus(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); _cmdkMoveFocus(-1); }
        else if (e.key === "Enter") {
          e.preventDefault();
          const entry = _cmdkEntries[_cmdkIndex];
          if (entry) { closeCmdk(); entry.run(); }
        } else if (e.key === "Escape") {
          e.preventDefault();
          closeCmdk();
        }
      });
    });

    // ── Help modal ─────────────────────────────────────────────────
    function openHelpModal() { openManagedModal(document.getElementById("help-modal"), "button"); }
    function closeHelpModal() { closeManagedModal(document.getElementById("help-modal")); }

    // ── Contextual hover/focus help ────────────────────────────────
    function clampNumber(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }
    function positionUiHelpTooltip(anchor, tooltip) {
      if (!anchor || !tooltip) return;
      const margin = 8;
      const rect = anchor.getBoundingClientRect();
      const tipRect = tooltip.getBoundingClientRect();
      const left = clampNumber(
        rect.left + rect.width / 2 - tipRect.width / 2,
        margin,
        Math.max(margin, window.innerWidth - tipRect.width - margin)
      );
      let top = rect.bottom + margin;
      if (top + tipRect.height > window.innerHeight - margin) {
        top = rect.top - tipRect.height - margin;
      }
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${Math.max(margin, top)}px`;
    }
    function showUiHelp(anchor) {
      const tooltip = document.getElementById("ui-help-tooltip");
      const text = anchor?.dataset?.help || "";
      if (!tooltip || !text) return;
      tooltip.textContent = text;
      tooltip.setAttribute("aria-hidden", "false");
      tooltip.classList.add("visible");
      window.requestAnimationFrame(() => positionUiHelpTooltip(anchor, tooltip));
    }
    function hideUiHelp() {
      const tooltip = document.getElementById("ui-help-tooltip");
      if (!tooltip) return;
      tooltip.classList.remove("visible");
      tooltip.setAttribute("aria-hidden", "true");
    }
    function setupContextualHelp() {
      document.querySelectorAll(".help-target[data-help], .field-help[data-help]").forEach(el => {
        el.addEventListener("mouseenter", () => showUiHelp(el));
        el.addEventListener("focus", () => showUiHelp(el));
        el.addEventListener("mouseleave", hideUiHelp);
        el.addEventListener("blur", hideUiHelp);
      });
      window.addEventListener("resize", hideUiHelp);
      window.addEventListener("scroll", hideUiHelp, {passive: true});
    }

    // ── Toast system ────────────────────────────────────────────────
    function showToast(message, type = "info", duration = 3500) {
      const container = document.getElementById("toast-container");
      const el = document.createElement("div");
      el.className = "toast " + type;
      el.textContent = message;
      container.appendChild(el);
      setTimeout(() => el.remove(), duration);
    }

    // ── Record detail modal ────────────────────────────────────────
    let drawerItem = null;
    let drawerEditing = false;

    function _drawerRestoreButtons(item) {
      const isDone = ["[x]", "[-]"].includes(item.status);
      const idKey = (typeof appConfig !== "undefined" && appConfig?.ids?.key) || "id";
      const hasId = !!(item?.details?.[idKey]?.[0] || item?.id);
      document.getElementById("drawer-head-btns").innerHTML =
        `<button class="secondary" onclick="drawerMarkDone()" id="drawer-done-btn"${!item.editable || isDone ? " disabled" : ""}>Done</button>` +
        `<button class="secondary" id="drawer-edit-btn" onclick="drawerEdit()"${!item.editable ? " disabled" : ""}>Edit</button>` +
        `<button class="secondary" id="drawer-copy-id" onclick="drawerCopyId()" title="Copy item ID to clipboard"${hasId ? "" : ' style="display:none"'}>Copy ID</button>` +
        `<button class="secondary" id="drawer-share-btn" onclick="drawerShareLink()" title="Copy deep link to this item">Share</button>` +
        `<button class="secondary" onclick="drawerCopyMarkdown()" title="Copy item as Markdown">MD</button>` +
        `<button class="danger" onclick="drawerDelete()" id="drawer-delete-btn"${!item.editable ? " disabled" : ""}>Delete</button>`;
    }

    function openDrawer(item) {
      drawerEditing = false;
      drawerItem = item;
      const drawer = document.getElementById("detail-drawer");
      const body = document.getElementById("drawer-body");
      const title = document.getElementById("drawer-title");
      const isDone = ["[x]", "[-]"].includes(item.status);
      const statusCls = STATUS_CLASS[item.status] || "status-note";
      const statusLbl = STATUS_LABEL[item.status] || item.status;
      const typeCls = "type-" + (item.type || "N");
      const typeFullName = ITEM_TYPE_NAMES[item.type] || item.type;
      title.innerHTML = `<span class="status-badge ${statusCls}">${escapeHtml(statusLbl)}</span>` +
        `<span class="type-badge ${typeCls}" style="margin-left:.35rem" title="${escapeHtml(typeFullName)}">${escapeHtml(item.type)}</span>` +
        `<span style="margin-left:.25rem;font-size:.78rem;color:var(--muted)">${escapeHtml(typeFullName)}</span>` +
        `<span style="margin-left:.4rem;font-weight:700">${escapeHtml(item.title)}</span>`;
      _drawerRestoreButtons(item);
      const REF_KEYS = new Set(["depends_on", "parent", "blocks", "related", "ref"]);
      let fieldsHtml = `<div class="drawer-section-title">Fields</div><div class="drawer-fields">`;
      for (const [key, values] of Object.entries(item.details || {})) {
        const valHtml = (values || []).map(v => {
          if (REF_KEYS.has(key)) {
            return `<a class="drawer-link" onclick="drawerNavigate(${escapeHtml(jsLiteral(String(v)))})">${escapeHtml(String(v))}</a>`;
          }
          return escapeHtml(String(v));
        }).join(", ");
        fieldsHtml += `<div class="drawer-field"><span class="key">${escapeHtml(key)}</span><span class="val">${valHtml}</span></div>`;
      }
      fieldsHtml += `</div>`;
      const bodyHtml = item?.markdown?.details?.body?.[0]
        ? `<div class="drawer-section-title">Body</div><div class="markdown">${item.markdown.details.body[0]}</div>` : "";
      const sourceHtml = `<div class="drawer-section-title">Source</div>` +
        `<div style="font-size:.82rem;color:var(--muted)">${escapeHtml(item.source || "")} line ${escapeHtml(String(item.line || ""))}</div>`;
      const rawHtml = item?.raw
        ? `<details class="drawer-raw-details"><summary>Raw line</summary><pre class="drawer-raw-pre">${escapeHtml(item.raw || "")}</pre></details>`
        : "";
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0] || "";
      const threadHtml = item.type === "M" && itemId
        ? `<div id="drawer-thread"><div class="drawer-section-title">Message Thread</div><div class="empty">Loading…</div></div>`
        : "";
      const replyHtml = item.type === "M" && itemId
        ? `<form class="message-reply-form" onsubmit="event.preventDefault();replyToMessage(${escapeHtml(jsLiteral(itemId))})">` +
          `<div class="drawer-section-title">Reply</div>` +
          `<input id="message-reply-title" placeholder="Reply title" autocomplete="off">` +
          `<textarea id="message-reply-body" placeholder="Message body"></textarea>` +
          `<div class="actions"><button type="submit">Send Reply</button><button type="button" class="secondary" onclick="document.getElementById('message-reply-title').value='';document.getElementById('message-reply-body').value=''">Clear</button></div>` +
          `</form>`
        : "";
      const progressHtml = buildEstProgressHtml(item);
      const canDue = item.editable && ["T", "D", "R", "E", "H"].includes(item.type);
      const dueQuickHtml = canDue
        ? `<div class="due-quick-bar"><span style="font-size:.78rem;color:var(--muted)">Due:</span>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('today')" title="Set due to today">Today</button>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('+1d')" title="Postpone by one day">+1d</button>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('+1w')" title="Postpone by one week">+1w</button>` +
          (item?.details?.due?.length ? `<button type="button" class="secondary" onclick="drawerPostpone('clear')" title="Remove due date">Clear</button>` : "") +
          `</div>`
        : "";
      body.innerHTML = fieldsHtml + progressHtml + dueQuickHtml + bodyHtml +
        `<div id="drawer-blockers"></div>` +
        `<div id="drawer-deps"><div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty dep-loading">Loading…</div></div>` +
        threadHtml + replyHtml +
        sourceHtml + rawHtml;
      rememberRecentItem(item);
      openManagedModal(drawer, ".drawer-close-btn");
      loadDependencyLinks(item);
      loadBlockerChain(item);
      if (item.type === "M" && itemId) loadDrawerMessageThread(item);
    }

    // ── "Why is this blocked?" chain in detail modal ───────────────
    async function loadBlockerChain(item) {
      const container = document.getElementById("drawer-blockers");
      if (!container) return;
      container.innerHTML = "";
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0];
      if (!itemId || ["[x]", "[-]"].includes(item.status)) return;
      try {
        const data = await api(`/api/blockers?id=${encodeURIComponent(itemId)}`);
        if (!data.blocked) return;
        let html = `<div class="drawer-section-title" style="color:var(--danger)">⚡ Why is this blocked?</div><div class="blocker-chain">`;
        for (const entry of data.chain || []) {
          const indent = Math.min(entry.level - 1, 4) * 0.85;
          const statusIcon = STATUS_ICON[entry.blocker_status] || "·";
          const statusCls = STATUS_CLASS[entry.blocker_status] || "status-note";
          const nav = escapeHtml(jsLiteral(entry.blocker_id || ""));
          const relation = entry.level === 1
            ? (entry.relation === "blocks" ? "blocked by" : "waiting on")
            : "which waits on";
          html += `<div class="blocker-chain-row" style="margin-left:${indent}rem">` +
            `<span>${entry.level === 1 ? "⚡" : "↳"}</span>` +
            `<span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(statusIcon)}</span>` +
            `<span style="color:var(--muted);font-size:.78rem;white-space:nowrap">${escapeHtml(relation)}</span>` +
            `<a class="drawer-link" onclick="drawerNavigate(${nav})">${escapeHtml(entry.blocker_title || entry.blocker_id || "?")}</a>` +
            `</div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(_) {
        container.innerHTML = "";
      }
    }

    const DEP_RELATION_LABEL = {
      depends_on: "depends on", blocks: "blocks", parent: "child of",
      related: "related", ref: "ref",
    };
    const STATUS_ICON = {"[ ]": "○", "[x]": "✓", "[-]": "✕", "[/]": "◑", "[>]": "→", "[?]": "?", "[!]": "!"};

    function graphColor(type) {
      return {
        T: "#2563eb", E: "#16a34a", D: "#dc2626", R: "#f59e0b",
        H: "#7c3aed", N: "#64748b", S: "#0891b2", M: "#db2777", J: "#9333ea",
      }[type || ""] || "#475569";
    }

    function truncateLabel(value, maxLen = 16) {
      const text = String(value || "");
      return text.length > maxLen ? text.slice(0, maxLen - 1) + "…" : text;
    }

    function computeLayeredPositions(shownNodes, shownEdges, layout, w, h) {
      const ids = shownNodes.map(n => String(n.id));
      const idSet = new Set(ids);
      const indeg = new Map(ids.map(id => [id, 0]));
      const out = new Map(ids.map(id => [id, []]));
      for (const e of shownEdges) {
        const s = String(e.source), t = String(e.target);
        if (!idSet.has(s) || !idSet.has(t) || s === t) continue;
        out.get(s).push(t);
        indeg.set(t, indeg.get(t) + 1);
      }
      // Kahn-style layering; cycles fall into the trailing layer.
      const layer = new Map();
      const seen = new Set();
      let frontier = ids.filter(id => indeg.get(id) === 0);
      if (!frontier.length && ids.length) frontier = [ids[0]];
      let depth = 0;
      const remaining = new Map(indeg);
      while (frontier.length) {
        const next = [];
        for (const id of frontier) {
          if (seen.has(id)) continue;
          seen.add(id);
          layer.set(id, depth);
          for (const t of out.get(id) || []) {
            remaining.set(t, remaining.get(t) - 1);
            if (remaining.get(t) <= 0 && !seen.has(t)) next.push(t);
          }
        }
        frontier = next;
        depth++;
      }
      for (const id of ids) if (!layer.has(id)) layer.set(id, depth);
      const byLayer = new Map();
      for (const id of ids) {
        const l = layer.get(id);
        if (!byLayer.has(l)) byLayer.set(l, []);
        byLayer.get(l).push(id);
      }
      const layers = [...byLayer.keys()].sort((a, b) => a - b);
      const main = layout === "lr" ? w : h;
      const cross = layout === "lr" ? h : w;
      const mainPad = 52, crossPad = 36;
      const positions = {};
      layers.forEach((l, li) => {
        const layerIds = byLayer.get(l);
        const mainPos = layers.length > 1 ? mainPad + (main - 2 * mainPad) * li / (layers.length - 1) : main / 2;
        layerIds.forEach((id, i) => {
          const crossPos = layerIds.length > 1 ? crossPad + (cross - 2 * crossPad) * i / (layerIds.length - 1) : cross / 2;
          positions[id] = layout === "lr" ? {x: mainPos, y: crossPos} : {x: crossPos, y: mainPos};
        });
      });
      return positions;
    }

    function renderGraphSvg(nodes, edges, options = {}) {
      const compact = !!options.compact;
      const focusId = options.focusId || "";
      const layout = options.layout || "ring";
      const maxNodes = compact ? 10 : 40;
      const shownNodes = (nodes || []).slice(0, maxNodes);
      const shown = new Set(shownNodes.map(n => String(n.id)));
      const shownEdges = (edges || []).filter(e => shown.has(String(e.source)) && shown.has(String(e.target)));
      const w = compact ? 360 : 640;
      const h = compact ? 180 : 300;
      let positions = {};
      if (layout === "lr" || layout === "tb") {
        positions = computeLayeredPositions(shownNodes, shownEdges, layout, w, h);
      } else {
        const cx = w / 2;
        const cy = h / 2;
        const r = compact ? 56 : 110;
        const focusIndex = shownNodes.findIndex(n => String(n.id) === String(focusId));
        const ringNodes = focusIndex >= 0 ? shownNodes.filter((_, i) => i !== focusIndex) : shownNodes;
        if (focusIndex >= 0) positions[String(focusId)] = {x: cx, y: cy};
        ringNodes.forEach((node, i) => {
          const angle = (Math.PI * 2 * i / Math.max(1, ringNodes.length)) - Math.PI / 2;
          positions[String(node.id)] = {x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r};
        });
      }
      const defs = `<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#94a3b8"/></marker></defs>`;
      const edgeHtml = shownEdges.map(e => {
        const a = positions[String(e.source)];
        const b = positions[String(e.target)];
        if (!a || !b) return "";
        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;
        return `<line class="graph-edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"></line>` +
          `<text class="graph-edge-label" x="${mx}" y="${my - 4}" text-anchor="middle">${escapeHtml(truncateLabel(e.relation, compact ? 8 : 12))}</text>`;
      }).join("");
      const nodeHtml = shownNodes.map(node => {
        const p = positions[String(node.id)];
        if (!p) return "";
        const id = String(node.id || "");
        const missing = !!node.missing;
        const label = truncateLabel(node.title || id, compact ? 12 : 18) + (missing ? " (?)" : "");
        const nav = escapeHtml(jsLiteral(id));
        const radius = id === String(focusId) ? (compact ? 18 : 24) : (compact ? 14 : 20);
        const tooltip = id + " " + (node.title || "") + (missing ? " — referenced but not found in loaded files" : "");
        return `<g class="graph-node${missing ? " missing" : ""}" onclick="drawerNavigate(${nav})" transform="translate(${p.x},${p.y})">` +
          `<title>${escapeHtml(tooltip)}</title>` +
          `<circle r="${radius}"${missing ? "" : ` fill="${graphColor(node.type)}"`}></circle>` +
          `<text text-anchor="middle" y="${radius + 13}">${escapeHtml(label)}</text>` +
          `</g>`;
      }).join("");
      const more = (nodes || []).length > shownNodes.length
        ? `<text x="${w - 10}" y="${h - 10}" text-anchor="end" fill="#64748b" font-size="10">+${(nodes || []).length - shownNodes.length} more</text>`
        : "";
      return `<svg class="graph-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="life.txt dependency graph">${defs}${edgeHtml}${nodeHtml}${more}</svg>`;
    }

    // ── Graph layout presets + SVG/PNG export ─────────────────────
    let _graphLayout = (function() {
      try { return localStorage.getItem("lifetxt_graph_layout") || "ring"; } catch(_) { return "ring"; }
    })();
    function setGraphLayout(layout) {
      _graphLayout = layout;
      try { localStorage.setItem("lifetxt_graph_layout", layout); } catch(_) {}
      _syncGraphLayoutBtns();
      if (graphLoaded) loadGraphPanel();
      if (drawerItem) loadDependencyLinks(drawerItem);
    }
    function _syncGraphLayoutBtns() {
      document.querySelectorAll(".graph-layout-btn[data-layout]").forEach(b => {
        b.classList.toggle("active", b.dataset.layout === _graphLayout);
      });
    }
    const GRAPH_EXPORT_CSS = "svg{background:#ffffff;font-family:sans-serif}" +
      ".graph-edge{stroke:#94a3b8;stroke-width:1.4;marker-end:url(#arrow);opacity:.8}" +
      ".graph-edge-label{fill:#68706a;font-size:9px}" +
      ".graph-node circle{stroke:#fff;stroke-width:2}" +
      ".graph-node text{fill:#202421;font-size:10px;font-weight:700}" +
      ".graph-node.missing circle{fill:#ffffff;stroke:#9ca3af;stroke-dasharray:4 3}" +
      ".graph-node.missing text{font-style:italic;fill:#9ca3af}";
    function _graphSvgForExport() {
      const svg = document.querySelector("#graph-panel .graph-svg");
      if (!svg) { showToast("Open and load the Graph panel first.", "warning"); return null; }
      const clone = svg.cloneNode(true);
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
      style.textContent = GRAPH_EXPORT_CSS;
      clone.insertBefore(style, clone.firstChild);
      clone.querySelectorAll("[onclick]").forEach(el => el.removeAttribute("onclick"));
      return clone;
    }
    function _downloadBlob(blob, filename) {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    }
    function exportGraphSvg() {
      const clone = _graphSvgForExport();
      if (!clone) return;
      const text = new XMLSerializer().serializeToString(clone);
      _downloadBlob(new Blob([text], {type: "image/svg+xml"}), "lifetxt-graph.svg");
      showToast("Graph exported as SVG.", "success");
    }
    function exportGraphPng() {
      const clone = _graphSvgForExport();
      if (!clone) return;
      const vb = (clone.getAttribute("viewBox") || "0 0 640 300").split(/\s+/).map(Number);
      clone.setAttribute("width", String(vb[2]));
      clone.setAttribute("height", String(vb[3]));
      const text = new XMLSerializer().serializeToString(clone);
      const img = new Image();
      const scale = 2;
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = vb[2] * scale;
        canvas.height = vb[3] * scale;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(blob => {
          if (!blob) { showToast("PNG export failed.", "error"); return; }
          _downloadBlob(blob, "lifetxt-graph.png");
          showToast("Graph exported as PNG.", "success");
        }, "image/png");
      };
      img.onerror = () => showToast("PNG export failed.", "error");
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text);
    }

    function graphFromLinkRecords(records, focusId) {
      const map = new Map();
      const edges = [];
      const put = (id, title, status, type, missing) => {
        if (!id) return;
        const key = String(id);
        if (!map.has(key)) map.set(key, {id: key, title: title || key, status: status || "", type: type || "", missing: !!missing});
        else if (!missing) map.get(key).missing = false;
      };
      put(focusId, focusId, "", "", false);
      for (const r of records || []) {
        put(r.source_id, r.source_title, r.source_status, r.source_type, false);
        put(r.target_id, r.target_title, r.target_status, r.target_type, r.status === "missing");
        if (r.source_id && r.target_id) edges.push({source: r.source_id, target: r.target_id, relation: r.relation});
      }
      return {nodes: [...map.values()], edges};
    }

    function renderDependencyMiniGraph(records, focusId, graphData) {
      const graph = graphData && (graphData.nodes || graphData.edges)
        ? {nodes: graphData.nodes || [], edges: graphData.edges || []}
        : graphFromLinkRecords(records, focusId);
      if (graph.nodes.length <= 1) return "";
      const layoutBar = `<div class="graph-layout-bar" style="margin:.1rem 0 .3rem">` +
        ["ring", "lr", "tb"].map(l =>
          `<button class="graph-layout-btn${l === _graphLayout ? " active" : ""}" type="button" onclick="setGraphLayout(${escapeHtml(jsLiteral(l))})" title="Switch mini-graph layout">${l.toUpperCase()}</button>`
        ).join("") + `</div>`;
      return `<div class="drawer-graph-mini">${layoutBar}${renderGraphSvg(graph.nodes, graph.edges, {compact: true, focusId, layout: _graphLayout})}</div>`;
    }

    async function loadGraphPanel() {
      const panel = document.getElementById("graph-panel");
      if (!panel) return;
      graphLoaded = true;
      const rootInput = document.getElementById("graph-root");
      const depthInput = document.getElementById("graph-depth");
      const root = (rootInput && rootInput.value) || firstParam(query(), ["graph_root", "root"], "");
      const depth = (depthInput && depthInput.value) || firstParam(query(), ["graph_depth", "depth"], "");
      const params = new URLSearchParams();
      if (root) params.set("root", root);
      if (depth) params.set("depth", depth);
      panel.innerHTML = `<div class="empty">Loading graph…</div>`;
      try {
        const data = await api(`/api/graph?${params.toString()}`);
        const nodes = data.nodes || [];
        const edges = data.edges || [];
        if (!nodes.length) {
          panel.innerHTML = `<div class="empty">No ID links. Add id: plus parent:, ref:, depends_on:, blocks:, or related: details.</div>`;
          return;
        }
        const missingCount = nodes.filter(n => n.missing).length;
        const missingNote = missingCount ? ` ${missingCount} dashed node(s) are referenced but missing.` : "";
        panel.innerHTML = renderGraphSvg(nodes, edges, {focusId: root, layout: _graphLayout}) +
          `<div class="note" style="margin-top:.45rem">${nodes.length} nodes / ${edges.length} edges. Click a node to open it.${escapeHtml(missingNote)}</div>`;
      } catch(e) {
        panel.innerHTML = `<div class="diagnostic">Graph error: ${escapeHtml(e.message)}</div>`;
      }
    }

    async function loadDependencyLinks(item) {
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || (item?.details?.[idKey]?.[0]);
      const container = document.getElementById("drawer-deps");
      if (!container) return;
      if (!itemId) {
        container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">No ID — cannot look up links.</div>`;
        return;
      }
      try {
        const data = await api(`/api/links?id=${encodeURIComponent(itemId)}&direction=both`);
        const records = data.records || [];
        let graphData = null;
        try {
          graphData = await api(`/api/graph?root=${encodeURIComponent(itemId)}&depth=2`);
        } catch(_) {}
        if (!records.length) {
          container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">No links.</div>`;
          return;
        }
        const outgoing = records.filter(r => r.source_id === itemId);
        const incoming = records.filter(r => r.target_id === itemId && r.source_id !== itemId);
        let html = `<div class="drawer-section-title">Dependencies &amp; Links (${records.length})</div>` +
          renderDependencyMiniGraph(records, itemId, graphData) +
          `<div class="dep-graph">`;

        function depRow(arrow, arrowCls, relLabel, otherId, otherTitle, otherStatus, otherType) {
          const statusIcon = STATUS_ICON[otherStatus] || "·";
          const statusCls = STATUS_CLASS[otherStatus] || "status-note";
          const typeCls = "type-" + (otherType || "N");
          const nav = escapeHtml(jsLiteral(otherId || ""));
          return `<div class="dep-row">
            <span class="dep-arrow ${arrowCls}">${arrow}</span>
            <span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(statusIcon)}</span>
            <span class="type-badge ${typeCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(otherType || "?")}</span>
            <span class="dep-rel">${escapeHtml(relLabel)}</span>
            ${otherId
              ? `<a class="drawer-link" onclick="drawerNavigate(${nav})">${escapeHtml(otherTitle || otherId)}</a>`
              : `<span class="dep-missing">${escapeHtml(otherTitle || otherId || "?")}</span>`}
          </div>`;
        }

        if (outgoing.length) {
          html += `<div class="dep-group-label">This item →</div>`;
          for (const r of outgoing) {
            const lbl = DEP_RELATION_LABEL[r.relation] || r.relation;
            html += depRow("→", "dep-out", lbl, r.target_id, r.target_title, r.target_status, r.target_type);
          }
        }
        if (incoming.length) {
          html += `<div class="dep-group-label" style="margin-top:.5rem">← This item</div>`;
          for (const r of incoming) {
            const lbl = DEP_RELATION_LABEL[r.relation] || r.relation;
            html += depRow("←", "dep-in", lbl, r.source_id, r.source_title, r.source_status, r.source_type);
          }
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(e) {
        if (container) container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">Error: ${escapeHtml(e.message)}</div>`;
      }
    }

    async function loadDrawerMessageThread(item) {
      const container = document.getElementById("drawer-thread");
      if (!container) return;
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0];
      if (!itemId) return;
      try {
        const data = await api(`/api/messages/thread/${encodeURIComponent(itemId)}`);
        const rows = data.items || [];
        if (!rows.length) {
          container.innerHTML = `<div class="drawer-section-title">Message Thread</div><div class="empty">No related messages.</div>`;
          return;
        }
        let html = `<div class="drawer-section-title">Message Thread (${rows.length})</div><div class="message-thread">`;
        for (const row of rows) {
          const rowId = row?.id || row?.details?.[idKey]?.[0] || "";
          const current = rowId === itemId ? " current" : "";
          const sender = row?.details?.sender?.[0] || "";
          const recipients = (row?.details?.recipient || []).join(", ");
          const when = row?.details?.notify_at?.[0] || row?.details?.created?.[0] || "";
          const nav = escapeHtml(jsLiteral(rowId));
          const actions = rowId
            ? `<div class="actions" style="margin-top:.3rem;gap:.25rem"><button class="secondary" type="button" onclick="drawerNavigate(${nav})">Open</button><button class="secondary" type="button" onclick="ackMessage(${nav})">Ack</button></div>`
            : "";
          html += `<div class="message-thread-row${current}"><div><strong>${escapeHtml(row.title || "")}</strong></div>` +
            `<div class="message-thread-meta">${escapeHtml(sender)} -> ${escapeHtml(recipients)}${when ? " / " + escapeHtml(when) : ""}</div>${actions}</div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(e) {
        container.innerHTML = `<div class="drawer-section-title">Message Thread</div><div class="empty">Error: ${escapeHtml(e.message)}</div>`;
      }
    }

    async function replyToMessage(messageId) {
      const titleEl = document.getElementById("message-reply-title");
      const bodyEl = document.getElementById("message-reply-body");
      const title = (titleEl?.value || "").trim();
      const body = (bodyEl?.value || "").trim();
      if (!title && !body) {
        showToast("Reply title or body is required.", "warning");
        return;
      }
      try {
        await api(`/api/messages/id/${encodeURIComponent(messageId)}/reply`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({title: title || body.slice(0, 60) || "Reply", body}),
        });
        if (titleEl) titleEl.value = "";
        if (bodyEl) bodyEl.value = "";
        showToast("Reply added.", "success");
        await refreshAll();
        if (drawerItem) {
          const idKey = appConfig?.ids?.key || "id";
          const currentId = drawerItem?.id || drawerItem?.details?.[idKey]?.[0] || messageId;
          await drawerNavigate(currentId);
        }
      } catch(e) {
        showToast("Reply failed: " + (e.message || e), "error");
      }
    }

    function closeDrawer() {
      closeManagedModal(document.getElementById("detail-drawer"));
      drawerItem = null;
    }

    function drawerEdit() {
      if (!drawerItem) return;
      if (!drawerItem.editable) { showToast("This record is read-only.", "warning"); return; }
      drawerEditing = true;
      document.getElementById("drawer-head-btns").innerHTML =
        `<button class="primary" onclick="drawerSaveEdit()">Save</button>` +
        `<button class="secondary" onclick="drawerCancelEdit()">Cancel</button>`;
      const item = drawerItem;
      const statusOpts = ["[ ]","[/]","[x]","[-]","[>]","[?]","[N]"]
        .map(s => `<option${s === item.status ? " selected" : ""}>${s}</option>`).join("");
      const typeOpts = ["T","E","D","R","H","N","S","M","J"]
        .map(t => `<option${t === item.type ? " selected" : ""}>${t}</option>`).join("");
      document.getElementById("drawer-body").innerHTML =
        `<form class="drawer-edit-form" onsubmit="event.preventDefault();drawerSaveEdit()">` +
        `<label>Status<select id="drawer-edit-status">${statusOpts}</select></label>` +
        `<label>Type<select id="drawer-edit-type">${typeOpts}</select></label>` +
        `<label>Title<input id="drawer-edit-title" value="${escapeHtml(item.title)}" required autocomplete="off"></label>` +
        `<label>Details<textarea id="drawer-edit-details" rows="7" placeholder="due:2026-01-01&#10;project:work">${escapeHtml(detailsToText(item.details))}</textarea></label>` +
        `</form>`;
      document.getElementById("drawer-edit-title").focus();
    }

    function drawerCancelEdit() {
      drawerEditing = false;
      openDrawer(drawerItem);
    }

    async function drawerSaveEdit() {
      if (!drawerItem || !drawerItem.editable) return;
      const saveLine = drawerItem.line;
      const titleEl = document.getElementById("drawer-edit-title");
      if (!titleEl || !titleEl.value.trim()) { showToast("Title is required.", "warning"); return; }
      const payload = {
        status: document.getElementById("drawer-edit-status").value,
        type: document.getElementById("drawer-edit-type").value,
        title: titleEl.value.trim(),
        details: parseDetails(document.getElementById("drawer-edit-details").value),
      };
      try {
        await api(`/api/items/${saveLine}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        drawerEditing = false;
        showToast("Record saved.", "success");
        await refreshAll();
        const updated = (currentItems || []).find(i => i.line === saveLine && i.editable);
        if (updated) openDrawer(updated);
      } catch(e) {
        showToast("Save failed: " + (e.message || e), "error");
      }
    }

    async function drawerMarkDone() {
      if (!drawerItem || !drawerItem.editable) return;
      const line = drawerItem.line;
      const prevPayload = {status: drawerItem.status, type: drawerItem.type, title: drawerItem.title, details: drawerItem.details || {}};
      await api(`/api/items/${line}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({...prevPayload, status: "[x]"}),
      });
      registerUndo("Marked done.", async () => {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(prevPayload),
        });
      });
      closeDrawer();
      await refreshAll();
    }

    async function drawerDelete() {
      if (!drawerItem || !drawerItem.editable) return;
      if (!confirm(`Delete "${drawerItem.title}"?`)) return;
      const rawLine = drawerItem.text;
      await api(`/api/items/${drawerItem.line}`, {method: "DELETE"});
      if (rawLine) {
        registerUndo("Item deleted.", async () => {
          await api("/api/items/raw", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({line: rawLine})});
        });
      } else {
        showToast("Item deleted.", "info");
      }
      closeDrawer();
      newItem();
      await refreshAll();
    }

    // ── Drawer: due-date quick actions (postpone) ──────────────────
    async function drawerPostpone(action) {
      if (!drawerItem || !drawerItem.editable) return;
      const line = drawerItem.line;
      const prevPayload = {status: drawerItem.status, type: drawerItem.type, title: drawerItem.title, details: drawerItem.details || {}};
      const details = JSON.parse(JSON.stringify(drawerItem.details || {}));
      const current = details.due?.[0] || "";
      const timePart = current.includes("T") ? current.split("T")[1] : "";
      const today = new Date(); today.setHours(0, 0, 0, 0);
      let label;
      if (action === "clear") {
        delete details.due;
        label = "Due date cleared.";
      } else {
        let base = current ? new Date(current.split("T")[0] + "T00:00:00") : new Date(today);
        if (isNaN(base)) base = new Date(today);
        base.setHours(0, 0, 0, 0);
        let next;
        if (action === "today") next = new Date(today);
        else if (action === "+1d") { next = new Date(Math.max(+base, +today)); next.setDate(next.getDate() + 1); }
        else if (action === "+1w") { next = new Date(Math.max(+base, +today)); next.setDate(next.getDate() + 7); }
        else return;
        const pad = n => String(n).padStart(2, "0");
        const dateStr = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
        details.due = [timePart ? `${dateStr}T${timePart}` : dateStr];
        label = `Due set to ${details.due[0]}.`;
      }
      try {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, details}),
        });
        registerUndo(label, async () => {
          await api(`/api/items/${line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await refreshAll();
        const updated = (currentItems || []).find(i => i.line === line && i.editable);
        if (updated) openDrawer(updated);
      } catch(e) {
        showToast("Due update failed: " + (e.message || e), "error");
      }
    }

    // ── est/elapsed progress bar ────────────────────────────────────
    function parseDurationMinutes(value) {
      const text = String(value || "").trim().toLowerCase();
      if (!text) return null;
      let total = 0;
      let matched = false;
      const re = /(\d+(?:\.\d+)?)\s*([dhm])/g;
      let m;
      while ((m = re.exec(text)) !== null) {
        matched = true;
        const n = parseFloat(m[1]);
        total += m[2] === "d" ? n * 24 * 60 : m[2] === "h" ? n * 60 : n;
      }
      if (!matched) {
        const n = parseFloat(text);
        return isNaN(n) ? null : n;
      }
      return total;
    }
    function buildEstProgressHtml(item) {
      const estRaw = item?.details?.est?.[0];
      const est = parseDurationMinutes(estRaw);
      if (!est || est <= 0) return "";
      const elapsedRaw = item?.details?.elapsed?.[0];
      const elapsed = parseDurationMinutes(elapsedRaw) || 0;
      const pct = Math.round(elapsed / est * 100);
      const width = Math.min(100, pct);
      const over = pct > 100;
      return `<div class="progress-wrap"><div class="drawer-section-title">Progress (elapsed vs est)</div>` +
        `<div class="progress-track"><div class="progress-fill${over ? " over" : ""}" style="width:${width}%"></div></div>` +
        `<div class="progress-label">${escapeHtml(elapsedRaw || "0m")} of ${escapeHtml(estRaw)} (${pct}%)${over ? " — over estimate" : ""}</div></div>`;
    }

    async function drawerNavigate(itemId) {
      if (!itemId) return;
      try {
        const data = await api(`/api/items/id/${encodeURIComponent(itemId)}`);
        if (data?.item) openDrawer(data.item);
      } catch(e) {
        showToast("Item not found: " + itemId, "error");
      }
    }

    // ── Live syntax check for quick-add bar ───────────────────────
    let _checkTimer = null;
    document.addEventListener("DOMContentLoaded", async () => {
      // Show read-only banner if server is in read-only mode
      try {
        const health = await api("/api/health");
        if (health.read_only) {
          const banner = document.getElementById("read-only-banner");
          if (banner) banner.style.display = "";
        }
      } catch(_) {}

      const qInput = document.getElementById("quick-line");
      if (qInput) {
        qInput.addEventListener("input", () => {
          clearTimeout(_checkTimer);
          _checkTimer = setTimeout(() => liveCheckLine(qInput.value), 280);
        });
      }
      const rawInput = document.getElementById("import-raw-input");
      if (rawInput) {
        rawInput.addEventListener("input", () => {
          clearTimeout(_checkTimer);
          _checkTimer = setTimeout(() => liveParseRawImport(rawInput.value), 280);
        });
      }
      // Sync agenda limit spinner from URL and wire change handler
      const spinner = document.getElementById("agenda-limit-spinner");
      if (spinner) {
        const raw = new URLSearchParams(location.search).get("agenda_limit");
        if (raw !== null) spinner.value = raw === "0" ? "0" : String(Number(raw) || 8);
        spinner.addEventListener("change", () => {
          const n = parseInt(spinner.value, 10);
          const params = new URLSearchParams(location.search);
          if (!n || n === 8) params.delete("agenda_limit");
          else params.set("agenda_limit", String(n < 0 ? 0 : n));
          const qs = params.toString();
          history.replaceState(null, "", qs ? "?" + qs : location.pathname);
          refresh();
        });
      }
    });
    async function liveCheckLine(line) {
      const qInput = document.getElementById("quick-line");
      if (!qInput) return;
      if (!line.trim()) { qInput.className = ""; document.getElementById("quick-check-msg") && (document.getElementById("quick-check-msg").textContent = ""); return; }
      try {
        const data = await api("/api/check-line", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        qInput.classList.toggle("ok", data.ok);
        qInput.classList.toggle("err", !data.ok);
        const msg = document.getElementById("quick-check-msg");
        if (msg) {
          const errs = (data.diagnostics || []).filter(d => d.severity === "error");
          msg.textContent = errs.length ? errs[0].message : (data.ok && data.item_count > 0 ? "✓" : "");
          msg.className = "check-msg " + (data.ok ? "ok" : "err");
        }
      } catch(_) {}
    }
    async function liveParseRawImport(line) {
      const preview = document.getElementById("import-raw-preview");
      if (!preview) return;
      const text = String(line || "").trim();
      if (!text) {
        preview.style.display = "none";
        preview.className = "parse-preview";
        preview.textContent = "";
        return;
      }
      try {
        const data = await api("/api/items/parse", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line: text}),
        });
        renderRawParsePreview(data);
      } catch(e) {
        preview.style.display = "";
        preview.className = "parse-preview err";
        preview.textContent = "Parse preview failed: " + (e.message || e);
      }
    }
    function renderRawParsePreview(data) {
      const preview = document.getElementById("import-raw-preview");
      if (!preview) return;
      const diagnostics = data?.diagnostics || [];
      const errors = diagnostics.filter(d => d.severity === "error");
      const warnings = diagnostics.filter(d => d.severity === "warning");
      const item = (data?.items || [])[0];
      preview.style.display = "";
      preview.className = "parse-preview " + (errors.length ? "err" : warnings.length ? "warn" : "ok");
      const diagLines = diagnostics.map(d => `${String(d.severity || "").toUpperCase()} ${d.code || ""}: ${d.message || ""}`);
      const itemLine = item ? `Parsed: ${item.status} ${item.type} ${item.title}` : `Parsed item count: ${data?.item_count || 0}`;
      preview.innerHTML = `<div>${escapeHtml(itemLine)}</div>` +
        (diagLines.length ? `<ul>${diagLines.map(line => `<li>${escapeHtml(line)}</li>`).join("")}</ul>` : `<div>No diagnostics.</div>`);
    }

    // ── Type-aware field hints in editor ────────────────────────────
    const TYPE_HINTS = {
      T: "due: est: project: tag: assignee: depends_on: parent:",
      E: "from: to: attendee: project: location: url:",
      D: "due: project: tag: assignee:",
      R: "repeat: interval: due: project:",
      H: "repeat: interval: done: project:",
      N: "body: tag: project: url:",
      S: "person: state: from: project:",
      M: "sender: recipient: notify_at: channel: body: ref:",
      J: "mood: body: project: on:",
    };
    document.addEventListener("change", function(e) {
      if (e.target.id === "edit-type") updateTypeHints(e.target.value);
    });
    function updateTypeHints(type) {
      const el = document.getElementById("type-hints");
      if (!el) return;
      const hint = TYPE_HINTS[type];
      if (hint) { el.textContent = "Suggested keys: " + hint; el.style.display = ""; }
      else el.style.display = "none";
    }

    // ── Search highlighting in item list ────────────────────────────
    function highlightText(html, query) {
      if (!query || !query.trim()) return html;
      const safe = query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        return html.replace(new RegExp("(" + safe + ")", "gi"), "<mark>$1</mark>");
      } catch(_) { return html; }
    }
    // ── Agenda overdue/due-soon highlighting ───────────────────────
    function agendaDueSoonClass(record) {
      const due = record?.details?.due?.[0] || record?.due;
      if (!due) return "";
      const d = new Date(due); if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      d.setHours(0,0,0,0);
      const diffDays = Math.floor((d - today) / 86400000);
      if (diffDays < 0) return "overdue";
      if (diffDays <= dueSoonDays()) return "due-soon";
      return "";
    }

    // ── Notification permission state display ──────────────────────
    function updateNotifPermissionDisplay() {
      const bar = document.getElementById("notif-permission-bar");
      if (!("Notification" in window)) { if (bar) { bar.textContent = "Browser notifications not supported."; bar.style.display = ""; } return; }
      const perm = Notification.permission;
      const classes = {granted: "notif-perm-granted", denied: "notif-perm-denied", default: "notif-perm-default"};
      const labels = {
        granted: "Notifications: granted",
        denied: "Notifications: blocked. Re-enable them from the browser site settings for this page.",
        default: "Notifications: not yet requested",
      };
      if (bar) {
        bar.className = "notif-permission " + (classes[perm] || "");
        if (perm === "denied") {
          bar.innerHTML = `<span>${escapeHtml(labels.denied)}</span><button class="secondary" type="button" onclick="showNotificationSettingsHelp()">How</button>`;
        } else {
          bar.textContent = labels[perm] || perm;
        }
        bar.style.display = "";
      }
    }
    function showNotificationSettingsHelp() {
      showToast("Use the browser lock/site icon, open Site settings, and allow Notifications for this URL.", "info", 8000);
    }

    // ── Git status badge + modal ─────────────────────────────────
    let gitPollTimer = null;
    function startGitPolling() {
      if (!appConfig?.git?.enable_api || appConfig?.git?.ui_poll === false) return;
      const seconds = appConfig?.git?.ui_poll_seconds || 60;
      loadGitStatus();
      gitPollTimer = setInterval(loadGitStatus, seconds * 1000);
    }
    async function loadGitStatus() {
      const badge = document.getElementById("git-status-badge");
      if (!badge) return;
      try {
        const data = await api("/api/git/status");
        badge.style.display = "";
        const out = (data.stdout || "").trim();
        if (!out) { badge.className = "git-badge git-clean"; badge.textContent = "git: clean"; }
        else { badge.className = "git-badge git-modified"; badge.textContent = "git: modified"; }
      } catch(e) {
        badge.style.display = "";
        badge.className = "git-badge git-error";
        badge.textContent = "git: error";
      }
    }
    async function openGitModal() {
      document.getElementById("git-output").style.display = "none";
      document.getElementById("git-output").textContent = "";
      openManagedModal(document.getElementById("git-modal"), "#git-commit-msg");
      const statusEl = document.getElementById("git-status-output");
      if (statusEl) {
        statusEl.textContent = "Loading…";
        try {
          const data = await api("/api/git/status");
          statusEl.textContent = (data.stdout || "(clean)").trim() || "(clean)";
        } catch(e) { statusEl.textContent = "Could not load status: " + e.message; }
      }
    }
    function closeGitModal() { closeManagedModal(document.getElementById("git-modal")); }
    async function gitCommit() {
      const msg = document.getElementById("git-commit-msg").value.trim();
      if (!msg) { showToast("Enter a commit message.", "error"); return; }
      try {
        const data = await api("/api/git/commit", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message: msg}),
        });
        const out = document.getElementById("git-output");
        out.textContent = (data.stdout || "") + (data.stderr || "");
        out.style.display = out.textContent ? "" : "none";
        if (data.ok) { showToast("Committed.", "success"); await loadGitLog(); }
        else showToast("Commit failed — see output.", "error");
        loadGitStatus();
      } catch(e) { showToast(e.message, "error"); }
    }
    async function gitPush() {
      try {
        const data = await api("/api/git/push", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
        const out = document.getElementById("git-output");
        out.textContent = (data.stdout || "") + (data.stderr || "");
        out.style.display = out.textContent ? "" : "none";
        if (data.ok) showToast("Pushed.", "success");
        else showToast("Push failed — see output.", "error");
        loadGitStatus();
      } catch(e) { showToast(e.message, "error"); }
    }

    // ── Statistics / Chart.js panel ────────────────────────────────
    let chartJsLoaded = false;
    let mainChart = null;
    let statsLoaded = false;

    // ── Kiosk mode (bulletin board / 掲示板モード) ────────────────
    let _kioskClockTimer = null;
    let _kioskScrollTimer = null;
    let _kioskAutoScroll = null;

    function _kioskApply() {
      const active = isKioskMode();
      const clock = document.getElementById("kiosk-clock");
      const exitBtn = document.getElementById("kiosk-exit-btn");
      const list = document.getElementById("items");
      const h1 = document.querySelector("header h1");
      if (!clock || !exitBtn) return;
      clock.style.display = active ? "flex" : "none";
      exitBtn.style.display = active ? "inline-flex" : "none";
      if (active) {
        if (h1 && _kioskDefaultTitle === null) _kioskDefaultTitle = h1.textContent;
        const title = firstParam(query(), ["kiosk_title"], "");
        if (h1 && title) h1.textContent = title;
        const cols = parseInt(firstParam(query(), ["kiosk_cols"], ""), 10);
        if (list && Number.isFinite(cols) && cols > 0) {
          list.style.gridTemplateColumns = `repeat(${Math.min(cols, 8)}, minmax(0, 1fr))`;
        } else if (list) {
          list.style.gridTemplateColumns = "";
        }
        _kioskStartClock();
        _kioskStartScroll();
        _kioskAddProgressBar();
      } else {
        if (h1 && _kioskDefaultTitle !== null) h1.textContent = _kioskDefaultTitle;
        if (list) list.style.gridTemplateColumns = "";
        _kioskStopClock();
        _kioskStopScroll();
        _kioskRemoveProgressBar();
      }
    }

    function _kioskStartClock() {
      if (_kioskClockTimer) clearInterval(_kioskClockTimer);
      const update = () => {
        const now = new Date();
        const date = now.toLocaleDateString(undefined, { weekday:"short", month:"short", day:"numeric" });
        const time = now.toLocaleTimeString(undefined, { hour:"2-digit", minute:"2-digit" });
        const el = document.getElementById("kiosk-clock");
        if (el) el.textContent = date + "  " + time;
      };
      update();
      _kioskClockTimer = setInterval(update, 1000);
    }

    function _kioskStopClock() {
      if (_kioskClockTimer) { clearInterval(_kioskClockTimer); _kioskClockTimer = null; }
      const el = document.getElementById("kiosk-clock");
      if (el) el.textContent = "";
    }

    function _kioskStartScroll() {
      _kioskStopScroll();
      const list = document.getElementById("items");
      if (!list) return;
      const intervalValue = document.documentElement.style.getPropertyValue("--kiosk-interval") || "60";
      const intervalMs = (parseFloat(intervalValue) || 60) * 1000;
      const scrollStep = () => {
        if (!isKioskMode()) { _kioskStopScroll(); return; }
        const { scrollTop, scrollHeight, clientHeight } = list;
        if (scrollTop + clientHeight >= scrollHeight - 2) {
          list.scrollTo({ top: 0, behavior: "smooth" });
        } else {
          list.scrollBy({ top: Math.ceil(clientHeight * 0.8), behavior: "smooth" });
        }
      };
      _kioskScrollTimer = setInterval(scrollStep, intervalMs);
    }

    function _kioskStopScroll() {
      if (_kioskScrollTimer) { clearInterval(_kioskScrollTimer); _kioskScrollTimer = null; }
    }

    function _kioskAddProgressBar() {
      if (document.querySelector(".kiosk-progress-bar")) return;
      const bar = document.createElement("div");
      bar.className = "kiosk-progress-bar";
      document.body.appendChild(bar);
      const secs = firstParam(query(), ["refresh"], "60");
      document.documentElement.style.setProperty("--kiosk-interval", secs + "s");
    }

    function _kioskRemoveProgressBar() {
      const bar = document.querySelector(".kiosk-progress-bar");
      if (bar) bar.remove();
    }

    function toggleKioskMode() {
      const params = query();
      const active = isKioskMode();
      if (active) {
        params.delete("mode");
        params.delete("view");
      } else {
        params.set("mode", "kiosk");
      }
      history.pushState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      applyUrlToControls();
      refreshAll();
    }

    function toggleStats() {
      switchWorkspace("stats");
    }

    async function loadStatsBreakdown() {
      const el = document.getElementById("stats-breakdown");
      if (!el) return;
      try {
        const fromVal = (document.getElementById("breakdown-from") || {}).value || "";
        const toVal = (document.getElementById("breakdown-to") || {}).value || "";
        const qs = (fromVal ? `from=${encodeURIComponent(fromVal)}&` : "") + (toVal ? `to=${encodeURIComponent(toVal)}` : "");
        const data = await api("/api/stats/summary" + (qs ? "?" + qs : ""));
        const STATUS_EMOJI = {"[ ]": "○", "[/]": "◑", "[x]": "✓", "[-]": "✕", "[>]": "→"};
        const typeRows = Object.entries(data.by_type || {})
          .sort((a,b) => b[1]-a[1])
          .map(([k,v]) => `<div style="display:flex;justify-content:space-between"><span>${escapeHtml(ITEM_TYPE_NAMES[k]||k)}</span><span style="color:var(--muted)">${v}</span></div>`)
          .join("");
        const statusRows = Object.entries(data.by_status || {})
          .sort((a,b) => b[1]-a[1])
          .map(([k,v]) => `<div style="display:flex;justify-content:space-between"><span>${escapeHtml(STATUS_EMOJI[k]||"")} ${escapeHtml(STATUS_LABEL[k]||k)}</span><span style="color:var(--muted)">${v}</span></div>`)
          .join("");
        el.innerHTML = `
          <div>
            <div class="drawer-section-title" style="font-size:.72rem;margin-bottom:.3rem">By Type</div>
            <div style="font-size:.82rem;display:grid;gap:.2rem">${typeRows || "<em>none</em>"}</div>
          </div>
          <div>
            <div class="drawer-section-title" style="font-size:.72rem;margin-bottom:.3rem">By Status</div>
            <div style="font-size:.82rem;display:grid;gap:.2rem">${statusRows || "<em>none</em>"}</div>
          </div>`;
        el.style.display = "grid";
      } catch(e) {
        if (el) el.style.display = "none";
      }
    }

    function toggleNotifPanel() {
      switchWorkspace("notifications");
      updateNotifBtnLabel();
      if (("Notification" in window) && Notification.permission === "default") {
        enableBrowserNotifications();
      }
    }

    function updateNotifBtnLabel() {
      const btn = document.getElementById("notif-btn");
      if (!btn) return;
      const perm = ("Notification" in window) ? Notification.permission : "unsupported";
      const indicator = perm === "granted" ? " ●" : perm === "denied" ? " ✕" : " ○";
      btn.textContent = "Notifications" + indicator;
    }

    async function triggerRefresh() {
      const btn = document.getElementById("refresh-btn");
      if (btn) { btn.classList.add("btn-active"); btn.textContent = "…"; btn.disabled = true; }
      try { await refreshAll(); } finally {
        if (btn) { btn.classList.remove("btn-active"); btn.textContent = "Refresh"; btn.disabled = false; }
      }
    }

    async function loadChart(type) {
      const container = document.getElementById("chart-container");
      if (type === "habits-heatmap") {
        renderHeatmap(container);
        return;
      }
      await ensureChartJs();
      container.innerHTML = `<div class="chart-panel"><canvas id="main-chart"></canvas></div>`;
      const canvas = document.getElementById("main-chart");
      if (mainChart) { mainChart.destroy(); mainChart = null; }
      try {
        const groupParam = GROUP_SUPPORTED.has(type) ? `?group=${encodeURIComponent(currentChartGroup)}` : "";
        const data = await api("/api/chart/" + encodeURIComponent(type) + groupParam);
        const ctx = canvas.getContext("2d");
        const isBar = ["tasks", "habits", "elapsed"].includes(type);
        mainChart = new Chart(ctx, {
          type: isBar ? "bar" : "line",
          data: {
            labels: data.labels || [],
            datasets: (data.datasets || []).map((ds, i) => ({
              label: ds.label,
              data: ds.data,
              backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "88",
              borderColor: CHART_COLORS[i % CHART_COLORS.length],
              borderWidth: 1.5,
              fill: !isBar,
              spanGaps: true,
              pointRadius: 2,
            })),
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {position: "top"}},
            scales: {
              y: {
                beginAtZero: true,
                title: {
                  display: GROUP_SUPPORTED.has(type) && currentChartGroup !== "daily",
                  text: currentChartGroup === "weekly" ? "completions / week"
                      : currentChartGroup === "monthly" ? "completions / month" : "",
                },
              },
            },
          },
        });
      } catch(err) {
        container.innerHTML = `<div class="diagnostic">Chart error: ${escapeHtml(err.message)}</div>`;
      }
    }

    async function renderHeatmap(container) {
      container.innerHTML = `<div class="empty">Loading heatmap…</div>`;
      try {
        const data = await api("/api/chart/habits-heatmap");
        const today = new Date().toISOString().slice(0, 10);
        const rangeStart = new Date(data.range?.from || new Date().getFullYear() + "-01-01");
        if (!data.habits?.length) { container.innerHTML = `<div class="empty">No habit data.</div>`; return; }

        // Build month labels array (one per week column)
        const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        function buildMonthLabels(start, end) {
          const labels = [];
          let col = 0;
          const d = new Date(start);
          const startPad = d.getDay();
          for (let pad = 0; pad < startPad; pad++) { labels.push(""); col++; }
          let lastMonth = -1;
          while (d <= end) {
            const mo = d.getMonth();
            if (d.getDay() === 0) {
              labels.push(mo !== lastMonth ? MONTHS[mo] : "");
              lastMonth = mo;
            }
            d.setDate(d.getDate() + 1);
          }
          return labels;
        }

        const endDate = new Date();
        const monthLabels = buildMonthLabels(new Date(rangeStart), endDate);

        let html = `<div class="heatmap-section" style="padding:.5rem 1rem">`;
        for (const habit of data.habits) {
          html += `<div class="heatmap-habit">
            <div class="heatmap-title">${escapeHtml(habit.title)}<span class="heatmap-streak">🔥 ${habit.streak} day streak</span></div>
            <div class="heatmap-months">${monthLabels.map(m => `<div class="heatmap-month-cell">${escapeHtml(m)}</div>`).join("")}</div>
            <div class="heatmap-grid">`;
          const start = new Date(rangeStart);
          const startDay = start.getDay();
          for (let pad = 0; pad < startDay; pad++) html += `<div class="heatmap-cell" style="visibility:hidden"></div>`;
          const d = new Date(start);
          while (d <= endDate) {
            const ds = d.toISOString().slice(0, 10);
            const isDone = !!(habit.dates && habit.dates[ds]);
            const isToday = ds === today;
            html += `<div class="heatmap-cell${isDone ? " done" : ""}${isToday ? " today" : ""}" data-date="${ds}"></div>`;
            d.setDate(d.getDate() + 1);
          }
          html += `</div></div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(e) {
        container.innerHTML = `<div class="diagnostic">Heatmap error: ${escapeHtml(e.message)}</div>`;
      }
    }

    function showChart(type, btn) {
      document.querySelectorAll(".chart-tab").forEach(t => t.classList.remove("active"));
      if (btn) btn.classList.add("active");
      currentChartType = type;
      const groupBar = document.getElementById("chart-group-bar");
      if (groupBar) groupBar.style.display = GROUP_SUPPORTED.has(type) ? "" : "none";
      loadChart(type);
    }

    async function refreshCharts() {
      const active = document.querySelector(".chart-tab.active");
      const type = active ? active.textContent.trim().toLowerCase() : "tasks";
      await loadChart(type);
    }

    function exportChartCsv() {
      if (!mainChart) { showToast("No chart data to export.", "error"); return; }
      const labels = mainChart.data.labels || [];
      const datasets = mainChart.data.datasets || [];
      const header = ["label", ...labels].join(",");
      const rows = datasets.map(ds => {
        const vals = (ds.data || []).map(v => v == null ? "" : String(v));
        return [JSON.stringify(ds.label || ""), ...vals].join(",");
      });
      const csv = [header, ...rows].join("\n");
      const blob = new Blob([csv], {type: "text/csv"});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `lifetxt-chart-${currentChartType}-${currentChartGroup}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    }

    const CHART_COLORS = ["#256b5f","#e07b54","#4a7db5","#8e6bbf","#b5a14a","#5aa876","#c0524a"];

    function ensureChartJs() {
      if (chartJsLoaded) return Promise.resolve();
      return new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js";
        s.onload = () => { chartJsLoaded = true; resolve(); };
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }

    // ── Status quick-filter buttons (multi-select) ────────────────
    function syncStatusFilterBtns(activeValues) {
      const params = query();
      const isBlocked = params.get("blocked") === "true";
      const rawStatus = params.get("status") || "";
      const selected = new Set(rawStatus ? rawStatus.split(",").map(s => s.trim()).filter(Boolean) : []);
      // Count items per status from current loaded items
      const counts = {};
      for (const item of (currentItems || [])) {
        counts[item.status] = (counts[item.status] || 0) + 1;
      }
      const total = (currentItems || []).length;
      document.querySelectorAll("#status-filter-bar .filter-btn").forEach(btn => {
        const sv = btn.dataset.status;
        const label = btn.dataset.label || btn.textContent.replace(/\s*\(\d+\)$/, "").trim();
        btn.dataset.label = label;
        if (sv === "") {
          btn.classList.toggle("active", !isBlocked && selected.size === 0);
          btn.textContent = total ? `${label} (${total})` : label;
        } else if (sv === "__blocked__") {
          btn.classList.toggle("active", isBlocked);
        } else {
          btn.classList.toggle("active", selected.has(sv));
          const n = counts[sv] || 0;
          btn.textContent = n ? `${label} (${n})` : label;
        }
      });
    }

    // ── Search result count ────────────────────────────────────────
    function updateSearchCount(count) {
      const el = document.getElementById("search-count");
      if (!el) return;
      el.textContent = count != null ? `(${count})` : "";
    }

    // ── View presets (config-defined, applied via ?preset= URL) ────
    function configViewPresets() {
      return appConfig?.views && typeof appConfig.views === "object" ? appConfig.views : {};
    }
    function getViewPreset(name) {
      return configViewPresets()[name];
    }

    // ── Clickable ID refs in item rows ────────────────────────────
    const ROW_REF_KEYS = new Set(["depends_on", "parent", "blocks", "related", "ref"]);
    function detailTextWithRefs(details) {
      const parts = [];
      for (const [key, values] of Object.entries(details || {})) {
        const vals = (values || []).map(v => {
          if (ROW_REF_KEYS.has(key)) return String(v);
          return String(v);
        });
        if (vals.length) parts.push(key + ":" + vals.join(","));
      }
      return parts.join("  ");
    }
    // ── Parent indicator in item rows ─────────────────────────────
    function buildParentIndicator(details) {
      const parents = details?.parent;
      if (!parents?.length) return "";
      return `<span class="parent-indicator" title="parent: ${escapeHtml(parents[0])}">↳ ${escapeHtml(parents[0])}</span>`;
    }

    // ── Drawer keyboard navigation ([ / ]) ────────────────────────
    function drawerPrev() {
      if (!drawerItem || !currentItems.length) return;
      const idx = currentItems.findIndex(i => i.line === drawerItem.line);
      if (idx > 0) openDrawer(currentItems[idx - 1]);
    }
    function drawerNext() {
      if (!drawerItem || !currentItems.length) return;
      const idx = currentItems.findIndex(i => i.line === drawerItem.line);
      if (idx >= 0 && idx < currentItems.length - 1) openDrawer(currentItems[idx + 1]);
    }

    // ── Relative time display ─────────────────────────────────────
    function relativeTime(isoString) {
      if (!isoString) return "";
      const d = new Date(isoString);
      if (isNaN(d)) return "";
      const diff = Date.now() - d.getTime();
      const absDiff = Math.abs(diff);
      const future = diff < 0;
      const mins = Math.floor(absDiff / 60000);
      const hours = Math.floor(absDiff / 3600000);
      const days = Math.floor(absDiff / 86400000);
      let label;
      if (mins < 1) label = "just now";
      else if (mins < 60) label = `${mins} min${mins > 1 ? "s" : ""} ${future ? "from now" : "ago"}`;
      else if (hours < 24) label = `${hours} hr${hours > 1 ? "s" : ""} ${future ? "from now" : "ago"}`;
      else label = `${days} day${days > 1 ? "s" : ""} ${future ? "from now" : "ago"}`;
      return label;
    }

    // ── Notification row state display ────────────────────────────
    function notifStateBadge(record) {
      const ack = record?.details?.ack?.[0];
      const snooze = record?.details?.snooze_until?.[0];
      if (ack) return `<span class="notif-state notif-state-ack" title="Acked at ${escapeHtml(ack)}">✓ Acked</span>`;
      if (snooze) return `<span class="notif-state notif-state-snoozed" title="Snoozed until ${escapeHtml(snooze)}">⏱ Snoozed</span>`;
      return `<span class="notif-state notif-state-pending">● Pending</span>`;
    }

    async function gitPull() {
      try {
        const data = await api("/api/git/pull", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
        const out = document.getElementById("git-output");
        out.textContent = (data.stdout || "") + (data.stderr || "");
        out.style.display = out.textContent ? "" : "none";
        if (data.ok) showToast("Pulled.", "success");
        else showToast("Pull failed — see output.", "error");
        const statusEl = document.getElementById("git-status-output");
        if (statusEl) {
          const s = await api("/api/git/status");
          statusEl.textContent = (s.stdout || "(clean)").trim() || "(clean)";
        }
        loadGitStatus();
      } catch(e) { showToast(e.message, "error"); }
    }

    // ── Heatmap: month labels + JS tooltip ───────────────────────
    (function setupHeatmapTooltip() {
      document.addEventListener("mouseover", function(e) {
        const cell = e.target.closest(".heatmap-cell");
        if (!cell || !cell.dataset.date) return;
        const tip = document.getElementById("hm-tooltip");
        if (!tip) return;
        tip.textContent = cell.dataset.date + (cell.classList.contains("done") ? " ✓" : "");
        tip.style.display = "";
        tip.style.left = (e.clientX + 12) + "px";
        tip.style.top = (e.clientY - 28) + "px";
      });
      document.addEventListener("mousemove", function(e) {
        const tip = document.getElementById("hm-tooltip");
        if (tip && tip.style.display !== "none") {
          tip.style.left = (e.clientX + 12) + "px";
          tip.style.top = (e.clientY - 28) + "px";
        }
      });
      document.addEventListener("mouseout", function(e) {
        if (!e.target.closest(".heatmap-cell")) return;
        const tip = document.getElementById("hm-tooltip");
        if (tip) tip.style.display = "none";
      });
    })();

    // ── Chart group selector (daily/weekly/monthly) ───────────────
    let currentChartType = "tasks";
    let currentChartGroup = "daily";
    const GROUP_SUPPORTED = new Set(["tasks", "habits", "mood"]);

    function setChartGroup(group, btn) {
      currentChartGroup = group;
      document.querySelectorAll(".chart-group-btn").forEach(b => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      loadChart(currentChartType);
    }

    // ── Status filter bar URL sync + `<`/`>` keyboard cycle ──────
    const STATUS_CYCLE = ["", "[ ]", "[/]", "[x]", "[-]", "__blocked__"];
    function syncStatusFilterBarsFromUrl() {
      syncStatusFilterBtns();
    }
    function cycleStatusFilter(direction) {
      const params = query();
      const rawStatus = params.get("status") || "";
      const isBlocked = params.get("blocked") === "true";
      // For cycling, treat multi-select as the first active value (or "All")
      const selected = rawStatus.split(",").map(s => s.trim()).filter(Boolean);
      const current = isBlocked ? "__blocked__" : (selected.length === 1 ? selected[0] : "");
      const idx = STATUS_CYCLE.indexOf(current);
      const next = STATUS_CYCLE[(idx + direction + STATUS_CYCLE.length) % STATUS_CYCLE.length];
      if (next === "__blocked__") {
        // Force blocked on (not toggle) for keyboard cycling
        const params = query();
        params.delete("status");
        params.set("blocked", "true");
        params.set("open_only", "true");
        document.getElementById("open-only").checked = true;
        history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
        loadItems();
        syncStatusFilterBtns();
      } else {
        setStatusFilter(next);
      }
    }

    // ── Clear every list filter (search, kind, status, blocked) ──
    function clearAllFilters() {
      document.getElementById("search").value = "";
      document.getElementById("kind").value = "";
      document.getElementById("open-only").checked = false;
      document.getElementById("limit").value = "";
      const groupSel = document.getElementById("group-by");
      if (groupSel) groupSel.value = "";
      const params = query();
      for (const key of [
        "text", "q", "kind", "type", "status", "blocked", "open", "open_only",
        "project", "tag", "tag_all", "exclude_tag", "user", "team", "person",
        "owner", "assignee", "attendee", "sender", "recipient", "after", "before",
        "limit", "group_by",
      ]) params.delete(key);
      history.replaceState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      loadItems();
      syncStatusFilterBtns();
    }

    // ── setStatusFilter: "All" button — clears everything ────────
    function setStatusFilter(statusValue) {
      const params = query();
      params.delete("blocked");
      params.delete("status");
      params.delete("open_only");
      document.getElementById("open-only").checked = false;
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
      syncStatusFilterBtns();
    }

    // ── toggleStatusFilter: multi-select individual statuses ──────
    function toggleStatusFilter(statusValue) {
      const params = query();
      params.delete("blocked");
      params.delete("open_only");
      document.getElementById("open-only").checked = false;
      const rawStatus = params.get("status") || "";
      const selected = new Set(rawStatus ? rawStatus.split(",").map(s => s.trim()).filter(Boolean) : []);
      if (selected.has(statusValue)) {
        selected.delete(statusValue);
      } else {
        selected.add(statusValue);
      }
      if (selected.size === 0) {
        params.delete("status");
      } else {
        params.set("status", [...selected].join(","));
      }
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
      syncStatusFilterBtns();
    }

    // ── toggleBlockedFilter: toggle blocked filter ────────────────
    function toggleBlockedFilter() {
      const params = query();
      const isBlocked = params.get("blocked") === "true";
      if (isBlocked) {
        // Turn off blocked filter → go to All
        params.delete("blocked");
        params.delete("status");
        params.delete("open_only");
        document.getElementById("open-only").checked = false;
      } else {
        params.delete("status");
        params.set("blocked", "true");
        params.set("open_only", "true");
        document.getElementById("open-only").checked = true;
      }
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadItems();
      syncStatusFilterBtns();
    }

    // ── Git log display ───────────────────────────────────────────
    let _gitLogOffset = 0;
    const GIT_LOG_PAGE = 10;
    async function loadGitLog(reset) {
      if (!appConfig?.git?.enable_api) return;
      if (reset !== false) _gitLogOffset = 0;
      try {
        const n = _gitLogOffset + GIT_LOG_PAGE;
        const data = await api(`/api/git/log?n=${n}&count=true`);
        const commits = data.commits || [];
        if (!commits.length) return;
        const shown = commits.slice(0, n);
        const hasMore = commits.length >= n;
        const totalLabel = data.total != null ? ` / ${data.total} total` : "";
        const titleEl = document.getElementById("git-modal-title");
        if (titleEl) titleEl.textContent = `Git${data.total != null ? ` (${data.total} commits)` : ""}`;
        const container = document.getElementById("git-log-container");
        const target = container || document.getElementById("git-output");
        if (!target) return;
        let html = `<div id="git-log-container" style="margin-top:.5rem">
          <div class="drawer-section-title" style="font-size:.72rem">Recent commits (${shown.length}${totalLabel})</div>`;
        for (const c of shown) {
          html += `<div class="git-log-entry"><span class="git-log-hash">${escapeHtml(c.hash)}</span><span class="git-log-msg">${escapeHtml(c.message)}</span></div>`;
        }
        if (hasMore) {
          html += `<div style="margin-top:.3rem"><a href="#" class="drawer-link" onclick="event.preventDefault();_gitLogOffset+=10;loadGitLog(false)">Show more…</a></div>`;
        }
        html += `</div>`;
        if (container) container.outerHTML = html;
        else target.insertAdjacentHTML("afterend", html);
      } catch(_) {}
    }


    // ── Ref-link count badge (multiple refs → dep_on(2)) ─────────
    function buildRefLinksHtml(details) {
      const counts = {};
      const firstIds = {};
      for (const [key, values] of Object.entries(details || {})) {
        if (!ROW_REF_KEYS.has(key)) continue;
        const valid = (values || []).filter(v => String(v).trim());
        if (!valid.length) continue;
        counts[key] = valid.length;
        firstIds[key] = String(valid[0]);
      }
      return Object.entries(counts).map(([key, count]) => {
        const label = count > 1 ? `${key.slice(0,3)}(${count})` : `${key.slice(0,3)}:${firstIds[key]}`;
        const nav = count === 1 ? escapeHtml(jsLiteral(firstIds[key])) : escapeHtml(jsLiteral(""));
        const onclick = count === 1
          ? `event.stopPropagation();drawerNavigate(${nav})`
          : `event.stopPropagation();(function(){const it=currentItems.find(i=>i.line===${Number(details?._line||0)});if(it)openDrawer(it);setTimeout(scrollDrawerDepsIntoView,200);})()`;
        return `<span class="ref-link" onclick="${onclick}" title="${escapeHtml(key)}: ${count} item(s)">${escapeHtml(label)}</span>`;
      }).join("");
    }
    function scrollDrawerDepsIntoView() {
      const deps = document.getElementById("drawer-deps");
      const body = document.getElementById("drawer-body");
      if (!deps || !body) return;
      try {
        body.scrollTop = Math.max(0, deps.offsetTop - body.offsetTop - 12);
      } catch(_) {
        deps.scrollIntoView({behavior: "smooth", block: "start"});
      }
    }

    // ── Notification: inline snooze with custom duration ─────────
    function snoozeInline(id) {
      const row = document.querySelector(`.notif-snooze-${CSS.escape(id)}`);
      if (!row) return;
      row.style.display = row.style.display === "none" ? "" : "none";
    }
    async function snoozeMessageCustom(id, inputId) {
      const input = document.getElementById(inputId);
      const duration = input ? input.value.trim() : "10m";
      if (!duration) { showToast("Enter a duration (e.g. 30m, 1h)", "error"); return; }
      await snoozeMessage(id, duration);
    }

    // ── Editor: Import raw line ───────────────────────────────────
    function toggleImportRaw(show) {
      const row = document.getElementById("import-raw-row");
      if (!row) return;
      const visible = show !== undefined ? show : row.style.display === "none";
      row.style.display = visible ? "" : "none";
      if (visible) document.getElementById("import-raw-input").focus();
    }
    async function importRawLine() {
      const input = document.getElementById("import-raw-input");
      const line = input ? input.value.trim() : "";
      if (!line) return;
      try {
        const parseData = await api("/api/items/parse", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        renderRawParsePreview(parseData);
        if (!parseData.ok) {
          const errs = (parseData.diagnostics || []).filter(d => d.severity === "error");
          showToast("Invalid: " + (errs[0]?.message || "parse error"), "error");
          return;
        }
        const item = (parseData.items || [])[0];
        if (!item) { showToast("No item parsed from line.", "error"); return; }
        document.getElementById("edit-status").value = item.status;
        document.getElementById("edit-type").value = item.type;
        document.getElementById("edit-title").value = item.title;
        document.getElementById("edit-details").value = detailsToText(item.details || {});
        selectedItem = null;
        document.getElementById("editor-heading").textContent = "New Record";
        document.getElementById("save-button").textContent = "Create";
        document.getElementById("delete-button").disabled = true;
        updateTypeHints(item.type);
        toggleImportRaw(false);
        if (input) input.value = "";
        const preview = document.getElementById("import-raw-preview");
        if (preview) { preview.style.display = "none"; preview.textContent = ""; preview.className = "parse-preview"; }
        showToast("Form populated from raw line.", "success");
      } catch(e) {
        showToast("Import error: " + e.message, "error");
      }
    }

    // ── Dark mode ─────────────────────────────────────────────────
    (function initDarkMode() {
      const stored = localStorage.getItem("lifetxt_dark");
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const urlTheme = new URLSearchParams(location.search).get("theme");
      const dark = urlTheme
        ? urlTheme === "dark"
        : (stored !== null ? stored === "1" : prefersDark);
      if (dark) document.documentElement.setAttribute("data-theme", "dark");
      const btn = document.getElementById("dark-btn");
      if (btn) btn.textContent = dark ? "☀️" : "🌙";
      // Auto-follow OS theme when user has not explicitly set a preference
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function(ev) {
        if (localStorage.getItem("lifetxt_dark") !== null) return;
        const wantsDark = ev.matches;
        if (wantsDark) document.documentElement.setAttribute("data-theme", "dark");
        else document.documentElement.removeAttribute("data-theme");
        const b = document.getElementById("dark-btn");
        if (b) b.textContent = wantsDark ? "☀️" : "🌙";
      });
    })();
    function toggleDarkMode() {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      if (isDark) {
        document.documentElement.removeAttribute("data-theme");
        localStorage.setItem("lifetxt_dark", "0");
      } else {
        document.documentElement.setAttribute("data-theme", "dark");
        localStorage.setItem("lifetxt_dark", "1");
      }
      const btn = document.getElementById("dark-btn");
      if (btn) btn.textContent = !isDark ? "☀️" : "🌙";
    }

    // ── Density toggle (comfortable / compact) ────────────────────
    function _applyDensity(compact) {
      document.body.classList.toggle("density-compact", compact);
      const btn = document.getElementById("density-btn");
      if (btn) btn.classList.toggle("btn-active", compact);
    }
    function toggleDensity() {
      const compact = !document.body.classList.contains("density-compact");
      try { localStorage.setItem("lifetxt_density", compact ? "compact" : "comfortable"); } catch(_) {}
      _applyDensity(compact);
      showToast(compact ? "Compact density." : "Comfortable density.", "info", 1800);
    }
    document.addEventListener("DOMContentLoaded", () => {
      let stored = "";
      try { stored = localStorage.getItem("lifetxt_density") || ""; } catch(_) {}
      if (stored === "compact") _applyDensity(true);
    });

    // ── Back-to-top button ────────────────────────────────────────
    window.addEventListener("scroll", () => {
      const btn = document.getElementById("back-to-top");
      if (btn) btn.classList.toggle("visible", window.scrollY > 400);
    }, {passive: true});

    // ── Clear view preset ─────────────────────────────────────────

    // ── Drawer: copy ID to clipboard ──────────────────────────────
    function drawerCopyId() {
      if (!drawerItem) return;
      const idKey = (appConfig?.ids?.key) || "id";
      const idVal = drawerItem?.details?.[idKey]?.[0] || drawerItem?.id || "";
      if (!idVal) { showToast("No ID on this item.", "error"); return; }
      navigator.clipboard.writeText(String(idVal)).then(
        () => showToast("Copied: " + idVal, "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Drawer: copy as Markdown ───────────────────────────────────
    function drawerCopyMarkdown() {
      if (!drawerItem) return;
      const item = drawerItem;
      const tick = item.status === "[x]" ? "x" : item.status === "[-]" ? "-" : " ";
      const due = item?.details?.due?.[0] ? ` — due: ${item.details.due[0]}` : "";
      const proj = item?.details?.project?.[0] ? ` — project: ${item.details.project[0]}` : "";
      const tags = (item?.details?.tag || []).map(t => `#${t}`).join(" ");
      const md = `- [${tick}] ${item.title}${due}${proj}${tags ? " " + tags : ""}`;
      navigator.clipboard.writeText(md).then(
        () => showToast("Copied as Markdown.", "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Drawer: share deep-link ────────────────────────────────────
    function drawerShareLink() {
      if (!drawerItem) return;
      const url = location.origin + location.pathname + "?line=" + encodeURIComponent(drawerItem.line);
      navigator.clipboard.writeText(url).then(
        () => showToast("Link copied: ?line=" + drawerItem.line, "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Context menu: copy line number + share link ───────────────
    function ctxCopyLineNumber() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      navigator.clipboard.writeText(String(t.line)).then(
        () => showToast("Line " + t.line + " copied.", "success"),
        () => showToast("Copy failed.", "error")
      );
    }
    function ctxShareLink() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      const url = location.origin + location.pathname + "?line=" + encodeURIComponent(t.line);
      navigator.clipboard.writeText(url).then(
        () => showToast("Link copied: ?line=" + t.line, "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Agenda: blocked-item filter (all / only / hide) ───────────
    function agendaBlockedMode() {
      return firstParam(query(), ["agenda_blocked"], "");
    }
    function _syncAgendaBlockedBtn(mode) {
      const btn = document.getElementById("agenda-blocked-btn");
      if (!btn) return;
      btn.textContent = mode === "only" ? "⚡ Only" : mode === "hide" ? "⚡ Hidden" : "⚡ All";
      btn.classList.toggle("active", !!mode);
    }
    function toggleAgendaBlocked() {
      const modes = ["", "only", "hide"];
      const next = modes[(modes.indexOf(agendaBlockedMode()) + 1) % modes.length];
      const params = query();
      if (next) params.set("agenda_blocked", next);
      else params.delete("agenda_blocked");
      history.replaceState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      loadAgenda();
    }

    // ── Agenda: "view all" — set agenda_limit to 0 ───────────────
    function setAgendaLimit(n) {
      const params = query();
      if (n === 0) params.delete("agenda_limit");
      else params.set("agenda_limit", String(n));
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadAgenda();
    }

    // ── Context menu ──────────────────────────────────────────────
    let ctxTarget = null;
    function openCtxMenu(e, item) {
      e.preventDefault();
      ctxTarget = item;
      const menu = document.getElementById("ctx-menu");
      if (!menu) return;
      menu.style.display = "";
      menu.style.left = Math.min(e.clientX, window.innerWidth - 170) + "px";
      menu.style.top = Math.min(e.clientY, window.innerHeight - 160) + "px";
      const doneEl = document.getElementById("ctx-done");
      if (doneEl) doneEl.style.display = (item?.editable && !["[x]","[-]"].includes(item?.status)) ? "" : "none";
    }
    function closeCtxMenu() {
      const menu = document.getElementById("ctx-menu");
      if (menu) menu.style.display = "none";
      ctxTarget = null;
    }
    document.addEventListener("click", function(e) {
      const menu = document.getElementById("ctx-menu");
      if (menu && !menu.contains(e.target)) closeCtxMenu();
    });
    document.addEventListener("contextmenu", function(e) {
      // Close menu if right-clicking outside of an item row
      if (!e.target.closest(".item")) closeCtxMenu();
    });
    document.addEventListener("keydown", function(e) { if (e.key === "Escape") closeCtxMenu(); }, true);
    async function ctxMarkDone() {
      const t = ctxTarget; closeCtxMenu();
      if (!t || !t.editable) return;
      const prevPayload = {status: t.status, type: t.type, title: t.title, details: t.details || {}};
      try {
        await api(`/api/items/${t.line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, status: "[x]"}),
        });
        registerUndo("Marked done.", async () => {
          await api(`/api/items/${t.line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await refreshAll();
      } catch(e) {
        showToast("Failed: " + e.message, "error");
      }
    }
    function ctxCopyTitle() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      navigator.clipboard.writeText(t.title || "").then(
        () => showToast("Copied: " + (t.title || ""), "success"),
        () => showToast("Copy failed.", "error")
      );
    }
    function ctxCopyId() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      const idKey = appConfig?.ids?.key || "id";
      const idVal = t?.details?.[idKey]?.[0] || t?.id || "";
      if (!idVal) { showToast("No ID on this item.", "error"); return; }
      navigator.clipboard.writeText(String(idVal)).then(
        () => showToast("Copied: " + idVal, "success"),
        () => showToast("Copy failed.", "error")
      );
    }
    function ctxOpenDrawer() {
      const t = ctxTarget; closeCtxMenu();
      if (t) openDrawer(t);
    }
    function ctxEdit() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      selectItem(t);
      openEditorModal();
    }
    function ctxDuplicate() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      openEditorModal();
      document.getElementById("edit-status").value = "[ ]";
      document.getElementById("edit-type").value = t.type || "T";
      document.getElementById("edit-title").value = t.title || "";
      document.getElementById("edit-details").value = detailsToText(t.details || {});
      selectedItem = null;
      document.getElementById("editor-heading").textContent = "New Record (duplicate)";
      document.getElementById("save-button").textContent = "Create";
      document.getElementById("delete-button").disabled = true;
      updateTypeHints(t.type || "T");
      setEditorDisabled(false);
      document.getElementById("edit-title").focus();
      showToast("Duplicated — edit and save to create.", "info");
    }
    function ctxShowRawPath() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      const path = t.source || "(unknown source)";
      showToast("File: " + path, "info", 5000);
    }

    // ── Jump to line number ───────────────────────────────────────
    function jumpToLine() {
      const n = prompt("Go to line number:");
      if (!n || !n.trim()) return;
      const lineNum = parseInt(n.trim(), 10);
      if (!isNaN(lineNum)) openItemByLine(lineNum);
    }
    async function openItemByLine(lineNum) {
      try {
        const data = await api(`/api/items/${lineNum}`);
        if (data?.item) { openDrawer(data.item); selectItem(data.item); }
        else showToast("No item at line " + lineNum, "error");
      } catch(e) { showToast("Line " + lineNum + ": " + e.message, "error"); }
    }

    // ── Tag datalist autocomplete ──────────────────────────────────
    function updateTagSuggestions(items) {
      const dl = document.getElementById("tag-suggestions");
      if (!dl) return;
      const tags = new Set();
      for (const item of (items || [])) {
        for (const t of (item?.details?.tag || [])) tags.add(String(t));
      }
      dl.innerHTML = [...tags].sort().map(t => `<option value="${escapeHtml(t)}">`).join("");
    }

    // ── Agenda overdue badge ──────────────────────────────────────
    function updateAgendaOverdueBadge(records) {
      const badge = document.getElementById("agenda-overdue-badge");
      if (!badge) return;
      const today = new Date(); today.setHours(0,0,0,0);
      const count = (records || []).filter(r => {
        if (!r.when) return false;
        const d = new Date(r.when); d.setHours(0,0,0,0);
        return d < today && !["[x]","[-]"].includes(r.status);
      }).length;
      badge.textContent = count > 0 ? String(count) : "";
      badge.style.display = count > 0 ? "" : "none";
    }

    // ── Stats summary: per-project mini-table ────────────────────
    async function loadProjectStats() {
      try {
        const data = await api("/api/stats/summary");
        const projects = (data.by_project || []).filter(p => p.total > 0);
        if (!projects.length) return;
        const el = document.getElementById("stats-summary");
        if (!el || el.style.display === "none") return;
        const maxTotal = Math.max(...projects.map(p => p.total), 1);
        let table = `<div style="margin-top:.5rem"><div class="drawer-section-title" style="font-size:.72rem;margin-bottom:.25rem">Top Projects</div>
          <table class="proj-stats-table"><thead><tr><th>Project</th><th>Done</th><th>Total</th><th style="min-width:4rem"></th></tr></thead><tbody>`;
        for (const p of projects.slice(0, 8)) {
          const barW = Math.round(p.total / maxTotal * 60);
          table += `<tr>
            <td>${escapeHtml(p.project)}</td>
            <td>${p.done}</td>
            <td>${p.total}</td>
            <td><span class="proj-stats-bar" style="width:${barW}px;opacity:${0.4 + 0.6*(p.done/Math.max(p.total,1))}"></span></td>
          </tr>`;
        }
        table += `</tbody></table></div>`;
        el.insertAdjacentHTML("beforeend", table);
      } catch(_) {}
    }

    // ── Notification retry button ─────────────────────────────────
    async function retryBrowserNotification(id) {
      const record = (window._lastNotifRecords || []).find(r => r.id === id || r.notification_id === id);
      if (!record) { showToast("Notification not found.", "error"); return; }
      try {
        if (Notification.permission !== "granted") {
          await enableBrowserNotifications();
        }
        seenNotifications.delete(record.notification_id || record.id || record.text);
        showBrowserNotification(record);
        showToast("Notification resent.", "success");
      } catch(e) {
        showToast("Retry failed: " + e.message, "error");
      }
    }

    // ── Dashboard view ──────────────────────────────────────────────
    let _dashChart = null;
    function _fmtDate(d) {
      const pad = n => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    function _dashItemRow(item) {
      const statusCls = STATUS_CLASS[item.status] || "status-note";
      const statusIcon = STATUS_ICON[item.status] || "·";
      const dueRel = buildDueRelLabel(item);
      return `<div class="dash-row">
        <span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.08rem .4rem">${escapeHtml(statusIcon)}</span>
        <span class="type-badge type-${escapeHtml(item.type || "N")}" style="font-size:.68rem;padding:.08rem .4rem">${escapeHtml(item.type || "?")}</span>
        <a class="drawer-link dash-row-title" onclick="openItemByLine(${Number(item.line) || 0})">${escapeHtml(item.title)}</a>
        ${dueRel}
      </div>`;
    }
    async function loadDashboard() {
      const dateEl = document.getElementById("dash-date");
      if (dateEl) dateEl.textContent = new Date().toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"});
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 13);
      let openItems = [], blockedItems = [], agendaRecords = [], chartData = null, summary = null;
      try {
        [openItems, blockedItems, agendaRecords, chartData, summary] = await Promise.all([
          api("/api/items?open_only=true").then(d => d.items || []).catch(() => []),
          api("/api/items?blocked=true&open_only=true").then(d => d.items || []).catch(() => []),
          api("/api/agenda?around=now&window=1d&open_only=true").then(d => d.records || []).catch(() => []),
          api(`/api/chart/tasks?from=${_fmtDate(weekAgo)}&to=${_fmtDate(today)}&group=daily`).catch(() => null),
          api("/api/stats/summary").catch(() => null),
        ]);
      } catch(_) {}
      // KPI tiles
      const overdue = openItems.filter(i => itemDueSoonClass(i) === "overdue");
      const dueToday = openItems.filter(i => {
        const due = i?.details?.due?.[0];
        if (!due) return false;
        const d = new Date(due); if (isNaN(d)) return false;
        d.setHours(0, 0, 0, 0);
        return +d === +today;
      });
      let doneRecent = 0;
      if (chartData?.datasets?.length) {
        for (const ds of chartData.datasets) {
          if (/done/i.test(ds.label || "")) doneRecent = (ds.data || []).reduce((a, b) => a + (Number(b) || 0), 0);
        }
        if (!doneRecent) doneRecent = (chartData.datasets[0].data || []).reduce((a, b) => a + (Number(b) || 0), 0);
      }
      const kpis = [
        {n: openItems.length, label: "Open", icon: "○", view: "", params: {open_only: "true"}},
        {n: dueToday.length, label: "Due today", icon: "📅", view: "focus", params: {}},
        {n: overdue.length, label: "Overdue", icon: "⚠️", cls: overdue.length ? "kpi-danger" : "", view: "focus", params: {}},
        {n: blockedItems.length, label: "Blocked", icon: "⚡", cls: blockedItems.length ? "kpi-warn" : "", view: "", params: {blocked: "true", open_only: "true"}},
        {n: doneRecent, label: "Done (14d)", icon: "✓", cls: "kpi-ok", view: "stats", params: {}},
      ];
      const kpiEl = document.getElementById("dash-kpis");
      if (kpiEl) {
        kpiEl.innerHTML = kpis.map((k, i) =>
          `<button type="button" class="kpi-tile ${k.cls || ""}" onclick="dashNavigate(${i})">` +
          `<span class="kpi-icon" aria-hidden="true">${k.icon}</span>` +
          `<span class="kpi-n">${k.n}</span><span class="kpi-label">${escapeHtml(k.label)}</span></button>`
        ).join("");
        window._dashKpis = kpis;
      }
      // Today agenda
      const todayEl = document.getElementById("dash-today");
      if (todayEl) {
        const limit = dashboardLimit("today", 7);
        todayEl.innerHTML = agendaRecords.length
          ? agendaRecords.slice(0, limit).map(r =>
              `<div class="dash-row"><span class="pill">${escapeHtml((r.when || "").replace("T", " "))}</span>` +
              (r.blocked ? `<span class="blocked-badge">⚡</span>` : "") +
              `<span class="dash-row-title">${escapeHtml(r.title)}</span></div>`
            ).join("") + (agendaRecords.length > limit ? `<a class="drawer-link" onclick="switchWorkspace('agenda')">View all ${agendaRecords.length} →</a>` : "")
          : `<div class="empty">Nothing scheduled around now.</div>`;
      }
      // Needs attention: overdue + blocked
      const overdueEl = document.getElementById("dash-overdue");
      if (overdueEl) {
        const attention = [...overdue.map(i => ({...i, _why: "overdue"})),
                           ...blockedItems.filter(b => !overdue.some(o => o.line === b.line && o.source === b.source)).map(i => ({...i, _why: "blocked"}))];
        const limit = dashboardLimit("needs_attention", 7);
        overdueEl.innerHTML = attention.length
          ? attention.slice(0, limit).map(_dashItemRow).join("") +
            (attention.length > limit ? `<a class="drawer-link" onclick="switchWorkspace('focus')">View all ${attention.length} →</a>` : "")
          : `<div class="empty">🎉 Nothing overdue or blocked.</div>`;
      }
      // Projects
      const projEl = document.getElementById("dash-projects");
      if (projEl) {
        const projects = (summary?.by_project || []).filter(p => p.total > 0).slice(0, dashboardLimit("projects", 7));
        const maxTotal = Math.max(...projects.map(p => p.total), 1);
        projEl.innerHTML = projects.length
          ? projects.map(p =>
              `<div class="dash-row"><span class="dash-row-title">${escapeHtml(p.project)}</span>` +
              `<span style="color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums">${p.done}/${p.total}</span>` +
              `<span class="proj-stats-bar" style="width:${Math.round(p.total / maxTotal * 70)}px;opacity:${(0.4 + 0.6 * (p.done / Math.max(p.total, 1))).toFixed(2)}"></span></div>`
            ).join("")
          : `<div class="empty">No project data.</div>`;
      }
      // Chart
      const chartCard = document.querySelector('[data-dashboard-card="completions"]');
      if (chartData && !(chartCard && chartCard.classList.contains("card-hidden"))) {
        try {
          await ensureChartJs();
          const canvas = document.getElementById("dash-chart");
          if (canvas) {
            if (_dashChart) { _dashChart.destroy(); _dashChart = null; }
            _dashChart = new Chart(canvas.getContext("2d"), {
              type: "bar",
              data: {
                labels: (chartData.labels || []).map(l => String(l).slice(5)),
                datasets: (chartData.datasets || []).map((ds, i) => ({
                  label: ds.label, data: ds.data,
                  backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "88",
                  borderColor: CHART_COLORS[i % CHART_COLORS.length],
                  borderWidth: 1.2,
                })),
              },
              options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {y: {beginAtZero: true}}},
            });
          }
        } catch(_) {}
      }
    }
    function dashNavigate(index) {
      const kpi = (window._dashKpis || [])[index];
      if (!kpi) return;
      const params = query();
      for (const key of ["text", "q", "status", "blocked", "open", "open_only", "kind", "type"]) params.delete(key);
      for (const [key, value] of Object.entries(kpi.params || {})) params.set(key, value);
      history.replaceState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      switchWorkspace(kpi.view, "replace");
    }

    // ── Focus view (today's work, distraction-free) ────────────────
    async function loadFocus() {
      const listEl = document.getElementById("focus-list");
      if (!listEl) return;
      const dateEl = document.getElementById("focus-date");
      if (dateEl) dateEl.textContent = new Date().toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"});
      let items = [];
      try {
        items = (await api("/api/items?open_only=true")).items || [];
      } catch(e) {
        listEl.innerHTML = `<div class="diagnostic">Focus error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const detailDate = (item, keys) => {
        for (const key of keys) {
          const value = item?.details?.[key]?.[0];
          if (!value) continue;
          const d = new Date(value); if (isNaN(d)) continue;
          d.setHours(0, 0, 0, 0);
          return d;
        }
        return null;
      };
      // Reminders count at:/on: as their due date; tasks and deadlines use due: only.
      const dueKeysByType = {T: ["due"], D: ["due"], R: ["due", "at", "on"], H: ["due"]};
      const dueDiff = (item) => {
        const d = detailDate(item, dueKeysByType[item.type] || ["due"]);
        return d === null ? null : Math.round((d - today) / 86400000);
      };
      const workTypes = new Set(["T", "D", "R", "H"]);
      const overdue = [], dueToday = [], todayEvents = [], inProgress = [], anytimeReminders = [];
      for (const item of items) {
        if (item.type === "E") {
          const d = detailDate(item, ["from", "on", "at", "due"]);
          if (d && +d === +today) todayEvents.push(item);
          continue;
        }
        if (!workTypes.has(item.type)) continue;
        const diff = dueDiff(item);
        if (diff !== null && diff < 0) overdue.push(item);
        else if (diff === 0) dueToday.push(item);
        else if (item.status === "[/]") inProgress.push(item);
        else if (item.type === "R" && diff === null) anytimeReminders.push(item);
      }
      todayEvents.sort((a, b) =>
        String(a?.details?.from?.[0] || a?.details?.at?.[0] || "").localeCompare(
          String(b?.details?.from?.[0] || b?.details?.at?.[0] || "")));
      const groups = [
        {label: "⚠️ Overdue", items: overdue, cls: "focus-overdue"},
        {label: "📅 Due today", items: dueToday, cls: ""},
        {label: "🕑 Today's schedule", items: todayEvents, cls: ""},
        {label: "◑ In progress", items: inProgress, cls: ""},
        {label: "📌 Anytime reminders", items: anytimeReminders, cls: ""},
      ].filter(g => g.items.length);
      if (!groups.length) {
        listEl.innerHTML = `<div class="empty-state"><div class="empty-icon" aria-hidden="true">🎉</div>` +
          `<div class="empty-title">All clear</div>` +
          `<div class="empty-hint">Nothing overdue, due today, or in progress. Enjoy the calm — or pull something forward from Items.</div>` +
          `<button type="button" class="secondary" onclick="switchWorkspace('')">Open Items</button></div>`;
        return;
      }
      window._focusItems = groups.flatMap(g => g.items);
      const eventTime = (item) => {
        const value = String(item?.details?.from?.[0] || item?.details?.at?.[0] || "");
        const match = value.match(/T(\d{2}:\d{2})/);
        return match ? match[1] : "🕑";
      };
      let idx = 0;
      let html = "";
      for (const group of groups) {
        html += `<div class="focus-group-label ${group.cls}">${group.label} (${group.items.length})</div>`;
        for (const item of group.items) {
          const dueRel = buildDueRelLabel(item);
          const proj = item?.details?.project?.[0] ? `<span class="pill">${escapeHtml(item.details.project[0])}</span>` : "";
          const lead = item.type === "E"
            ? `<span class="focus-event-time pill">${escapeHtml(eventTime(item))}</span>`
            : `<button type="button" class="focus-check" title="${item.editable ? "Mark done" : "Read-only"}" ${item.editable ? `onclick="focusMarkDone(${idx})"` : "disabled"}></button>`;
          html += `<div class="focus-row${item.editable ? "" : " focus-readonly"}">` + lead +
            `<div class="focus-row-main" onclick="focusOpen(${idx})">` +
            `<div class="focus-row-title">${escapeHtml(item.title)}</div>` +
            `<div class="focus-row-meta">${proj}${dueRel}</div>` +
            `</div></div>`;
          idx++;
        }
      }
      listEl.innerHTML = html;
    }
    async function focusQuickAdd() {
      const input = document.getElementById("focus-quick-title");
      const title = (input?.value || "").trim();
      if (!title) return;
      const safe = /^[A-Za-z0-9_.\-]+$/.test(title)
        ? title
        : `"${title.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
      const line = `[ ] T ${safe} due:${_fmtDate(new Date())}`;
      try {
        await api("/api/items/raw", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        input.value = "";
        showToast("Task added for today.", "success");
        await loadFocus();
      } catch(e) {
        showToast("Quick add failed: " + (e.message || e), "error");
      }
    }
    async function focusMarkDone(index) {
      const item = (window._focusItems || [])[index];
      if (!item || !item.editable) return;
      const line = item.line;
      const prevPayload = {status: item.status, type: item.type, title: item.title, details: item.details || {}};
      try {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, status: "[x]"}),
        });
        registerUndo(`Done: ${item.title}`, async () => {
          await api(`/api/items/${line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await loadFocus();
      } catch(e) {
        showToast("Mark done failed: " + (e.message || e), "error");
      }
    }
    function focusOpen(index) {
      const item = (window._focusItems || [])[index];
      if (item) openDrawer(item);
    }

    // ── Review view (weekly/monthly retrospective) ────────────────
    let reviewRange = "week";
    function setReviewRange(range) {
      reviewRange = range;
      document.querySelectorAll("#review-range-bar .review-range-btn").forEach(btn =>
        btn.classList.toggle("active", btn.dataset.range === range));
      loadReview();
    }
    function setReviewCustom() {
      reviewRange = "custom";
      document.querySelectorAll("#review-range-bar .review-range-btn").forEach(btn =>
        btn.classList.remove("active"));
      loadReview();
    }
    function _reviewProjectParam() {
      const value = (document.getElementById("review-project")?.value || "").trim();
      return value ? `&project=${encodeURIComponent(value)}` : "";
    }
    function _reviewQuery() {
      const today = new Date();
      if (reviewRange === "week") return "week=true" + _reviewProjectParam();
      if (reviewRange === "last-week") {
        const dow = (today.getDay() + 6) % 7; // Monday-based weekday
        const monday = new Date(today); monday.setDate(today.getDate() - dow);
        const start = new Date(monday); start.setDate(monday.getDate() - 7);
        const end = new Date(monday); end.setDate(monday.getDate() - 1);
        return `from=${_fmtDate(start)}&to=${_fmtDate(end)}` + _reviewProjectParam();
      }
      const y = today.getFullYear(), m = today.getMonth();
      if (reviewRange === "month") return `month=${y}-${String(m + 1).padStart(2, "0")}` + _reviewProjectParam();
      if (reviewRange === "custom") {
        const start = (document.getElementById("review-from")?.value || "").trim();
        const end = (document.getElementById("review-to")?.value || "").trim();
        const parts = [];
        if (start) parts.push(`from=${encodeURIComponent(start)}`);
        if (end) parts.push(`to=${encodeURIComponent(end)}`);
        const project = _reviewProjectParam().replace(/^&/, "");
        if (project) parts.push(project);
        return parts.join("&") || "week=true";
      }
      const prev = new Date(y, m - 1, 1);
      return `month=${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}` + _reviewProjectParam();
    }
    async function loadReview() {
      const kpiEl = document.getElementById("review-kpis");
      if (!kpiEl) return;
      let data;
      try {
        data = await api(`/api/review?${_reviewQuery()}`);
      } catch(e) {
        kpiEl.innerHTML = `<div class="diagnostic">Review error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      window._lastReviewData = data;
      const rangeEl = document.getElementById("review-range-label");
      if (rangeEl) rangeEl.textContent = data.range || "";
      const habitTitles = Object.keys(data.habits || {});
      const kpis = [
        {n: data.completed_tasks || 0, label: "Completed", icon: "✓", cls: "kpi-ok"},
        {n: data.open_tasks || 0, label: "Still open", icon: "○"},
        {n: data.journals || 0, label: "Journal entries", icon: "📓"},
        {n: habitTitles.length, label: "Habits tracked", icon: "🔁"},
      ];
      kpiEl.innerHTML = kpis.map(k =>
        `<div class="kpi-tile ${k.cls || ""}"><span class="kpi-icon" aria-hidden="true">${k.icon}</span>` +
        `<span class="kpi-n">${k.n}</span><span class="kpi-label">${escapeHtml(k.label)}</span></div>`
      ).join("");
      const doneEl = document.getElementById("review-completed");
      if (doneEl) {
        const completed = data.completed || [];
        doneEl.innerHTML = completed.length
          ? completed.map(t =>
              `<div class="dash-row">` +
              (t.done ? `<span class="pill">${escapeHtml(String(t.done).slice(0, 10))}</span>` : "") +
              (t.id
                ? `<button type="button" class="dash-row-title review-click" onclick="drawerNavigate(${escapeHtml(jsLiteral(t.id))})">${escapeHtml(t.title)}</button>`
                : `<span class="dash-row-title">${escapeHtml(t.title)}</span>`) +
              (t.project ? `<span class="pill">${escapeHtml(t.project)}</span>` : "") +
              `</div>`).join("")
          : `<div class="empty">No tasks completed in this range.</div>`;
      }
      const habitsEl = document.getElementById("review-habits");
      if (habitsEl) {
        habitsEl.innerHTML = habitTitles.length
          ? habitTitles.map(title => {
              const h = data.habits[title];
              const total = h.done + h.open;
              return `<div class="dash-row"><span class="dash-row-title">${escapeHtml(title)}</span>` +
                `<span class="review-num">${h.done}/${total} (${h.completion_rate}%)</span>` +
                `<span class="review-habit-bar"><span style="width:${h.completion_rate}%"></span></span></div>`;
            }).join("")
          : `<div class="empty">No habit records in this range.</div>`;
      }
      const journalEl = document.getElementById("review-journal");
      if (journalEl) {
        const entries = data.journal_entries || [];
        const moods = data.mood_trend || [];
        const moodLine = moods.length
          ? `<div class="dash-row review-mood-row"><span class="review-num">Mood:</span>${moods.map(m =>
              `<span class="pill" title="${escapeHtml(m.date)}">${escapeHtml(m.mood)}</span>`).join("")}</div>`
          : "";
        journalEl.innerHTML = (entries.length || moods.length)
          ? moodLine + entries.map(e =>
              `<div class="dash-row"><span class="pill">${escapeHtml(e.date)}</span>` +
              `<div style="flex:1;min-width:0"><div class="dash-row-title">${escapeHtml(e.title)}</div>` +
              (e.excerpt ? `<div class="review-excerpt">${escapeHtml(e.excerpt)}</div>` : "") +
              `</div></div>`).join("")
          : `<div class="empty">No journal entries in this range.</div>`;
      }
      const elapsedEl = document.getElementById("review-elapsed");
      if (elapsedEl) {
        const rows = Object.entries(data.elapsed_by_project || {});
        elapsedEl.innerHTML = rows.length
          ? rows.map(([proj, elapsed]) =>
              `<div class="dash-row"><span class="dash-row-title">${escapeHtml(proj)}</span>` +
              `<span class="pill">${escapeHtml(elapsed)}</span></div>`).join("")
          : `<div class="empty">No elapsed time recorded.</div>`;
      }
    }
    function reviewMarkdown(data) {
      const lines = [
        "# life.txt Review",
        "",
        `Range: ${data?.range || ""}`,
        "",
        "## Summary",
        `- Completed tasks: ${data?.completed_tasks || 0}`,
        `- Open tasks: ${data?.open_tasks || 0}`,
        `- Journal entries: ${data?.journals || 0}`,
      ];
      const completed = data?.completed || [];
      if (completed.length) {
        lines.push("", "## Completed");
        for (const item of completed) {
          const bits = [];
          if (item.done) bits.push(`done:${item.done}`);
          if (item.project) bits.push(`project:${item.project}`);
          if (item.id) bits.push(`id:${item.id}`);
          lines.push(`- [x] ${item.title}${bits.length ? " (" + bits.join(", ") + ")" : ""}`);
        }
      }
      const habits = Object.entries(data?.habits || {});
      if (habits.length) {
        lines.push("", "## Habits");
        for (const [title, h] of habits) {
          const total = (Number(h.done) || 0) + (Number(h.open) || 0);
          lines.push(`- ${title}: ${h.done}/${total} (${h.completion_rate}%)`);
        }
      }
      const journals = data?.journal_entries || [];
      if (journals.length) {
        lines.push("", "## Journal");
        for (const entry of journals) {
          lines.push(`- ${entry.date} ${entry.title}${entry.excerpt ? " — " + entry.excerpt : ""}`);
        }
      }
      const elapsed = Object.entries(data?.elapsed_by_project || {});
      if (elapsed.length) {
        lines.push("", "## Elapsed");
        for (const [project, value] of elapsed) lines.push(`- ${project}: ${value}`);
      }
      return lines.join("\n");
    }
    function copyReviewMarkdown() {
      const data = window._lastReviewData;
      if (!data) { showToast("Load a review first.", "warning"); return; }
      navigator.clipboard.writeText(reviewMarkdown(data)).then(
        () => showToast("Review copied as Markdown.", "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    loadConfig().then(() => {
      applyPresetToUrl();
      applyUrlToControls();
      updateNotifPermissionDisplay();
      updateNotifBtnLabel();
      updateTypeHints(document.getElementById("edit-type").value);
      setupContextualHelp();
      setupWorkspaceTabs();
      syncStatusFilterBarsFromUrl();
      _syncGraphLayoutBtns();
      startGitPolling();
      // Back-compat: ?workspace=new used to open the editor panel
      if (firstParam(query(), ["workspace", "panel"], "").toLowerCase() === "new") newItem();
      return refreshAll().then(() => {
        // Auto-open detail modal for ?line=N deep links
        const lineParam = query().get("line");
        if (lineParam) {
          const lineNum = parseInt(lineParam, 10);
          if (!isNaN(lineNum)) openItemByLine(lineNum);
        }
      });
    }).catch(error => {
      document.body.insertAdjacentHTML("beforeend", `<pre class="diagnostic">${escapeHtml(error.message)}</pre>`);
    });
  </script>
</body>
</html>
"""
