import json
import sys
from collections import OrderedDict
from datetime import datetime

from .agenda import (
    agenda_records,
    filter_agenda_records,
    filter_items,
    parse_agenda_range,
    parse_optional_time_range,
)
from .config import (
    config_notification_recipient,
    config_paths,
    config_section,
    config_tag_aliases,
    config_team_aliases,
    config_team_members,
    config_user_aliases,
    config_write_file,
)
from .ids import id_key_from_config
from .links import dependency_blocker_records, link_records
from .notifier import notification_records
from .parser import parse_text
from .serializer import item_to_line
from .status_summary import latest_status_records
from .webapp import (
    ack_message_in_file,
    api_item,
    append_item_to_file,
    assign_auto_id_from_paths,
    auto_id_paths,
    delete_item_by_id_from_file,
    find_item_by_id,
    item_from_payload,
    items_response,
    limit_items,
    links_response,
    message_item_from_payload,
    message_reply_from_payload,
    normalize_server_paths,
    read_life_inputs,
    read_text,
    snooze_message_in_file,
    sort_items,
    update_item_by_id_in_file,
    _subgraph,
)


SERVER_NAME = "lifetxt-mcp"
SERVER_VERSION = "0.1.0"


class McpContext:
    def __init__(self, paths=None, writable_path=None, config=None, read_only=False):
        self.config = config or {}
        configured_paths = paths or config_paths(self.config) or ["life.txt"]
        self.paths = normalize_server_paths(configured_paths)
        self.writable_path = writable_path or config_write_file(self.config) or self.paths[0]
        self.read_only = bool(read_only)

    @classmethod
    def from_args(cls, args):
        config = getattr(args, "config_data", None) or {}
        paths = list(getattr(args, "paths", None) or []) or config_paths(config) or ["life.txt"]
        return cls(
            paths=paths,
            writable_path=getattr(args, "write_file", None) or config_write_file(config),
            config=config,
            read_only=getattr(args, "read_only", False),
        )


def cmd_mcp(args, input_stream=None, output_stream=None):
    context = McpContext.from_args(args)
    return run_stdio_server(context, input_stream=input_stream, output_stream=output_stream)


def run_stdio_server(context, input_stream=None, output_stream=None):
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for raw_line in input_stream:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            request = json.loads(raw_line)
            response = handle_request(request, context)
        except Exception as exc:
            response = _jsonrpc_error(None, -32603, str(exc))
        if response is None:
            continue
        output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        output_stream.flush()
    return 0


def handle_request(request, context):
    if not isinstance(request, dict):
        return _jsonrpc_error(None, -32600, "Invalid JSON-RPC request.")
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    if request_id is None and method not in ("initialize", "tools/list", "tools/call", "resources/list", "resources/read"):
        return None

    try:
        if method == "initialize":
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {
                        "tools": {},
                        "resources": {"subscribe": False, "listChanged": False},
                    },
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )
        if method == "ping":
            return _jsonrpc_result(request_id, {})
        if method == "tools/list":
            return _jsonrpc_result(request_id, {"tools": tool_schemas()})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            result = call_tool(name, arguments, context)
            return _jsonrpc_result(request_id, _tool_result(result))
        if method == "resources/list":
            return _jsonrpc_result(request_id, {"resources": resource_list(context)})
        if method == "resources/read":
            uri = params.get("uri", "")
            return _jsonrpc_result(request_id, resource_read(context, uri))
        return _jsonrpc_error(request_id, -32601, "Method not found: %s" % method)
    except ValueError as exc:
        return _jsonrpc_error(request_id, -32000, str(exc))


def call_tool(name, arguments, context):
    if name not in TOOL_HANDLERS:
        raise ValueError("Unknown MCP tool: %s" % name)
    return TOOL_HANDLERS[name](arguments or {}, context)


