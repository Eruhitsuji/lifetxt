# Design

## Summary

The `/capture` form keeps Quick as its default. Selecting todo.txt changes the
first submit into a non-writing `POST /api/quick/resolve` preview. The server
uses `resolve_quick_input(..., syntax="todo")`; the browser only renders its
result. A contextual review binds the canonical mapped line to the captured
workspace fingerprint and writable revision.

Confirmation repeats the original todo.txt input, context token, and source
revision to `POST /api/items/capture`. The server resolves and reviews again,
rejects changed input/context/revision, then rejoins the existing ID,
validation, duplicate, transaction, audit, and atomic-write path.

## Interfaces

- MODIFIED: `POST /api/quick/resolve` accepts `syntax: "todo"` and returns the
  mapped fields, diagnostics, context token, and source revision.
- MODIFIED: `POST /api/items/capture` accepts preview-bound todo.txt input.
- ADDED: explicit Quick/todo.txt selector, semantic review region, and confirm
  control on `/capture`.
- PRESERVED: Quick remains the default one-submit workflow.

## Safety Boundaries

- The browser contains no todo.txt grammar.
- Changing the input hides and invalidates confirmation.
- Server confirmation re-resolves and re-reviews; a token is not trusted as
  authorization and never bypasses the existing middleware.
- `If-Match` and the body revision both bind the writable snapshot.
- The workspace fingerprint detects changes in configured read sources.
- Read-only and authentication middleware apply unchanged.
- There is no automatic retry after a conflict or uncertain result.

## Residual Limit

As with contextual native batch review, another non-writable source can change
immediately after the final captured scan. The writable destination remains an
atomic compare-and-swap mutation.
