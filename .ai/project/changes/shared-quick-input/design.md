# Shared Quick input

Implementation phase; adaptive-default / W-model; Feature; Standard assurance
as assigned by #1021: additive input resolution only, existing mutation, revision,
auth and ID policy remain authoritative. No schema or mutation architecture change.
M is kept as one PR because migrating the shared contract and consumers separately
would temporarily retain the exact surface drift this issue eliminates.

Reuse decision: extend Quick Capture using parser.parse_text, shorthand.parse_capture,
serializer.item_to_line and each established validated mutation contract. Classification
is a single leading `[` safety discriminator matching parser status intent; Format
validity is decided only by the authoritative parser/validator. One physical line;
unknown custom keys remain valid. Context fills missing details and explicit fields win.
CLI authoring flags/presets/defaults apply to shorthand; complete records are authoritative
and ignore authoring defaults/flags. IDs remain surface-specific: CLI respects ids.auto;
TUI/Web/MCP guarantee addressable IDs; all reuse configured ID keys/prefixes and preserve
explicit full-record IDs. MCP source metadata/proposal policy remains in force.

## Surface inventory

| Surface | Before | Target |
| --- | --- | --- |
| CLI quick/q/add, stdin | shorthand | shared resolver; unchanged persistence |
| quick --journal | delegates to quick with Journal flags | inherits resolver |
| Web POST /api/items/capture | shorthand | shared resolver |
| Focus Quick Add | browser-built raw task | common capture + absent-field today due context |
| Web command /add | capture API | inherits shared resolver |
| Existing Web Quick Add + live preview | JS raw/capture detection | common capture + read-only resolver preview |
| /capture | JS raw/capture detection | common capture API |
| Planner | capture API | inherits shared server semantics |
| Local TUI /add and alias a | shorthand | shared resolver |
| Local TUI /related | shorthand plus context | shared resolver + absent-field context |
| Remote TUI /add, /related | client shorthand parser + structured create | unchanged text to server capture; revision/cache guards |
| MCP capture_item | shorthand plus proposal/source metadata | shared resolver + existing safeguards |
| Explicit raw/import, structured create, guided authoring, presence/message commands | intentional distinct contracts | remain explicit; not Quick text ingestion |
| Remote v1 item create | structured payload | remains structured; Remote TUI Quick uses guarded common Web API |

## Review and test viewpoints

Review parser reuse, no silent fallback, legacy shorthand precedence, quoted/repeated
fields, configured IDs, workspace duplicates, no-write failures, auth/read-only/revision
and proposal guards, browser feedback/focus/pending-submit, Remote server authority.
Coding: cohesive pure resolver, thin adapters, no new dependencies or grammar.
Security: untrusted text never bypasses validation, revision, auth or mutation; browser
renders feedback as text; no secrets or permission changes. Tests must compare logical
records across shared/CLI/TUI/Web/MCP and exercise Remote HTTP delegation and real JS.
Shared registry/traceability files integrate sequentially under owner Eruhitsuji;
refresh origin/main before final push. Revert PR to roll back; no migration needed.
