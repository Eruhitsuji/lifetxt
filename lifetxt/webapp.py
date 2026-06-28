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
from .links import build_id_index, item_id_values, link_records, reference_diagnostics
from .stats import (
    MOOD_VALUES,
    build_stats,
    habit_stats,
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


def create_app(paths=None, writable_path=None, config=None):
    try:
        from fastapi import Body, FastAPI, HTTPException, Query, Request
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Web dependencies are not installed. Run: pip install -r requirements-web.txt"
        ) from exc

    app = FastAPI(title="life.txt API", version="0.1.0")
    app.state.paths = normalize_server_paths(paths)
    app.state.writable_path = writable_path or app.state.paths[0]
    app.state.config = config or {}

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
            from .links import dependency_blocker_records
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
                }
            if tgt_id and tgt_id not in nodes_map:
                nodes_map[tgt_id] = {
                    "id": tgt_id,
                    "title": rec.get("target_title", tgt_id),
                    "status": rec.get("target_status", ""),
                    "type": rec.get("target_type", ""),
                }
            edges.append({"source": src_id, "target": tgt_id, "relation": rec["relation"]})
        nodes = list(nodes_map.values())
        if root:
            nodes, edges = _subgraph(nodes, edges, root, depth)
        return {"nodes": nodes, "edges": edges}

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
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        habit_items = [item for item in items if item.kind == "H"]
        buckets = make_buckets(s, e, group)
        habits = habit_stats(habit_items, s, e, buckets)
        labels = [b[0].isoformat() if b[0] == b[1] else "%s/%s" % (b[0].isoformat(), b[1].isoformat()) for b in buckets]
        datasets = []
        for habit in habits:
            sp = habit.get("sparkline", "")
            from .stats import SPARK, MISSING
            data = []
            for ch in sp:
                if ch == MISSING:
                    data.append(0)
                else:
                    idx = SPARK.find(ch)
                    data.append(max(0, idx))
            if len(data) < len(labels):
                data.extend([0] * (len(labels) - len(data)))
            datasets.append({"label": habit["title"], "streak": habit["streak"], "data": data[:len(labels)]})
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
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        s, e = stats_range(start, end)
        journal_items = [item for item in items if item.kind == "J"]
        buckets = make_buckets(s, e, group)
        mood = mood_stats(journal_items, buckets)
        labels = [b[0].isoformat() if b[0] == b[1] else "%s/%s" % (b[0].isoformat(), b[1].isoformat()) for b in buckets]
        from .stats import SPARK, MISSING
        sp = mood.get("sparkline", "")
        data = []
        for ch in sp:
            if ch == MISSING:
                data.append(None)
            else:
                idx = SPARK.find(ch)
                data.append(round(1 + idx * (len(MOOD_VALUES) - 1) / max(1, len(SPARK) - 1), 2))
        if len(data) < len(labels):
            data.extend([None] * (len(labels) - len(data)))
        return {
            "labels": labels,
            "datasets": [{"label": "mood", "data": data[:len(labels)]}],
            "mood_scale": MOOD_VALUES,
            "counts": dict(mood.get("counts", {})),
            "range": {"from": s.isoformat(), "to": e.isoformat(), "group": group},
        }

    @app.get("/api/chart/elapsed")
    def chart_elapsed(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        project=None,
    ):
        items, _diags = read_life_inputs(app.state.paths, app.state.config)
        elapsed_by_project = {}
        for item in items:
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
    def git_log(request: Request, n: int = 5):
        _git_guard(request)
        n = min(max(1, n), 50)
        result = _run_git(["git", "log", "--pretty=format:%H\t%s\t%ai", "-%d" % n])
        commits = []
        if result.get("ok") and result.get("stdout"):
            for line in result["stdout"].strip().splitlines():
                parts = line.split("\t", 2)
                if len(parts) >= 2:
                    commits.append({"hash": parts[0][:8], "message": parts[1], "date": parts[2] if len(parts) > 2 else ""})
        return {"commits": commits, "ok": result.get("ok", False)}

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
        filtered_records = limit_items(filtered_records, limit)
        return {"count": len(filtered_records), "records": filtered_records}

    @app.get("/api/status")
    def get_status(person=None, active=False):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        records = latest_status_records(items, person=person, active_only=active)
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


