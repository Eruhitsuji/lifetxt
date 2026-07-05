# life.txt Web API And GUI

The web interface is optional. It uses FastAPI and uvicorn, but the core parser
and CLI remain dependency-free.

## Install

```sh
pip install -r requirements-web.txt
```

## Start

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

Open:

```txt
http://127.0.0.1:8000/
```

Multiple files can be read at once. Paths may be glob patterns such as
`projects/**/*.life.txt`, and directories are expanded to life.txt-like `.txt`
files. Create, update, and delete operations use the first file unless
`--write-file` is specified.

```sh
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve "projects/**/*.life.txt" --write-file life.txt
```

## REST API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Show server paths and writable file |
| `GET` | `/api/config` | Show public runtime config used by the GUI |
| `GET` | `/api/items` | List items with optional filters |
| `POST` | `/api/items/parse` | Parse a raw life.txt line/body block and return parsed item data without writing |
| `POST` | `/api/items/raw` | Append a validated raw life.txt line to the writable file |
| `GET` | `/api/items/id/{id}` | Get an item by exact `id:` |
| `PUT` | `/api/items/id/{id}` | Replace an item by exact `id:` in the writable file |
| `DELETE` | `/api/items/id/{id}` | Delete an item by exact `id:` in the writable file |
| `GET` | `/api/links` | List ID-based links such as `parent:`, `ref:`, `depends_on:`, `blocks:`, and `related:` |
| `GET` | `/api/graph` | Return `nodes` and `edges` for ID references used by the graph UI; nodes referenced but not found carry `missing: true` |
| `GET` | `/api/blockers` | Return the transitive blocker chain for `?id=ID` (levels 1..N, `depth` caps traversal, default 5) |
| `GET` | `/api/messages` | List type `M` message items with message filters |
| `GET` | `/api/messages/id/{id}` | Get a message by exact `id:` |
| `PUT` | `/api/messages/id/{id}` | Replace a message by exact `id:` in the writable file |
| `DELETE` | `/api/messages/id/{id}` | Delete a message by exact `id:` in the writable file |
| `POST` | `/api/messages/id/{id}/ack` | Mark a writable message as acknowledged with `ack:` |
| `POST` | `/api/messages/id/{id}/snooze` | Set `snooze_until:` on a writable message |
| `GET` | `/api/messages/thread/{id}` | List messages whose `id:` or `parent:` matches the id |
| `POST` | `/api/messages/id/{id}/reply` | Append a reply message with `parent:{id}` |
| `POST` | `/api/messages` | Append a type `M` message item using a message-oriented payload |
| `POST` | `/api/items` | Append an item to the writable file |
| `PUT` | `/api/items/{line}` | Replace an item on a line in the writable file |
| `DELETE` | `/api/items/{line}` | Delete an item line from the writable file |
| `GET` | `/api/agenda` | Show agenda records for a datetime range |
| `GET` | `/api/status` | Show latest status / presence records |
| `GET` | `/api/notifications` | Show due message notifications for a recipient |
| `GET` | `/api/chart/tasks` | Task count chart data |
| `GET` | `/api/chart/habits` | Habit completion chart data |
| `GET` | `/api/chart/mood` | Journal mood chart data; empty buckets use `null` |
| `GET` | `/api/chart/elapsed` | Elapsed time chart data |
| `GET` | `/api/chart/habits-heatmap` | Habit heatmap data |

If config has `ids.auto: true`, `POST /api/items`, `POST /api/messages`, and
`POST /api/messages/id/{id}/reply` assign an `id:` when the payload does not
include one. The API scans all loaded input files and the writable file before
writing, so the generated ID avoids collisions across multiple `life.txt` files.
Duplicate IDs are reported as diagnostic warning `W213` in item list responses;
id-based operations reject ambiguous IDs. If config `ids.key` / `api.id_key` is
changed, id-based endpoints use that configured detail key while still exposing
the selected value as top-level `id` in API item responses.

`GET /api/agenda` uses the same agenda records as the CLI. Records include
`blocked: true` and `blocked_by` when an open item is blocked by an open
`depends_on:` or `blocks:` relation, and `?blocked=only` / `?blocked=hide`
keeps or removes blocked records. Repeated records that are expanded at
request time include `generated: true`, `source_id`, `occurrence_start`,
`occurrence_end`, `occurrence_index`, and `repeat_rule` when available; the API
does not write generated occurrences back to the source file.

