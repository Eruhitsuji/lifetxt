import contextlib
import os
import sys
from collections import OrderedDict
from datetime import datetime, time

from .atomic import atomic_write_text
from .completion import (
    VALUE_KINDS as _COMPLETION_KINDS,
    candidates as completion_candidates,
)
from .agenda import (
    agenda_records,
    filter_items,
    next_repeat_occurrence,
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
from .diagnostic_contract import diagnostics_to_output
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
from .timezone_policy import local_now_naive, today as timezone_today
from .timeutil import format_datetime as format_life_datetime, parse_date_or_datetime
from .validator import validate_item
from .web_read_service import find_item_by_id as _service_find_item_by_id
from .web_read_service import limit_items as _service_limit_items
from .web_read_service import read_life_inputs as _service_read_life_inputs
from .web_read_service import sort_items as _service_sort_items
from .web_read_service import sort_key_for_item as _service_sort_key_for_item
from .web_assets import HTML_PAGE
from .web_routes_analytics import register_analytics_routes
from .web_routes_git import register_git_routes


#: Commands the browser implements. Everything else in the shared catalog is
#: terminal-only and the palette says so instead of failing silently.
WEB_COMMANDS = frozenset(
    [
        "help",
        "view",
        "next",
        "search",
        "project",
        "context",
        "tag",
        "sort",
        "clear",
        "goto",
        "mark",
        "done",
        "status",
        "set",
        "due",
        "assign",
        "add",
        "delete",
        "state",
        "now",
        "timer",
        "export",
        "stats",
        "detail",
        "reload",
        "theme",
    ]
)

#: Why a command is unavailable, or how the browser differs from the terminal.
WEB_COMMAND_NOTES = {
    "edit": "Opens $EDITOR, which only exists at a terminal. Use the record editor instead.",
    "quit": "Close the browser tab.",
    "limit": "The browser paginates instead; use the filter bar.",
    "window": "Use the Agenda range controls.",
    "undo": "Use the undo toast or the undo history panel.",
    "mark": "Selects rows; the browser uses checkboxes and the x key.",
    "detail": "Opens the detail drawer for the selected record.",
}


def _timer_args(path, item_id, config):
    import argparse

    return argparse.Namespace(path=path, item_id=item_id, note=None, config_data=config)


@contextlib.contextmanager
def _quiet_stdout():
    """The timer helpers report to stdout for CLI use; a server must not."""
    import io as _io

    buffer = _io.StringIO()
    original = sys.stdout
    sys.stdout = buffer
    try:
        yield buffer
    finally:
        sys.stdout = original


def create_app(paths=None, writable_path=None, config=None, read_only=False):
    try:
        from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
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
    transactions_config = (
        app.state.config.get("transactions")
        if isinstance(app.state.config.get("transactions"), dict)
        else {}
    )
    if not read_only and transactions_config.get("preflight_on_startup"):
        from .transaction_admin import preflight_report
        from .transaction_journal import journal_directory

        report = preflight_report(
            journal_directory(
                config=app.state.config, writable_path=app.state.writable_path
            ),
            config=app.state.config,
            create=True,
        )
        if not report["ok"]:
            raise RuntimeError(
                "Transaction startup preflight failed: %s" % "; ".join(report["errors"])
            )
    app.state.transaction_preflight = (
        None
        if read_only
        else (report if transactions_config.get("preflight_on_startup") else None)
    )

    _READ_ONLY_ALLOWED_PATHS = frozenset(
        {
            "/api/check-line",
            "/api/items/parse",
            "/api/remote/v1/browser/login",
            "/api/remote/v1/browser/logout",
            "/api/remote/v1/write-check",
        }
    )

    @app.get("/api/time")
    def get_time(client_time=None):
        from .clock_skew import clock_skew_report

        return clock_skew_report(client_time, config=app.state.config)

    @app.get("/api/transactions/preflight")
    def get_transaction_preflight(create=False):
        from .transaction_admin import preflight_report
        from .transaction_journal import journal_directory

        return preflight_report(
            journal_directory(
                config=app.state.config, writable_path=app.state.writable_path
            ),
            config=app.state.config,
            create=bool(create and not app.state.read_only),
        )

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
            if request.url.path in (
                "/",
                "/api/health",
                "/remote",
            ) or request.url.path.startswith("/api/remote/v1/"):
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
                detail=diagnostics_to_output(diagnostics),
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
        fuzzy=False,
        after=None,
        before=None,
        sort="line",
        order="asc",
        limit=None,
    ):
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        range_start, range_end = parse_optional_time_range(after, before)
        open_only_flag = _bool_query(open_only)
        blocked_flag = _bool_query(blocked)
        filtered = filter_items(
            items,
            open_only=open_only_flag or blocked_flag,
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
            fuzzy=_bool_query(fuzzy),
        )
        if blocked_flag:
            key = id_key_from_config(app.state.config)
            blocker_records = dependency_blocker_records(items, key=key)
            blocked_item_ids = set(
                r["blocked_id"] for r in blocker_records if r.get("blocked_id")
            )
            blocked_lines = set(
                r["blocked_line"]
                for r in blocker_records
                if r.get("blocked_line") is not None
            )
            filtered = [
                item
                for item in filtered
                if (
                    item.details.get(key)
                    and str(item.details[key][0]) in blocked_item_ids
                )
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

    @app.get("/api/complete")
    def get_complete(
        kind=Query(...),
        prefix="",
        limit=20,
    ):
        """Completion candidates for the browser, from the same source as the
        shell scripts and the TUI. Typing drives this, so an unreadable file
        yields the built-in candidates rather than an error."""
        try:
            requested = int(limit)
        except (TypeError, ValueError):
            requested = 20
        requested = max(1, min(requested, 200))

        if kind not in _COMPLETION_KINDS:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UNKNOWN_KIND",
                    "message": "Unknown completion kind %r." % kind,
                    "detail": {"supported": list(_COMPLETION_KINDS)},
                },
            )

        try:
            items, _ = read_life_inputs(app.state.paths, app.state.config)
        except Exception:
            items = []
        return {
            "kind": kind,
            "prefix": prefix or "",
            "candidates": completion_candidates(
                kind, prefix or "", items=items, limit=requested
            ),
        }

    @app.post("/api/check-line")
    def check_line(payload=Body(...)):
        line = (
            payload.get("line", "") if isinstance(payload, dict) else str(payload or "")
        )
        if not str(line).strip():
            return {"ok": True, "item_count": 0, "diagnostics": []}
        text = str(line).rstrip("\n") + "\n"
        parsed_items, diagnostics = parse_text(text)
        has_error = any(d.severity == "error" for d in diagnostics)
        return {
            "ok": not has_error,
            "item_count": len(parsed_items),
            "diagnostics": diagnostics_to_output(diagnostics),
        }

    @app.post("/api/items/parse")
    def parse_item_line(payload=Body(...)):
        line = (
            payload.get("line", "") if isinstance(payload, dict) else str(payload or "")
        )
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
            "diagnostics": diagnostics_to_output(diagnostics),
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
            edges.append(
                {"source": src_id, "target": tgt_id, "relation": rec["relation"]}
            )
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
            raise HTTPException(
                status_code=422, detail="Query parameter 'id' is required."
            )
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
                    entry = {k: v for k, v in rec.items() if not k.startswith("_")}
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

    register_analytics_routes(app, read_life_inputs, _elapsed_to_minutes)
    register_git_routes(app)

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
            open_only=_bool_query(open_only),
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
        blocked_mode = _blocked_query_mode(blocked)
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
        active_only = _bool_query(active)
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
            open_only=_bool_query(open_only),
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
            raise HTTPException(
                status_code=404, detail="Message id:%s was not found." % message_id
            )
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
            if thread_id in item.details.get(
                item_id_key, []
            ) or thread_id in item.details.get("parent", []):
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
            raise HTTPException(
                status_code=404, detail="Message id:%s was not found." % message_id
            )
        try:
            item = message_reply_from_payload(
                original, message_id, payload, app.state.config
            )
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

    @app.get("/api/commands")
    def get_commands():
        """The slash-command catalog, shared with the TUI.

        Names, aliases, usage, and summaries come from `lifetxt.tui_app` so a
        command means the same thing in the terminal and the browser. The
        `web` flag says whether the browser implements it; commands that only
        make sense at a terminal are listed but marked unsupported so the
        palette can explain rather than silently omit them.
        """
        from .tui_app import COMMANDS

        rows = []
        for command in COMMANDS:
            rows.append(
                {
                    "name": command.name,
                    "alias": command.alias or "",
                    "usage": command.usage,
                    "summary": command.summary,
                    "web": command.name in WEB_COMMANDS,
                    "note": WEB_COMMAND_NOTES.get(command.name, ""),
                }
            )
        return {"count": len(rows), "commands": rows}

    @app.get("/api/timer")
    def get_timer():
        from . import timer as timer_module

        return timer_module.timer_status_data(
            config=app.state.config, paths=app.state.paths
        )

    @app.post("/api/timer")
    def post_timer(response: Response, payload=Body(...)):
        """Drive the shared timer with explicit state and item revisions."""
        from . import timer as timer_module
        from .mutation import MutationConflict

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        action = str(payload.get("action") or "").strip().lower()
        if action not in ("start", "stop", "pause", "resume", "cancel"):
            raise HTTPException(
                status_code=400,
                detail="action must be start, stop, pause, resume, or cancel.",
            )
        required = getattr(app.state, "revision_mode", "observe") == "required"
        timer_revision = payload.get("timer_revision")
        item_revision = payload.get("item_revision")
        needs_item = action in ("start", "stop")
        missing = []
        if timer_revision in (None, ""):
            missing.append("timer_revision")
        if needs_item and item_revision in (None, ""):
            missing.append("item_revision")
        if required and missing:
            raise HTTPException(
                status_code=428,
                detail={
                    "error": "PRECONDITION_REQUIRED",
                    "message": "Timer writes require revisions for every touched target.",
                    "missing": missing,
                },
            )
        if missing:
            response.headers["X-Lifetxt-Legacy-Revision-Fallback"] = "used"
            response.headers["Deprecation"] = "true"

        try:
            if action == "start":
                item_id = str(payload.get("id") or "").strip()
                if not item_id:
                    raise HTTPException(
                        status_code=400, detail="id is required to start a timer."
                    )
                result = timer_module.start_timer_transaction(
                    app.state.writable_path,
                    item_id,
                    note=payload.get("note"),
                    config=app.state.config,
                    expected_item_revision=item_revision,
                    expected_timer_revision=timer_revision,
                    require_revisions=required,
                )
                result["elapsed_written"] = False
                return result
            if action == "stop":
                result = timer_module.stop_timer_transaction(
                    config=app.state.config,
                    expected_item_revision=item_revision,
                    expected_timer_revision=timer_revision,
                    require_revisions=required,
                )
                result["elapsed_written"] = True
                return result
            if action == "pause":
                return timer_module.pause_timer_transaction(
                    config=app.state.config,
                    expected_timer_revision=timer_revision,
                    require_revision=required,
                )
            if action == "resume":
                return timer_module.resume_timer_transaction(
                    config=app.state.config,
                    expected_timer_revision=timer_revision,
                    require_revision=required,
                )
            result = timer_module.cancel_timer_transaction(
                config=app.state.config,
                expected_timer_revision=timer_revision,
                require_revision=required,
            )
            if not result.get("canceled"):
                raise HTTPException(status_code=409, detail="No running timer.")
            result["elapsed_written"] = False
            return result
        except MutationConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "CONFLICT",
                    "path": exc.path,
                    "expected_revision": exc.expected_hash,
                    "current_revision": exc.actual_hash,
                    "operation": exc.operation,
                },
            )
        except ValueError as exc:
            message = error_detail(exc)
            status = (
                409
                if "already running" in message or "No running timer" in message
                else 400
            )
            raise HTTPException(status_code=status, detail=message)

    @app.get("/api/work-session")
    def get_work_session():
        from . import timer as timer_module

        return timer_module.timer_status_data(
            config=app.state.config, paths=app.state.paths
        )

    @app.post("/api/work-session")
    def mutate_work_session(response: Response, payload=Body(...)):
        from .mutation import MutationConflict
        from .work_session import start_work_transaction, stop_work_transaction

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        action = str(payload.get("action") or "").strip().lower()
        if action not in ("start", "stop"):
            raise HTTPException(status_code=400, detail="action must be start or stop.")
        required = getattr(app.state, "revision_mode", "observe") == "required"
        item_revision = payload.get("item_revision")
        timer_revision = payload.get("timer_revision")
        missing = [
            name
            for name, value in (
                ("item_revision", item_revision),
                ("timer_revision", timer_revision),
            )
            if value in (None, "")
        ]
        if required and missing:
            raise HTTPException(
                status_code=428,
                detail={
                    "error": "PRECONDITION_REQUIRED",
                    "message": "Work-session writes require item and timer revisions.",
                    "missing": missing,
                },
            )
        if missing:
            response.headers["X-Lifetxt-Legacy-Revision-Fallback"] = "used"
            response.headers["Deprecation"] = "true"
        try:
            if action == "start":
                item_id = str(payload.get("id") or "").strip()
                if not item_id:
                    raise ValueError("id is required to start work.")
                return start_work_transaction(
                    app.state.writable_path,
                    item_id,
                    state=payload.get("state") or "busy",
                    use_timer=not bool(payload.get("no_timer")),
                    use_presence=not bool(payload.get("no_presence")),
                    config=app.state.config,
                    expected_item_revision=item_revision,
                    expected_timer_revision=timer_revision,
                    require_revisions=required,
                )
            return stop_work_transaction(
                path=payload.get("path"),
                done=bool(payload.get("done")),
                close_presence=not bool(payload.get("no_presence")),
                config=app.state.config,
                expected_item_revision=item_revision,
                expected_timer_revision=timer_revision,
                require_revisions=required,
            )
        except MutationConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "CONFLICT",
                    "path": exc.path,
                    "expected_revision": exc.expected_hash,
                    "current_revision": exc.actual_hash,
                    "operation": exc.operation,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))

    @app.get("/api/attachments/state")
    def get_attachment_state(path: str = Query(...)):
        from .attachment_transactions import attachment_state

        try:
            return attachment_state(
                app.state.writable_path, path, config=app.state.config
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))

    @app.post("/api/attachments")
    def mutate_attachment(response: Response, payload=Body(...)):
        import base64
        from .attachment_transactions import (
            delete_attachment,
            put_attachment,
            reference_attachment,
        )
        from .mutation import MutationConflict

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        action = str(payload.get("action") or "").strip().lower()
        if action not in ("put", "reference", "delete"):
            raise HTTPException(
                status_code=400, detail="action must be put, reference, or delete."
            )
        item_id = str(payload.get("id") or "").strip()
        stored_path = str(payload.get("path") or "").strip()
        if not item_id or not stored_path:
            raise HTTPException(status_code=400, detail="id and path are required.")
        required = getattr(app.state, "revision_mode", "observe") == "required"
        item_revision = payload.get("item_revision")
        attachment_revision = payload.get("attachment_revision")
        missing = []
        if item_revision in (None, ""):
            missing.append("item_revision")
        if attachment_revision in (None, ""):
            missing.append("attachment_revision")
        if required and missing:
            raise HTTPException(
                status_code=428,
                detail={
                    "error": "PRECONDITION_REQUIRED",
                    "message": "Attachment writes require revisions for every touched target.",
                    "missing": missing,
                },
            )
        if missing:
            response.headers["X-Lifetxt-Legacy-Revision-Fallback"] = "used"
            response.headers["Deprecation"] = "true"
        try:
            common = dict(
                item_revision=item_revision,
                attachment_expected_revision=attachment_revision,
                config=app.state.config,
                require_revisions=required,
            )
            if action == "reference":
                return reference_attachment(
                    app.state.writable_path, item_id, stored_path, **common
                )
            if action == "delete":
                return delete_attachment(
                    app.state.writable_path, item_id, stored_path, **common
                )
            encoded = payload.get("content_base64")
            text = payload.get("content_text")
            if encoded not in (None, "") and text not in (None, ""):
                raise ValueError("Use only one of content_base64 or content_text.")
            if encoded not in (None, ""):
                try:
                    data = base64.b64decode(str(encoded), validate=True)
                except Exception as exc:
                    raise ValueError("Invalid content_base64: %s" % exc)
            elif text is not None:
                data = str(text).encode("utf-8")
            else:
                raise ValueError("put requires content_base64 or content_text.")
            return put_attachment(
                app.state.writable_path,
                item_id,
                stored_path,
                data,
                allow_executable=bool(payload.get("allow_executable")),
                **common,
            )
        except MutationConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "CONFLICT",
                    "path": exc.path,
                    "expected_revision": exc.expected_hash,
                    "current_revision": exc.actual_hash,
                    "operation": exc.operation,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))

    @app.post("/api/status", status_code=201)
    def set_status(payload=Body(...)):
        """Record a presence status, closing the previously open one.

        One request performs the whole transition so a client cannot leave two
        records looking current.
        """
        from .presence import status_transition

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        state_value = payload.get("state")
        close_only = bool(payload.get("end"))
        if not close_only and not state_value:
            raise HTTPException(
                status_code=400,
                detail='state is required, or pass {"end": true} to close the current status.',
            )

        details = {}
        for key in ("note", "project", "service", "visibility"):
            value = payload.get(key)
            if value:
                details[key] = [str(value)]

        path = app.state.writable_path
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                text = handle.read()
        except OSError:
            text = ""

        try:
            result = status_transition(
                text,
                state=state_value,
                title=payload.get("title"),
                person=payload.get("person") or "self",
                details=details,
                id_key=id_key_from_config(app.state.config),
                close_only=close_only,
                force=bool(payload.get("force")),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))

        if result.unchanged:
            return {
                "closed": [],
                "opened": "",
                "unchanged": result.unchanged,
                "path": path,
            }

        write_text(path, result.text)
        return {
            "closed": result.closed,
            "opened": result.opened,
            "unchanged": "",
            "path": path,
        }

    @app.post("/api/shorthand/parse")
    def parse_shorthand(payload=Body(...)):
        """Expand capture sigils without writing anything.

        The browser uses this for the live preview under the quick-add box, so
        the sigil rules never drift between the server and a JS reimplementation.
        """
        from .shorthand import (
            ShorthandError,
            describe_date_tokens,
            describe_sigils,
            parse_capture,
            resolve_date_token,
        )

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        text = str(payload.get("text") or "")
        try:
            title, details = parse_capture(text, strict_dates=True)
        except ShorthandError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        result = {
            "title": title,
            "details": details,
            "sigils": [
                {"token": token, "expands_to": target}
                for token, target in describe_sigils()
            ],
            "date_tokens": [
                {"token": token, "meaning": meaning}
                for token, meaning in describe_date_tokens()
            ],
        }
        # Resolving a single token is what the /due command needs; the browser
        # must not reimplement the date grammar.
        date_value = payload.get("date")
        if date_value:
            try:
                result["date"] = resolve_date_token(str(date_value), strict=True)
            except ShorthandError as exc:
                raise HTTPException(status_code=400, detail=error_detail(exc))
        return result

    @app.post("/api/items/capture", status_code=201)
    def capture_item(payload=Body(...)):
        """Append a task from plain text, expanding capture sigils.

        Building the line here rather than in the browser keeps one
        serializer, so the Web UI cannot drift from `lifetxt quick`.
        """
        from .shorthand import ShorthandError, parse_capture

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required.")
        try:
            title, details = parse_capture(text, strict_dates=True)
        except ShorthandError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        if not title:
            raise HTTPException(
                status_code=400,
                detail="Capture shorthand consumed the whole title. Add a title.",
            )

        kind = str(payload.get("type") or "T")
        item = Item("[ ]", kind, title, details or None)
        ensure_item_id(item, key=id_key_from_config(app.state.config))
        append_item_to_file(app.state.writable_path, item)
        return {
            "line": item_to_line(item),
            "item": api_item(
                item, app.state.writable_path, id_key_from_config(app.state.config)
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
        raw = (
            payload.get("line", "") if isinstance(payload, dict) else str(payload or "")
        )
        raw = str(raw).strip()
        if not raw:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ERROR",
                    "message": "line is required.",
                    "detail": None,
                },
            )
        text = raw.rstrip("\n") + "\n"
        parsed_items, diagnostics = parse_text(text)
        has_error = any(d.severity == "error" for d in diagnostics)
        if has_error or not parsed_items:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": diagnostics[0].message
                    if diagnostics
                    else "Could not parse line.",
                    "detail": diagnostics_to_output(diagnostics),
                },
            )
        writable = app.state.writable_path
        if not writable:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "READONLY",
                    "message": "No writable file configured.",
                    "detail": None,
                },
            )
        ensure_parent_dir(writable)
        existing = read_text(writable) if os.path.exists(writable) else ""
        prefix = "\n" if existing and not existing.endswith(("\n", "\r")) else ""
        write_text(writable, existing + prefix + raw + "\n")
        line_no = len(existing.splitlines()) + 1
        return {
            "line": line_no,
            "item": api_item(
                parsed_items[0], writable, id_key_from_config(app.state.config)
            ),
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
            raise HTTPException(
                status_code=404, detail="Item id:%s was not found." % item_id
            )
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

    @app.post("/api/items/id/{item_id}/complete")
    def complete_item_by_id(item_id, payload=Body(None)):
        # Mirror the CLI `complete` command and MCP `complete_item` tool: mark a
        # repeat-enabled task done and materialize the next occurrence so CLI,
        # Web API, and MCP stay in sync (see cli.command_complete /
        # mcp._tool_complete_item).
        key = id_key_from_config(app.state.config)
        items, diagnostics = read_life_inputs(app.state.paths, app.state.config)
        raise_for_errors(diagnostics)
        try:
            item = find_item_by_id(items, item_id, key=key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        if item is None:
            raise HTTPException(
                status_code=404, detail="Item id:%s was not found." % item_id
            )
        if item.status == "[x]":
            return {
                "id": item_id,
                "item": api_item(item, app.state.writable_path, key),
                "next": None,
            }
        date_value = (payload or {}).get("date") if isinstance(payload, dict) else None
        if date_value:
            completion_dt = parse_date_or_datetime(str(date_value), is_end=False)
            if completion_dt is None:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date %r. Use YYYY-MM-DD." % date_value,
                )
            completion_date = completion_dt.date()
        else:
            completion_date = timezone_today()
        date_iso = completion_date.isoformat()

        next_item = None
        if item.details.get("repeat"):
            repeat_base = resolve_web_repeat_base(item, app.state.config)
            try:
                anchor_key, next_dt, _rule = next_repeat_occurrence(
                    item, repeat_base, completion_date
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=error_detail(exc))
            if next_dt is not None:
                new_details = OrderedDict()
                for detail_key, values in item.details.items():
                    if detail_key in (key, "done"):
                        continue
                    new_details[detail_key] = list(values)
                if next_dt.time() == time():
                    next_value = next_dt.date().isoformat()
                else:
                    next_value = format_life_datetime(next_dt)
                new_details[anchor_key] = [next_value]
                next_item = Item("[ ]", item.kind, item.title, new_details)
                existing_ids = collect_item_ids(items, key=key)
                ensure_item_id(
                    next_item,
                    existing_ids=existing_ids,
                    key=key,
                    prefix=id_prefix_for_item(next_item, app.state.config),
                )

        details = OrderedDict((k, list(v)) for k, v in item.details.items())
        if not details.get("done"):
            details["done"] = [date_iso]
        try:
            updated = update_item_by_id_in_file(
                app.state.writable_path,
                item_id,
                {
                    "status": "[x]",
                    "type": item.kind,
                    "title": item.title,
                    "details": details,
                },
                key=key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))

        result = {
            "id": item_id,
            "item": api_item(updated, app.state.writable_path, key),
            "next": None,
        }
        if next_item is not None:
            append_item_to_file(app.state.writable_path, next_item)
            result["next"] = api_item(next_item, app.state.writable_path, key)
        return result

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


