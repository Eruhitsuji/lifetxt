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
from .links import link_records, reference_diagnostics
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
        from fastapi import Body, FastAPI, HTTPException, Query
        from fastapi.responses import HTMLResponse
    except ImportError as exc:
        raise RuntimeError(
            "Web dependencies are not installed. Run: pip install -r requirements-web.txt"
        ) from exc

    app = FastAPI(title="life.txt API", version="0.1.0")
    app.state.paths = normalize_server_paths(paths)
    app.state.writable_path = writable_path or app.state.paths[0]
    app.state.config = config or {}

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
            "views": public_views_config(app.state.config),
            "users": public_users_config(app.state.config),
            "teams": public_teams_config(app.state.config),
            "tags": public_tags_config(app.state.config),
        }

    @app.get("/api/items")
    def get_items(
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
      <button class="secondary" onclick="enableBrowserNotifications()">Enable Notifications</button>
      <button class="secondary" onclick="refreshAll()">Refresh</button>
    </div>
  </header>
  <main>
    <section class="item-section">
      <div class="section-head">
        <h2>Items</h2>
        <div class="toolbar">
          <input id="search" placeholder="Search">
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
      <div id="diagnostics"></div>
      <div id="items" class="content"></div>
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
            <textarea id="edit-details" placeholder="due:2026-06-12&#10;project:research"></textarea>
          </label>
          <div id="editor-note" class="note wide">Create a new item or select an editable row.</div>
          <div class="actions">
            <button id="save-button">Create</button>
            <button id="delete-button" class="danger" type="button" onclick="deleteSelected()" disabled>Delete</button>
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
        <div class="section-head"><h2>Notifications</h2></div>
        <div id="notifications" class="stack"></div>
      </section>
    </div>
  </main>
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
    function renderItems(items) {
      const root = document.getElementById("items");
      root.innerHTML = items.length ? "" : `<div class="empty">No items found.</div>`;
      for (const item of items) {
        const node = document.createElement("button");
        node.type = "button";
        node.className = "item";
        if (selectedItem && item.line === selectedItem.line && item.editable === selectedItem.editable) {
          node.classList.add("selected");
        }
        node.addEventListener("click", () => selectItem(item));
        node.innerHTML = `
          <span class="pill">${escapeHtml(item.status)}</span>
          <span class="pill">${escapeHtml(item.type)}</span>
          <div>
            <div class="title">${escapeHtml(item.title)}</div>
            <div class="meta">${escapeHtml(detailText(item.details))}</div>
          </div>
          <span class="source">${escapeHtml(item.source || `line ${item.line || ""}`)}${item.generated ? " / generated" : ""}${item.editable ? "" : " / read-only"}</span>
        `;
        root.appendChild(node);
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
        node.insertAdjacentHTML(
          "beforeend",
          `<div><span class="pill">${escapeHtml(record.when)}</span><div class="title">${escapeHtml(record.title)}</div></div>`
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
      for (const record of data.records) {
        const actions = record.id ? `
          <div class="actions">
            <button class="secondary" type="button" onclick="ackMessage(${escapeHtml(jsLiteral(record.id))})">Ack</button>
            <button class="secondary" type="button" onclick="snoozeMessage(${escapeHtml(jsLiteral(record.id))}, ${escapeHtml(jsLiteral(snoozeDefault))})">Snooze ${escapeHtml(snoozeDefault)}</button>
          </div>
        ` : "";
        node.insertAdjacentHTML(
          "beforeend",
          `<div class="notification-row"><span class="pill">${escapeHtml(record.when)}</span><div class="title">${escapeHtml(record.title)}</div><div class="meta">${escapeHtml(record.sender)} -> ${escapeHtml((record.recipients || []).join(", "))}</div>${actions}</div>`
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
    loadConfig().then(() => {
      applyPresetToUrl();
      applyUrlToControls();
      return refreshAll();
    }).catch(error => {
      document.body.insertAdjacentHTML("beforeend", `<pre class="diagnostic">${escapeHtml(error.message)}</pre>`);
    });
  </script>
</body>
</html>
"""