def tool_schemas():
    return [
        _tool(
            "list_items",
            "List life.txt items with the same filters as GET /api/items.",
            {
                "open_only": _bool("Only open workflow statuses."),
                "blocked": _string("Use true/only to return blocked items."),
                "status": _string("Comma-separated status filter."),
                "type": _string("Comma-separated type filter."),
                "project": _string("Comma-separated project filter."),
                "tag": _string("Comma-separated tag filter."),
                "tag_all": _string("Comma-separated tag groups that must all match."),
                "exclude_tag": _string("Comma-separated tags to exclude."),
                "user": _string("User filter."),
                "team": _string("Team filter."),
                "person": _string("Presence/person filter."),
                "owner": _string("Owner filter."),
                "assignee": _string("Assignee filter."),
                "attendee": _string("Attendee filter."),
                "sender": _string("Message sender filter."),
                "recipient": _string("Message recipient filter."),
                "text": _string("Text search query."),
                "after": _string("Lower time bound."),
                "before": _string("Upper time bound."),
                "sort": _string("Sort key."),
                "order": _string("asc or desc."),
                "limit": _integer("Maximum number of items."),
            },
        ),
        _tool("get_item", "Get one item by ID.", {"id": _string("Item ID.")}, required=["id"]),
        _tool("check_line", "Validate a raw life.txt line.", {"line": _string("Raw line.")}, required=["line"]),
        _tool("parse_item", "Parse a raw life.txt item and return preview items.", {"line": _string("Raw line or body block.")}, required=["line"]),
        _tool(
            "create_item",
            "Append a new item to the writable life.txt file.",
            {
                "status": _string("Workflow status such as [ ]."),
                "type": _string("Item type such as T, E, M, S, or J."),
                "title": _string("Item title."),
                "details": _object("Detail key/value object."),
            },
            required=["type", "title"],
        ),
        _tool(
            "update_item",
            "Update an item by ID. Use set_details/remove_details for partial detail edits.",
            {
                "id": _string("Item ID."),
                "status": _string("New status."),
                "type": _string("New type."),
                "title": _string("New title."),
                "details": _object("Complete replacement details."),
                "set_details": _object("Detail keys to set."),
                "remove_details": _array("Detail keys to remove."),
            },
            required=["id"],
        ),
        _tool(
            "mark_done",
            "Mark an item done by ID and add done: when missing.",
            {"id": _string("Item ID."), "done": _string("done: value. Defaults to now.")},
            required=["id"],
        ),
        _tool("delete_item", "Delete an item by ID.", {"id": _string("Item ID.")}, required=["id"]),
        _tool(
            "get_agenda",
            "Return agenda records for a time range.",
            {
                "from": _string("Range start."),
                "to": _string("Range end."),
                "around": _string("Center time, e.g. now."),
                "window": _string("Window such as 1h, 2d, or 1w."),
                "open_only": _bool("Only open records."),
                "blocked": _string("all, only, or hide."),
                "status": _string("Comma-separated status filter."),
                "type": _string("Comma-separated type filter."),
                "project": _string("Project filter."),
                "tag": _string("Tag filter."),
                "text": _string("Text search query."),
                "limit": _integer("Maximum number of records."),
            },
        ),
        _tool(
            "get_review",
            "Return a weekly/monthly review report: completed tasks, habit "
            "completion, journal entries, mood trend, and elapsed time.",
            {
                "week": _bool("Review the current week (Monday to Sunday)."),
                "month": _string("Review a calendar month, formatted YYYY-MM."),
                "from": _string("Range start date, YYYY-MM-DD. Defaults to the current week start."),
                "to": _string("Range end date, YYYY-MM-DD. Defaults to today."),
                "project": _string("Restrict the review to one project."),
            },
        ),
        _tool(
            "get_graph",
            "Return ID reference graph nodes and edges.",
            {"root": _string("Optional root ID."), "depth": _integer("Optional traversal depth.")},
        ),
        _tool(
            "get_blockers",
            "Return transitive open blockers for an item ID.",
            {"id": _string("Item ID."), "depth": _integer("Traversal depth, clamped to 1..10.")},
            required=["id"],
        ),
        _tool(
            "list_links",
            "List ID reference links.",
            {
                "id": _string("Focus item ID."),
                "direction": _string("incoming, outgoing, or both."),
                "relation": _string("Comma-separated relation filter."),
                "limit": _integer("Maximum number of links."),
            },
        ),
        _tool(
            "list_status",
            "Return latest presence status records.",
            {"person": _string("Person filter."), "active": _bool("Only active statuses.")},
        ),
        _tool(
            "list_notifications",
            "Return due message notification records.",
            {
                "recipient": _string("Recipient. Defaults to configured user."),
                "lookahead": _string("Future notification window."),
                "grace": _string("Past grace window."),
                "limit": _integer("Maximum number of notifications."),
            },
        ),
        _tool(
            "list_messages",
            "List message items with filters.",
            {
                "open_only": _bool("Only open messages."),
                "sender": _string("Sender filter."),
                "recipient": _string("Recipient filter."),
                "project": _string("Project filter."),
                "tag": _string("Tag filter."),
                "text": _string("Text search query."),
                "after": _string("Lower time bound."),
                "before": _string("Upper time bound."),
                "sort": _string("Sort key."),
                "order": _string("asc or desc."),
                "limit": _integer("Maximum number of messages."),
            },
        ),
        _tool(
            "create_message",
            "Append a type M message using message defaults from config.",
            {
                "title": _string("Message title."),
                "body": _string("Message body."),
                "sender": _string("Sender."),
                "recipient": _string("Recipient."),
                "recipients": _array("Recipients."),
                "notify_at": _string("Notification time."),
                "notify_from": _string("Notification window start."),
                "notify_to": _string("Notification window end."),
                "details": _object("Extra details."),
            },
            required=["title"],
        ),
        _tool(
            "reply_message",
            "Reply to a message ID and link it with parent:ID.",
            {"id": _string("Original message ID."), "title": _string("Reply title."), "body": _string("Reply body."), "details": _object("Extra details.")},
            required=["id", "title"],
        ),
        _tool("ack_message", "Acknowledge a message notification.", {"id": _string("Message ID."), "ack": _string("Ack timestamp.")}, required=["id"]),
        _tool(
            "snooze_message",
            "Snooze a message notification.",
            {"id": _string("Message ID."), "duration": _string("Duration such as 10m."), "until": _string("Explicit snooze_until value.")},
            required=["id"],
        ),
    ]


