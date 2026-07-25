import hashlib
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, time, timedelta

from .agenda import (
    agenda_records,
    filter_agenda_records,
    filter_items,
    next_repeat_occurrence,
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
from .ids import (
    collect_item_ids,
    ensure_item_id,
    id_key_from_config,
    id_prefix_for_item,
)
from .links import dependency_blocker_records, link_records
from .model import Item
from .notifier import notification_records
from .parser import parse_text
from .serializer import item_to_line
from .status_summary import latest_status_records
from .timezone_policy import local_now_naive, today as timezone_today
from .timeutil import format_datetime, parse_date_or_datetime
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
    write_text,
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
        transactions_config = self.config.get("transactions") if isinstance(self.config.get("transactions"), dict) else {}
        self.transaction_preflight = None
        if not self.read_only and transactions_config.get("preflight_on_startup"):
            from .transaction_admin import preflight_report
            from .transaction_journal import journal_directory
            self.transaction_preflight = preflight_report(
                journal_directory(config=self.config, writable_path=self.writable_path),
                config=self.config,
                create=True,
            )
            if not self.transaction_preflight["ok"]:
                raise RuntimeError("Transaction startup preflight failed: %s" % "; ".join(self.transaction_preflight["errors"]))

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
    if request_id is None and method not in (
        "initialize",
        "tools/list",
        "tools/call",
        "resources/list",
        "resources/read",
        "prompts/list",
        "prompts/get",
    ):
        return None

    try:
        if method == "initialize":
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
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
        if method == "prompts/list":
            return _jsonrpc_result(request_id, {"prompts": prompt_list()})
        if method == "prompts/get":
            return _jsonrpc_result(
                request_id,
                prompt_get(params.get("name"), params.get("arguments") or {}),
            )
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


#: Tools that never write. Clients use readOnlyHint to skip confirmation.
READ_ONLY_TOOLS = frozenset(
    [
        "list_items", "get_item", "check_line", "parse_item", "get_agenda",
        "get_review", "get_graph", "get_blockers", "list_links", "list_status",
        "list_notifications", "list_messages", "get_file_state", "search_items",
        "get_next_actions", "get_stats", "get_habit_streaks", "get_workload",
        "get_status", "parse_shorthand", "timer_status", "check_files",
        "complete", "attachment_state",
        "get_projects", "get_project", "get_portfolio", "get_command_center",
        "get_areas", "get_backlinks", "get_clock_status",
        "run_query", "list_saved_views", "run_saved_view",
        "list_groups", "resolve_recipients", "get_delivery_state",
        "list_people", "get_person", "get_group_overview",
    ]
)

#: Tools that can remove or overwrite existing content.
DESTRUCTIVE_TOOLS = frozenset(
    ["delete_item", "set_status", "timer_cancel", "update_item", "stop_work", "attachment_delete"]
)


def _annotate(schema):
    """Apply MCP annotations from the central classification.

    Keeping the classification in one place means a new tool cannot quietly
    ship with the wrong hint just because its _tool() call omitted a flag.
    """
    name = schema.get("name", "")
    read_only = name in READ_ONLY_TOOLS
    annotations = schema.setdefault("annotations", {})
    annotations["title"] = name.replace("_", " ")
    annotations["readOnlyHint"] = read_only
    annotations["destructiveHint"] = name in DESTRUCTIVE_TOOLS
    annotations["idempotentHint"] = read_only
    annotations["openWorldHint"] = False
    return schema


def tool_schemas():
    return [_annotate(schema) for schema in _tool_schemas()]


def _tool_schemas():
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
        _tool(
            "complete_item",
            "Complete a repeat-enabled task instance by ID and materialize the next "
            "occurrence (Taskwarrior-style), using repeat_base:due|done. Non-repeating "
            "items are marked done with no new occurrence, matching mark_done.",
            {
                "id": _string("Item ID."),
                "date": _string("Completion date, YYYY-MM-DD. Defaults to today."),
            },
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
        _tool(
            "check_files",
            "Verify file: and dir: attachments: existence, correct type, content "
            "hash, and portability of the stored path.",
            {
                "id": _string("Only check attachments on this item id."),
                "problems_only": _bool("Only return attachments with an issue."),
                "no_verify": _bool("Skip hashing; check existence only."),
            },
        ),
        _tool(
            "attach_file",
            "Attach a file or directory to an item and record its content hash. "
            "The path is stored relative to the life.txt file with forward "
            "slashes, so it resolves on every platform.",
            {
                "id": _string("Item id to attach to."),
                "path": _string("Path to the file or directory."),
                "key": _string("Force file or dir; otherwise chosen from what is on disk."),
                "no_hash": _bool("Record the path without a content hash."),
                "dry_run": _bool("Return a diff instead of writing."),
                "expected_file_hash": _string("Reject the write if the file changed."),
                "attachment_revision": _string("Expected attachment SHA-256 revision for file references."),
            },
            required=["id", "path"],
        ),
        _tool(
            "attachment_put",
            "Create or replace an attachment and update its life.txt reference in one journal-backed transaction.",
            {
                "id": _string("Item ID."),
                "path": _string("Attachment destination relative to life.txt."),
                "content_base64": _string("Attachment bytes encoded as base64."),
                "content_text": _string("UTF-8 text content; mutually exclusive with content_base64."),
                "item_revision": _string("Expected life.txt SHA-256 revision."),
                "attachment_revision": _string("Expected attachment revision or <missing>."),
                "allow_executable": _bool("Allow executable/script attachment content."),
            },
            required=["id", "path"],
        ),
        _tool(
            "attachment_delete",
            "Delete an attachment and remove its life.txt reference in one journal-backed transaction.",
            {
                "id": _string("Item ID."),
                "path": _string("Attachment path relative to life.txt."),
                "item_revision": _string("Expected life.txt SHA-256 revision."),
                "attachment_revision": _string("Expected attachment SHA-256 revision."),
            },
            required=["id", "path"],
        ),
        _tool(
            "attachment_state",
            "Inspect attachment confinement, type, executable state, and revision.",
            {"path": _string("Attachment path relative to life.txt.")},
            required=["path"],
        ),
        _tool(
            "get_file_state",
            "Paths, write target, read-only flag, and content hashes. Call this "
            "before a write to obtain expected_file_hash for conflict detection.",
            {},
        ),
        _tool(
            "search_items",
            "Fuzzy search across titles, ids, and detail values. Title matches "
            "rank above id matches, which rank above detail matches.",
            {
                "query": _string("Search text."),
                "limit": _integer("Maximum results. Defaults to 20."),
            },
            required=["query"],
        ),
        _tool(
            "get_next_actions",
            "Actionable work: open or in progress, not blocked by a dependency, "
            "and not parked behind a someday or waiting tag. Ordered by "
            "priority, then due date, then age.",
            {
                "limit": _integer("Maximum results."),
                "project": _string("Only this project:."),
                "assignee": _string("Only this assignee:."),
            },
        ),
        _tool(
            "get_stats",
            "Task, habit, mood, and project statistics for a date range.",
            {
                "from": _string("Start date (YYYY-MM-DD)."),
                "to": _string("End date (YYYY-MM-DD)."),
                "group": _string("Bucket size: day, week, or month."),
            },
        ),
        _tool(
            "get_habit_streaks",
            "Per-habit completion counts and current streaks.",
            {
                "from": _string("Start date (YYYY-MM-DD)."),
                "to": _string("End date (YYYY-MM-DD)."),
            },
        ),
        _tool(
            "get_workload",
            "Open, actionable, due-soon, and overdue counts per assignee.",
            {},
        ),
        _tool(
            "get_status",
            "Presence records, including which status is currently open.",
            {
                "person": _string("Only this person:."),
                "active": _bool("Only records without to:."),
            },
        ),
        _tool(
            "set_status",
            "Record a presence status, closing the previously open one in the "
            "same write. Pass end=true to close without opening a new one. "
            "Switching to a state that is already open writes nothing unless "
            "force=true, so a repeated call cannot fragment one long block.",
            {
                "state": _string("New presence state, such as busy or focus."),
                "title": _string("Status title. Defaults to the state name."),
                "person": _string("Person the status belongs to. Defaults to self."),
                "note": _string("Free-text note stored as note:."),
                "project": _string("Associated project stored as project:."),
                "service": _string("Service stored as service:."),
                "visibility": _string("Visibility stored as visibility:."),
                "end": _bool("Close the current status without opening a new one."),
                "force": _bool("Record a new block even when the state is unchanged."),
                "dry_run": _bool("Return a unified diff instead of writing."),
                "expected_file_hash": _string(
                    "Hash from get_file_state. The write is rejected if the file changed."
                ),
            },
        ),
        _tool(
            "capture_item",
            "Create a task from plain text, expanding capture shorthand: "
            "@project sets project:, #tag adds tag:, !value sets priority:, and "
            "^date sets due:. Relative dates such as tomorrow or +3d resolve. "
            "lifetxt generates the id; do not invent one.",
            {
                "text": _string("Title with optional @ # ! ^ tokens."),
                "type": _string("Item type. Defaults to T."),
                "status": _string("Initial status. Defaults to [ ]."),
                "dry_run": _bool("Return a unified diff instead of writing."),
                "expected_file_hash": _string(
                    "Hash from get_file_state. The write is rejected if the file changed."
                ),
            },
            required=["text"],
        ),
        _tool(
            "parse_shorthand",
            "Preview capture-sigil and date-token expansion without writing. "
            "Call with no arguments to list every supported token.",
            {
                "text": _string("Text to expand."),
                "date": _string("A single date token to resolve."),
            },
        ),
        _tool(
            "complete",
            "Values already used in this file for a detail kind: projects, "
            "tags, ids, people, presence states, contexts. Use it to reuse an "
            "existing value instead of inventing a near-duplicate. Call with "
            "no kind to list the supported kinds.",
            {
                "kind": _string(
                    "One of: state, project, tag, person, id, type, status, "
                    "context, priority, key, team, service, channel."
                ),
                "prefix": _string("Only values starting with or containing this."),
                "limit": _integer("Maximum values to return. Defaults to 50."),
            },
        ),
        _tool(
            "timer_status",
            "The running timer, if any, with elapsed minutes.",
            {},
        ),
        _tool(
            "timer_start",
            "Start the single shared timer on an item and set it in progress.",
            {
                "id": _string("Item id to track."),
                "note": _string("Optional note stored with the timer state."),
                "dry_run": _bool("Describe the change instead of applying it."),
                "item_revision": _string("Expected life.txt SHA-256 revision."),
                "timer_revision": _string("Expected timer-state revision; use <missing> when idle."),
            },
            required=["id"],
        ),
        _tool(
            "timer_stop",
            "Stop the running timer and add the elapsed minutes to elapsed:.",
            {
                "dry_run": _bool("Describe the change instead of applying it."),
                "item_revision": _string("Expected life.txt SHA-256 revision."),
                "timer_revision": _string("Expected timer-state SHA-256 revision."),
            },
        ),
        _tool(
            "timer_cancel",
            "Discard the running timer without writing elapsed:.",
            {
                "dry_run": _bool("Describe the change instead of applying it."),
                "timer_revision": _string("Expected timer-state SHA-256 revision."),
            },
        ),
        _tool(
            "start_work",
            "Begin a work session: set the task in progress, start its timer, "
            "and record presence, in one call.",
            {
                "id": _string("Item id to work on."),
                "state": _string("Presence state. Defaults to busy."),
                "no_timer": _bool("Skip starting the timer."),
                "no_presence": _bool("Skip recording presence."),
                "dry_run": _bool("Describe the change instead of applying it."),
                "item_revision": _string("Expected life.txt SHA-256 revision."),
                "timer_revision": _string("Expected timer-state revision; use <missing> when idle."),
            },
            required=["id"],
        ),
        _tool(
            "stop_work",
            "End a work session: stop the timer and write elapsed:, close the "
            "open presence status, and optionally mark the task done.",
            {
                "done": _bool("Also mark the task complete."),
                "no_presence": _bool("Leave the presence status open."),
                "dry_run": _bool("Describe the change instead of applying it."),
                "item_revision": _string("Expected life.txt SHA-256 revision."),
                "timer_revision": _string("Expected timer-state SHA-256 revision."),
            },
        ),
        _tool(
            "get_projects",
            "List projects built from project: records with progress and health.",
            {"all": _bool("Include archived projects.")},
            read_only=True,
        ),
        _tool(
            "get_project",
            "Aggregated hub for one project: tasks, milestones, risks, decisions, meetings.",
            {"name": _string("Project name or alias.")},
            required=["name"],
            read_only=True,
        ),
        _tool(
            "get_portfolio",
            "Compare projects by state, progress, risk, and workload with transparent formulas.",
            {"all": _bool("Include archived projects.")},
            read_only=True,
        ),
        _tool(
            "get_command_center",
            "Daily command center: overdue, due, upcoming, blocked, waiting, messages, "
            "habits, captures, and projects needing attention.",
            {
                "horizon": _integer("Upcoming horizon in days. Default 3."),
                "person": _string("Scope unacknowledged messages to a recipient."),
                "mode": _string("Brief mode label: today, morning, or evening."),
            },
            read_only=True,
        ),
        _tool(
            "get_areas",
            "Group tasks and projects by area: with progress per area.",
            {},
            read_only=True,
        ),
        _tool(
            "get_backlinks",
            "Items that reference a given ID through parent/ref/depends_on/blocks/related.",
            {"id": _string("Target item ID.")},
            required=["id"],
            read_only=True,
        ),
        _tool(
            "run_query",
            "Filter items with the shared query language, e.g. "
            "'open project:web tag:urgent due<2026-08-01'.",
            {
                "query": _string("Query string."),
                "sort": _string("Sort key (line, due, status, title, ...)."),
                "order": _string("asc or desc."),
                "limit": _integer("Maximum items."),
            },
            required=["query"],
            read_only=True,
        ),
        _tool(
            "list_saved_views",
            "List saved views (named queries) with validation diagnostics.",
            {},
            read_only=True,
        ),
        _tool(
            "run_saved_view",
            "Run a saved view by name.",
            {"name": _string("Saved view name.")},
            required=["name"],
            read_only=True,
        ),
        _tool(
            "list_groups",
            "List messaging groups with resolved member counts and validation.",
            {},
            read_only=True,
        ),
        _tool(
            "resolve_recipients",
            "Expand people/teams/groups into a deterministic recipient set.",
            {"to": _string("Comma-separated people, teams, or groups.")},
            required=["to"],
            read_only=True,
        ),
        _tool(
            "get_delivery_state",
            "Per-recipient delivery state and acknowledgement status for messages.",
            {
                "id": _string("Restrict to one message ID."),
                "policy": _string("Override acknowledgement policy: any, all, or a count."),
            },
            read_only=True,
        ),
        _tool(
            "list_people",
            "List people with open-work, message, and meeting counts.",
            {},
            read_only=True,
        ),
        _tool(
            "get_person",
            "Overview of one person: assigned work, messages, meetings, projects, memberships.",
            {"name": _string("Person name or alias.")},
            required=["name"],
            read_only=True,
        ),
        _tool(
            "get_group_overview",
            "A group's members with each member's open work and message counts.",
            {"name": _string("Group name.")},
            required=["name"],
            read_only=True,
        ),
        _tool(
            "get_clock_status",
            "Report server-authoritative UTC time and optional client clock skew.",
            {"client_time": _string("ISO-8601 timestamp with UTC offset.")},
            read_only=True,
        ),
    ]


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------

#: Reusable workflows exposed through the MCP prompts capability. Clients show
#: these as slash commands, so the useful sequences do not have to be
#: rediscovered by every model on every conversation.
PROMPT_DEFINITIONS = OrderedDict(
    [
        (
            "daily_review",
            {
                "description": "Review today: what is due, what is actionable, what slipped.",
                "arguments": [],
                "template": (
                    "Review my life.txt for today.\n\n"
                    "1. Call get_agenda for today to see what is scheduled.\n"
                    "2. Call get_next_actions to see what is actionable now.\n"
                    "3. Call list_items with open_only and a before date of today to find "
                    "anything overdue.\n\n"
                    "Then summarise: what is due today, what I should do next in priority "
                    "order, and anything overdue that needs rescheduling. Do not write "
                    "anything; propose changes and wait for me to confirm."
                ),
            },
        ),
        (
            "weekly_review",
            {
                "description": "Weekly review: completions, stalled work, and habits.",
                "arguments": [],
                "template": (
                    "Run my weekly review.\n\n"
                    "1. Call get_review with week=true for completions and elapsed time.\n"
                    "2. Call get_stats with group=day for the same range.\n"
                    "3. Call get_habit_streaks for habit consistency.\n"
                    "4. Call get_blockers to find work waiting on something.\n\n"
                    "Summarise what I finished, where time went, which habits slipped, and "
                    "which items have been open longest. Suggest what to drop. Propose "
                    "changes with dry_run=true first."
                ),
            },
        ),
        (
            "standup",
            {
                "description": "Standup summary: done yesterday, today, blocked.",
                "arguments": [
                    {"name": "person", "description": "Person to report for.", "required": False}
                ],
                "template": (
                    "Write my standup update.\n\n"
                    "1. Call get_review for the last two days to find completions.\n"
                    "2. Call get_next_actions for what is planned.\n"
                    "3. Call get_blockers for anything blocked.\n\n"
                    "Format as three short bullet lists: Done, Today, Blocked. Keep it under "
                    "120 words and do not write to the file."
                ),
            },
        ),
        (
            "inbox_triage",
            {
                "description": "Process untriaged captures into projects and dates.",
                "arguments": [],
                "template": (
                    "Help me triage my inbox.\n\n"
                    "1. Call list_items with open_only=true to list open work.\n"
                    "2. Identify items with no project: and no due:.\n\n"
                    "For each, propose a project, a due date, and a priority, using "
                    "capture shorthand where helpful. Call update_item with dry_run=true so "
                    "I can review the diffs before anything is written."
                ),
            },
        ),
        (
            "start_focus",
            {
                "description": "Pick the next action and start a focused work session.",
                "arguments": [
                    {"name": "project", "description": "Limit to one project.", "required": False}
                ],
                "template": (
                    "Start a focus session.\n\n"
                    "1. Call get_next_actions (optionally filtered by project) and pick the "
                    "single best next action, explaining why in one sentence.\n"
                    "2. Confirm the choice with me.\n"
                    "3. On confirmation call start_work with that id, which sets it in "
                    "progress, starts the timer, and sets my presence to busy.\n\n"
                    "When I say I am done, call stop_work with done=true."
                ),
            },
        ),
    ]
)


def prompt_list():
    return [
        {
            "name": name,
            "description": spec["description"],
            "arguments": spec["arguments"],
        }
        for name, spec in PROMPT_DEFINITIONS.items()
    ]


def prompt_get(name, arguments=None):
    spec = PROMPT_DEFINITIONS.get(name)
    if spec is None:
        raise ValueError("Unknown prompt: %s" % name)
    text = spec["template"]
    for key, value in (arguments or {}).items():
        if value:
            text += "\n\nContext: %s = %s" % (key, value)
    return {
        "description": spec["description"],
        "messages": [
            {"role": "user", "content": {"type": "text", "text": text}}
        ],
    }


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


def _tool(name, description, properties, required=None, read_only=False, destructive=False):
    """Build a tool schema, including MCP annotations.

    Annotations are hints a client uses to decide what needs confirmation:
    readOnlyHint means the tool never writes, destructiveHint means it can
    remove or overwrite existing data.
    """
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
        "annotations": {
            "title": name.replace("_", " "),
            "readOnlyHint": bool(read_only),
            "destructiveHint": bool(destructive),
            "idempotentHint": bool(read_only),
            "openWorldHint": False,
        },
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


# ---------------------------------------------------------------------------
# write safety
# ---------------------------------------------------------------------------

#: Detail written on records the AI creates, so a human can always tell which
#: rows came from a model. Disable with config mcp.source_metadata = false.
SOURCE_DETAIL_KEY = "source"
SOURCE_DETAIL_VALUE = "mcp"


def file_hash(path):
    """Content hash of a life.txt file, or "" when it does not exist yet.

    Used as an optimistic-concurrency token: a client reads a hash, then passes
    it back on write so a change made in between is rejected instead of being
    silently overwritten.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()


def _read_text_safe(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return handle.read()
    except OSError:
        return ""


def _check_expected_hash(context, args):
    """Reject a write when the file changed after the client read it."""
    expected = args.get("expected_file_hash") or args.get("file_hash")
    if not expected:
        return
    current = file_hash(context.writable_path)
    if str(expected) != current:
        raise ValueError(
            "Write conflict: %s changed since it was read (expected %s, found %s). "
            "Re-read the file and retry." % (context.writable_path, expected, current)
        )


def _source_metadata_enabled(context):
    section = config_section(context.config, "mcp")
    value = section.get("source_metadata")
    if value is None:
        return True
    return str(value).strip().lower() not in ("0", "false", "no", "off")


def _stamp_source(item, context):
    if not _source_metadata_enabled(context):
        return item
    if not item.details.get(SOURCE_DETAIL_KEY):
        item.details[SOURCE_DETAIL_KEY] = [SOURCE_DETAIL_VALUE]
    return item


def _diff_lines(before, after, path):
    """Unified diff of a proposed write, for proposal mode."""
    import difflib

    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="%s (current)" % path,
            tofile="%s (proposed)" % path,
            lineterm="",
            n=2,
        )
    )


def _proposal(context, before, after, summary):
    """Structured description of a write that was not performed."""
    return {
        "applied": False,
        "proposal": True,
        "summary": summary,
        "path": context.writable_path,
        "file_hash": file_hash(context.writable_path),
        "diff": _diff_lines(before, after, context.writable_path),
    }


def _dry_run(args):
    return _truthy(args.get("dry_run")) or _truthy(args.get("propose"))


def _applied(context, result, summary=""):
    """Annotate a completed write with the new hash so the client can chain."""
    result = dict(result or {})
    result.setdefault("applied", True)
    result.setdefault("proposal", False)
    if summary:
        result.setdefault("summary", summary)
    result["path"] = context.writable_path
    result["file_hash"] = file_hash(context.writable_path)
    return result


def _reject_client_id(args, context):
    """IDs are generated by lifetxt, never trusted from the model.

    A model that invents an id will happily reuse one, which silently merges
    two different records on the next update.
    """
    details = args.get("details") or {}
    key = _id_key(context)
    supplied = details.get(key) if isinstance(details, dict) else None
    if supplied:
        raise ValueError(
            "Do not supply %s: on create; lifetxt generates it. Remove it and read "
            "the id from the response." % key
        )


def _ensure_server_id(item, context):
    """Guarantee a server-generated id on records the model creates.

    Client-supplied ids are refused, so the server must always provide one:
    without it the model has no handle to update or complete what it just
    wrote. This applies regardless of config ids.auto, which governs
    hand-written capture rather than API writes.
    """
    key = _id_key(context)
    assign_auto_id_from_paths(item, context.config, auto_id_paths(context.paths, context.writable_path))
    if item.details.get(key):
        return item
    from .ids import generate_item_id

    existing = set()
    items, _diagnostics = _read_items(context)
    for other in items:
        for value in other.details.get(key, []):
            existing.add(value)
    item.details[key] = [generate_item_id(item, existing_ids=existing)]
    return item


def _preview_write(context, apply_fn, summary):
    """Run a write, capture the diff, then restore the file.

    The existing write helpers only operate on files, so proposal mode applies
    the change and rolls it back rather than reimplementing every mutation as a
    pure function. The rollback is unconditional, so a failure mid-way still
    leaves the original bytes in place.
    """
    path = context.writable_path
    before = _read_text_safe(path)
    try:
        apply_fn()
        after = _read_text_safe(path)
    finally:
        write_text(path, before)
    proposal = _proposal(context, before, after, summary)
    proposal["file_hash"] = file_hash(path)
    return proposal


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
    _reject_client_id(args, context)
    _check_expected_hash(context, args)
    payload = {
        "status": args.get("status", "[ ]"),
        "type": args.get("type") or args.get("kind"),
        "title": args.get("title"),
        "details": _normalize_details(args.get("details") or {}),
    }
    item = item_from_payload(payload)
    _stamp_source(item, context)
    _ensure_server_id(item, context)
    line_no = append_item_to_file(context.writable_path, item)
    return {
        "line": line_no,
        "item": api_item(item, context.writable_path, _id_key(context)),
        "text": item_to_line(item),
    }


def _tool_update_item(args, context):
    _require_writable(context)
    _check_expected_hash(context, args)
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
    if _dry_run(args):
        return _preview_write(
            context,
            lambda: update_item_by_id_in_file(
                context.writable_path, item_id, payload, key=_id_key(context)
            ),
            "Update %s" % item_id,
        )
    item = update_item_by_id_in_file(context.writable_path, item_id, payload, key=_id_key(context))
    return _applied(
        context,
        {"id": item_id, "item": api_item(item, context.writable_path, _id_key(context))},
        "Update %s" % item_id,
    )


def _tool_mark_done(args, context):
    _require_writable(context)
    _check_expected_hash(context, args)
    item_id = str(args.get("id"))
    items, _diagnostics = _read_items(context)
    item = find_item_by_id(items, item_id, key=_id_key(context))
    if item is None:
        raise ValueError("Item id:%s was not found." % item_id)
    details = _copy_details(item.details)
    if not details.get("done"):
        details["done"] = [_completion_value(context, args)]
    payload = {"status": "[x]", "type": item.kind, "title": item.title, "details": details}
    if _dry_run(args):
        return _preview_write(
            context,
            lambda: update_item_by_id_in_file(
                context.writable_path, item_id, payload, key=_id_key(context)
            ),
            "Mark %s done" % item_id,
        )
    updated = update_item_by_id_in_file(
        context.writable_path, item_id, payload, key=_id_key(context)
    )
    return _applied(
        context,
        {"id": item_id, "item": api_item(updated, context.writable_path, _id_key(context))},
        "Mark %s done" % item_id,
    )


def _resolve_repeat_base(item, config):
    values = item.details.get("repeat_base")
    repeat_base = values[0] if values else None
    if not repeat_base:
        defaults = config_section(config, "defaults")
        repeat_base = defaults.get("repeat_base") or "due"
    return str(repeat_base).strip().lower()


def _tool_complete_item(args, context):
    _require_writable(context)
    item_id = str(args.get("id"))
    id_key = _id_key(context)
    items, _diagnostics = _read_items(context)
    item = find_item_by_id(items, item_id, key=id_key)
    if item is None:
        raise ValueError("Item id:%s was not found." % item_id)
    if item.status == "[x]":
        return {"id": item_id, "item": api_item(item, context.writable_path, id_key), "next": None}

    date_value = args.get("date")
    if date_value:
        completion_dt = parse_date_or_datetime(date_value, is_end=False)
        if completion_dt is None:
            raise ValueError("Invalid date %r. Use YYYY-MM-DD." % date_value)
        completion_date = completion_dt.date()
    else:
        completion_date = timezone_today()
    date_iso = completion_date.isoformat()

    repeat_value = item.details.get("repeat")
    next_item = None
    if repeat_value:
        repeat_base = _resolve_repeat_base(item, context.config)
        anchor_key, next_dt, _rule = next_repeat_occurrence(item, repeat_base, completion_date)
        if next_dt is not None:
            new_details = OrderedDict()
            for key, values in item.details.items():
                if key in (id_key, "done"):
                    continue
                new_details[key] = list(values)
            if next_dt.time() == time():
                next_value = next_dt.date().isoformat()
            else:
                next_value = format_datetime(next_dt)
            new_details[anchor_key] = [next_value]
            next_item = Item("[ ]", item.kind, item.title, new_details)
            existing_ids = collect_item_ids(items, key=id_key)
            ensure_item_id(
                next_item,
                existing_ids=existing_ids,
                key=id_key,
                prefix=id_prefix_for_item(next_item, context.config),
            )

    details = _copy_details(item.details)
    if not details.get("done"):
        details["done"] = [date_iso]
    updated = update_item_by_id_in_file(
        context.writable_path,
        item_id,
        {"status": "[x]", "type": item.kind, "title": item.title, "details": details},
        key=id_key,
    )

    result = {"id": item_id, "item": api_item(updated, context.writable_path, id_key), "next": None}
    if next_item is not None:
        append_item_to_file(context.writable_path, next_item)
        result["next"] = api_item(next_item, context.writable_path, id_key)
    return result


def _tool_delete_item(args, context):
    _require_writable(context)
    _check_expected_hash(context, args)
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


# ---------------------------------------------------------------------------
# shorthand parity: presence, capture, completion precision
# ---------------------------------------------------------------------------


def _default_base_path(context):
    """File that anchors relative attachment paths for single-file loads."""
    return context.writable_path or (context.paths[0] if context.paths else None)


def _tool_check_files(args, context):
    """Verify file:/dir: attachments: existence, type, hash, and portability."""
    from .attachments import (
        STATUS_CHANGED,
        STATUS_ERROR,
        STATUS_MISSING,
        STATUS_WRONG_TYPE,
        attachment_records,
        item_base_dir,
    )

    items, _diagnostics = _read_items(context)
    wanted = args.get("id")
    verify = not _truthy(args.get("no_verify"))
    problems_only = _truthy(args.get("problems_only"))
    id_key = _id_key(context)

    rows = []
    problems = 0
    for item in items:
        if wanted and wanted not in [str(v) for v in item.details.get(id_key, [])]:
            continue
        for record in attachment_records(
            item,
            base_dir=item_base_dir(item, _default_base_path(context)),
            config=context.config,
            verify=verify,
        ):
            broken = record["status"] in (
                STATUS_MISSING, STATUS_CHANGED, STATUS_WRONG_TYPE, STATUS_ERROR
            )
            if broken:
                problems += 1
            if problems_only and not broken and not record["notes"]:
                continue
            rows.append(
                {
                    "id": (item.details.get(id_key) or [""])[0],
                    "title": item.title,
                    "key": record["key"],
                    "path": record["path"],
                    "status": record["status"],
                    "hash": record["hash"],
                    "actual_hash": record["actual_hash"],
                    "notes": record["notes"],
                }
            )
    return {"count": len(rows), "problems": problems, "attachments": rows}


def _tool_attach_file(args, context):
    """Attach a file or directory to an item, recording its content hash."""
    from .attachments import (
        DIR_KEY,
        FILE_KEY,
        AttachmentError,
        hash_target,
        item_base_dir,
        join_value,
        normalize_stored_path,
        resolve_raw_path,
    )

    _require_writable(context)
    _check_expected_hash(context, args)
    item_id = str(args.get("id") or "").strip()
    path_value = str(args.get("path") or "").strip()
    if not item_id or not path_value:
        raise ValueError("attach_file requires id and path.")

    items, _diagnostics = _read_items(context)
    item = find_item_by_id(items, item_id, key=_id_key(context))
    if item is None:
        raise ValueError("Item id:%s was not found." % item_id)

    base_dir = item_base_dir(item, _default_base_path(context))
    try:
        resolved = resolve_raw_path(path_value, base_dir)
    except AttachmentError as exc:
        raise ValueError(str(exc))
    if not os.path.exists(resolved):
        raise ValueError(
            "%s does not exist (resolved to %s). Attachments are relative to the "
            "life.txt file, not the working directory." % (path_value, resolved)
        )

    is_dir = os.path.isdir(resolved)
    key = DIR_KEY if is_dir else FILE_KEY
    if args.get("key") in (FILE_KEY, DIR_KEY) and args["key"] != key:
        raise ValueError(
            "%s is a %s; use key=%s." % (path_value, "directory" if is_dir else "file", key)
        )

    if not is_dir and not _dry_run(args):
        from .attachment_transactions import reference_attachment
        report = reference_attachment(
            context.writable_path,
            item_id,
            path_value,
            item_revision=args.get("expected_file_hash"),
            attachment_expected_revision=args.get("attachment_revision"),
            config=context.config,
            require_revisions=_timer_revisions_required(context),
        )
        refreshed, _diagnostics = _read_items(context)
        updated = find_item_by_id(refreshed, item_id, key=_id_key(context))
        report["key"] = FILE_KEY
        report["item"] = api_item(updated, context.writable_path, _id_key(context))
        return _applied(
            context, report, "Attach %s to %s" % (report.get("value"), item_id)
        )

    digest = ""
    if not _truthy(args.get("no_hash")):
        try:
            digest = hash_target(resolved, is_dir=is_dir)
        except AttachmentError as exc:
            raise ValueError(str(exc))
    value = join_value(normalize_stored_path(path_value), digest)

    details = _copy_details(item.details)
    existing = [str(v) for v in details.get(key, [])]
    from .attachments import split_value as _split

    kept = []
    for old in existing:
        try:
            old_path, _old_hash = _split(old)
        except AttachmentError:
            kept.append(old)
            continue
        if normalize_stored_path(old_path) != normalize_stored_path(path_value):
            kept.append(old)
    details[key] = kept + [value]

    payload = {"status": item.status, "type": item.kind, "title": item.title, "details": details}
    if _dry_run(args):
        return _preview_write(
            context,
            lambda: update_item_by_id_in_file(
                context.writable_path, item_id, payload, key=_id_key(context)
            ),
            "Attach %s to %s" % (value, item_id),
        )
    updated = update_item_by_id_in_file(
        context.writable_path, item_id, payload, key=_id_key(context)
    )
    return _applied(
        context,
        {
            "id": item_id,
            "key": key,
            "value": value,
            "item": api_item(updated, context.writable_path, _id_key(context)),
        },
        "Attach %s to %s" % (value, item_id),
    )


def _tool_attachment_put(args, context):
    import base64
    from .attachment_transactions import put_attachment

    _require_writable(context)
    item_id = str(args.get("id") or "").strip()
    path_value = str(args.get("path") or "").strip()
    if not item_id or not path_value:
        raise ValueError("attachment_put requires id and path.")
    encoded = args.get("content_base64")
    text = args.get("content_text")
    if encoded not in (None, "") and text not in (None, ""):
        raise ValueError("Use only one of content_base64 or content_text.")
    if encoded not in (None, ""):
        try:
            payload = base64.b64decode(str(encoded), validate=True)
        except Exception as exc:
            raise ValueError("Invalid content_base64: %s" % exc)
    elif text is not None:
        payload = str(text).encode("utf-8")
    else:
        raise ValueError("attachment_put requires content_base64 or content_text.")
    return put_attachment(
        context.writable_path, item_id, path_value, payload,
        item_revision=args.get("item_revision") or args.get("expected_file_hash"),
        attachment_expected_revision=args.get("attachment_revision"),
        config=context.config,
        allow_executable=_truthy(args.get("allow_executable")),
        require_revisions=_timer_revisions_required(context),
    )


def _tool_attachment_delete(args, context):
    from .attachment_transactions import delete_attachment

    _require_writable(context)
    item_id = str(args.get("id") or "").strip()
    path_value = str(args.get("path") or "").strip()
    if not item_id or not path_value:
        raise ValueError("attachment_delete requires id and path.")
    return delete_attachment(
        context.writable_path, item_id, path_value,
        item_revision=args.get("item_revision") or args.get("expected_file_hash"),
        attachment_expected_revision=args.get("attachment_revision"),
        config=context.config,
        require_revisions=_timer_revisions_required(context),
    )


def _tool_attachment_state(args, context):
    from .attachment_transactions import attachment_state

    path_value = str(args.get("path") or "").strip()
    if not path_value:
        raise ValueError("attachment_state requires path.")
    return attachment_state(context.writable_path, path_value, config=context.config)


def _tool_set_status(args, context):
    """Record a presence status, closing the previously open one."""
    from .presence import status_transition

    _require_writable(context)
    _check_expected_hash(context, args)

    close_only = _truthy(args.get("end"))
    state_value = args.get("state")
    if not close_only and not state_value:
        raise ValueError("set_status requires state, or end=true to close the current status.")

    details = OrderedDict()
    for key in ("note", "project", "service", "visibility"):
        value = args.get(key)
        if value:
            details[key] = [str(value)]

    before = _read_text_safe(context.writable_path)
    result = status_transition(
        before,
        state=state_value,
        title=args.get("title"),
        person=args.get("person") or "self",
        details=details,
        id_key=_id_key(context),
        close_only=close_only,
        force=_truthy(args.get("force")),
    )

    if result.unchanged:
        return {
            "applied": False,
            "proposal": False,
            "unchanged": result.unchanged,
            "summary": "Already %s; nothing written. Pass force=true to start a new record."
            % result.unchanged,
            "path": context.writable_path,
            "file_hash": file_hash(context.writable_path),
        }

    summary = "Close status" if close_only else "Switch status to %s" % state_value
    if _dry_run(args):
        proposal = _proposal(context, before, result.text, summary)
        proposal["closed"] = result.closed
        proposal["opened"] = result.opened
        return proposal

    write_text(context.writable_path, result.text)
    return _applied(
        context,
        {"closed": result.closed, "opened": result.opened, "unchanged": ""},
        summary,
    )


def _tool_get_status(args, context):
    """Presence records, including which one is currently open."""
    from .presence import active_status_items

    items, _diagnostics = _read_items(context)
    person = args.get("person")
    records = latest_status_records(items, person=person, active_only=_truthy(args.get("active")))
    open_items = active_status_items(items, person=person)
    return {
        "count": len(records),
        "records": records,
        "open": [
            {
                "person": (item.details.get("person") or ["self"])[0],
                "state": (item.details.get("state") or [""])[0],
                "since": (item.details.get("from") or [""])[0],
                "title": item.title,
            }
            for item in open_items
        ],
    }


def _tool_capture_item(args, context):
    """Create a task from plain text, expanding capture sigils."""
    from .shorthand import ShorthandError, parse_capture

    _require_writable(context)
    _check_expected_hash(context, args)
    text = str(args.get("text") or "").strip()
    if not text:
        raise ValueError("capture_item requires text.")
    try:
        title, details = parse_capture(text, strict_dates=True)
    except ShorthandError as exc:
        raise ValueError(str(exc))
    if not title:
        raise ValueError("Capture shorthand consumed the whole title. Include a title.")

    payload = {
        "status": args.get("status", "[ ]"),
        "type": args.get("type") or "T",
        "title": title,
        "details": _normalize_details(details),
    }
    item = item_from_payload(payload)
    _stamp_source(item, context)
    _ensure_server_id(item, context)

    before = _read_text_safe(context.writable_path)
    line = item_to_line(item)
    if _dry_run(args):
        after = before + ("" if before.endswith(("\n", "")) else "\n") + line + "\n"
        proposal = _proposal(context, before, after, "Capture %s" % title)
        proposal["text"] = line
        return proposal

    line_no = append_item_to_file(context.writable_path, item)
    return _applied(
        context,
        {
            "line": line_no,
            "item": api_item(item, context.writable_path, _id_key(context)),
            "text": line,
        },
        "Capture %s" % title,
    )


def _tool_complete(args, context):
    """Values this file already uses, so agents reuse rather than reinvent.

    Backed by the same `completion` layer as the shell scripts, the Web UI,
    and the TUI, so every surface offers the same candidates.
    """
    from .completion import VALUE_KINDS, candidates

    kind = args.get("kind")
    if not kind:
        return {"kinds": list(VALUE_KINDS)}
    if kind not in VALUE_KINDS:
        raise ValueError(
            "Unknown kind %r. Use one of: %s" % (kind, ", ".join(VALUE_KINDS))
        )

    limit = args.get("limit")
    try:
        limit = int(limit) if limit is not None else 50
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    items, _diagnostics = _read_items(context)
    values = candidates(kind, args.get("prefix") or "", items=items, limit=limit)
    return {
        "kind": kind,
        "prefix": args.get("prefix") or "",
        "count": len(values),
        "values": values,
    }


def _tool_parse_shorthand(args, _context):
    """Preview capture-sigil expansion without writing anything."""
    from .shorthand import (
        ShorthandError,
        describe_date_tokens,
        describe_sigils,
        parse_capture,
        resolve_date_token,
    )

    text = str(args.get("text") or "")
    result = {
        "sigils": [{"token": token, "expands_to": target} for token, target in describe_sigils()],
        "date_tokens": [{"token": token, "meaning": meaning} for token, meaning in describe_date_tokens()],
    }
    if text:
        try:
            title, details = parse_capture(text, strict_dates=True)
        except ShorthandError as exc:
            raise ValueError(str(exc))
        result["title"] = title
        result["details"] = details
    date_value = args.get("date")
    if date_value:
        try:
            result["date"] = resolve_date_token(date_value, strict=True)
        except ShorthandError as exc:
            raise ValueError(str(exc))
    return result


def _completion_value(context, args):
    """done: value honouring the same config the CLI and TUI use."""
    explicit = args.get("done") or args.get("date")
    if explicit:
        return str(explicit)
    precision = str(config_section(context.config, "done").get("precision") or "date").lower()
    if _truthy(args.get("now")):
        precision = "datetime"
    if precision not in ("date", "datetime"):
        raise ValueError("config done.precision must be date or datetime.")
    moment = local_now_naive()
    if precision == "datetime":
        return moment.strftime("%Y-%m-%dT%H:%M")
    return moment.date().isoformat()


# ---------------------------------------------------------------------------
# timer and work sessions
# ---------------------------------------------------------------------------


def _timer_state_file(context):
    from . import timer as timer_module

    return timer_module.timer_state_file(context.config)


def _tool_timer_status(_args, context):
    from . import timer as timer_module

    return timer_module.timer_status_data(config=context.config, paths=context.paths)


def _timer_revisions_required(context):
    from .revision_telemetry import revision_mode

    return revision_mode(context.config) == "required"


def _tool_timer_start(args, context):
    from . import timer as timer_module

    _require_writable(context)
    item_id = str(args.get("id") or "").strip()
    if not item_id:
        raise ValueError("timer_start requires id.")
    items, _diagnostics = _read_items(context)
    item = find_item_by_id(items, item_id, key=_id_key(context))
    if item is None:
        raise ValueError("Item id:%s was not found." % item_id)
    if _dry_run(args):
        return {
            "applied": False,
            "proposal": True,
            "summary": "Start a timer for %s and set it in progress" % item_id,
            "id": item_id,
            "required_revisions": ["item_revision", "timer_revision"],
        }
    source = getattr(item, "source", None) or context.writable_path
    result = timer_module.start_timer_transaction(
        source,
        item_id,
        note=args.get("note"),
        config=context.config,
        expected_item_revision=args.get("item_revision"),
        expected_timer_revision=args.get("timer_revision"),
        require_revisions=_timer_revisions_required(context),
    )
    return _applied(context, result, "Timer started for %s" % item_id)


def _tool_timer_stop(args, context):
    from . import timer as timer_module

    _require_writable(context)
    status = timer_module.timer_status_data(config=context.config, paths=context.paths)
    if not status.get("running"):
        raise ValueError("No running timer.")
    if _dry_run(args):
        return {
            "applied": False,
            "proposal": True,
            "summary": "Stop the timer for %s and write elapsed:" % status.get("id"),
            "id": status.get("id"),
            "required_revisions": ["item_revision", "timer_revision"],
        }
    result = timer_module.stop_timer_transaction(
        config=context.config,
        expected_item_revision=args.get("item_revision"),
        expected_timer_revision=args.get("timer_revision"),
        require_revisions=_timer_revisions_required(context),
    )
    return _applied(context, result, "Timer stopped")


def _tool_timer_cancel(args, context):
    from . import timer as timer_module

    _require_writable(context)
    status = timer_module.timer_status_data(config=context.config, paths=context.paths)
    if not status.get("running"):
        raise ValueError("No running timer to cancel.")
    if _dry_run(args):
        return {
            "applied": False,
            "proposal": True,
            "summary": "Discard the timer for %s without writing elapsed:" % status.get("id"),
            "required_revisions": ["timer_revision"],
        }
    result = timer_module.cancel_timer_transaction(
        config=context.config,
        expected_timer_revision=args.get("timer_revision"),
        require_revision=_timer_revisions_required(context),
    )
    result.update({"applied": True, "proposal": False})
    return result


def _tool_start_work(args, context):
    """Start task, timer, and presence in one journal-backed transaction."""
    from .work_session import start_work_transaction

    _require_writable(context)
    item_id = str(args.get("id") or "").strip()
    if not item_id:
        raise ValueError("start_work requires id.")
    items, _diagnostics = _read_items(context)
    item = find_item_by_id(items, item_id, key=_id_key(context))
    if item is None:
        raise ValueError("Item id:%s was not found." % item_id)
    state_value = args.get("state") or "busy"
    if _dry_run(args):
        return {
            "applied": False, "proposal": True,
            "summary": "Start %s, timer, and presence %s as one transaction" % (item_id, state_value),
            "required_revisions": ["item_revision", "timer_revision"],
        }
    result = start_work_transaction(
        context.writable_path, item_id, state=state_value,
        use_timer=not _truthy(args.get("no_timer")),
        use_presence=not _truthy(args.get("no_presence")),
        config=context.config,
        expected_item_revision=args.get("item_revision"),
        expected_timer_revision=args.get("timer_revision"),
        require_revisions=_timer_revisions_required(context),
    )
    result.update({"applied": True, "proposal": False})
    return result


def _tool_stop_work(args, context):
    """Stop timer, update task, and close presence in one transaction."""
    from .work_session import stop_work_transaction

    _require_writable(context)
    status = _tool_timer_status({}, context)
    if not status.get("running"):
        raise ValueError("No running timer.")
    if _dry_run(args):
        return {
            "applied": False, "proposal": True,
            "summary": "Stop %s and close the compound work session" % status.get("id"),
            "required_revisions": ["item_revision", "timer_revision"],
        }
    result = stop_work_transaction(
        path=status.get("file"),
        done=_truthy(args.get("done")),
        close_presence=not _truthy(args.get("no_presence")),
        config=context.config,
        expected_item_revision=args.get("item_revision"),
        expected_timer_revision=args.get("timer_revision"),
        require_revisions=_timer_revisions_required(context),
    )
    result.update({"applied": True, "proposal": False})
    return result


def _namespace(**kwargs):
    import argparse as _argparse

    return _argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------


def _tool_get_next_actions(args, context):
    """Open, unblocked, non-parked work ordered by priority then due date."""
    from .nextaction import next_action_items

    items, diagnostics = _read_items(context)
    selected = next_action_items(
        items,
        key=_id_key(context),
        limit=args.get("limit"),
        project=args.get("project"),
        assignee=args.get("assignee"),
    )
    return items_response(selected, diagnostics, context.writable_path, _id_key(context))


def _tool_search_items(args, context):
    """Fuzzy search across titles, ids, and detail values."""
    from .shorthand import parse_capture  # noqa: F401  (keeps import cost in one place)
    from .tui_app import fuzzy_match

    query = str(args.get("query") or args.get("q") or "").strip()
    if not query:
        raise ValueError("search_items requires query.")
    items, diagnostics = _read_items(context)
    limit = args.get("limit") or 20

    scored = []
    for index, item in enumerate(items):
        haystacks = [
            (item.title or "", 3.0),
            (" ".join(str(v) for v in item.details.get(_id_key(context)) or []), 2.0),
        ]
        detail_text = " ".join(
            "%s:%s" % (key, value)
            for key, values in item.details.items()
            for value in values
        )
        haystacks.append((detail_text, 1.0))
        best = None
        for text, weight in haystacks:
            if not text:
                continue
            match = fuzzy_match(query, text)
            if match is None:
                continue
            score = match[0] * weight
            if best is None or score > best:
                best = score
        if best is not None:
            scored.append((-best, index, item))
    scored.sort()
    if scored:
        best = -scored[0][0]
        cutoff = best * 0.25
        scored = [entry for entry in scored if -entry[0] >= cutoff]
    selected = [entry[2] for entry in scored[: max(1, int(limit))]]
    return items_response(selected, diagnostics, context.writable_path, _id_key(context))


def _tool_get_stats(args, context):
    """Task, habit, mood, and project statistics for a date range."""
    from .stats import build_stats, stats_range

    items, _diagnostics = _read_items(context)
    start, end = stats_range(args.get("from"), args.get("to"))
    group = args.get("group") or "day"
    if group not in ("day", "week", "month"):
        raise ValueError("group must be day, week, or month.")
    return build_stats(items, start, end, group)


def _tool_get_habit_streaks(args, context):
    """Per-habit completion counts and current streaks."""
    from .stats import habit_stats, stats_range

    items, _diagnostics = _read_items(context)
    start, end = stats_range(args.get("from"), args.get("to"))
    # habit_stats does not filter by kind; build_stats passes only H records
    # and so must this, or every task with a done: date looks like a habit.
    habits = [item for item in items if item.kind == "H"]
    return {"habits": habit_stats(habits, start, end)}


def _tool_get_workload(args, context):
    """Open, due-soon, and overdue counts per assignee."""
    from .nextaction import is_actionable

    items, _diagnostics = _read_items(context)
    today = timezone_today().isoformat()
    soon = (timezone_today() + timedelta(days=7)).isoformat()

    people = OrderedDict()
    for item in items:
        if item.kind not in ("T", "D", "R", "H"):
            continue
        if item.status not in ("[ ]", "[/]"):
            continue
        owners = [str(v) for v in item.details.get("assignee") or []] or ["(unassigned)"]
        due = (item.details.get("due") or [""])[0]
        for owner in owners:
            row = people.setdefault(
                owner, {"person": owner, "open": 0, "due_soon": 0, "overdue": 0, "actionable": 0}
            )
            row["open"] += 1
            if is_actionable(item.status, item.details, kind=item.kind):
                row["actionable"] += 1
            if due:
                if due < today:
                    row["overdue"] += 1
                elif due <= soon:
                    row["due_soon"] += 1
    return {"count": len(people), "people": list(people.values())}


def _tool_get_projects(args, context):
    """Project summaries with progress and health, from project: records."""
    from .projects import project_list

    items, _diagnostics = _read_items(context)
    rows = project_list(items, context.config, timezone_today(),
                        include_archived=_truthy(args.get("all")))
    return {"count": len(rows), "projects": rows}


def _tool_get_project(args, context):
    """Aggregated hub for one project without duplicating records."""
    from .projects import project_hub

    items, _diagnostics = _read_items(context)
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("get_project requires 'name'.")
    return project_hub(items, context.config, name, timezone_today())


def _tool_get_portfolio(args, context):
    """Compare projects by state, progress, risk, and workload."""
    from .projects import portfolio

    items, _diagnostics = _read_items(context)
    return portfolio(items, context.config, timezone_today(),
                     include_archived=_truthy(args.get("all")))


def _tool_get_command_center(args, context):
    """Daily command center: overdue, due, blocked, messages, project attention."""
    from .command_center import command_center

    items, _diagnostics = _read_items(context)
    horizon = args.get("horizon")
    try:
        horizon = int(horizon) if horizon is not None else 3
    except (TypeError, ValueError):
        horizon = 3
    return command_center(items, context.config, timezone_today(),
                          horizon_days=horizon, person=args.get("person"),
                          mode=str(args.get("mode") or "today"))


def _tool_get_areas(args, context):
    """Group tasks and projects by area:."""
    from .areas import area_list

    items, _diagnostics = _read_items(context)
    rows = area_list(items, context.config)
    return {"count": len(rows), "areas": rows}


def _tool_get_backlinks(args, context):
    """Items that reference a given ID (incoming links)."""
    from .links import backlink_records

    items, _diagnostics = _read_items(context)
    target = str(args.get("id") or "")
    if not target:
        raise ValueError("get_backlinks requires 'id'.")
    records = backlink_records(items, target, key=_id_key(context))
    return {"target_id": target, "count": len(records), "backlinks": records}


def _tool_get_clock_status(args, context):
    from .clock_skew import clock_skew_report
    return clock_skew_report(args.get("client_time"), config=context.config)


def _tool_run_query(args, context):
    """Filter items with the shared query language."""
    from .query import run_query

    items, diagnostics = _read_items(context)
    query_text = str(args.get("query") or "")
    filtered, query_diags = run_query(
        items, query_text, config=context.config,
        sort=args.get("sort"), order=args.get("order") or "asc",
        limit=args.get("limit"),
    )
    response = items_response(filtered, diagnostics, context.writable_path, _id_key(context))
    response["query_diagnostics"] = query_diags
    return response


def _tool_list_saved_views(_args, context):
    """List saved views (named queries) from configuration."""
    from .saved_views import list_saved_views, validate_saved_views

    return {
        "views": list_saved_views(context.config),
        "diagnostics": validate_saved_views(context.config),
    }


def _tool_run_saved_view(args, context):
    """Run a saved view by name."""
    from .saved_views import run_saved_view

    items, diagnostics = _read_items(context)
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("run_saved_view requires 'name'.")
    filtered, query_diags = run_saved_view(items, context.config, name)
    response = items_response(filtered, diagnostics, context.writable_path, _id_key(context))
    response["query_diagnostics"] = query_diags
    return response


def _tool_list_groups(_args, context):
    """List messaging groups with resolved member counts and validation."""
    from .groups import group_summaries, validate_groups

    return {
        "groups": group_summaries(context.config),
        "diagnostics": validate_groups(context.config),
    }


def _tool_resolve_recipients(args, context):
    """Expand people/teams/groups into a deterministic recipient set."""
    from .groups import resolve_recipients

    refs = args.get("to") or args.get("references") or []
    if isinstance(refs, str):
        refs = [r.strip() for r in refs.split(",") if r.strip()]
    return resolve_recipients(context.config, refs)


def _tool_get_delivery_state(args, context):
    """Per-recipient delivery state and acknowledgement status for messages."""
    from .delivery import delivery_summary
    from .groups import resolve_recipients

    items, _diagnostics = _read_items(context)
    target_id = args.get("id")
    policy = args.get("policy")
    summaries = []
    for item in items:
        if item.kind != "M":
            continue
        if target_id and (item.details.get("id", [None])[0] != str(target_id)):
            continue
        summaries.append(delivery_summary(item, context.config, resolve_recipients, policy))
    return {"count": len(summaries), "messages": summaries}


def _tool_list_people(_args, context):
    """List people with open-work, message, and meeting counts."""
    from .people import people_list

    items, _diagnostics = _read_items(context)
    return {"people": people_list(items, context.config, timezone_today())}


def _tool_get_person(args, context):
    """Overview of one person: work, messages, meetings, projects, memberships."""
    from .people import person_overview

    items, _diagnostics = _read_items(context)
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("get_person requires 'name'.")
    return person_overview(items, context.config, name, timezone_today())


def _tool_get_group_overview(args, context):
    """A group's members with each member's open work and message counts."""
    from .people import group_overview

    items, _diagnostics = _read_items(context)
    name = str(args.get("name") or "")
    if not name:
        raise ValueError("get_group_overview requires 'name'.")
    return group_overview(items, context.config, name, timezone_today())


def _tool_get_file_state(_args, context):
    """Paths, write target, read-only flag, and content hashes.

    A client calls this before a write to obtain expected_file_hash.
    """
    return {
        "paths": list(context.paths),
        "writable_path": context.writable_path,
        "read_only": context.read_only,
        "file_hash": file_hash(context.writable_path),
        "hashes": OrderedDict((path, file_hash(path)) for path in context.paths),
        "source_metadata": _source_metadata_enabled(context),
        "done_precision": str(
            config_section(context.config, "done").get("precision") or "date"
        ).lower(),
    }


TOOL_HANDLERS = OrderedDict(
    [
        ("list_items", _tool_list_items),
        ("get_item", _tool_get_item),
        ("check_line", _tool_check_line),
        ("parse_item", _tool_parse_item),
        ("create_item", _tool_create_item),
        ("update_item", _tool_update_item),
        ("mark_done", _tool_mark_done),
        ("complete_item", _tool_complete_item),
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
        ("get_file_state", _tool_get_file_state),
        ("search_items", _tool_search_items),
        ("get_next_actions", _tool_get_next_actions),
        ("get_stats", _tool_get_stats),
        ("get_habit_streaks", _tool_get_habit_streaks),
        ("get_workload", _tool_get_workload),
        ("get_status", _tool_get_status),
        ("set_status", _tool_set_status),
        ("capture_item", _tool_capture_item),
        ("parse_shorthand", _tool_parse_shorthand),
        ("complete", _tool_complete),
        ("timer_status", _tool_timer_status),
        ("timer_start", _tool_timer_start),
        ("timer_stop", _tool_timer_stop),
        ("timer_cancel", _tool_timer_cancel),
        ("start_work", _tool_start_work),
        ("stop_work", _tool_stop_work),
        ("check_files", _tool_check_files),
        ("attach_file", _tool_attach_file),
        ("attachment_put", _tool_attachment_put),
        ("attachment_delete", _tool_attachment_delete),
        ("attachment_state", _tool_attachment_state),
        ("get_projects", _tool_get_projects),
        ("get_project", _tool_get_project),
        ("get_portfolio", _tool_get_portfolio),
        ("get_command_center", _tool_get_command_center),
        ("get_areas", _tool_get_areas),
        ("get_backlinks", _tool_get_backlinks),
        ("run_query", _tool_run_query),
        ("list_saved_views", _tool_list_saved_views),
        ("run_saved_view", _tool_run_saved_view),
        ("list_groups", _tool_list_groups),
        ("resolve_recipients", _tool_resolve_recipients),
        ("get_delivery_state", _tool_get_delivery_state),
        ("list_people", _tool_list_people),
        ("get_person", _tool_get_person),
        ("get_group_overview", _tool_get_group_overview),
        ("get_clock_status", _tool_get_clock_status),
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
    return local_now_naive().replace(second=0, microsecond=0).isoformat(timespec="minutes")


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