def public_web_config(config):
    web = config_section(config, "web")
    return {
        "display_refresh": int(web.get("display_refresh") or 60),
        "notification_poll_seconds": int(web.get("notification_poll_seconds") or 30),
        "notification_lookahead": web.get("notification_lookahead", "0m"),
        "default_limit": web.get("default_limit", ""),
        "default_sort": web.get("default_sort", "line"),
        "default_order": web.get("default_order", "asc"),
        "due_soon_days": int(web.get("due_soon_days") or 3),
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
    max_depth = int(depth) if depth is not None else None
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
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #202421;
      --muted: #68706a;
      --line: #d9ddd7;
      --line-strong: #b8c0b7;
      --accent: #256b5f;
      --danger: #a63c2f;
      --soft: #eef2ee;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: var(--bg);
      font-family: "Segoe UI", "Yu Gothic", sans-serif;
      font-size: 15px;
    }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 1rem;
      max-width: 1180px;
      margin: 0 auto;
      padding: 1.25rem clamp(.75rem, 3vw, 1.5rem);
    }
    h1 { margin: 0; font-size: clamp(1.6rem, 4vw, 2.4rem); letter-spacing: -.04em; }
    .subtitle { margin: .25rem 0 0; color: var(--muted); }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(20rem, 25rem);
      gap: 1rem;
      max-width: 1180px;
      margin: 0 auto;
      padding: 0 clamp(.75rem, 3vw, 1.5rem) 2rem;
    }
    section {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: .75rem;
      overflow: hidden;
    }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: .75rem;
      padding: .85rem 1rem;
      border-bottom: 1px solid var(--line);
    }
    h2 { margin: 0; font-size: .92rem; letter-spacing: .04em; text-transform: uppercase; }
    .toolbar, .actions {
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      align-items: center;
    }
    input, select, textarea, button {
      max-width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: .45rem;
      padding: .55rem .65rem;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    input:disabled, select:disabled, textarea:disabled {
      color: var(--muted);
      background: #f5f6f4;
    }
    textarea {
      width: 100%;
      min-height: 8rem;
      resize: vertical;
      font-family: Consolas, "Courier New", monospace;
      font-size: .9rem;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 650;
    }
    button.secondary { background: #fff; color: var(--accent); }
    button.danger { background: #fff; border-color: #d8a9a0; color: var(--danger); }
    button:disabled { cursor: not-allowed; opacity: .55; }
    .content, .stack { display: grid; gap: .65rem; padding: 1rem; }
    .item {
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr) auto;
      gap: .55rem;
      align-items: start;
      width: 100%;
      padding: .7rem;
      border: 1px solid var(--line);
      border-radius: .6rem;
      background: #fff;
      text-align: left;
      color: inherit;
    }
    .item:hover, .item.selected { border-color: var(--accent); background: #f7fbf9; }
    .title { font-weight: 700; overflow-wrap: anywhere; }
    .meta { color: var(--muted); font-size: .84rem; overflow-wrap: anywhere; }
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
      min-height: 1.55rem;
      padding: .15rem .45rem;
      border-radius: 999px;
      background: var(--soft);
      font-family: Consolas, "Courier New", monospace;
      font-size: .82rem;
      white-space: nowrap;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      min-height: 1.55rem;
      padding: .15rem .5rem;
      border-radius: 999px;
      font-family: Consolas, "Courier New", monospace;
      font-size: .82rem;
      white-space: nowrap;
      font-weight: 700;
    }
    .status-open   { background: #d9eef8; color: #1a5a80; }
    .status-active { background: #fff3cd; color: #7a5200; }
    .status-done   { background: #d4edda; color: #1a5c30; text-decoration: line-through; opacity: .7; }
    .status-cancel { background: #f0f0f0; color: #666; text-decoration: line-through; opacity: .7; }
    .status-defer  { background: #e8e0f5; color: #4a2d85; }
    .status-maybe  { background: #fce8e8; color: #8a2020; }
    .status-note   { background: #f5f5f5; color: #555; }
    .type-badge {
      display: inline-flex;
      align-items: center;
      min-height: 1.55rem;
      padding: .15rem .45rem;
      border-radius: .35rem;
      font-size: .78rem;
      font-weight: 700;
      white-space: nowrap;
      letter-spacing: .04em;
    }
    .type-T { background: #e8f4fd; color: #1a5a80; }
    .type-E { background: #fce8ff; color: #6a1a80; }
    .type-D { background: #fde8e8; color: #8a1a1a; }
    .type-R { background: #fdf4e8; color: #7a4a00; }
    .type-H { background: #e8fdf0; color: #1a5c30; }
    .type-N { background: #f5f5f5; color: #555; }
    .type-S { background: #e8f0fd; color: #1a3080; }
    .type-M { background: #fdf0e8; color: #80401a; }
    .type-J { background: #fdfde8; color: #6a6a00; }
    .item.overdue   { border-left: 3px solid #c0392b; }
    .item.due-soon  { border-left: 3px solid #e67e22; }
    .stats-summary {
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
      padding: .6rem 1rem;
      border-bottom: 1px solid var(--line);
      background: var(--soft);
      font-size: .85rem;
    }
    .stats-count { display: flex; gap: .3rem; align-items: center; }
    .stats-count .n { font-weight: 700; font-size: 1.05rem; }
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
      padding: .2rem .5rem;
      border-radius: 999px;
      background: #e0eeea;
      color: var(--accent);
      font-size: .82rem;
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
    .chart-panel {
      position: relative;
      height: 200px;
    }
    .chart-tabs { display: flex; gap: .3rem; padding: .5rem 1rem; border-bottom: 1px solid var(--line); }
    .chart-tab {
      padding: .25rem .65rem;
      border-radius: .35rem;
      border: 1px solid var(--line-strong);
      background: #fff;
      color: var(--muted);
      font-size: .82rem;
      cursor: pointer;
    }
    .chart-tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    .quick-add-bar {
      display: flex;
      gap: .4rem;
      padding: .5rem 1rem;
      border-bottom: 1px solid var(--line);
      background: var(--soft);
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
      position: fixed;
      top: 0;
      right: -460px;
      width: min(460px, 92vw);
      height: 100vh;
      overflow-y: auto;
      background: var(--panel);
      border-left: 1px solid var(--line);
      box-shadow: -4px 0 32px rgba(0,0,0,.14);
      transition: right .22s ease;
      z-index: 100;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .detail-drawer.open { right: 0; }
    .drawer-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: .85rem 1.1rem;
      border-bottom: 1px solid var(--line);
      gap: .5rem;
      position: sticky;
      top: 0;
      background: var(--panel);
      z-index: 1;
    }
    .drawer-head h3 { margin: 0; font-size: .95rem; }
    .drawer-body { padding: 1rem 1.1rem; display: grid; gap: 1rem; }
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
      padding: .65rem 1.1rem;
      border-radius: .5rem;
      background: #fff;
      border: 1px solid var(--line);
      box-shadow: 0 2px 16px rgba(0,0,0,.14);
      font-size: .88rem;
      max-width: 340px;
      pointer-events: auto;
      animation: toastIn .18s ease;
    }
    .toast.success { border-color: #86efac; background: #f0fdf4; color: #166534; }
    .toast.error   { border-color: #fca5a5; background: #fef2f2; color: #991b1b; }
    .toast.info    { border-color: #93c5fd; background: #eff6ff; color: #1e40af; }
    @keyframes toastIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
    .git-badge {
      padding: .2rem .55rem;
      border-radius: .35rem;
      font-size: .78rem;
      font-weight: 700;
      cursor: pointer;
      border: none;
      white-space: nowrap;
    }
    .git-clean    { background: #d4edda; color: #1a5c30; }
    .git-modified { background: #fff3cd; color: #7a5200; }
    .git-error    { background: #fde8e8; color: #8a1a1a; }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.45);
      z-index: 200;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      background: var(--panel);
      border-radius: .75rem;
      padding: 1.5rem 1.75rem;
      max-width: 520px;
      width: 92vw;
      max-height: 82vh;
      overflow-y: auto;
      box-shadow: 0 8px 40px rgba(0,0,0,.2);
    }
    .modal h3 { margin: 0 0 1rem; }
    .modal table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    .modal td { padding: .3rem .5rem; border-bottom: 1px solid var(--line); }
    .modal td:first-child { color: var(--muted); width: 7rem; white-space: nowrap; }
    .notif-permission { display: flex; align-items: center; gap: .4rem; font-size: .82rem; padding: .5rem 1rem; border-bottom: 1px solid var(--line); }
    .notif-perm-granted { color: #166534; }
    .notif-perm-denied  { color: #991b1b; }
    .notif-perm-default { color: #7a5200; }
    mark { background: #fff9c4; border-radius: .2rem; padding: 0 .1rem; }
    /* ── Button active state ─────────────────────────────────────── */
    .secondary.btn-active {
      background: #dbeafe; border-color: #3b82f6; color: #1e3a8a; font-weight: 600;
    }
    /* ── Dependency graph rows ───────────────────────────────────── */
    .dep-graph { display: grid; gap: .3rem; }
    .dep-group-label { font-size: .73rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-top: .15rem; }
    .dep-row { display: flex; align-items: center; gap: .35rem; padding: .25rem .4rem; border-radius: .35rem; background: var(--bg); border: 1px solid var(--line); }
    .dep-row:hover { border-color: #93c5fd; }
    .dep-arrow { font-weight: 700; font-size: .9rem; min-width: 1.2rem; text-align: center; }
    .dep-out { color: #0c4a6e; }
    .dep-in  { color: #7c3aed; }
    .dep-rel { font-size: .72rem; color: var(--muted); min-width: 5.5rem; }
    .dep-missing { color: #9ca3af; font-style: italic; font-size: .85rem; }
    a.drawer-link { color: var(--accent); text-decoration: none; font-size: .88rem; }
    a.drawer-link:hover { text-decoration: underline; }
    /* ── Status quick-filter bar ──────────────────────────────────── */
    .filter-bar { display: flex; gap: .35rem; flex-wrap: wrap; margin: .4rem 0 .2rem; }
    .filter-btn { padding: .2rem .6rem; border-radius: 1rem; font-size: .77rem; border: 1px solid var(--line); background: var(--bg); cursor: pointer; color: var(--text); transition: background .12s, border-color .12s; }
    .filter-btn:hover { border-color: var(--accent); color: var(--accent); }
    .filter-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; }
    /* ── Ref links in item rows ───────────────────────────────────── */
    .ref-link { display: inline-block; color: var(--accent); font-size: .75rem; border: 1px solid currentColor; border-radius: .25rem; padding: 0 .3rem; margin-left: .15rem; cursor: pointer; opacity: .85; }
    .ref-link:hover { opacity: 1; text-decoration: underline; }
    .parent-indicator { font-size: .73rem; color: var(--muted); margin-left: .3rem; }
    /* ── Notification state badges ────────────────────────────────── */
    .notif-state { display: inline-block; font-size: .72rem; padding: .1rem .45rem; border-radius: .25rem; margin-left: .4rem; vertical-align: middle; }
    .notif-state-ack      { background: #d1fae5; color: #065f46; }
    .notif-state-snoozed  { background: #fef9c3; color: #713f12; }
    .notif-state-pending  { background: #dbeafe; color: #1e40af; }
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
    /* ── View preset dropdown ─────────────────────────────────────── */
    #view-preset-select { font-size: .82rem; padding: .2rem .4rem; border: 1px solid var(--line); border-radius: .35rem; background: var(--bg); color: var(--text); cursor: pointer; }
    /* ── Search result count ──────────────────────────────────────── */
    #search-count { font-size: .77rem; color: var(--muted); margin-left: .35rem; white-space: nowrap; }
    /* ── Heatmap tooltip ─────────────────────────────────────────── */
    .hm-tooltip { position:fixed; background:rgba(0,0,0,.78); color:#fff; font-size:.75rem; padding:.25rem .55rem; border-radius:.3rem; pointer-events:none; z-index:9999; display:none; }
    /* ── Chart group buttons ─────────────────────────────────────── */
    .chart-group-bar { display:flex; gap:.25rem; padding:.25rem 1rem; border-bottom:1px solid var(--line); }
    .chart-group-btn { font-size:.73rem; padding:.15rem .5rem; border:1px solid var(--line); border-radius:1rem; background:var(--bg); cursor:pointer; color:var(--text); }
    .chart-group-btn.active { background:var(--accent); color:#fff; border-color:var(--accent); }
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
    .source { color: var(--muted); font-size: .78rem; white-space: nowrap; }
    .side { display: grid; gap: 1rem; align-content: start; min-width: 0; }
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
      border: 1px solid #e6bbb3;
      border-radius: .45rem;
      color: var(--danger);
      background: #fff8f6;
      font-family: Consolas, "Courier New", monospace;
      font-size: .86rem;
    }
    .notification-row {
      padding: .65rem;
      border: 1px solid var(--line);
      border-radius: .55rem;
      background: #fff;
    }
    .messages-mode main,
    .status-mode main {
      grid-template-columns: minmax(0, 1fr) minmax(18rem, 23rem);
    }
    .messages-mode .status-section,
    .messages-mode .agenda-section,
    .status-mode .item-section,
    .status-mode .editor-section,
    .status-mode .agenda-section,
    .status-mode .notifications-section {
      display: none;
    }
    .status-mode main {
      grid-template-columns: minmax(0, 42rem);
      justify-content: center;
    }
    .status-mode .side {
      display: block;
    }
    .status-mode .status-section {
      display: block;
    }
    .display-mode {
      background: #0f1412;
      color: #edf4ef;
      font-size: clamp(18px, 1.4vw, 28px);
    }
    .display-mode header {
      max-width: none;
      padding: 1.2rem 2rem;
    }
    .display-mode h1 { font-size: clamp(2.6rem, 6vw, 5rem); }
    .display-mode .subtitle { color: #aebbb4; }
    .display-mode main {
      max-width: none;
      grid-template-columns: minmax(0, 1fr) minmax(20rem, 28rem);
      padding: 0 2rem 2rem;
    }
    .display-mode section,
    .display-mode .item {
      background: #151c19;
      border-color: #31413b;
    }
    .display-mode .section-head { border-color: #31413b; }
    .display-mode .toolbar,
    .display-mode .editor-section,
    .display-mode header button { display: none; }
    .display-mode .pill {
      background: #23322d;
      color: #edf4ef;
    }
    .display-mode .meta,
    .display-mode .source,
    .display-mode .empty,
    .display-mode .note { color: #aebbb4; }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .side { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
      .side section:first-child { grid-column: 1 / -1; }
      .display-mode main { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      header { align-items: start; }
      main, header { padding-left: .75rem; padding-right: .75rem; }
      .section-head { align-items: stretch; flex-direction: column; }
      .toolbar > *, .actions > *, .section-head button { flex: 1 1 100%; }
      .side { grid-template-columns: 1fr; }
      .item { grid-template-columns: auto auto minmax(0, 1fr); }
      .source { grid-column: 1 / -1; }
      form.stack { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>life.txt</h1>
      <p class="subtitle">Plain text tasks, schedule, presence, and notes.</p>
    </div>
    <div class="toolbar">
      <select id="view-preset-select" title="Switch named view preset" onchange="applyViewPreset(this.value)">
        <option value="">— View —</option>
      </select>
      <button id="stats-btn" class="secondary" onclick="toggleStats()" title="Toggle statistics panel (s)">Stats</button>
      <button id="notif-btn" class="secondary" onclick="toggleNotifPanel()" title="Toggle notifications / enable browser alerts">Notifications</button>
      <button id="refresh-btn" class="secondary" onclick="triggerRefresh()" title="Refresh (r)">Refresh</button>
      <button class="secondary" onclick="openHelpModal()" title="Keyboard shortcuts">?</button>
      <button id="git-status-badge" class="git-badge" style="display:none" onclick="openGitModal()"></button>
    </div>
  </header>
  <main>
    <section class="item-section">
      <div class="section-head">
        <h2>Items</h2>
        <div class="toolbar">
          <input id="search" placeholder="Search (/)"><span id="search-count"></span>
          <label class="inline"><input id="open-only" type="checkbox"> Open</label>
          <select id="kind">
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
          <select id="sort">
            <option value="line">Line</option>
            <option value="time">Time</option>
            <option value="title">Title</option>
            <option value="type">Type</option>
            <option value="status">Status</option>
            <option value="source">Source</option>
          </select>
          <select id="order">
            <option value="asc">Asc</option>
            <option value="desc">Desc</option>
          </select>
          <input id="limit" inputmode="numeric" placeholder="Limit">
          <button onclick="loadItems()">Apply</button>
        </div>
      </div>
      <div class="quick-add-bar" id="quick-add-bar" style="display:none">
        <input id="quick-line" placeholder="[ ] T My_task  due:tomorrow  project:work" autocomplete="off">
        <span id="quick-check-msg" class="check-msg"></span>
        <button onclick="quickAddLine()">Add</button>
        <span class="hint">q or Escape to close</span>
      </div>
      <div class="filter-bar" id="status-filter-bar">
        <button class="filter-btn active" onclick="setStatusFilter('')">All</button>
        <button class="filter-btn" onclick="setStatusFilter('[ ]')">○ Open</button>
        <button class="filter-btn" onclick="setStatusFilter('[/]')">◑ In Progress</button>
        <button class="filter-btn" onclick="setStatusFilter('[x]')">✓ Done</button>
        <button class="filter-btn" onclick="setStatusFilter('[-]')">✕ Cancelled</button>
        <button class="filter-btn" onclick="setBlockedFilter()" title="Items blocked by open dependencies">⚡ Blocked</button>
      </div>
      <div id="filter-chips" class="filter-chips"></div>
      <div id="stats-summary" class="stats-summary" style="display:none"></div>
      <div id="diagnostics"></div>
      <div id="items" class="content"></div>
    </section>
    <section class="stats-section" style="display:none">
      <div class="section-head">
        <h2>Statistics</h2>
        <button class="secondary" onclick="refreshCharts()">Refresh</button>
      </div>
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
      </div>
      <div id="chart-container" style="padding:.75rem 1rem">
        <div class="chart-panel"><canvas id="main-chart"></canvas></div>
      </div>
    </section>
    <div class="side">
      <section class="editor-section">
        <div class="section-head">
          <h2 id="editor-heading">New Item</h2>
          <button class="secondary" onclick="newItem()">New</button>
        </div>
        <form class="stack" onsubmit="saveItem(event)">
          <label>Status
            <select id="edit-status">
              <option>[ ]</option><option>[/]</option><option>[x]</option>
              <option>[-]</option><option>[>]</option><option>[?]</option><option>[N]</option>
            </select>
          </label>
          <label>Type
            <select id="edit-type">
              <option>T</option><option>E</option><option>D</option><option>R</option>
              <option>H</option><option>N</option><option>S</option><option>M</option><option>J</option>
            </select>
          </label>
          <label class="wide">Title
            <input id="edit-title" required>
          </label>
          <label class="wide">Details
            <div id="type-hints" class="type-hints" style="display:none"></div>
            <textarea id="edit-details" placeholder="due:2026-06-12&#10;project:research"></textarea>
          </label>
          <div id="editor-note" class="note wide">Create a new item or select an editable row.</div>
          <div id="import-raw-row">
            <label class="wide" style="margin-top:.35rem">Import raw line
              <input id="import-raw-input" placeholder="[ ] T Task_title due:2026-06-28 project:work" autocomplete="off">
            </label>
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
      </section>
      <section class="agenda-section">
        <div class="section-head"><h2>Agenda</h2></div>
        <div id="agenda" class="stack"></div>
      </section>
      <section class="status-section">
        <div class="section-head"><h2>Status</h2></div>
        <div id="status" class="stack"></div>
      </section>
      <section class="notifications-section">
        <div class="section-head">
          <h2>Notifications</h2>
          <div id="notif-permission-badge"></div>
        </div>
        <div id="notif-permission-bar" class="notif-permission" style="display:none"></div>
        <div id="notifications" class="stack"></div>
      </section>
    </div>
  </main>
  <!-- Detail Side Drawer -->
  <aside id="detail-drawer" class="detail-drawer" role="complementary" aria-label="Item detail">
    <div class="drawer-head">
      <h3 id="drawer-title">Item Detail</h3>
      <div style="display:flex;gap:.4rem">
        <button class="secondary" onclick="drawerMarkDone()" id="drawer-done-btn" disabled>Done</button>
        <button class="secondary" onclick="drawerEdit()">Edit</button>
        <button class="danger" onclick="drawerDelete()" id="drawer-delete-btn" disabled>Delete</button>
        <button class="secondary" onclick="closeDrawer()">✕</button>
      </div>
    </div>
    <div class="drawer-body" id="drawer-body"></div>
  </aside>

  <!-- Toast container -->
  <div id="toast-container"></div>
  <div id="hm-tooltip" class="hm-tooltip"></div>

  <!-- Keyboard Help Modal -->
  <div class="modal-backdrop" id="help-modal" onclick="if(event.target===this)closeHelpModal()">
    <div class="modal">
      <h3>Keyboard shortcuts</h3>
      <table>
        <tr><td>/</td><td>Focus search</td></tr>
        <tr><td>n</td><td>New item (focus editor title)</td></tr>
        <tr><td>q</td><td>Toggle quick-add bar</td></tr>
        <tr><td>r</td><td>Refresh all</td></tr>
        <tr><td>s</td><td>Toggle statistics panel</td></tr>
        <tr><td>Esc</td><td>Close drawer / blur input</td></tr>
        <tr><td>[ / ]</td><td>Prev / next item in drawer</td></tr>
        <tr><td>&lt; / &gt;</td><td>Prev / next status filter</td></tr>
        <tr><td>?</td><td>Show / hide this help</td></tr>
      </table>
      <div class="actions" style="margin-top:1rem"><button onclick="closeHelpModal()">Close</button></div>
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
    let refreshTimer = null;
    let notificationTimer = null;
    let browserNotificationsEnabled = false;
    let seenNotifications = new Set();
    let appConfig = {};

    async function api(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }
    function detailText(details) {
      return Object.entries(details || {}).flatMap(([key, values]) =>
        values.map(value => `${key}:${value}`)
      ).join(" ");
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
    function isDisplayMode() {
      const params = query();
      return firstParam(params, ["mode", "view"], "").toLowerCase() === "display";
    }
    function currentView() {
      const params = query();
      const value = firstParam(params, ["view", "mode"], "").toLowerCase();
      if (["messages", "status", "display"].includes(value)) return value;
      return "";
    }
    function applyPresetToUrl() {
      const params = query();
      // Support ?view=NAME as alias for ?preset=NAME
      if (params.get("view") && !params.get("preset")) {
        params.set("preset", params.get("view"));
        history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      }
      const presetName = params.get("preset");
      if (!presetName || params.get("_preset_applied") === presetName) return;
      const preset = appConfig?.views?.[presetName];
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
      document.body.classList.toggle("messages-mode", currentView() === "messages");
      document.body.classList.toggle("status-mode", currentView() === "status");
      document.getElementById("search").value = firstParam(params, ["text", "q"], "");
      const fallbackKind = currentView() === "messages" ? "M" : (currentView() === "status" ? "S" : "");
      const fallbackSort = currentView() === "messages" || currentView() === "status" ? "time" : (appConfig?.web?.default_sort || "line");
      document.getElementById("kind").value = firstParam(params, ["kind", "type"], fallbackKind);
      document.getElementById("sort").value = firstParam(params, ["sort"], fallbackSort);
      document.getElementById("order").value = firstParam(params, ["order"], appConfig?.web?.default_order || "asc");
      document.getElementById("open-only").checked = boolParam(params, ["open", "open_only"]);
      document.getElementById("limit").value = firstParam(params, ["limit"], appConfig?.web?.default_limit || "");
      syncStatusFilterBarsFromUrl();
      configureAutoRefresh();
      configureNotificationPolling();
    }
    function configureAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const seconds = Number(firstParam(query(), ["refresh"], isDisplayMode() ? "60" : ""));
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
      return result;
    }
    function updateUrlFromControls() {
      const current = query();
      const next = new URLSearchParams();
      for (const key of [
        "mode", "view", "refresh", "around", "window", "from", "to",
        "status", "project", "tag", "tag_all", "exclude_tag", "user", "team",
        "person", "owner", "assignee", "attendee",
        "sender", "recipient", "after", "before"
      ]) {
        if (current.has(key)) next.set(key, current.get(key));
      }
      const text = document.getElementById("search").value;
      const kind = document.getElementById("kind").value;
      const limit = document.getElementById("limit").value;
      if (text) next.set("text", text);
      if (kind) next.set("kind", kind);
      if (document.getElementById("open-only").checked) next.set("open_only", "true");
      if (limit) next.set("limit", limit);
      next.set("sort", document.getElementById("sort").value);
      next.set("order", document.getElementById("order").value);
      history.replaceState(null, "", `${location.pathname}?${next.toString()}`);
    }
    async function loadItems() {
      updateUrlFromControls();
      const params = itemQueryParams();
      const data = await api(`/api/items?${params}`);
      currentItems = data.items;
      renderDiagnostics(data.diagnostics);
      renderItems(data.items);
      if (selectedItem) {
        const match = data.items.find(item => item.line === selectedItem.line && item.editable);
        if (match) selectItem(match);
      }
    }
    function renderDiagnostics(diagnostics) {
      document.getElementById("diagnostics").innerHTML = diagnostics
        .map(d => `<div class="diagnostic">${escapeHtml(d.severity)} ${escapeHtml(d.code)}: ${escapeHtml(d.message)}</div>`)
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
    function renderItems(items) {
      const root = document.getElementById("items");
      root.innerHTML = items.length ? "" : `<div class="empty">No items found.</div>`;
      renderSummary(items);
      renderFilterChips();
      updateSearchCount(items.length);
      for (const item of items) {
        const titleHtml = safeMarkdownHtml(item?.markdown?.title, item.title);
        const previewHtml = firstMarkdownDetail(item, "body") || firstMarkdownDetail(item, "note");
        const preview = previewHtml ? `<div class="markdown body-preview">${previewHtml}</div>` : "";
        const statusCls = STATUS_CLASS[item.status] || "status-note";
        const statusLabel = STATUS_LABEL[item.status] || item.status;
        const typeCls = "type-" + (item.type || "N");
        const dueCls = itemDueSoonClass(item);
        const refLinks = buildRefLinksHtml(item.details);
        const parentInd = buildParentIndicator(item.details);
        const node = document.createElement("button");
        node.type = "button";
        node.className = "item" + (dueCls ? " " + dueCls : "");
        if (selectedItem && item.line === selectedItem.line && item.editable === selectedItem.editable) {
          node.classList.add("selected");
        }
        node.addEventListener("click", (e) => {
          if (e.target.closest(".ref-link")) return;
          selectItem(item);
        });
        node.innerHTML = `
          <span class="status-badge ${statusCls}" title="${escapeHtml(item.status)}">${escapeHtml(statusLabel)}</span>
          <span class="type-badge ${typeCls}">${escapeHtml(item.type)}</span>
          <div>
            <div class="title markdown">${titleHtml}${parentInd}</div>
            <div class="meta">${escapeHtml(detailText(item.details))}${refLinks}</div>
            ${preview}
          </div>
          <span class="source">${escapeHtml(item.source || `line ${item.line || ""}`)}${item.generated ? " / generated" : ""}${item.editable ? "" : " / read-only"}</span>
        `;
        root.appendChild(node);
      }
      const queryText = document.getElementById("search").value.trim();
      if (queryText) {
        root.querySelectorAll(".title.markdown").forEach(el => {
          el.innerHTML = highlightText(el.innerHTML, queryText);
        });
      }
    }
    function selectItem(item) {
      if (isDisplayMode()) return;
      selectedItem = item;
      document.getElementById("editor-heading").textContent = item.editable ? `Edit line ${item.line}` : "Read-only item";
      document.getElementById("edit-status").value = item.status;
      document.getElementById("edit-type").value = item.type;
      document.getElementById("edit-title").value = item.title;
      document.getElementById("edit-details").value = detailsToText(item.details);
      document.getElementById("save-button").textContent = "Save";
      document.getElementById("delete-button").disabled = !item.editable;
      document.getElementById("editor-note").textContent = item.editable
        ? "Editing the writable file. Save replaces this item line."
        : "This item comes from a read-only input or generated file.";
      setEditorDisabled(!item.editable);
      renderItems(currentItems);
      openDrawer(item);
    }
    function newItem() {
      selectedItem = null;
      document.getElementById("editor-heading").textContent = "New Item";
      document.getElementById("edit-status").value = "[ ]";
      document.getElementById("edit-type").value = "T";
      document.getElementById("edit-title").value = "";
      document.getElementById("edit-details").value = "";
      document.getElementById("save-button").textContent = "Create";
      document.getElementById("delete-button").disabled = true;
      document.getElementById("editor-note").textContent = "Create a new item or select an editable row.";
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
      if (selectedItem && selectedItem.editable) {
        await api(`/api/items/${selectedItem.line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
      } else {
        await api("/api/items", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        newItem();
      }
      await refreshAll();
    }
    async function deleteSelected() {
      if (!selectedItem || !selectedItem.editable) return;
      if (!confirm(`Delete line ${selectedItem.line}?`)) return;
      await api(`/api/items/${selectedItem.line}`, {method: "DELETE"});
      newItem();
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
      const data = await api(`/api/agenda?${agendaParams}`);
      const node = document.getElementById("agenda");
      node.innerHTML = data.records.length ? "" : `<div class="empty">No agenda items.</div>`;
      const maxAgenda = Number(firstParam(query(), ["agenda_limit"], "8"));
      for (const record of data.records.slice(0, Number.isFinite(maxAgenda) ? maxAgenda : 8)) {
        const dueCls = agendaDueSoonClass(record);
        const borderStyle = dueCls === "overdue" ? "border-left:3px solid #c0392b;" : dueCls === "due-soon" ? "border-left:3px solid #e67e22;" : "";
        node.insertAdjacentHTML(
          "beforeend",
          `<div style="${borderStyle}padding-left:.45rem"><span class="pill">${escapeHtml(record.when)}</span><div class="title">${escapeHtml(record.title)}</div></div>`
        );
      }
    }
    async function loadStatus() {
      const params = query();
      const statusParams = new URLSearchParams();
      statusParams.set("active", firstParam(params, ["active"], "true"));
      if (params.has("person")) statusParams.set("person", params.get("person"));
      const data = await api(`/api/status?${statusParams}`);
      const node = document.getElementById("status");
      node.innerHTML = data.records.length ? "" : `<div class="empty">No active status.</div>`;
      for (const record of data.records) {
        node.insertAdjacentHTML(
          "beforeend",
          `<div><span class="pill">${escapeHtml(record.person)}</span> ${escapeHtml(record.state)}<div class="meta">${escapeHtml(record.title)}</div></div>`
        );
      }
    }
    async function loadConfig() {
      appConfig = await api("/api/config");
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
          </div>
          <div id="${snoozeRowId}" class="snooze-inline" style="display:none">
            <input id="${snoozeInputId}" value="${escapeHtml(snoozeDefault)}" placeholder="30m / 1h / 2h">
            <button class="secondary" type="button" onclick="snoozeMessageCustom(${escapeHtml(jsLiteral(record.id))}, ${escapeHtml(jsLiteral(snoozeInputId))})">Go</button>
          </div>
        ` : "";
        const stateBadge = notifStateBadge(record);
        node.insertAdjacentHTML(
          "beforeend",
          `<div class="notification-row"><span class="pill">${escapeHtml(record.when)}</span>${stateBadge}<div class="title">${escapeHtml(record.title)}</div><div class="meta">${escapeHtml(record.sender)} → ${escapeHtml((record.recipients || []).join(", "))}</div>${actions}</div>`
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
    async function refreshAll() {
      await Promise.all([loadItems(), loadAgenda(), loadStatus(), loadNotifications()]);
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
      const active = document.activeElement;
      const inInput = active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
      if (e.key === "Escape") {
        if (document.getElementById("help-modal").classList.contains("open")) { closeHelpModal(); return; }
        if (document.getElementById("git-modal").classList.contains("open")) { closeGitModal(); return; }
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
        document.getElementById("edit-title").focus();
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        document.getElementById("search").focus();
        return;
      }
      if (e.key === "q") { e.preventDefault(); toggleQuickAdd(); return; }
      if (e.key === "r" || e.key === "R") { e.preventDefault(); refreshAll(); return; }
      if (e.key === "s" || e.key === "S") { e.preventDefault(); toggleStats(); return; }
    });

    // ── Help modal ─────────────────────────────────────────────────
    function openHelpModal() { document.getElementById("help-modal").classList.add("open"); }
    function closeHelpModal() { document.getElementById("help-modal").classList.remove("open"); }

    // ── Toast system ────────────────────────────────────────────────
    function showToast(message, type = "info", duration = 3500) {
      const container = document.getElementById("toast-container");
      const el = document.createElement("div");
      el.className = "toast " + type;
      el.textContent = message;
      container.appendChild(el);
      setTimeout(() => el.remove(), duration);
    }

    // ── Detail side-drawer ─────────────────────────────────────────
    let drawerItem = null;

    function openDrawer(item) {
      drawerItem = item;
      const drawer = document.getElementById("detail-drawer");
      const body = document.getElementById("drawer-body");
      const title = document.getElementById("drawer-title");
      const doneBt = document.getElementById("drawer-done-btn");
      const delBt = document.getElementById("drawer-delete-btn");
      const isDone = ["[x]", "[-]"].includes(item.status);
      const statusCls = STATUS_CLASS[item.status] || "status-note";
      const statusLbl = STATUS_LABEL[item.status] || item.status;
      const typeCls = "type-" + (item.type || "N");
      title.innerHTML = `<span class="status-badge ${statusCls}">${escapeHtml(statusLbl)}</span>
        <span class="type-badge ${typeCls}" style="margin-left:.35rem">${escapeHtml(item.type)}</span>
        <span style="margin-left:.4rem;font-weight:700">${escapeHtml(item.title)}</span>`;
      doneBt.disabled = !item.editable || isDone;
      delBt.disabled = !item.editable;
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
      const sourceHtml = `<div class="drawer-section-title">Source</div>
        <div style="font-size:.82rem;color:var(--muted)">${escapeHtml(item.source || "")} line ${escapeHtml(String(item.line || ""))}</div>`;
      body.innerHTML = fieldsHtml + bodyHtml +
        `<div id="drawer-deps"><div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty dep-loading">Loading…</div></div>` +
        sourceHtml;
      drawer.classList.add("open");
      loadDependencyLinks(item);
    }

    const DEP_RELATION_LABEL = {
      depends_on: "depends on", blocks: "blocks", parent: "child of",
      related: "related", ref: "ref",
    };
    const STATUS_ICON = {"[ ]": "○", "[x]": "✓", "[-]": "✕", "[/]": "◑", "[>]": "→", "[?]": "?", "[!]": "!"};

    async function loadDependencyLinks(item) {
      const itemId = item?.id || (item?.details?.id?.[0]);
      const container = document.getElementById("drawer-deps");
      if (!container) return;
      if (!itemId) {
        container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">No ID — cannot look up links.</div>`;
        return;
      }
      try {
        const data = await api(`/api/links?id=${encodeURIComponent(itemId)}&direction=both`);
        const records = data.records || [];
        if (!records.length) {
          container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">No links.</div>`;
          return;
        }
        const outgoing = records.filter(r => r.source_id === itemId);
        const incoming = records.filter(r => r.target_id === itemId && r.source_id !== itemId);
        let html = `<div class="drawer-section-title">Dependencies &amp; Links (${records.length})</div><div class="dep-graph">`;

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

    function closeDrawer() {
      document.getElementById("detail-drawer").classList.remove("open");
      drawerItem = null;
    }

    function drawerEdit() {
      if (!drawerItem) return;
      selectItem(drawerItem);
      closeDrawer();
    }

    async function drawerMarkDone() {
      if (!drawerItem || !drawerItem.editable) return;
      await api(`/api/items/${drawerItem.line}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({...drawerItem.details && {details: drawerItem.details}, status: "[x]", type: drawerItem.type, title: drawerItem.title}),
      });
      showToast("Marked done.", "success");
      closeDrawer();
      await refreshAll();
    }

    async function drawerDelete() {
      if (!drawerItem || !drawerItem.editable) return;
      if (!confirm(`Delete "${drawerItem.title}"?`)) return;
      await api(`/api/items/${drawerItem.line}`, {method: "DELETE"});
      showToast("Item deleted.", "info");
      closeDrawer();
      newItem();
      await refreshAll();
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
    document.addEventListener("DOMContentLoaded", () => {
      const qInput = document.getElementById("quick-line");
      if (qInput) {
        qInput.addEventListener("input", () => {
          clearTimeout(_checkTimer);
          _checkTimer = setTimeout(() => liveCheckLine(qInput.value), 280);
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
      const badge = document.getElementById("notif-permission-badge");
      if (!("Notification" in window)) { if (bar) { bar.textContent = "Browser notifications not supported."; bar.style.display = ""; } return; }
      const perm = Notification.permission;
      const classes = {granted: "notif-perm-granted", denied: "notif-perm-denied", default: "notif-perm-default"};
      const labels = {granted: "Notifications: granted", denied: "Notifications: denied — check browser settings", default: "Notifications: not yet requested"};
      if (bar) {
        bar.className = "notif-permission " + (classes[perm] || "");
        bar.textContent = labels[perm] || perm;
        bar.style.display = "";
      }
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
      document.getElementById("git-modal").classList.add("open");
      document.getElementById("git-commit-msg").focus();
      const statusEl = document.getElementById("git-status-output");
      if (statusEl) {
        statusEl.textContent = "Loading…";
        try {
          const data = await api("/api/git/status");
          statusEl.textContent = (data.stdout || "(clean)").trim() || "(clean)";
        } catch(e) { statusEl.textContent = "Could not load status: " + e.message; }
      }
    }
    function closeGitModal() { document.getElementById("git-modal").classList.remove("open"); }
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
    let statsVisible = false;

    let notifPanelVisible = true;

    function toggleStats() {
      statsVisible = !statsVisible;
      const sec = document.querySelector(".stats-section");
      if (sec) sec.style.display = statsVisible ? "" : "none";
      if (statsVisible) loadChart("tasks");
      const btn = document.getElementById("stats-btn");
      if (btn) btn.classList.toggle("btn-active", statsVisible);
    }

    function toggleNotifPanel() {
      const sec = document.querySelector(".notifications-section");
      if (!sec) { enableBrowserNotifications(); return; }
      notifPanelVisible = !notifPanelVisible;
      sec.style.display = notifPanelVisible ? "" : "none";
      const btn = document.getElementById("notif-btn");
      if (btn) {
        btn.classList.toggle("btn-active", notifPanelVisible);
        updateNotifBtnLabel();
      }
      if (notifPanelVisible && Notification.permission === "default") {
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
            scales: {y: {beginAtZero: true}},
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

    // ── Status quick-filter buttons ───────────────────────────────
    function syncStatusFilterBtns(activeValue) {
      const btns = document.querySelectorAll("#status-filter-bar .filter-btn");
      const values = ["", "[ ]", "[/]", "[x]", "[-]", "__blocked__"];
      btns.forEach((btn, i) => btn.classList.toggle("active", values[i] === activeValue));
    }

    // ── Search result count ────────────────────────────────────────
    function updateSearchCount(count) {
      const el = document.getElementById("search-count");
      if (!el) return;
      el.textContent = count != null ? `(${count})` : "";
    }

    // ── View preset selector ───────────────────────────────────────
    function populateViewPresets() {
      const sel = document.getElementById("view-preset-select");
      if (!sel || !appConfig?.views) return;
      for (const name of Object.keys(appConfig.views)) {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        sel.appendChild(opt);
      }
      const current = query().get("preset") || query().get("view");
      if (current) sel.value = current;
    }
    function applyViewPreset(name) {
      if (!name) return;
      const params = query();
      const preset = appConfig?.views?.[name];
      if (!preset) return;
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(preset)) next.set(key, value);
      next.set("preset", name);
      next.delete("_preset_applied");
      history.replaceState(null, "", `${location.pathname}?${next.toString()}`);
      savePresetToStorage(name);
      applyPresetToUrl();
      applyUrlToControls();
      syncStatusFilterBarsFromUrl();
      refreshAll();
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
      const params = query();
      const statusParam = params.get("status");
      const isBlocked = params.get("blocked") === "true";
      const active = isBlocked ? "__blocked__" : (statusParam || "");
      syncStatusFilterBtns(active);
    }
    function cycleStatusFilter(direction) {
      const params = query();
      const statusParam = params.get("status");
      const isBlocked = params.get("blocked") === "true";
      const current = isBlocked ? "__blocked__" : (statusParam || "");
      const idx = STATUS_CYCLE.indexOf(current);
      const next = STATUS_CYCLE[(idx + direction + STATUS_CYCLE.length) % STATUS_CYCLE.length];
      if (next === "__blocked__") {
        setBlockedFilter();
      } else {
        setStatusFilter(next);
      }
    }

    // ── Blocked filter: use server-side ?blocked=true ─────────────
    function setBlockedFilter() {
      const params = query();
      params.delete("status");
      params.set("blocked", "true");
      params.set("open_only", "true");
      document.getElementById("open-only").checked = true;
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadItems();
      syncStatusFilterBtns("__blocked__");
    }

    // ── setStatusFilter: clear blocked when switching to non-blocked ──
    function setStatusFilter(statusValue) {
      const params = query();
      params.delete("blocked");
      if (statusValue) {
        params.set("status", statusValue);
        params.delete("open_only");
        document.getElementById("open-only").checked = false;
      } else {
        params.delete("status");
      }
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
      syncStatusFilterBtns(statusValue);
    }

    // ── Git log display after commit ──────────────────────────────
    async function loadGitLog() {
      if (!appConfig?.git?.enable_api) return;
      try {
        const data = await api("/api/git/log?n=3");
        const commits = data.commits || [];
        if (!commits.length) return;
        let html = `<div style="margin-top:.5rem"><div class="drawer-section-title" style="font-size:.72rem">Recent commits</div>`;
        for (const c of commits) {
          html += `<div class="git-log-entry"><span class="git-log-hash">${escapeHtml(c.hash)}</span><span class="git-log-msg">${escapeHtml(c.message)}</span></div>`;
        }
        html += `</div>`;
        const out = document.getElementById("git-output");
        if (out) {
          out.insertAdjacentHTML("afterend", html);
        }
      } catch(_) {}
    }

    // ── Persist view preset in localStorage ──────────────────────
    function savePresetToStorage(name) {
      try { localStorage.setItem("lifetxt_preset", name); } catch(_) {}
    }
    function loadPresetFromStorage() {
      try { return localStorage.getItem("lifetxt_preset") || ""; } catch(_) { return ""; }
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
          : `event.stopPropagation();selectItem(currentItems.find(i=>i.line===${Number(details?._line||0)})||drawerItem)`;
        return `<span class="ref-link" onclick="${onclick}" title="${escapeHtml(key)}">${escapeHtml(label)}</span>`;
      }).join("");
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
        const checkData = await api("/api/check-line", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        if (!checkData.ok) {
          const errs = (checkData.diagnostics || []).filter(d => d.severity === "error");
          showToast("Invalid: " + (errs[0]?.message || "parse error"), "error");
          return;
        }
        // Parse fields from the raw line
        const m = line.match(/^(\[.\])\s+(\w+)\s+(\S+)([\s\S]*)$/);
        if (!m) { showToast("Could not parse line structure.", "error"); return; }
        const [, status, type, title, rest] = m;
        document.getElementById("edit-status").value = status;
        document.getElementById("edit-type").value = type;
        document.getElementById("edit-title").value = title.replace(/_/g, " ");
        const detailsRaw = rest.trim().replace(/\s{2,}/g, "\n").trim();
        document.getElementById("edit-details").value = detailsRaw.replace(/(\w+):(?=\S)/g, "$1:");
        updateTypeHints(type);
        toggleImportRaw(false);
        if (input) input.value = "";
        showToast("Form populated from raw line.", "success");
      } catch(e) {
        showToast("Import error: " + e.message, "error");
      }
    }

    loadConfig().then(() => {
      applyPresetToUrl();
      applyUrlToControls();
      updateNotifPermissionDisplay();
      updateNotifBtnLabel();
      updateTypeHints(document.getElementById("edit-type").value);
      populateViewPresets();
      syncStatusFilterBarsFromUrl();
      // Restore preset from localStorage if no URL param
      const storedPreset = loadPresetFromStorage();
      if (storedPreset && !query().get("preset") && !query().get("view") && appConfig?.views?.[storedPreset]) {
        applyViewPreset(storedPreset);
      }
      startGitPolling();
      return refreshAll();
    }).catch(error => {
      document.body.insertAdjacentHTML("beforeend", `<pre class="diagnostic">${escapeHtml(error.message)}</pre>`);
    });
  </script>
</body>
</html>
"""
