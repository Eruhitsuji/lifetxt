# Design

## Summary

Extend the existing `lifetxt.conversion` registry. Keep `items_from_todo_text`
as the only todo decoder and add the inverse encoder there. The `convert` CLI
continues as a thin adapter; `from-todo` delegates to the same shared decoder.
No file I/O, synchronization, or workspace mutation moves into the core.

## Interfaces and Contracts

- ADDED: `todo` target and supported `life -> todo` pair.
- MODIFIED: todo decoding handles priority before creation date, Unicode
  non-whitespace project/context tokens, and valid `key:value` extensions.
- ADDED: strict todo encoder for Task records with `[ ]` or `[x]` status.
- ADDED: explicit conversion loss errors naming item and field; no partial
  output is written on failure.
- PRESERVED: `from-todo` input/output and existing `convert` target behavior.

## Alternatives

- A second todo parser was rejected because the existing conversion helper is
  already shared with `from-todo`.
- Silent omission and task/status coercion were rejected because the formats do
  not have equivalent representations for all life.txt records.
- Lossy mode and named compatibility profiles are deferred until their user
  semantics and diagnostic contract are separately agreed.

## Risks

- `key:value` metadata is an extension point, not a standard todo.txt field;
  third-party clients may ignore or alter custom values.
- Todo token syntax cannot represent arbitrary whitespace or colon-bearing
  metadata values without an agreed escaping convention. Strict export rejects
  these cases.
- Generated IDs and source metadata must be preserved as extension tokens or
  cause a strict error; tests must verify identity behavior.

## Operations Impact

None. Conversion remains a local, stateless operation.

## Compatibility Impact

Additive target support. Decoder changes correct previously misinterpreted
todo.txt token order and broaden accepted standard tokens. Existing `from-todo`
continues using the shared parser. Format 1.0 and existing Quick shorthand are
unchanged.
