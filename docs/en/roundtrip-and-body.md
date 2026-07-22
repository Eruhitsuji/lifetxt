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

## Forms that are intentionally rejected

Do not combine an inline `body:` detail with `|` continuation lines:

```txt
[N] N Note body:inline
| ambiguous continuation
```

The continuation could mean "append to the inline value" or "create another body value". The parser therefore reports error `E022` at the continuation line.

Repeated single-line body values remain valid and lossless:

```txt
[N] N Note body:first body:second
```

However, repeated `body:` values cannot be serialized when any value is multiline. The `|` syntax has no boundary marker that could preserve which continuation lines belong to which repeated value, so the serializer raises `ValueError` instead of flattening or merging the values.

## Authoring guidance

Use one of these forms:

- one short inline value: `body:short_text`;
- repeated inline values when every value is single-line; or
- one continuation block for one multiline value.

Never mix the inline and continuation forms on the same item. This fail-loud rule prevents a formatter, converter, editor integration, or future LSP action from silently changing the data model.
