# Public surface revision contracts

Web API and MCP life.txt writes use the same optimistic-concurrency contract as `lifetxt.mutation`.

A client must first read the current writable-file revision. The following write is accepted only when that exact revision still matches. This prevents a stale browser tab or MCP client from silently replacing a newer file.

## Web API

Every successful `/api/` read response includes:

```http
ETag: "<sha256>"
X-Lifetxt-Revision: <sha256>
```

The ETag identifies the writable life.txt snapshot used while building the response. Browser code can also read the revision explicitly:

```http
GET /api/revision
```

Supported life.txt write endpoints require either:

```http
If-Match: "<sha256>"
```

or:

```http
X-Lifetxt-Expected-Revision: <sha256>
```

The built-in Web UI installs a small `fetch` bridge. It obtains the revision, adds `If-Match` to supported writes, and replaces its stored revision from each response ETag.

### Missing precondition

A write without a revision returns HTTP 428:

```json
{
  "error": "PRECONDITION_REQUIRED",
  "message": "An expected revision is required for this write.",
  "expected_revision": null,
  "current_revision": "...",
  "attempted_change": {
    "operation": "web.create",
    "path": "/absolute/path/life.txt"
  }
}
```

### Stale revision

A stale write returns HTTP 409 with the stable conflict shape:

```json
{
  "error": "CONFLICT",
  "message": "...",
  "expected_revision": "...",
  "current_revision": "...",
  "current_item": null,
  "attempted_change": {
    "operation": "web.update",
    "path": "/absolute/path/life.txt"
  }
}
```

Reload the current state, review the newer item, and retry deliberately. lifetxt never treats this as an automatic three-way merge.

### Compound writes

A Web request may call several historical helper functions. For example, repeat completion updates the completed item and appends its next occurrence. These writes are staged in memory and committed once, so another writer cannot observe only half of the operation.

## MCP

Call `get_file_state` before a write and retain its `file_hash`:

```json
{
  "writable_path": "life.txt",
  "file_hash": "<sha256>"
}
```

Revision-protected tools require `expected_file_hash` in their input schema. This includes item creation and update, completion, deletion, message creation/reply/acknowledgement/snooze, status changes, and capture.

```json
{
  "id": "T-42",
  "status": "[/]",
  "expected_file_hash": "<sha256>"
}
```

Successful results include the new `revision` and `file_hash`. Missing and stale revisions return the same structured precondition or conflict fields used by the Web API.

The MCP server also exposes:

- `get_capabilities`
- `lifetxt://capabilities`

Both report the format/schema versions, operation matrix, read-only state, writable target, and revision-precondition support.

## Format-version mutation guard

The shared mutation entry point now checks the current and replacement text for `#! format_version:`. A declared unsupported version is still readable for inspection, but a mutation fails with `UNSUPPORTED_FORMAT_VERSION` until an explicit migration is performed.

Unversioned files remain writable in compatibility mode. Format 1.0 files use:

```text
#! format_version: 1
```

## Server target validation

Web application startup now inspects the configured read and write targets.

- A differing write target emits a warning before the first request.
- A Windows drive-relative target such as `C:relative\\life.txt` is rejected. Use an absolute target such as `C:\\work\\life.txt`.

## Named review ranges

The shared review resolver now supports:

- `last-week`
- `last-month`
- `year`

Web example:

```http
GET /api/review?range=last-week
GET /api/review?range=year&year=2026
```

MCP example:

```json
{
  "range": "last-month"
}
```

Both surfaces delegate to `review.resolve_named_review_range` rather than deriving dates independently.

## Current boundary

The operation matrix deliberately does not claim full revision enforcement for timer and attachment operations. Those workflows can modify more than the writable life.txt file, such as timer JSON state or attachment storage. They need a multi-target transaction design before they can make the same atomicity guarantee.

Real-terminal TUI/fzf verification, SMTP delivery tests, browser-engine accessibility smoke tests, timezone application across all date boundaries, and release-gate CI remain separate roadmap items.
