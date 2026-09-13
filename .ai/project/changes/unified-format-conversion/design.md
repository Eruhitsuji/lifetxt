# Design

`lifetxt.conversion` owns the canonical format names, supported-pair matrix,
decoders, encoders, explicit error types, and `convert_text()` result contract.
It transforms in-memory text through the existing `Item` model and imports the
authoritative parser/serializers; it does not read paths, fetch URLs, or mutate a
workspace.

`lifetxt convert` is a thin adapter that reads each path or stdin, aggregates
decoded items, invokes the shared encoder, and writes stdout or `-o`. Existing
JSON/JSONL/CSV wrappers call the same encode/decode boundary where their
semantics match. The existing ICS renderer moves into `lifetxt.ics` so both
`to-ics` and the shared core use one implementation. Todo and Markdown decoder
helpers likewise become shared.

Every source can target the item-preserving `life`, `json`, `jsonl`, and `csv`
formats. Only `life -> ics` is advertised initially. The new route rejects any
life item that the event-only ICS representation would discard; legacy
`to-ics` retains its established skip behavior through an explicit
`reject_loss=False` compatibility call.

The existing `from-markdown --preset github` path intentionally remains a
higher-level GitHub-aware convenience workflow: it adds assignee/reference IDs
and parent links that the canonical, generic `markdown-task-list` decoder does
not invent. It therefore keeps its established parser instead of pretending to
be byte-equivalent. `import`/`export` likewise keep workflow-only filtering,
append, inference, and binary-format behavior outside the pure core.
