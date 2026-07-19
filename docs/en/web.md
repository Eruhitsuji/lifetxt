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
python -m lifetxt serve "projects/**/*.life.txt" --write-file life.txt --read-only
```

Use `--read-only` for public dashboards or always-on displays where users
should be able to inspect and validate records but not change source files.

## MCP Server

For MCP-compatible AI clients, run the dependency-free stdio MCP server:

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve life.txt --mcp
```

The MCP server exposes tools for `list_items`, `get_item`, `create_item`,
`update_item`, `mark_done`, `delete_item`, `get_agenda`, `get_graph`,
`get_blockers`, `list_links`, `list_status`, `list_notifications`, and type `M`
message operations. It also exposes `lifetxt://source/N` resources for the
loaded source files. With multiple files, reads scan every configured path while
write tools modify only `--write-file`; pass `--read-only` to disable write
tools.

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
| `GET` | `/api/review` | Review report for a date window: completed tasks, habit completion, journal entries, mood trend, and elapsed time |
| `GET` | `/api/status` | Show latest status / presence records |
| `POST` | `/api/status` | Record a presence status, closing the previously open one. Body: `{"state": "busy"}`, `{"end": true}`, or add `"force": true` to repeat a state |
| `POST` | `/api/items/capture` | Append a task from plain text, expanding `@project #tag !priority ^due` |
| `POST` | `/api/shorthand/parse` | Preview shorthand expansion without writing |
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
curl -X POST http://127.0.0.1:8000/api/status \n  -H "Content-Type: application/json" -d '{"state": "busy"}'
curl -X POST http://127.0.0.1:8000/api/status \n  -H "Content-Type: application/json" -d '{"end": true}'
curl -X POST http://127.0.0.1:8000/api/items/capture \n  -H "Content-Type: application/json" -d '{"text": "Buy milk @home ^tomorrow"}'
curl "http://127.0.0.1:8000/api/review?week=true"
curl "http://127.0.0.1:8000/api/review?month=2026-07&project=research"
curl "http://127.0.0.1:8000/api/review?from=2026-06-29&to=2026-07-05"
```

`GET /api/review` returns the same report as the CLI `review` command and the
MCP `get_review` tool: `completed_tasks` / `open_tasks` counts, a `completed`
list (title, done date, project, id), per-habit completion rates, journal
entries with excerpts, a `mood_trend` list, and `elapsed_by_project` totals.
Range selectors follow the CLI precedence: `week=true`, then `month=YYYY-MM`,
then `from`/`to` (defaulting to the current week start and today). Invalid
selectors return `400`.

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
- URL-driven filters, ordering, limits, and view selection
- A contextual View Guide below the header. It explains the active workspace
  and exposes the most common actions for that view, such as New record,
  Quick add, Timeline range changes, Review Markdown copy, or Team/Status
  navigation.
- Contextual hover/focus help on primary controls, workspace tabs, Timeline
  range buttons, Calendar navigation, export/group/sort controls, and the
  record editor. Tooltips are viewport-aware so they avoid clipping at the
  edges of small browser windows.
- Keyboard-friendly workspace navigation: the header view bar is exposed as a
  tablist, `Left`/`Right` move between views, `Home`/`End` jump to the ends,
  and a skip-to-content link lets keyboard users bypass the header.
- A single-content view bar: Dashboard, Items, Agenda, Timeline, Calendar, Focus,
  Review, Messages, Team, Status, Notifications, Stats, Graph, Display, and Kiosk —
  exactly one view fills the screen at a time
- A Dashboard view with clickable KPI tiles (open, due today, overdue,
  blocked, recent completions), today's agenda, a needs-attention list, a
  14-day completion chart, and per-project progress. Dashboard cards can be
  hidden, reordered, and capped through `web.dashboard.cards` and
  `web.dashboard.limits`
- A Focus view showing overdue, due-today, and in-progress work items with
  one-click done buttons and undo, plus today's timed events, reminders whose
  `at:`/`on:` falls today, undated "anytime" reminders, and a quick-add input
  that captures a task with `due:` today without leaving the view
- A Review view backed by `GET /api/review` with This week / Last week / This
  month / Last month presets, project filtering, custom from/to dates,
  clickable completed-task rows when records have an `id:`, and a Markdown
  copy action for weekly-report or chat handoff workflows
- A Timeline view: a chronological board of agenda records with a red "now"
  line, per-type colored rail nodes, hour labels, all-day rows, day headers,
  dimmed past records, URL-persisted Today / Next 24h / Week range presets,
  a refreshed "now" line while the view stays open, guided empty states with
  dated-key examples when the selected range has no dated records, a "no
  upcoming records left today" banner when all today records are already in
  the past, and `ongoing` badges for records that started before the selected
  range but still overlap it; cards open the record detail modal
- A Calendar view: a month or single-week grid that plots agenda records —
  including expanded repeat occurrences — on the day they fall. Cells show the
  first few entries with a `+N more` expander, color-coded per record type and
  overdue/due-soon state, a today highlight, and per-day counts. Clicking an
  entry opens the record detail modal; clicking a day number opens that day in
  Agenda. Prev/Next/Today navigation and Month/Week mode are keyboard-driven
  (`,` `.` previous/next period, `t` today, `m` toggle mode) and persisted in
  the URL via `?view=calendar&calmode=month|week&cal=YYYY-MM-DD`. The first
  weekday column follows the `web.week_start` config (`monday` default or
  `sunday`)
- A Team view: a presence board combining latest status records (colored
  presence dot and state badge per person), open messages addressed to each
  person, and an open/overdue workload summary per assignee — designed for
  wall displays with `?view=team&refresh=60` and the fullscreen toggle
- Colored presence indicators on the Status and Team views: state values map
  to a dot and badge color (available/free/online → green, busy/meeting →
  red, focus/dnd → violet, away/lunch → amber, out/offline or ended → gray
  outline; anything else → blue), with the state text always shown so color
  is never the only signal
- A fullscreen toggle (header ⛶ button, `f` key, or command palette) using
  the browser Fullscreen API — pairs with kiosk/display mode for wall
  screens
- A Display workspace tab and command-palette action for read-focused wall
  displays. Display mode hides editing controls, keeps a visible Exit Display
  button, uses a light wall-display palette unless the page is in dark theme,
  and follows browser Back/Forward URL state.
- Showing near-current agenda records with a blocked-item filter
- Showing active status / presence records
- Team cards include a `View items` action that opens the shared Items view
  filtered with `user=PERSON&open_only=true`, so presence, assignments,
  sent messages, and received messages can be inspected from one place.
- Showing due message notifications
- Showing repeated agenda occurrences with occurrence badges
- Browser notifications after the user grants permission
- Showing message threads in the record detail modal using `parent:`
- Replying to message threads from the record detail modal
- Keyboard-trapped modals for Help, Git, Undo history, record details, and the
  record editor
- A fuzzy command palette with actions, view switching, Calendar/Kiosk/Display
  shortcuts, and recently opened items
- Guided empty states in the Items view. When no records exist, the UI offers
  New record, Quick add, and the command palette; when filters hide all
  records, it offers Clear filters and New record.
- Showing ID reference graphs for `parent:`, `ref:`, `depends_on:`,
  `blocks:`, and `related:`
- Rendering sanitized Markdown title/body/note previews
- Highlighting search matches in titles, details, and body/note previews
- Creating new items in a centered record editor modal (`＋ New` or `n`) with
  viewport-aware hover/focus help on the New button and the editor Status,
  Type, Title, and Details fields
- Importing a raw life.txt line/body block into the editor through the server
  parser, with a live parse preview before writing
- Selecting editable items and saving changes
- Deleting editable item lines
- Session undo history for the last five undoable browser actions, available
  from the command palette as `Show undo history`

Editable items are items from the writable file. Items loaded from generated
files, such as `.generated/google_calendar.life.txt`, are shown read-only.

The layout follows a one-screen-one-content rule: the header view bar picks a
single full-width page (Items, Dashboard, Agenda, Timeline, Focus, Review,
Messages, Team, Status, Notifications, Stats, Graph, Display, or Kiosk), and nothing else
competes for space. The
record editor opens as a centered modal from `＋ New`, and clicking an item
opens a centered record detail modal.

## Web UI Configuration

`/api/config` exposes a safe subset of `web.*` settings to the browser. The
GUI applies these values at startup:

```json
{
  "web": {
    "theme": {
      "accent": "#0e7a65",
      "accent_hover": "#0a6252",
      "accent_soft": "#e0f0ea",
      "accent_ink": "#ffffff"
    },
    "dashboard": {
      "cards": ["today", "needs_attention", "completions", "projects"],
      "limits": {"today": 7, "needs_attention": 7, "projects": 7}
    }
  }
}
```

Supported theme token names mirror the CSS variables without the leading
`--`: `bg`, `panel`, `panel_2`, `soft`, `ink`, `muted`, `line`,
`line_strong`, `accent`, `accent_hover`, `accent_soft`, `accent_ink`,
`danger`, `warn`, `ok`, `info`, `violet`, `shadow_1`, `shadow_2`,
`shadow_3`, `r_sm`, `r_md`, and `r_lg` plus the matching `*_soft` semantic
tokens. Dotted keys such as `"theme.accent"` and `"dashboard.cards"` are also
accepted for flat config generators.

## URL Parameters

The GUI reads query parameters on load. This is useful for bookmarks, wall
displays, and sharing fixed views.

Examples:

```txt
http://127.0.0.1:8000/?kind=T&open_only=true&sort=time&order=asc
http://127.0.0.1:8000/?view=dashboard&refresh=60
http://127.0.0.1:8000/?view=agenda&around=now&window=1d
http://127.0.0.1:8000/?view=timeline&range=week&refresh=120
http://127.0.0.1:8000/?view=focus&theme=dark
http://127.0.0.1:8000/?mode=display&window=12h&sort=time&order=asc&limit=20&refresh=60
http://127.0.0.1:8000/?mode=display&type=S&person=self&refresh=30
```

Supported parameters:

| Parameter | Meaning |
|---|---|
| `view=dashboard\|agenda\|timeline\|focus\|review\|messages\|team\|status\|notifications\|stats\|graph` | Open a full-screen view; `view=messages` also defaults the item filter to type `M` |
| `mode=display` or `view=display` | Wall-display mode: hides editing controls and enables auto-refresh |
| `mode=kiosk` or `view=kiosk` | Always-on kiosk board mode with auto-scroll and card grid |
| `preset=NAME` | Apply URL parameters from config `views.NAME` |
| `workspace=agenda\|status\|notifications\|stats\|graph` | Legacy alias for `view=...`; `workspace=new` opens the record editor modal |
| `refresh=SECONDS` | Auto-refresh interval; display mode defaults to 60 seconds |
| `kind=E` or `type=E` | Filter by life.txt type |
| `text=VALUE` or `q=VALUE` | Search title, line text, and detail values |
| `open_only=true` or `open=true` | Show unfinished workflow items only |
| `status=todo` | Filter by status or status alias |
| `project=VALUE`, `tag=VALUE`, `tag_all=VALUE`, `exclude_tag=VALUE` | Filter by tags and projects |
| `user=VALUE`, `team=VALUE`, `person=VALUE` | Filter by users, teams, or presence target |
| `owner=VALUE`, `assignee=VALUE`, `attendee=VALUE` | Filter by people details |
| `sender=VALUE`, `recipient=VALUE` | Filter by message details |
| `sort=line\|time\|title\|type\|status\|source` | Item sort key |
| `order=asc\|desc` | Item sort order |
| `limit=N` | Limit item and agenda results |
| `around=now`, `window=1d` | Agenda range |
| `from=YYYY-MM-DD`, `to=YYYY-MM-DD` | Agenda range |
| `range=today\|24h\|week` | Timeline range when `view=timeline`; the UI updates this value when range buttons are clicked |
| `calmode=month\|week` | Calendar grid mode when `view=calendar`; the UI updates this value when the Month/Week buttons are used |
| `cal=YYYY-MM-DD` | Anchor date of the visible calendar period; the UI updates this value on Prev/Next/Today navigation |
| `after=VALUE`, `before=VALUE` | Item time filters |
| `notify_refresh=SECONDS` | Notification polling interval |
| `notify_lookahead=DURATION` | Future notification lookahead for browser notifications |
| `kiosk_cols=N` | Fixed kiosk card columns, up to 8 |
| `kiosk_filter=kind:T,status:[/]` | Kiosk-only compact filter expression |
| `kiosk_title=TEXT` | Header title shown only in kiosk mode |
| `theme=dark` or `theme=light` | Force the color theme; useful for kiosks and wall displays where `localStorage` cannot be pre-seeded |
| `graph_root=ID`, `graph_depth=N` | Initial graph panel root/depth parameters |

## Command Palette

Press `Ctrl+K` to open the command palette. It supports fuzzy matching, shows
recently opened records when the query is empty, switches between views
(`Go to Dashboard`, `Go to Focus`, ...), and includes common actions such as
quick-add, export, theme toggle, kiosk mode, and agenda blocked-filter
toggling.

### Quick add shorthand and presence

The quick-add input accepts either a full life.txt line (anything starting with
`[`) or plain text with capture shorthand:

```
Buy milk @home #errand !high ^tomorrow
```

`@` sets `project:`, `#` adds `tag:`, `!` sets `priority:`, and `^` sets `due:`
with the shared relative date tokens (`today`, `tomorrow`, weekday names,
`+3d`). A live preview under the input shows exactly what will be written, and
the expansion happens on the server so it cannot drift from `lifetxt quick`.

Press `p` to open the presence bar. Type a state (`busy`, or `focus Deep work`
to add a title) and press Enter to record it; the previously open status is
closed in the same request. `End` closes the current status without opening a
new one. Repeating the state that is already open writes nothing and reports it.
Both actions are also in the command palette as `Set status` and `End status`.

There is no browser-side "save view" feature: shareable views are plain URLs
(every filter, sort, and view choice is reflected in the query string), and
reusable presets are defined in config `views.NAME` and applied with
`?preset=NAME`.

## Browser Notifications

The GUI polls `/api/notifications` and shows due type `M` records in the
Notifications view. Click `Notifications` in the top toolbar or the view tab
to open it. Click `Enable Notifications` to request browser permission and
receive native browser notifications.

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

Email delivery is handled by the CLI watcher rather than the browser:
`python -m lifetxt notify life.txt --watch --email --email-to me@example.com`.
SMTP host/user/password values are read from environment variables named by
`notifications.email.*`.

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
automatically. In light theme it uses a warm, high-contrast wall-display
palette; in dark theme it switches to the dark display palette. Open it from
the Display workspace tab, `Ctrl+K` command palette, `?mode=display`, or
`?view=display`. The header keeps an Exit Display button, and browser
Back/Forward navigation reapplies the URL state so kiosk or display styling
does not remain after leaving the mode. `display_title=TEXT` can override the
subtitle while Display mode is active.

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

### Port Cannot Be Bound

If `serve` exits immediately, the port could not be bound. `lifetxt` checks
before starting and names the cause:

```
ERROR: Cannot bind 127.0.0.1:8000 ([WinError 10013] ...).
Windows is reserving that port, so nothing can bind it even though nothing is listening.
```

**Windows reserved ports.** Hyper-V, WSL, and Docker reserve blocks of ports.
A reserved port cannot be bound even though nothing is listening on it, so
`netstat` looks clear and the failure is confusing. List the reserved ranges:

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

Port 8000 commonly falls inside a reserved range. Start outside it:

```sh
lifetxt serve life.txt --port 8080
```

Or set a default in config so you do not have to pass it every time:

```json
{ "web": { "port": 8080 } }
```

**Port already in use.** Another process holds it; stop that process or pick a
different port.

**Ports below 1024.** These need elevated privileges on macOS and Linux. Use a
port above 1024.

