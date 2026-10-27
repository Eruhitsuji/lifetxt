# Design

## Summary

`/todo TASK` resolves exactly one explicitly labelled todo.txt line through
`resolve_quick_input(..., syntax="todo")` and stores a non-writing modal review
in TUI state. The renderer lists title, status, type, every ordered detail, and
all diagnostics. Enter confirms; Escape cancels; arrows/page keys scroll the
review after resize; other keys are inert except the existing Ctrl-C exit.

Confirmation re-resolves the original source and compares the semantic item to
the reviewed item. Local TUI appends through the existing ID-aware serializer,
file lock, validation, and compare-and-swap writer using the revision captured
before preview. Remote TUI sends the mapped structured item to the established
`POST /api/items` route with that same captured revision as `If-Match`.

## Interfaces

- ADDED: TUI `/todo TASK` command and semantic review screen.
- MODIFIED: Remote TUI structured create accepts an explicit expected revision.
- PRESERVED: `/add` and `/a` remain immediate Quick creation commands.

## Safety boundaries

- There is no TUI todo.txt grammar; the shared adapter is authoritative.
- Preview performs no write and a failed new preview clears any older review.
- Confirmation cannot use input edited behind the modal review.
- Local and Remote writes fail on a stale reviewed revision.
- A successful write clears the review before reload, preventing resubmission.

## Residual limit

As with existing TUI creation, local identity checks use the loaded workspace
item set. The writable destination remains protected by an atomic revision
comparison; users reload and preview again after any reported conflict.