def resource_list(context):
    resources = []
    for index, path in enumerate(context.paths):
        resources.append(
            {
                "uri": "lifetxt://source/%d" % index,
                "name": path,
                "description": "life.txt input source",
                "mimeType": "text/plain",
            }
        )
    return resources


def resource_read(context, uri):
    prefix = "lifetxt://source/"
    if not str(uri).startswith(prefix):
        raise ValueError("Unsupported resource URI: %s" % uri)
    try:
        index = int(str(uri)[len(prefix):])
    except ValueError:
        raise ValueError("Invalid resource index in URI: %s" % uri)
    if index < 0 or index >= len(context.paths):
        raise ValueError("Resource index is out of range: %s" % uri)
    path = context.paths[index]
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "text/plain",
                "text": read_text(path),
            }
        ]
    }


def _tool(name, description, properties, required=None):
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }
    if required:
        schema["required"] = list(required)
    return {
        "name": name,
        "description": description,
        "inputSchema": schema,
    }


def _string(description):
    return {"type": "string", "description": description}


def _integer(description):
    return {"type": "integer", "description": description}


def _bool(description):
    return {"type": "boolean", "description": description}


def _object(description):
    return {"type": "object", "description": description, "additionalProperties": True}


def _array(description):
    return {"type": "array", "description": description, "items": {"type": "string"}}


def _read_items(context):
    return read_life_inputs(context.paths, context.config)


def _id_key(context):
    return id_key_from_config(context.config)


def _tool_list_items(args, context):
    items, diagnostics = _read_items(context)
    range_start, range_end = parse_optional_time_range(args.get("after"), args.get("before"))
    filtered = filter_items(
        items,
        open_only=_truthy(args.get("open_only")) or _truthy(args.get("blocked")),
        statuses=_csv_values(args.get("status")),
        kinds=_csv_values(args.get("kind") or args.get("type")),
        projects=_csv_values(args.get("project")),
        tags=_csv_values(args.get("tag")),
        tag_all=_csv_values(args.get("tag_all")),
        exclude_tags=_csv_values(args.get("exclude_tag")),
        users=_csv_values(args.get("user")),
        persons=_csv_values(args.get("person")),
        owners=_csv_values(args.get("owner")),
        assignees=_csv_values(args.get("assignee")),
        attendees=_csv_values(args.get("attendee")),
        senders=_csv_values(args.get("sender")),
        recipients=_csv_values(args.get("recipient")),
        teams=_csv_values(args.get("team")),
        text=args.get("text") or args.get("q"),
        range_start=range_start,
        range_end=range_end,
        user_aliases=config_user_aliases(context.config),
        team_members=config_team_members(context.config),
        team_aliases=config_team_aliases(context.config),
        tag_aliases=config_tag_aliases(context.config),
    )
    if _truthy(args.get("blocked")):
        key = _id_key(context)
        blocker_records = dependency_blocker_records(items, key=key)
        blocked_item_ids = {r["blocked_id"] for r in blocker_records if r.get("blocked_id")}
        blocked_lines = {r["blocked_line"] for r in blocker_records if r.get("blocked_line") is not None}
        filtered = [
            item for item in filtered
            if (item.details.get(key) and str(item.details[key][0]) in blocked_item_ids)
            or (item.line is not None and item.line in blocked_lines)
        ]
    filtered = sort_items(filtered, args.get("sort") or "line", args.get("order") or "asc")
    filtered = limit_items(filtered, args.get("limit"))
    return items_response(filtered, diagnostics, context.writable_path, _id_key(context))


