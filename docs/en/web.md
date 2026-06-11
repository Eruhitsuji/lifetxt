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
| `GET` | `/api/items` | List items with optional filters |
| `POST` | `/api/items` | Append an item to the writable file |
| `PUT` | `/api/items/{line}` | Replace an item on a line in the writable file |
| `DELETE` | `/api/items/{line}` | Delete an item line from the writable file |
| `GET` | `/api/agenda` | Show agenda records for a datetime range |
| `GET` | `/api/status` | Show latest status / presence records |

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
curl "http://127.0.0.1:8000/api/agenda?around=now&window=1d"
curl "http://127.0.0.1:8000/api/status?active=true"
```

## GUI

The browser GUI supports:

- Listing and filtering items
- Sorting items by line, time, title, type, status, or source
- Showing near-current agenda records
- Showing active status / presence records
- Creating new items
- Selecting editable items and saving changes
- Deleting editable item lines

Editable items are items from the writable file. Items loaded from generated
files, such as `.generated/google_calendar.life.txt`, are shown read-only.

The layout is responsive: the editor sits beside the item list on wide screens
and moves below it on narrower browser windows.
