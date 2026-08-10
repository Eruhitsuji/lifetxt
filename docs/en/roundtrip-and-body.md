# Round-trip and multiline body rules

This document records the lossless rules enforced by the reference parser and serializer. The executable examples live in `tests/golden/roundtrip_cases.json` and are checked by `tests/test_roundtrip_golden.py`.

## Parse-serialize-parse contract

For a valid life.txt document, the reference implementation must be able to:

1. parse the input without an error diagnostic;
2. serialize every parsed item to canonical life.txt text;
3. parse the canonical text again without an error diagnostic; and
4. recover the same status, type, title, indentation, detail keys, repeated-value order, and detail values.

The canonical serializer writes LF line endings. Reading accepts LF, CRLF, and CR. UTF-8 text, Unicode titles and values, quoted escapes, repeated details, hierarchy, and explicit timezone-offset strings are covered by the golden corpus.

JSON and JSONL preserve every detail as an array. CSV stores repeated values as a JSON array cell. Explicit datetime offsets such as `+09:00` remain part of the detail string during JSON, JSONL, and CSV interchange; datetime comparison code may normalize parsed values separately, but interchange must not rewrite the authored value.

## One continuation block means one body value

A sequence of lines beginning with `|` represents exactly one multiline `body:` value:

```txt
[N] J "Research log" on:2026-07-22
| First paragraph.
|
| Third line after a blank line.
```

The parsed body value is:

```text
First paragraph.\n\nThird line after a blank line.
```

The serializer uses this continuation form when an item has exactly one `body:` value containing a newline.
Indentation is preserved at the item level: a child item with a multiline body
serializes the same item indentation before each `|` continuation line, so the
body stays attached to that child rather than becoming a sibling item.

For backward compatibility, one inline `body:` value may be followed by continuation lines:

```txt
[N] N Note body:First_line
| Second line
```

This has one unambiguous target and parses as `First_line\nSecond line`. Its canonical serialized form removes the inline detail and uses only continuation lines:

```txt
[N] N Note
| First_line
| Second line
```

## Forms that are intentionally rejected

A continuation block must not follow repeated inline `body:` details:

```txt
[N] N Note body:first body:second
| ambiguous continuation
```

The continuation has no marker saying whether it belongs to `first`, `second`, or a new value. The parser therefore reports error `E022` at the continuation line and leaves the repeated inline values unchanged.

Repeated single-line body values remain valid and lossless when there is no continuation block:

```txt
[N] N Note body:first body:second
```

However, repeated `body:` values cannot be serialized when any value is multiline. The `|` syntax has no boundary marker that could preserve which continuation lines belong to which repeated value, so the serializer raises `ValueError` instead of flattening or merging the values.

## Authoring guidance

Use one of these forms:

- one short inline value: `body:short_text`;
- repeated inline values when every value is single-line and no `|` block follows; or
- one continuation block for one multiline value.

A single inline value followed by continuation lines remains accepted for compatibility and canonicalizes to the continuation-only form. Never add a continuation block after repeated `body:` values. This fail-loud boundary prevents a formatter, converter, editor integration, or future LSP action from silently changing the data model.

## Verification checklist for integrations

When building an editor formatter, importer, exporter, or AI tool around
life.txt, test these cases before writing user data:

- parse and re-serialize `tests/golden/roundtrip_cases.json`;
- keep JSON/JSONL detail values as arrays even when a key appears once;
- preserve explicit timezone-offset strings during interchange;
- reject `body:first body:second` followed by `| continuation` with `E022`;
- raise rather than serialize a repeated `body:` set containing any multiline value.

The important rule is not that every surface prints identical whitespace; it is
that no surface silently merges, drops, or retargets an authored value.
