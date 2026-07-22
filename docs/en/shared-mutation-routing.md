# Shared mutation routing

All authoritative text and JSON replacement writes now enter through the shared mutation contract in `lifetxt.mutation`.

## Compatibility boundary

Existing modules historically imported these helpers:

```python
from lifetxt.atomic import atomic_write_text, atomic_write_json
```

Those names remain supported. They are now compatibility facades over `mutation.write_text`, so callers receive the shared behavior without changing their public API immediately:

- a per-target sidecar lock;
- an in-lock reread of the current bytes;
- detection of a file that changes while the transform is running;
- atomic byte replacement;
- permission preservation where supported;
- post-write hash verification;
- UTF-8 BOM and existing newline preservation when the shared writer updates an existing file.

`atomic_write_bytes` is different. It is the internal commit primitive used after the shared mutation lock has been acquired. Application and surface code must not call it directly.

The fzf/peco helper was the one remaining life.txt writer that used `open(..., "w")` directly. A narrow compatibility bridge now replaces that helper at package initialization, which also covers the TUI status and delete actions that reuse it.

## Covered surfaces

The routing regression suite verifies writes originating from:

- the atomic text and JSON compatibility APIs;
- TUI `_mutate_rows` status changes;
- TUI presence status transitions;
- Web message acknowledgement;
- MCP item creation;
- timer-backed item updates;
- the fzf/peco action helper.

Web and MCP write helpers already converge on the Web file helpers, which converge on the atomic compatibility API. Timer and most TUI operations also use the atomic API. As a result, those paths now share one lock and commit implementation.

## Optimistic concurrency is still explicit

Routing a replacement through the shared layer prevents simultaneous commits and detects a change that happens during the locked transform. It does not automatically know which older file version a caller used to calculate a prebuilt replacement.

Callers that read first and write later must capture a snapshot and pass its hash:

```python
from lifetxt.mutation import mutate_text, read_text_snapshot

snapshot = read_text_snapshot("life.txt")
result = mutate_text(
    "life.txt",
    lambda current: current + "[ ] T New task\n",
    expected_hash=snapshot.content_hash,
    operation="task.create",
)
```

A stale hash raises `MutationConflict` instead of overwriting the newer file.

Adding operation-specific expected hashes and concurrent stale-writer tests for quick capture, item update, MCP, acknowledgement, timer, archive, and undo remains the next release-safety task.

## Migration rule for new code

New authoritative writers should import `lifetxt.mutation` directly and provide a semantic transform that runs against the current in-lock text. The atomic compatibility API is retained for existing replacement-style callers, not as the preferred API for new surface code.
