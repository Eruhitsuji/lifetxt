import os
from collections import OrderedDict

from .agenda import (
    agenda_records,
    filter_items,
    parse_agenda_range,
    parse_optional_time_range,
)
from .model import Diagnostic, Item
from .parser import parse_line, parse_text
from .serializer import item_from_dict, item_to_line
from .status_summary import latest_status_records
from .validator import validate_item


def create_app(paths=None, writable_path=None):
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
        }

    @app.get("/api/items")
    def get_items(
        open_only=False,
        status=None,
        kind=None,
        project=None,
        tag=None,
        person=None,
        owner=None,
        assignee=None,
        attendee=None,
        text=None,
        after=None,
        before=None,
        sort="line",
        order="asc",
    ):
        items, diagnostics = read_life_inputs(app.state.paths)
        range_start, range_end = parse_optional_time_range(after, before)
        filtered = filter_items(
            items,
            open_only=open_only,
            statuses=_csv_values(status),
            kinds=_csv_values(kind),
            projects=_csv_values(project),
            tags=_csv_values(tag),
            persons=_csv_values(person),
            owners=_csv_values(owner),
            assignees=_csv_values(assignee),
            attendees=_csv_values(attendee),
            text=text,
            range_start=range_start,
            range_end=range_end,
        )
        filtered = sort_items(filtered, sort, order)
        return items_response(filtered, diagnostics, app.state.writable_path)

    @app.get("/api/agenda")
    def get_agenda(
        start=Query(None, alias="from"),
        end=Query(None, alias="to"),
        around=None,
        window="1h",
        open_only=False,
        status=None,
        kind=None,
        project=None,
        tag=None,
        person=None,
        text=None,
    ):
        items, diagnostics = read_life_inputs(app.state.paths)
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
            kinds=_csv_values(kind),
            projects=_csv_values(project),
            tags=_csv_values(tag),
            persons=_csv_values(person),
            text=text,
        )
        filtered_ids = set(id(item) for item in filtered_items)
        filtered_records = [
            record for record, item in record_items if id(item) in filtered_ids
        ]
        return {"count": len(filtered_records), "records": filtered_records}

    @app.get("/api/status")
    def get_status(person=None, active=False):
        items, diagnostics = read_life_inputs(app.state.paths)
        raise_for_errors(diagnostics)
        records = latest_status_records(items, person=person, active_only=active)
        return {"count": len(records), "records": records}

    @app.post("/api/items", status_code=201)
    def create_item(payload=Body(...)):
        try:
            item = item_from_payload(payload)
            line = append_item_to_file(app.state.writable_path, item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {"line": line, "item": api_item(item, app.state.writable_path)}

    @app.put("/api/items/{line_no}")
    def update_item(line_no, payload=Body(...)):
        try:
            item = update_item_in_file(app.state.writable_path, int(line_no), payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=error_detail(exc))
        return {"line": int(line_no), "item": api_item(item, app.state.writable_path)}

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
    return paths or ["life.txt"]


def read_life_inputs(paths):
    normalized = normalize_server_paths(paths)
    include_source = len(normalized) > 1
    items = []
    diagnostics = []
    for path in normalized:
        text = read_text(path)
        path_items, path_diagnostics = parse_text(text)
        if include_source:
            for item in path_items:
                item.source = path
            for diagnostic in path_diagnostics:
                diagnostic.source = path
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
    return items, diagnostics


def items_response(items, diagnostics, writable_path):
    return {
        "count": len(items),
        "items": [api_item(item, writable_path) for item in items],
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


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
            ("from", "due", "do", "on", "at", "to", "updated", "created"),
        )
    return _detail_sort_key(item, (key_name,))


def _detail_sort_key(item, keys):
    for key in keys:
        values = item.details.get(key)
        if values:
            return (0, values[0], item.line or 0)
    return (1, "", item.line or 0)


def api_item(item, writable_path=None):
    data = item.to_dict()
    data["line"] = item.line
    data["source"] = getattr(item, "source", None)
    data["text"] = getattr(item, "source_text", None) or item_to_line(item)
    data["editable"] = is_editable(item, writable_path)
    return data


def is_editable(item, writable_path):
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


def append_item_to_file(path, item):
    line = item_to_line(item)
    ensure_parent_dir(path)
    existing = ""
    if os.path.exists(path):
        existing = read_text(path)
    prefix = "\n" if existing and not existing.endswith(("\n", "\r")) else ""
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(prefix + line + "\n")
    return len(existing.splitlines()) + 1


def update_item_in_file(path, line_no, payload):
    raw_lines = read_text(path).splitlines(True)
    if line_no < 1 or line_no > len(raw_lines):
        raise ValueError("Line %s is out of range." % line_no)
    original_body, ending = split_line_ending(raw_lines[line_no - 1])
    original_item, diagnostics = parse_line(original_body, line_no)
    if original_item is None or _has_error(diagnostics):
        raise ValueError("Line %s is not a valid life.txt item." % line_no)
    updated = merge_item_payload(original_item, payload)
    line = item_to_line(updated)
    parsed, parsed_diagnostics = parse_line(line, line_no)
    diagnostics = parsed_diagnostics + validate_item(parsed)
    if _has_error(diagnostics):
        raise ValueError([diagnostic.to_dict() for diagnostic in diagnostics])
    raw_lines[line_no - 1] = line + ending
    write_text(path, "".join(raw_lines))
    return updated


def delete_item_from_file(path, line_no):
    raw_lines = read_text(path).splitlines(True)
    if line_no < 1 or line_no > len(raw_lines):
        raise ValueError("Line %s is out of range." % line_no)
    body, _ending = split_line_ending(raw_lines[line_no - 1])
    item, diagnostics = parse_line(body, line_no)
    if item is None or _has_error(diagnostics):
        raise ValueError("Line %s is not a valid life.txt item." % line_no)
    del raw_lines[line_no - 1]
    write_text(path, "".join(raw_lines))
    return item_to_line(item)


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
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


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
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .side { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
      .side section:first-child { grid-column: 1 / -1; }
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
    <button class="secondary" onclick="refreshAll()">Refresh</button>
  </header>
  <main>
    <section>
      <div class="section-head">
        <h2>Items</h2>
        <div class="toolbar">
          <input id="search" placeholder="Search">
          <select id="kind">
            <option value="">All types</option>
            <option value="T">Task</option>
            <option value="E">Event</option>
            <option value="D">Deadline</option>
            <option value="R">Reminder</option>
            <option value="H">Habit</option>
            <option value="N">Note</option>
            <option value="S">Status</option>
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
          <button onclick="loadItems()">Apply</button>
        </div>
      </div>
      <div id="diagnostics"></div>
      <div id="items" class="content"></div>
    </section>
    <div class="side">
      <section>
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
              <option>H</option><option>N</option><option>S</option>
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
      <section>
        <div class="section-head"><h2>Agenda</h2></div>
        <div id="agenda" class="stack"></div>
      </section>
      <section>
        <div class="section-head"><h2>Status</h2></div>
        <div id="status" class="stack"></div>
      </section>
    </div>
  </main>
  <script>
    let currentItems = [];
    let selectedItem = null;

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
      return Object.entries(details || {}).flatMap(([key, values]) =>
        values.map(value => `${key}:${value}`)
      ).join("\n");
    }
    function parseDetails(text) {
      const details = {};
      for (const line of text.split(/\n/)) {
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
    async function loadItems() {
      const params = new URLSearchParams();
      const kind = document.getElementById("kind").value;
      const text = document.getElementById("search").value;
      params.set("sort", document.getElementById("sort").value);
      params.set("order", document.getElementById("order").value);
      if (kind) params.set("kind", kind);
      if (text) params.set("text", text);
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
          <span class="source">${escapeHtml(item.source || `line ${item.line || ""}`)}${item.editable ? "" : " / read-only"}</span>
        `;
        root.appendChild(node);
      }
    }
    function selectItem(item) {
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
      const data = await api("/api/agenda?around=now&window=1d");
      const node = document.getElementById("agenda");
      node.innerHTML = data.records.length ? "" : `<div class="empty">No agenda items.</div>`;
      for (const record of data.records.slice(0, 8)) {
        node.insertAdjacentHTML(
          "beforeend",
          `<div><span class="pill">${escapeHtml(record.when)}</span><div class="title">${escapeHtml(record.title)}</div></div>`
        );
      }
    }
    async function loadStatus() {
      const data = await api("/api/status?active=true");
      const node = document.getElementById("status");
      node.innerHTML = data.records.length ? "" : `<div class="empty">No active status.</div>`;
      for (const record of data.records) {
        node.insertAdjacentHTML(
          "beforeend",
          `<div><span class="pill">${escapeHtml(record.person)}</span> ${escapeHtml(record.state)}<div class="meta">${escapeHtml(record.title)}</div></div>`
        );
      }
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    async function refreshAll() {
      await Promise.all([loadItems(), loadAgenda(), loadStatus()]);
    }
    refreshAll().catch(error => {
      document.body.insertAdjacentHTML("beforeend", `<pre class="diagnostic">${escapeHtml(error.message)}</pre>`);
    });
  </script>
</body>
</html>
"""