def _legacy_read_life_inputs(paths, config=None):
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
        "diagnostics": diagnostics_to_output(diagnostics),
    }


def links_response(records, diagnostics):
    return {
        "count": len(records),
        "records": records,
        "diagnostics": diagnostics_to_output(diagnostics),
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


PRESENCE_STATE_CLASSES = (
    "p-available",
    "p-busy",
    "p-focus",
    "p-away",
    "p-off",
    "p-unknown",
)


def public_web_presence_config(web):
    """Return user-defined presence state -> class overrides.

    Config accepts `web.presence.states` as a mapping of a presence word
    (matched case-insensitively) to one of the known presence classes, letting
    teams recolor states without code changes. Values that are not known
    classes are dropped so the client cannot inject arbitrary CSS class names.
    """
    presence = _nested_or_dotted(web, "presence")
    states = presence.get("states")
    if not isinstance(states, dict):
        states = {}
        prefix = "states."
        for key, value in presence.items():
            if isinstance(key, str) and key.startswith(prefix):
                states[key[len(prefix) :]] = value
    result = OrderedDict()
    for word, cls in states.items():
        cls_name = str(cls).strip()
        if not cls_name.startswith("p-"):
            cls_name = "p-" + cls_name
        if cls_name in PRESENCE_STATE_CLASSES:
            result[str(word).strip().lower()] = cls_name
    return result


def public_web_team_config(web):
    team = _nested_or_dotted(web, "team")
    return {
        "pin": _string_list(team.get("pin")),
        "order": _string_list(team.get("order")),
    }


def public_web_config(config):
    web = config_section(config, "web")
    return {
        "display_refresh": _int_or_default(web.get("display_refresh"), 60),
        "notification_poll_seconds": _int_or_default(
            web.get("notification_poll_seconds"), 30
        ),
        "notification_lookahead": web.get("notification_lookahead", "0m"),
        "default_limit": web.get("default_limit", ""),
        "default_sort": web.get("default_sort", "line"),
        "default_order": web.get("default_order", "asc"),
        "due_soon_days": _int_or_default(web.get("due_soon_days"), 3),
        "week_start": _normalize_week_start(web.get("week_start")),
        "high_contrast": _truthy_config(web.get("high_contrast")),
        "reduced_motion": _truthy_config(web.get("reduced_motion")),
        "language": str(web.get("language", "") or "").strip().lower(),
        "theme": public_web_theme_config(web),
        "dashboard": public_web_dashboard_config(web),
        "presence": public_web_presence_config(web),
        "team": public_web_team_config(web),
    }


def _truthy_config(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _normalize_week_start(value):
    """Normalize a configured week-start value to 'sunday' or 'monday'.

    The Web calendar and any future week-based views honor this so kiosks and
    personal setups can pick their preferred first column. Defaults to Monday,
    matching agenda/review week bucketing elsewhere in the codebase.
    """
    text = str(value or "").strip().lower()
    if text in ("sun", "sunday", "0", "7"):
        return "sunday"
    return "monday"


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
            data[str(name)] = OrderedDict(
                (str(key), str(value)) for key, value in values.items()
            )
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


def _legacy_sort_items(items, sort_key="line", order="asc"):
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


def _legacy_limit_items(items, limit):
    if limit in (None, ""):
        return items
    try:
        amount = int(limit)
    except (TypeError, ValueError):
        return items
    if amount < 0:
        return items
    return items[:amount]


def _legacy_sort_key_for_item(item, key_name):
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
        raise ValueError(diagnostics_to_output(diagnostics))
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

    if (
        "recipient" not in data
        and "recipients" not in data
        and "recipient" not in details
    ):
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


def resolve_web_repeat_base(item, config):
    """Resolve effective repeat_base ('due'|'done') for the Web API complete route.

    Item-level repeat_base: overrides config defaults.repeat_base, mirroring
    cli.resolve_repeat_base and mcp._resolve_repeat_base so all surfaces agree.
    """
    values = item.details.get("repeat_base")
    repeat_base = values[0] if values else None
    if not repeat_base:
        defaults = config_section(config, "defaults")
        repeat_base = defaults.get("repeat_base") or "due"
    return str(repeat_base).strip().lower()


def _legacy_find_item_by_id(items, item_id, kind=None, key="id"):
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


def read_life_inputs(paths, config=None):
    return _service_read_life_inputs(
        paths, config, normalize_server_paths, read_text, is_generated_path
    )


def sort_items(items, sort_key="line", order="asc"):
    return _service_sort_items(items, sort_key, order)


def sort_key_for_item(item, key_name):
    return _service_sort_key_for_item(item, key_name)


def limit_items(items, limit):
    return _service_limit_items(items, limit)


def find_item_by_id(items, item_id, kind=None, key="id"):
    return _service_find_item_by_id(items, item_id, kind=kind, key=key)


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
        raise ValueError(diagnostics_to_output(diagnostics))
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


def snooze_message_in_file(
    path, message_id, payload=None, config=None, now=None, key="id"
):
    payload = payload if isinstance(payload, dict) else {}
    until = payload.get("snooze_until") or payload.get("until")
    if not until:
        duration = payload.get("duration")
        if not duration:
            duration = config_section(config or {}, "notifications").get(
                "snooze_default"
            )
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


def patch_item_details_by_id_in_file(
    path, item_id, detail_updates, kind=None, key="id"
):
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
    atomic_write_text(path, text)


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
        value = local_now_naive()
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
    filtered_edges = [
        e for e in edges if e["source"] in reachable and e["target"] in reachable
    ]
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


def _bool_query(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "open", "only"):
        return True
    if text in ("0", "false", "no", "off", "none", "hide", ""):
        return False
    return default


def _blocked_query_mode(value):
    text = str(value or "").strip().lower()
    if text in ("hide", "none"):
        return "hide"
    if _bool_query(value):
        return "only"
    return ""


def _has_error(diagnostics):
    for diagnostic in diagnostics:
        if isinstance(diagnostic, Diagnostic) and diagnostic.severity == "error":
            return True
    return False


def error_detail(exc):
    if exc.args:
        return exc.args[0]
    return str(exc)