Example item payload:

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Write Report",
  "details": {
    "due": ["2026-06-12"],
    "project": ["university"]
  }
}
```

Item responses include a `markdown` object with sanitized HTML for fields that
commonly contain Markdown:

```json
{
  "title": "Research **day**",
  "details": {"body": ["**Done**"]},
  "markdown": {
    "title": "Research <strong>day</strong>",
    "details": {
      "body": ["<p><strong>Done</strong></p>"]
    }
  }
}
```

The raw `title` and `details` values are unchanged. The `markdown` HTML is
generated from the safe life.txt Markdown subset and escapes raw HTML.

Examples:

```sh
curl "http://127.0.0.1:8000/api/items?kind=T&open_only=true"
curl -X POST "http://127.0.0.1:8000/api/items/parse" \
  -H "Content-Type: application/json" \
  -d '{"line":"[N] J \"Research day\" on:2026-06-23\n| Wrote notes"}'
curl "http://127.0.0.1:8000/api/items/id/task_001"
curl "http://127.0.0.1:8000/api/links?id=task_001&direction=incoming"
curl "http://127.0.0.1:8000/api/graph?root=task_001&depth=2"
curl "http://127.0.0.1:8000/api/links?relation=depends_on,blocks"
curl "http://127.0.0.1:8000/api/items?team=research&tag_all=urgent,review"
curl "http://127.0.0.1:8000/api/messages?recipient=alice&open_only=true"
curl "http://127.0.0.1:8000/api/messages/thread/msg_001"
curl "http://127.0.0.1:8000/api/notifications?recipient=self"
curl "http://127.0.0.1:8000/api/agenda?around=now&window=1d"
curl "http://127.0.0.1:8000/api/status?active=true"
```

Example message payload:

```json
{
  "title": "Review slides",
  "sender": "self",
  "recipients": ["alice", "bob"],
  "notify_at": "2026-06-06T09:00",
  "channel": "teams"
}
```

## GUI

The browser GUI supports:

- Listing and filtering items
- Sorting items by line, time, title, type, status, or source
- URL-driven filters, ordering, limits, and display mode
- Saving the current filter/sort/workspace state as a browser-local custom
  view
- A header workspace bar that combines view switching (Items, Messages,
  Status, Kiosk) and tools (New Record, Agenda, Notifications, Statistics,
  Graph)
- Showing near-current agenda records
- Showing active status / presence records
- Showing due message notifications
- Showing repeated agenda occurrences with occurrence badges
- Browser notifications after the user grants permission
- Showing message threads in the record detail modal using `parent:`
- Replying to message threads from the record detail modal
- Keyboard-trapped modals for Help, Git, and record details
- A fuzzy command palette with actions, saved views, and recently opened items
- Showing ID reference graphs for `parent:`, `ref:`, `depends_on:`,
  `blocks:`, and `related:`
- Rendering sanitized Markdown title/body/note previews
- Highlighting search matches in titles, details, and body/note previews
- Creating new items
- Importing a raw life.txt line/body block into the editor through the server
  parser, with a live parse preview before writing
- Selecting editable items and saving changes
- Deleting editable item lines

Editable items are items from the writable file. Items loaded from generated
files, such as `.generated/google_calendar.life.txt`, are shown read-only.

The layout is responsive: the main item list stays in one readable column, and
the former right-side tools are collected into the header workspace bar. The
same bar also contains Items, Messages, Status, and Kiosk view switches. Only
one workspace panel is open at a time, so New Record, Statistics, Graph,
Agenda, Status, and Notifications remain visible on narrow and wide screens.
Clicking an item opens a centered record detail modal instead of a right-side
drawer.

## URL Parameters

The GUI reads query parameters on load. This is useful for bookmarks, wall
displays, and sharing fixed views.

Examples:

```txt
http://127.0.0.1:8000/?kind=T&open_only=true&sort=time&order=asc
http://127.0.0.1:8000/?workspace=agenda&around=now&window=1d
http://127.0.0.1:8000/?mode=display&window=12h&sort=time&order=asc&limit=20&refresh=60
http://127.0.0.1:8000/?mode=display&type=S&person=self&refresh=30
```

Supported parameters:

| Parameter | Meaning |
|---|---|
| `mode=display` or `view=display` | Wall-display mode: hides editing controls and enables auto-refresh |
| `mode=kiosk` or `view=kiosk` | Always-on kiosk board mode with auto-scroll and card grid |
| `view=messages` | Message-focused layout with type `M` as the default item filter |
| `view=status` | Status-focused layout with active status records emphasized |
| `preset=NAME` | Apply URL parameters from config `views.NAME` or a browser-local custom view |
| `workspace=new|agenda|status|notifications|stats|graph` | Open a workspace panel above the item list |
| `refresh=SECONDS` | Auto-refresh interval; display mode defaults to 60 seconds |
| `kind=E` or `type=E` | Filter by life.txt type |
| `text=VALUE` or `q=VALUE` | Search title, line text, and detail values |
| `open_only=true` or `open=true` | Show unfinished workflow items only |
| `status=todo` | Filter by status or status alias |
| `project=VALUE`, `tag=VALUE`, `tag_all=VALUE`, `exclude_tag=VALUE` | Filter by tags and projects |
| `user=VALUE`, `team=VALUE`, `person=VALUE` | Filter by users, teams, or presence target |
| `owner=VALUE`, `assignee=VALUE`, `attendee=VALUE` | Filter by people details |
| `sender=VALUE`, `recipient=VALUE` | Filter by message details |
| `sort=line|time|title|type|status|source` | Item sort key |
| `order=asc|desc` | Item sort order |
| `limit=N` | Limit item and agenda results |
| `around=now`, `window=1d` | Agenda range |
| `from=YYYY-MM-DD`, `to=YYYY-MM-DD` | Agenda range |
| `after=VALUE`, `before=VALUE` | Item time filters |
| `notify_refresh=SECONDS` | Notification polling interval |
| `notify_lookahead=DURATION` | Future notification lookahead for browser notifications |
| `kiosk_cols=N` | Fixed kiosk card columns, up to 8 |
| `kiosk_filter=kind:T,status:[/]` | Kiosk-only compact filter expression |
| `kiosk_title=TEXT` | Header title shown only in kiosk mode |
| `graph_root=ID`, `graph_depth=N` | Initial graph panel root/depth parameters |

## Saved Views and Command Palette

Use `Save View` in the header toolbar to store the current filters, search
text, sort order, grouping, display mode, and workspace panel as a browser-local
custom view. Custom views are stored in `localStorage`; they are available only
in the current browser profile. Config-defined views from `views` are shown in
the same selector but are read-only from the browser. Select a custom view and
click `Delete` to remove it, or click `x` to clear the active preset without
deleting it.

Press `Ctrl+K` to open the command palette. It supports fuzzy matching, shows
recently opened records when the query is empty, can apply saved views, and
includes common actions such as quick-add, export, theme toggle, kiosk mode,
and agenda blocked-filter toggling.

## Browser Notifications

The GUI polls `/api/notifications` and shows due type `M` records in the
Notifications workspace panel. Click `Notifications` in the top toolbar or the
workspace tab to open it. Click `Enable Notifications` to request browser
permission and receive native browser notifications.

Notification selection uses:

- `recipient=` query parameter, then `person=`, then `notifications.recipient`
  or `user.name` from config.
- `notify_at:` for one notification time.
- `notify_from:` / `notify_to:` for an active notification period.
- Open workflow statuses only: `[ ]`, `[/]`, `[>]`, and `[?]`.
- `ack:` suppresses future notifications for that message.
- Future `snooze_until:` suppresses notifications until that timestamp.

The notification panel shows `Ack` and `Snooze ...` actions for records with an
`id:`. The snooze duration defaults to `notifications.snooze_default`; these
actions write to the configured writable file.

If notification permission is blocked, the GUI cannot request it again through
JavaScript. The notification panel shows a short guide telling the user to open
the browser site settings for the current URL and allow notifications there.

## Graph And Threads

The Graph workspace panel reads `/api/graph` and renders a compact SVG reference
graph without external dependencies. Click a node to open that record in the
record detail modal. The modal also shows a smaller graph for the selected item
when it has ID references; the modal graph loads a depth-2 subgraph so indirect
blockers and related records are visible without leaving the modal.

Message items (`type:M`) with an `id:` show a thread section in the detail
modal. The modal also includes a reply form. Replies are records whose `parent:`
points at the root message ID and are also available from:

```sh
curl "http://127.0.0.1:8000/api/messages/thread/msg_001"
```

## Charts

Chart endpoints return stable `labels` and `datasets` arrays for browser
rendering. `GET /api/chart/elapsed` accepts the same practical filters as the
statistics view, including `from`, `to`, `project`, and `group`.

```sh
curl "http://127.0.0.1:8000/api/chart/elapsed?from=2026-06-01&to=2026-06-30&project=research"
```

## Display Mode

Display mode is intended for always-on screens. It keeps the page read-only,
uses larger typography, hides the editor and filter controls, and refreshes
automatically.

Recommended examples:

```txt
/?mode=display&around=now&window=8h&sort=time&order=asc&limit=20
/?mode=display&kind=T&open_only=true&sort=time&order=asc&refresh=120
/?mode=display&type=S&active=true&refresh=30
/?mode=kiosk&kiosk_cols=3&kiosk_filter=kind:T,status:[ ]&kiosk_title=Today&refresh=60
/?view=messages&recipient=self&open_only=true
/?view=status&active=true
/?preset=my_messages
```

Kiosk mode is optimized for a shared or always-on screen. It hides editor
controls, auto-scrolls the item grid, supports fixed column counts through
`kiosk_cols`, and can apply a compact display-only filter through
`kiosk_filter`. Named view presets from config `views` can also set these
parameters. When auto-refresh loads new or changed records, kiosk mode briefly
highlights only the changed cards.

Files listed in config `sync_ics.generated_paths` or `sync_ics.output` are
marked as generated in API responses and are treated as read-only in the GUI.
