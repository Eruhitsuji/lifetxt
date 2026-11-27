# life.txt JavaScript syntax checker

A read-only checker for supported Format 1 syntax and values. The shared `parser.mjs`
module uses browser APIs available in Node.js and takes a string. The Node.js
CLI requires Node.js 22 or later.

```sh
node check.mjs life.txt
```

Exit codes are 0 for no errors in checked input (warnings are allowed), 1 for
validation errors, 2 for usage or input errors, and 3 for incomplete checks
without validation errors.
Inputs are limited to 16,384 UTF-8 bytes and output to 100 diagnostics.

The checker reads item headers, titles, details, backslash line joins, and
`|` body lines. It preserves unknown and repeated detail keys. Unsupported
format versions are reported as unchecked. ID checks and reference resolution
require `lifetxt check`.

The built-in temporal fields check calendar dates (`YYYY-MM-DD`), datetimes
(`YYYY-MM-DDTHH:MM`), or times (`HH:MM`), depending on the key. The check
uses ASCII digits and accepts optional seconds, fractional seconds, and
UTC offsets in times and datetimes. The diagnostic gives the item line and
field name. Events with both `from:` and `to:` are checked for an end earlier
than the start, using the first value of each key. Datetimes with UTC offsets
are converted to the runtime's local wall clock before comparison, as in
Python Core. An event with an earlier end gets a warning.

Recurrence checks cover `repeat:daily`, `weekly`, `monthly`, `yearly`, and
`weekdays`, as well as positive `interval:` and `count:` values. The checked
`RRULE:` subset is `FREQ`, `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY`,
`BYMONTHDAY`, `BYMONTH`, and `WKST`. The checker reports the problematic part
and validates values and combinations without expanding any occurrences.
Recurrence numbers use ASCII digits.

The checker validates the shape of `requires:` conditions. Use
`requires:review=done,in_progress` or a JSON object such as
`requires:json<< {"any":[{"id":"review","state":"done"},"proxy=[x]"]} >>`.
Each repeated value is checked. Groups must contain at least one condition and
may be nested up to 32 levels. Use `lifetxt check` to verify the referenced IDs.

An indented item inherits `parent:` from the first `id:` value of the nearest
less-indented item unless it already has a parent value. An indented item
without an ancestor, or with an ancestor that has no ID, produces a warning.
The checker uses the default `id:` key and leaves the input text intact.

A backslash at the end of a physical line joins it to the next line.
Leave a space before the backslash when the next line starts a new detail.
A trailing backslash without another line or a join into a `|` body line
reports an error at the affected physical line.

JSON details use `key:json<< … >>` with whitespace around the JSON, including
line breaks. A top-level array supplies the list of values for the key. An
empty array supplies zero values, and an array nested inside the top-level
array is kept as one value. A JSON integer outside the JavaScript safe range
(−(2^53 − 1) through 2^53 − 1) leaves the check incomplete. Use
`lifetxt check` for those values and for key-specific validation.

The distribution ZIP contains the parser, CLI, this README, and LICENSE.

## Core comparison

From the repository root, run the same checks as the JS checker CI:

```sh
node --test contrib/lifetxt-js-check/parser.test.mjs
PYTHONPATH=. python contrib/lifetxt-js-check/check_core.py
```

The comparison runs both parsers over the same fixtures. It checks parsed
records and matches diagnostic severity and physical line number using an
explicit mapping from Core codes to JS codes. Core columns are checked against
fixture expectations. The current JS diagnostic format has no column field.

Fixtures also document the current engine-specific results for known gaps,
including oversized JSON integers and ID references. A changed diagnostic fails
CI with the fixture name and engine.
Update the corresponding expectations when a gap is resolved (#1731).
