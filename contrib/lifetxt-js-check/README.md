# life.txt JavaScript syntax checker

A read-only checker for supported Format 1 syntax and values. The shared `parser.mjs`
module uses browser APIs available in Node.js and takes a string. The Node.js
CLI requires Node.js 22 or later.

```sh
node check.mjs life.txt
node check.mjs inbox.life.txt projects.life.txt
node check.mjs --check-files inbox.life.txt projects.life.txt
node check.mjs --verify-files inbox.life.txt projects.life.txt
node check.mjs --config lifetxt.config.json inbox.life.txt projects.life.txt
```

Exit codes are 0 for no errors in checked input (warnings are allowed), 1 for
validation errors, 2 for usage or input errors, and 3 for incomplete checks
without validation errors.
Pass up to 64 regular files in argument order. Each file is limited to
16,384 UTF-8 bytes. The check displays up to 100 diagnostics in total.
Multiple-file output identifies the path and line, including the first
occurrence of a duplicate ID. Hierarchy, continuations, and format version
are evaluated within each file. Shared checks use records from the supported
inputs. An unreadable file stops the check with exit code 2.

An explicit `--config PATH` reads a UTF-8 JSON object (up to 16 KiB). The
checker uses the first nonempty ID key from `ids.key` and `api.id_key`, or
defaults to `id`. For example, `{"ids":{"key":"uid"}}` makes `uid:` the
identity for hierarchy inference, references, duplicate detection, and history
parent lookup. The option also accepts the Node attachment settings below. It does not
discover configuration files automatically. In the browser, select the JSON under
Checker settings to apply the same ID key to pasted text or selected life.txt
files. Clear that selection to use `id:` again.

The Node CLI checks attachment paths when you pass `--check-files` before
your inputs. Relative `file:` and `dir:` paths resolve from the life.txt file
that contains them. The checker looks up filesystem metadata, follows
symlinks, and warns about missing targets, incorrect kinds, or invalid
attachment values. It supports native absolute paths and `~` for the current
user. Hash fragments are checked for hexadecimal syntax. Use
`--verify-files` to also compare a recorded `file:` SHA-256 prefix, such as
`file:report.pdf#sha256=0123456789abcdef`, with the file's content. Only
regular files are read. The same option verifies recorded `dir:` hashes
by hashing the relative paths and content hashes of the files in the tree.
By default it uses Core's ignore list and caps each directory at 2,000
files and 200 MiB. To override these settings, pass a `--config` JSON such
as `{"attachments":{"ignore":[".git","cache"],"max_files":500,"max_bytes":104857600}}`.
An ignore list replaces the defaults and accepts exact file or directory
names, as a list or a comma-separated string. The limits accept positive safe
integers. It skips directory symlinks inside the tree.

Both options warn about paths with backslashes, absolute paths, drive
letters, UNC paths, non-NFC names, and trailing spaces or periods. They
also warn when a path resolves with different casing in its last component.
Attachment paths are accessed only when one of the two options is passed.

In the browser, choose an attachment folder under Checker settings. Pasted
text and selected life.txt inputs use the folder root as their base directory.
The checker uses file paths exposed by the browser and infers directories
from their files. It marks out-of-folder paths, unobserved directories
(including empty ones), and references without a selected folder as
unchecked. With Verify attachment SHA-256 enabled, the browser compares recorded
`file:` and `dir:` SHA-256 prefixes against the selected files. Directory
hashing uses the same default ignores, ordering, and limits as Node and
only includes files exposed by the folder picker. Its additional Web Crypto
limit is 16 MiB per file. With the checkbox off, the browser checks hash
fragment syntax using path metadata only.

The checker reads item headers, titles, details, backslash line joins, and
`|` body lines. It preserves unknown and repeated detail keys. Unsupported
format versions are reported as unchecked.

Use a compact ASCII token for `id:`. The checker warns about invalid text IDs
and repeated nonempty text IDs in the input, including repetitions on the same
item, and gives the first occurrence's line. IDs are case-sensitive. Non-text
ID values produce a type error and do not participate in duplicate detection.

Reference keys such as `parent:`, `ref:`, and `depends_on:` and valid
`requires:` conditions are checked against the same input. The checker
warns about missing targets, self references, and ambiguous IDs.
Cycle warnings show the starting line and the ID path. Cycle checks cover
`parent:`, `depends_on:` combined with reversed `blocks:`, and each of
`duplicate_of:`, `replaced_by:`, `follows:`, and `realizes:` separately.
Only IDs with exactly one occurrence participate. For `follows:` and
`replaced_by:`, the checker also warns when the successor is dated before
the predecessor. It uses the first comparable date from `due:`, `do:`,
`on:`, or `from:`, in that order. For datetimes, it compares the calendar
date as written. The Node CLI checks IDs, references, and related history across
all supplied files. The browser checker accepts pasted text or up to 64
selected files. It checks selected files together and shows their names in
diagnostics. All file reads and checks run locally in the browser.

