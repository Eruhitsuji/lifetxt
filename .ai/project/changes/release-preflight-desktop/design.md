# Design

Create a read-only workflow_call matrix, separate controller/source checkouts,
and a generated local shared Git checkout pinned to source SHA. Existing source
scripts build/stage the real runtime and set the existing SemVer/Apple metadata.
Reuse Core context/source checks and Standalone host/frozen smoke. Verify the
generated checkout changed only tauri.conf.json, plus generated untracked output;
reject unexpected tracked or runtime-resource changes. Original source stays clean.

Stage proof certifies runtime readiness only. Bundle revalidates stage and hashes,
runs native Tauri with a bounded timeout, checks output inventory/signatures, then
seals the complete report. Component creation after upload rehashes exact payload.
No claims of native GUI installation or extraction from every format are made.

Desktop names may contain spaces, unlike schema-1 payload paths. Preserve public
filenames in a sealed alias/public_name/format mapping, use safe internal aliases,
and require future consumers to authenticate the proof archive/API identity and
bind mapping to component hashes. Publish installer roles under public_name only.
The single bundled-core role is private evidence, never an extra release asset.
No common schema or canonical-writer changes. Handoff recorded on #1305/#1321/#1313.

All three target proofs must be collected explicitly; matrix outputs are not an
inventory. Revert the PR to remove the producer without touching public releases.
Exact commands, guarantees and limits are in the bilingual living contract docs.
