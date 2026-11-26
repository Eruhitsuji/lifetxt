# life.txt JavaScript syntax checker

A read-only checker for a subset of Format 1 syntax. The shared `parser.mjs`
module uses browser APIs available in Node.js and takes a string. The Node.js
CLI requires Node.js 22 or later.

```sh
node check.mjs life.txt
```

Exit codes are 0 for no errors in checked syntax, 1 for syntax errors, 2 for
usage or input errors, and 3 for incomplete checks without syntax errors.
Inputs are limited to 16,384 UTF-8 bytes and output to 100 diagnostics.

The checker reads item headers, titles, details, backslash line joins, and
`|` body lines. It preserves unknown and repeated detail keys. Unsupported
format versions are reported as unchecked. Dates, IDs, references and inferred
hierarchy are outside the checked scope. Use `lifetxt check` for full validation.

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
including oversized JSON integers, hierarchy, dates, requirements, and ID
references. A changed diagnostic fails CI with the fixture name and engine.
Update the corresponding expectations when a gap is resolved (#1731).
