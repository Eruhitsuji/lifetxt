# Human procedure guidance: read-only stage

Approved contract: [English](../../../../docs/en/procedure-guidance-design.md)
and [日本語](../../../../docs/ja/procedure-guidance-design.md).
User guide: [English](../../../../docs/en/procedure-guidance.md) and
[日本語](../../../../docs/ja/procedure-guidance.md).

D1–D4 were explicitly approved by Eruhitsuji following PR #1345 merge. The owner
requested three PRs: read-only (#1334–#1337), run/CLI (#1338–#1341), Web
(#1342/#1343). Each starts from current main after the previous PR merges.
Intra-stage dependencies are ordered within one PR. Stage 1 is M/complexity 6:
its projection, strict graph validation, CLI and examples form one reviewable
read-only capability. No intermediate sub-PRs or integration branch. Stage 1
source: e76125ed; branch feature/1332-procedure-readonly; final base main.

Discovery/requirements/architecture approval completed; Implementation →
Developer Verification → Independent Review, adaptive-default / W-model.
Owner/independent reviewer/integrator/merge authority: Eruhitsuji; executor Codex.
High assurance covers the adopted human-choice contract. Independent latest-head
implementation and integration review remains pending, not replaced by self-review.

## Boundaries and implementation

Four dedicated modules separate immutable projection, strict validation,
data-only rendering, and bounded CLI admission. No generic KNOWN_KEYS/check,
links, VM, flow, history or Task mutation changes. Node/details tuples snapshot
source values; no writes or run creation are present. Other roots and ordinary
records are excluded from the selected graph. Ambiguous file IDs and orphan
profile hierarchy fail closed rather than selecting a guessed owner.

Duplicate IDs, malformed hierarchy/fields, unresolved transitions, unreachable
nodes and end-unreachable components refuse the entire output. Exit-capable
cycles warn for browsing. Parent/record/step/edge/body/source/output limits are
explicit. Indexed edges, iterative reachability, reverse end reachability and
Kahn cycle detection avoid recursive graph walks. Input order is display order;
only proc_* defines procedure edges. No new public JSON schema is exposed.

Graph node IDs are local ordinals, Mermaid punctuation uses decimal entities,
DOT reuses the existing quote helper, and terminal controls are escaped. Input
is one explicit regular file, read through a bounded descriptor (nonblocking on
POSIX). Source hash covers exact BOM/newline bytes with mutation.hash_bytes,
the same primitive as read_text_snapshot, without its unbounded read. CLI
config/workspace paths never replace or pre-read the explicit file. Configured
noncanonical id-key refuses. Parser syntax errors become stable PG diagnostics
with line numbers, not raw potentially private lines/paths.

A minimal entrypoint dispatch follows existing flow's pattern, bypassing
speculative timezone pre-reads because procedures perform no date calculations.
FIFO testing demonstrated that a generic pre-read could block before admission.
Generic reference diagnostics are also not traversed during admission; only
syntax is parsed before dedicated bounded ID/graph validation. Existing commands
retain their original dispatch and timezone policies. CLI taxonomy and docs
navigation add the new read-only command without duplicating command registries.

## Quality and operations

Review viewpoints: selected-scope integrity, termination/reachability,
deterministic order, legacy compatibility, control/diagram injection, resource
admission, no new dependency, template bytes/status preservation.
Tests exercise actual CLI/subprocess output, negative input and boundary cases,
plus existing parser/links/VM/flow/taxonomy regressions. Verification records
executed commands separately from future acceptance plans.

Text-editor examples use only existing Note/Task syntax and keep two independent
occurrences separate from the reusable template. Machine-readable proc_* examples
remain separately opt-in; generic check intentionally retains W106.

No release/migration/deployment is performed. Revert stage 1 code/docs if needed;
there is no generated run state to migrate or delete. Run models/guards/events,
CAS persistence, executable CLI guidance and Web are stages 2/3. Their exact
schema/authorization mappings and implementation evidence are not claimed here.