A completed item with an open `depends_on:` prerequisite gets a warning.
A completed or canceled parent with open direct children gets a warning on the
parent line. Explicit and inferred `parent:` links both count.

The built-in temporal fields check calendar dates (`YYYY-MM-DD`), datetimes
(`YYYY-MM-DDTHH:MM`), or times (`HH:MM`), depending on the key. The check
uses ASCII digits and accepts optional seconds, fractional seconds, and
UTC offsets in times and datetimes. The diagnostic gives the item line and
field name. Events with both `from:` and `to:` are checked for an end earlier
than the start, using the first value of each key. Datetimes with UTC offsets
are converted to the runtime's local wall clock before comparison, as in
Python Core. An event with an earlier end gets a warning.

Status items (`S`) require `from:` and `state:`. The checker validates
the status datetimes and recommends `[/]` for an ongoing status or `[x]`
when `to:` is present. Unknown `state:` values produce a warning.

The checker recommends the `[N]` marker for notes (`N`) and journals (`J`).
Completed items generally use `done:`, except status items (`S`). A
`done:` field on an item with a marker other than `[x]` produces a warning.

Message items (`M`) require `sender:` and `recipient:`. The checker warns
about a missing boundary or reversed order in `notify_from:` and `notify_to:`,
and recommends a workflow marker for messages. A date-only start means
00:00:00, and a date-only end means 23:59:59.

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
may be nested up to 32 levels.

An indented item inherits `parent:` from the first `id:` value of the nearest
less-indented item unless it already has a parent value. An indented item
without an ancestor, or with an ancestor that has no ID, produces a warning.
The checker uses the configured ID key (default `id:`) and leaves the input text intact.

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

The distribution ZIP contains the parser, CLI, attachment checker, this README, and LICENSE.

Progress accepts percentages such as `75%` and fractions such as `3/5`.
The checker also validates `record:progress_event` notes and their sequence,
timestamps, and continuity with the current item in the same input. Progress
numbers use ASCII digits. Missing timestamps are reported without using the
current time as a substitute.

For `record:item_event` notes, the checker validates the event fields,
sequence, timestamps, and recorded status against the current item. A
partial history may start at a later sequence when it has no creation event.
History event records use `id:` even when the parent lookup uses a configured ID key. History comparisons use textual field values.

The checker validates `est:` and `elapsed:` using ASCII hours and minutes
and suggests a compact duration such as `1h30m` for `90`. When specified,
`importance:` must contain exactly one of `high`, `normal`, and `low`.

Detail keys use a lowercase ASCII letter followed by lowercase letters, digits,
or underscores. Nonconforming keys and unrecognized custom keys produce
warnings. Custom values are preserved, including JSON values within the
checker's supported range. Built-in keys require text values, except for
`requires:`, which also accepts structured conditions. Record-owned fields
are recognized for their corresponding `record:` markers. Validation against
user-defined custom field declarations requires `lifetxt check`.

## Compatibility with Python Core

The reference for this comparison is lifetxt 1.0.5 at commit
[`6266fa5`](https://github.com/Eruhitsuji/lifetxt/commit/6266fa5165de5e32f7b69eb8e26cc9939f91deed).
The comparison suite uses the Python Core from the same checkout so that
changes to either implementation are visible in CI.

| Area | JavaScript checker behavior |
| --- | --- |
| Format 1 | Checks the syntax, values, hierarchy, references, and histories described above. Reports physical lines with symbolic codes. Python uses numeric codes and can also report columns. |
| Input and settings | Supports up to 64 input files, each up to 16 KiB, and shows up to 100 diagnostics. Supply settings explicitly. Node applies the ID and attachment options documented above. The browser applies the ID option. |
| File and directory attachments | Node uses the location of each input file and enables filesystem checks via `--check-files` or `--verify-files`. The browser uses the selected folder as the common base and can only check files exposed by the picker. |
| Hashes | Both check SHA-256 prefixes for files and directories when enabled. Browser hashing requires Web Crypto and limits each file to 16 MiB. Directories that the picker does not expose, including empty ones, are reported as unchecked. |

### Known diagnostic differences

- JSON integers beyond JavaScript's safe range and unsupported format versions
  are reported as unchecked. The date and recurrence checks use ASCII digits.
- JavaScript skips non-text IDs and reference values when resolving links.
  Python can coerce some values and report additional duplicate or reference
  diagnostics.
- JavaScript reports an attachment's source file in multiple-file mode. Some
  Python attachment diagnostics omit the source even when several files were supplied.
- Python offers additional configuration and reporting, including custom
  field declarations, diagnostic filtering, and JSON or SARIF output.

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
including oversized JSON integers and non-text ID or reference values.
The CLI comparison also combines multiple files, a custom ID key, and
directory and file attachments to check diagnostic code, severity, file
when available, and physical line. A changed diagnostic fails CI with the
fixture name and engine.
Update the corresponding expectations when a gap is resolved (#1731).
