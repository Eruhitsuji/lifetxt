# Design

## Summary

Extend the surface-neutral Quick resolver with an explicit `syntax="todo"`
branch. That branch invokes `lifetxt.conversion.decode_text`, accepts exactly
one item with no decoder diagnostic, then rejoins the same serializer/parser,
identity, duplicate, locking, and atomic mutation path used by Quick capture.

## Interfaces

- ADDED: `lifetxt add|quick|q --syntax todo TASK`.
- MODIFIED: `resolve_quick_input(..., syntax="quick")`, preserving its default.
- PRESERVED: existing shorthand, complete life.txt line, presets, and flags.

## Safety Boundaries

- Todo mode is never inferred.
- Todo mode rejects semantic override flags rather than defining a second
  precedence system.
- Stdin is read completely in todo mode so extra physical lines cannot be
  silently ignored.
- Decoder warnings, including malformed calendar dates, block a write.

## Alternatives

- A CLI-only todo parser was rejected because #1432 requires shared decoding.
- Automatic detection was rejected because todo `@context` conflicts with
  established Quick shorthand semantics.
- Merging explicit CLI flags into decoded todo metadata was rejected because
  it creates a new, surprising precedence contract.
