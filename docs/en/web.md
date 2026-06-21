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

Multiple files can be read at once. Create, update, and delete operations use
the first file unless `--write-file` is specified.

```sh
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt
```

## REST API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Show server paths and writable file |
| `GET` | `/api/config` | Show public runtime config used by the GUI |
| `GET` | `/api/items` | List items with optional filters |
| `GET` | `/api/items/id/{id}` | Get an item by exact `id:` |
| `PUT` | `/api/items/id/{id}` | Replace an item by exact `id:` in the writable file |
| `DELETE` | `/api/items/id/{id}` | Delete an item by exact `id:` in the writable file |
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

If config has `ids.auto: true`, `POST /api/items`, `POST /api/messages`, and
`POST /api/messages/id/{id}/reply` assign an `id:` when the payload does not
include one. The API scans all loaded input files and the writable file before
writing, so the generated ID avoids collisions across multiple `life.txt` files.
Duplicate IDs are reported as diagnostic warning `W213` in item list responses;
id-based operations reject ambiguous IDs.

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

Examples:

```sh
curl "http://127.0.0.1:8000/api/items?kind=T&open_only=true"
curl "http://127.0.0.1:8000/api/items/id/task_001"
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
- Showing near-current agenda records
- Showing active status / presence records
- Showing due message notifications
- Browser notifications after the user grants permission
- Creating new items
- Selecting editable items and saving changes
- Deleting editable item lines

Editable items are items from the writable file. Items loaded from generated
files, such as `.generated/google_calendar.life.txt`, are shown read-only.

The layout is responsive: the editor sits beside the item list on wide screens
and moves below it on narrower browser windows.

## URL Parameters

The GUI reads query parameters on load. This is useful for bookmarks, wall
displays, and sharing fixed views.

Examples:

```txt
http://127.0.0.1:8000/?kind=T&open_only=true&sort=time&order=asc
http://127.0.0.1:8000/?mode=display&window=12h&sort=time&order=asc&limit=20&refresh=60
http://127.0.0.1:8000/?mode=display&type=S&person=self&refresh=30
```

Supported parameters:

| Parameter | Meaning |
|---|---|
| `mode=display` or `view=display` | Wall-display mode: hides editing controls and enables auto-refresh |
| `view=messages` | Message-focused layout with type `M` as the default item filter |
| `view=status` | Status-focused layout with active status records emphasized |
| `preset=NAME` | Apply URL parameters from config `views.NAME` |
| `refresh=SECONDS` | Auto-refresh interval; display mode defaults to 60 seconds |
| `kind=E` or `type=E` | Filter by life.txt type |
| `text=VALUE` or `q=VALUE` | Search title, line text, and detail values |
| `open_only=true` or `open=true` | Show unfinished workflow items only |
| `status=todo` | Filter by status or status alias |
| `project=VALUE`, `tag=VALUE`, `person=VALUE` | Filter by details |
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

## Browser Notifications

The GUI polls `/api/notifications` and shows due type `M` records in the
Notifications panel. Click `Enable Notifications` to request browser permission
and receive native browser notifications.

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

## Display Mode

Display mode is intended for always-on screens. It keeps the page read-only,
uses larger typography, hides the editor and filter controls, and refreshes
automatically.

Recommended examples:

```txt
/?mode=display&around=now&window=8h&sort=time&order=asc&limit=20
/?mode=display&kind=T&open_only=true&sort=time&order=asc&refresh=120
/?mode=display&type=S&active=true&refresh=30
/?view=messages&recipient=self&open_only=true
/?view=status&active=true
/?preset=my_messages
```

Files listed in config `sync_ics.generated_paths` or `sync_ics.output` are
marked as generated in API responses and are treated as read-only in the GUI.