def _tool_get_item(args, context):
    items, diagnostics = _read_items(context)
    item = find_item_by_id(items, str(args.get("id")), key=_id_key(context))
    if item is None:
        raise ValueError("Item id:%s was not found." % args.get("id"))
    return {
        "item": api_item(item, context.writable_path, _id_key(context)),
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def _tool_check_line(args, _context):
    line = str(args.get("line", ""))
    if not line.strip():
        return {"ok": True, "item_count": 0, "diagnostics": []}
    parsed_items, diagnostics = parse_text(line.rstrip("\n") + "\n")
    has_error = any(d.severity == "error" for d in diagnostics)
    return {
        "ok": not has_error,
        "item_count": len(parsed_items),
        "diagnostics": [d.to_dict() for d in diagnostics],
    }


def _tool_parse_item(args, context):
    line = str(args.get("line", ""))
    if not line.strip():
        return {"ok": True, "item_count": 0, "items": [], "diagnostics": []}
    parsed_items, diagnostics = parse_text(
        line.rstrip("\n") + "\n",
        id_key=_id_key(context),
        check_ids=False,
        check_references=False,
    )
    has_error = any(d.severity == "error" for d in diagnostics)
    return {
        "ok": not has_error,
        "item_count": len(parsed_items),
        "items": [api_item(item, None, _id_key(context)) for item in parsed_items],
        "diagnostics": [d.to_dict() for d in diagnostics],
    }


def _tool_create_item(args, context):
    _require_writable(context)
    payload = {
        "status": args.get("status", "[ ]"),
        "type": args.get("type") or args.get("kind"),
        "title": args.get("title"),
        "details": _normalize_details(args.get("details") or {}),
    }
    item = item_from_payload(payload)
    assign_auto_id_from_paths(item, context.config, auto_id_paths(context.paths, context.writable_path))
    line_no = append_item_to_file(context.writable_path, item)
    return {
        "line": line_no,
        "item": api_item(item, context.writable_path, _id_key(context)),
        "text": item_to_line(item),
    }


def _tool_update_item(args, context):
    _require_writable(context)
    item_id = str(args.get("id"))
    items, _diagnostics = _read_items(context)
    original = find_item_by_id(items, item_id, key=_id_key(context))
    if original is None:
        raise ValueError("Item id:%s was not found." % item_id)
    payload = {}
    for key in ("status", "title"):
        if key in args:
            payload[key] = args[key]
    if "type" in args:
        payload["type"] = args["type"]
    if "kind" in args:
        payload["type"] = args["kind"]
    if "details" in args:
        payload["details"] = _normalize_details(args.get("details") or {})
    elif "set_details" in args or "remove_details" in args:
        details = _copy_details(original.details)
        for key in _as_list(args.get("remove_details")):
            details.pop(str(key), None)
        for key, value in (args.get("set_details") or {}).items():
            details[str(key)] = _as_list(value)
        payload["details"] = details
    if not payload:
        raise ValueError("update_item requires at least one field to update.")
    item = update_item_by_id_in_file(context.writable_path, item_id, payload, key=_id_key(context))
    return {"id": item_id, "item": api_item(item, context.writable_path, _id_key(context))}


def _tool_mark_done(args, context):
    _require_writable(context)
    item_id = str(args.get("id"))
    items, _diagnostics = _read_items(context)
    item = find_item_by_id(items, item_id, key=_id_key(context))
    if item is None:
        raise ValueError("Item id:%s was not found." % item_id)
    details = _copy_details(item.details)
    if not details.get("done"):
        details["done"] = [str(args.get("done") or _now_text())]
    updated = update_item_by_id_in_file(
        context.writable_path,
        item_id,
        {"status": "[x]", "type": item.kind, "title": item.title, "details": details},
        key=_id_key(context),
    )
    return {"id": item_id, "item": api_item(updated, context.writable_path, _id_key(context))}


def _tool_delete_item(args, context):
    _require_writable(context)
    item_id = str(args.get("id"))
    deleted = delete_item_by_id_from_file(context.writable_path, item_id, key=_id_key(context))
    return {"id": item_id, "deleted": deleted}


def _tool_get_agenda(args, context):
    items, diagnostics = _read_items(context)
    range_start, range_end = parse_agenda_range(
        args.get("from"),
        args.get("to"),
        args.get("around"),
        args.get("window") or "1h",
    )
    records = agenda_records(items, range_start, range_end)
    blocked_mode = str(args.get("blocked") or "all").lower()
    blocked = None
    if blocked_mode in ("only", "true", "1"):
        blocked = True
    elif blocked_mode in ("hide", "none", "false", "0"):
        blocked = False
    records = filter_agenda_records(
        records,
        open_only=_truthy(args.get("open_only")),
        statuses=_csv_values(args.get("status")),
        kinds=_csv_values(args.get("kind") or args.get("type")),
        projects=_csv_values(args.get("project")),
        tags=_csv_values(args.get("tag")),
        text=args.get("text") or args.get("q"),
        blocked=blocked,
        user_aliases=config_user_aliases(context.config),
        team_members=config_team_members(context.config),
        team_aliases=config_team_aliases(context.config),
        tag_aliases=config_tag_aliases(context.config),
    )
    records = limit_items(records, args.get("limit"))
    return {
        "count": len(records),
        "range": {"from": range_start.isoformat(), "to": range_end.isoformat()},
        "records": records,
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def _tool_get_review(args, context):
    from .review import build_review, resolve_review_range

    items, diagnostics = _read_items(context)
    start, end = resolve_review_range(
        week=_truthy(args.get("week")),
        month=args.get("month"),
        from_date=args.get("from"),
        to_date=args.get("to"),
    )
    result = build_review(
        items,
        start,
        end,
        project=args.get("project"),
        id_key=_id_key(context),
    )
    result["diagnostics"] = [diagnostic.to_dict() for diagnostic in diagnostics]
    return result


def _tool_get_graph(args, context):
    items, _diagnostics = _read_items(context)
    nodes, edges = _graph_nodes_edges(items, _id_key(context))
    root = args.get("root")
    if root:
        nodes, edges = _subgraph(nodes, edges, str(root), _safe_depth(args.get("depth"), default=None))
    return {"nodes": nodes, "edges": edges}


def _tool_get_blockers(args, context):
    items, _diagnostics = _read_items(context)
    return _blockers_response(items, str(args.get("id")), _safe_depth(args.get("depth"), default=5), _id_key(context))


def _tool_list_links(args, context):
    items, diagnostics = _read_items(context)
    records = link_records(
        items,
        key=_id_key(context),
        focus_id=args.get("id"),
        direction=args.get("direction") or "both",
        relations=_csv_values(args.get("relation")),
    )
    records = limit_items(records, args.get("limit"))
    return links_response(records, diagnostics)


def _tool_list_status(args, context):
    items, diagnostics = _read_items(context)
    records = latest_status_records(
        items,
        person=args.get("person"),
        active_only=_truthy(args.get("active")),
    )
    return {"count": len(records), "records": records, "diagnostics": [d.to_dict() for d in diagnostics]}


def _tool_list_notifications(args, context):
    items, diagnostics = _read_items(context)
    notification_config = config_section(context.config, "notifications")
    records = notification_records(
        items,
        recipient=args.get("recipient") or config_notification_recipient(context.config),
        lookahead=args.get("lookahead") or notification_config.get("lookahead") or "0m",
        grace=args.get("grace") or notification_config.get("grace") or "2m",
    )
    records = limit_items(records, args.get("limit"))
    return {"count": len(records), "records": records, "diagnostics": [d.to_dict() for d in diagnostics]}


def _tool_list_messages(args, context):
    args = dict(args)
    args["type"] = "M"
    return _tool_list_items(args, context)


def _tool_create_message(args, context):
    _require_writable(context)
    item = message_item_from_payload(args, context.config)
    assign_auto_id_from_paths(item, context.config, auto_id_paths(context.paths, context.writable_path))
    line_no = append_item_to_file(context.writable_path, item)
    return {"line": line_no, "item": api_item(item, context.writable_path, _id_key(context)), "text": item_to_line(item)}


def _tool_reply_message(args, context):
    _require_writable(context)
    message_id = str(args.get("id"))
    items, diagnostics = _read_items(context)
    original = find_item_by_id(items, message_id, kind="M", key=_id_key(context))
    if original is None:
        raise ValueError("Message id:%s was not found." % message_id)
    payload = dict(args)
    payload.pop("id", None)
    item = message_reply_from_payload(original, message_id, payload, context.config)
    assign_auto_id_from_paths(item, context.config, auto_id_paths(context.paths, context.writable_path))
    line_no = append_item_to_file(context.writable_path, item)
    return {
        "line": line_no,
        "item": api_item(item, context.writable_path, _id_key(context)),
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def _tool_ack_message(args, context):
    _require_writable(context)
    message_id = str(args.get("id"))
    item = ack_message_in_file(context.writable_path, message_id, args, key=_id_key(context))
    return {"id": message_id, "item": api_item(item, context.writable_path, _id_key(context))}


def _tool_snooze_message(args, context):
    _require_writable(context)
    message_id = str(args.get("id"))
    item = snooze_message_in_file(context.writable_path, message_id, args, context.config, key=_id_key(context))
    return {"id": message_id, "item": api_item(item, context.writable_path, _id_key(context))}


TOOL_HANDLERS = OrderedDict(
    [
        ("list_items", _tool_list_items),
        ("get_item", _tool_get_item),
        ("check_line", _tool_check_line),
        ("parse_item", _tool_parse_item),
        ("create_item", _tool_create_item),
        ("update_item", _tool_update_item),
        ("mark_done", _tool_mark_done),
        ("delete_item", _tool_delete_item),
        ("get_agenda", _tool_get_agenda),
        ("get_review", _tool_get_review),
        ("get_graph", _tool_get_graph),
        ("get_blockers", _tool_get_blockers),
        ("list_links", _tool_list_links),
        ("list_status", _tool_list_status),
        ("list_notifications", _tool_list_notifications),
        ("list_messages", _tool_list_messages),
        ("create_message", _tool_create_message),
        ("reply_message", _tool_reply_message),
        ("ack_message", _tool_ack_message),
        ("snooze_message", _tool_snooze_message),
    ]
)


def _graph_nodes_edges(items, key):
    records = link_records(items, key=key)
    nodes_map = OrderedDict()
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
    return list(nodes_map.values()), edges


def _blockers_response(items, item_id, max_depth, key):
    focus = find_item_by_id(items, item_id, key=key)
    if focus is None:
        raise ValueError("No item with id %r." % item_id)
    max_depth = max(1, min(int(max_depth), 10))
    records = dependency_blocker_records(items, key=key)
    by_blocked_key = {}
    for rec in records:
        by_blocked_key.setdefault(rec["_blocked_item_key"], []).append(rec)
    chain = []
    visited = {id(focus)}
    frontier = [id(focus)]
    for level in range(1, max_depth + 1):
        next_frontier = []
        for item_key in frontier:
            for rec in by_blocked_key.get(item_key, []):
                entry = OrderedDict((k, v) for k, v in rec.items() if not k.startswith("_"))
                entry["level"] = level
                chain.append(entry)
                blocker_key = rec["_blocker_item_key"]
                if blocker_key not in visited:
                    visited.add(blocker_key)
                    next_frontier.append(blocker_key)
        if not next_frontier:
            break
        frontier = next_frontier
    return {"id": item_id, "blocked": any(entry["level"] == 1 for entry in chain), "count": len(chain), "chain": chain}


def _safe_depth(value, default=5):
    if value in (None, ""):
        return default
    try:
        depth = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(depth, 10))


def _normalize_details(details):
    normalized = OrderedDict()
    if not isinstance(details, dict):
        return normalized
    for key, value in details.items():
        normalized[str(key)] = _as_list(value)
    return normalized


def _copy_details(details):
    copied = OrderedDict()
    for key, values in details.items():
        copied[key] = list(values)
    return copied


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(entry) for entry in value if entry is not None]
    return [str(value)]


def _csv_values(value):
    if value in (None, ""):
        return None
    if isinstance(value, (list, tuple)):
        source_values = value
    else:
        source_values = str(value).split(",")
    values = [str(entry).strip() for entry in source_values if str(entry).strip()]
    return values or None


def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on", "only")


def _require_writable(context):
    if context.read_only:
        raise ValueError("MCP server is read-only.")
    if not context.writable_path:
        raise ValueError("No writable file is configured.")


def _now_text():
    return datetime.now().replace(second=0, microsecond=0).isoformat(timespec="minutes")


def _tool_result(result):
    text = json.dumps(result, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": result,
    }


def _jsonrpc_result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
