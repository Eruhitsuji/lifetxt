# SQLite Interchange Format (`lifetxt-sqlite-v1`)

Status: **approved for implementation** (#690). Implemented by #691.

This document defines the durable schema and round-trip contract for
`lifetxt export --format sqlite` / `lifetxt import --preset sqlite`. It is a
specification only; #691 implements it unmodified. Any future schema change
requires a new document version (`lifetxt-sqlite-v2`) and an explicit
migration/refusal plan -- this contract, once implemented, is not silently
revised in place.

## 1. Purpose and role

SQLite export gives a life.txt workspace a **queryable relational
interchange** representation: a `.db`/`.sqlite` file any SQL client
(`sqlite3` CLI, DB Browser for SQLite, a spreadsheet's ODBC driver, a
one-off analysis script) can query directly, with no lifetxt code involved.

SQLite is **not**:

- lifetxt's authoritative live-edit format (plain `life.txt` remains
  authoritative; see `.ai/project/RULES.md`'s Design Principles);
- a live-synchronized mirror of `life.txt` (export is a point-in-time
  snapshot; there is no watch mode);
- a general-purpose SQL dump / migration target for other tools.

## 2. Schema

### 2.1 `metadata`

```sql
CREATE TABLE metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Required rows, written by every export:

| `key` | `value` | Deterministic? |
|---|---|---|
| `schema_version` | `lifetxt-sqlite-v1` | yes |
| `generator` | `lifetxt` | yes |
| `item_count` | decimal string, e.g. `"42"` | yes (given identical logical input) |
| `exported_at` | UTC ISO-8601, e.g. `"2026-09-07T12:00:00+00:00"` | **no** -- provenance only, see §4 |

Import refuses a database missing the `metadata` table, missing
`schema_version`, or whose `schema_version` is not exactly
`lifetxt-sqlite-v1` (older *or* newer values are both refused -- v1 has no
predecessor, so any other value is either foreign or a not-yet-supported
future version). Refusal happens before any item is read into memory.

### 2.2 `items`

```sql
CREATE TABLE items (
    item_seq    INTEGER PRIMARY KEY,
    status      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    source_line TEXT NOT NULL
);
```

- `item_seq` is a 1-based sequence assigned in export order. It is the
  **only** ordering contract; consumers must `ORDER BY item_seq` explicitly
  rather than relying on SQLite's incidental physical/rowid order, which is
  not part of this contract.
- `status`/`kind`/`title` mirror `Item.status`/`Item.kind`/`Item.title`
  exactly (e.g. `"[ ]"`, `"T"`, `"Write report"`).
- `source_line` is the **canonical native rendering** of the item
  (`lifetxt.serializer.item_to_line`, via the shared
  `lifetxt.native_codec` boundary from #689), stored as human-readable
  verification/fallback data an operator can read directly with a SQL
  client. It is derived, not authoritative: reconstruction on import always
  goes through `items`+`details`, never by re-parsing `source_line`.

Indentation-based hierarchy is **flattened at export time**: every item is
run through `lifetxt.native_codec.canonical_hierarchy_items()` (the same
canonicalization `lifetxt filter --canonical` already performs), so
`items` never needs an `indent` column and parent/child relationships are
represented uniformly as an explicit `parent:` detail row in `details`
below.

### 2.3 `details`

```sql
CREATE TABLE details (
    item_seq    INTEGER NOT NULL REFERENCES items(item_seq),
    detail_seq  INTEGER NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (item_seq, detail_seq)
);
CREATE INDEX idx_details_item_seq ON details(item_seq);
```

- One row per `(key, value)` pair, in the exact order
  `Item.details.items()` iterates them (repeated keys therefore produce
  multiple consecutive rows with the same `key`).
- `detail_seq` is a 1-based per-item sequence over every `(key, value)`
  pair (not per-key), so reconstruction only needs
  `ORDER BY item_seq, detail_seq` to rebuild the exact original
  `OrderedDict[str, list[str]]` shape, including repeated-key order and
  custom (non-schema-known) keys, unchanged.
- `value` stores the detail value's exact text, including embedded
  newlines for a multiline `body:` value (SQLite `TEXT` has no line-length
  or newline restriction). Reconstruction hands this straight back to
  `Item.details["body"] = [multiline_text]`; `item_to_line()` already knows
  how to re-emit it as `\|`-continuation lines.

### 2.4 Indexes

```sql
CREATE INDEX idx_items_kind_status ON items(kind, status);
```

Justified by the two most common ad hoc queries external tooling is
expected to run against an exported database ("show me open tasks", "count
items by kind"). No further index is added speculatively; a future version
may add one with its own justification once real external-query evidence
exists.

## 3. Round-trip contract

**Semantic, not byte-level.** `life -> sqlite -> life` round-trips:

- item order (via `item_seq`);
- `status`/`kind`/`title`;
- every detail key (built-in and custom), its full ordered value list
  (repeated keys), and multiline values;
- `id:`/link/reference detail values (they are ordinary detail values, no
  special-casing);
- mixed item types in one export.

**Not preserved**, matching #689's already-documented native fidelity
boundary and this format's own explicit non-goals:

- original indentation (flattened to explicit `parent:` links at export,
  same as `filter --canonical`);
- blank lines, `#` comments, and `#!KEY: VALUE` directives (not part of the
  `Item` model at all -- see #689);
- the exact byte layout of the original `life.txt` file.

## 4. Determinism

Given the **same filtered item set and export options**:

- `items` and `details` row content and order are byte-identical across
  runs (deterministic serialization of an already-deterministic in-memory
  structure);
- `metadata.exported_at` is **not** deterministic by design -- it records
  when the export ran, which is provenance, not payload;
- the SQLite **file bytes** are not promised to be byte-identical between
  two exports even with `exported_at` held equal, because SQLite's own
  on-disk B-tree page layout, free-list state, and header fields are not
  specified by this contract and are not something lifetxt controls at the
  `sqlite3` API level. Byte-for-byte archive determinism is a property of
  the `.lifetxtz` format (`lifetxtz-v1`, #692), not this one.

This is a deliberately honest, narrower claim than full byte determinism:
row *content* and *order* are guaranteed and are what #691's round-trip and
determinism tests assert; the on-disk `.db` file itself is not asserted
byte-identical.

## 5. Import validation and refusal

Applied in order, before any output write:

1. The file must open as a SQLite database (`sqlite3.connect` + first
   query). A non-database file, or a file `sqlite3` cannot parse, is
   refused with the underlying error surfaced.
2. `metadata` must exist and contain `schema_version` ==
   `lifetxt-sqlite-v1`. Anything else (missing table, missing key, foreign
   value, a hypothetical future `lifetxt-sqlite-v2`) is refused by name --
   no guessing or best-effort partial import.
3. `items` and `details` must exist with the columns above; a missing or
   malformed table is refused.
4. No further semantic validation (e.g. via `lifetxt check`) is performed
   inside the codec itself; the reconstructed items are handed to the same
   `validate_item`/writer path every other import preset already uses, so
   existing diagnostics apply uniformly.

Every refusal happens **before** any destination file is touched.

## 6. Export safety

Export is transactional and produces no partially-valid destination on
failure:

1. Build the complete SQLite database at a private temporary path.
2. On any error during that build, delete the temporary file and raise;
   the destination path is never touched.
3. On success, read the temporary file's bytes and commit them to the
   destination through `lifetxt.atomic.atomic_write_bytes` -- the shared
   atomic-replace primitive already used across this codebase for other
   binary/text writes.

## 7. Extension recognition

`lifetxt import` infers `--preset sqlite` only for the unambiguous
extensions `.db`, `.sqlite`, and `.sqlite3` (case-insensitive). No other
extension is guessed as SQLite, matching #689's "never guess a plain
`.txt`" precedent for native life.

## 8. Example mappings

Task with repeated tags and a link:

```text
[ ] T "Write report" id:t1 due:2026-06-08 tag:urgent tag:review parent:proj1
```

```text
items:      item_seq=1 status="[ ]" kind=T title="Write report" source_line=<canonical line>
details:    (1,1,"id","t1") (1,2,"due","2026-06-08") (1,3,"tag","urgent")
            (1,4,"tag","review") (1,5,"parent","proj1")
```

Journal entry with a multiline body:

```text
[N] J "Research day" on:2026-06-23
| Read papers in the morning.
| ## homework
```

```text
items:      item_seq=2 status="[N]" kind=J title="Research day" source_line=<canonical line>
details:    (2,1,"on","2026-06-23")
            (2,2,"body","Read papers in the morning.\n## homework")
```

## 9. Future evolution

Not in v1, and explicitly out of scope until real evidence justifies a new
version:

- PostgreSQL/MySQL/DuckDB/remote database support;
- generic SQL text dump export;
- live/bidirectional synchronization;
- ORM or query-builder dependency;
- attachment/config/history packaging alongside items.
