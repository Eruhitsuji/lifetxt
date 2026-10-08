# Read-only CLI adapter

Implementation -> Developer Verification -> Independent Review; inherited
adaptive-default / continuous Kanban / W-model; Feature, S, complexity 5/10.
High assurance due to an additive public CLI interface. Codex implements;
Eruhitsuji owns/integrates and reviews implementation/integration on the final
head. Self-review is not independent approval.

Parser/dispatcher in cli.py delegates to daily_flow_cli.py. entrypoint.py routes
flow through that adapter's parser/config/workspace entry instead of the legacy
timezone prescan, which may read excluded archives or unrelated config/input
candidates before source certification. The authoritative parser and existing
config extensions still apply; every other command keeps its legacy route.
That adapter reuses
existing workspace/path expansion, exact-byte mutation.read_text_snapshot,
parser and diagnostic helpers, timezone resolver and injectable clock. It calls
build_daily_flow unchanged and emits its result directly as JSON or text; there
is no CLI scheduler, local ranking, dependency unlock or busy algorithm.

Resolve explicit paths or default workspace active paths (exclude archive roles),
else configured paths/life.txt. Canonical realpaths deduplicate aliases. Existing
directory/glob expansion remains explicit selection, not inferred archive search.
First resolved input's directive controls file-level timezone precedence. Refuse
unresolved local/host rather than silently freezing a host offset through DST.
Timezone, offset-bearing window and one UTC evaluated_at are in the core result.

Read every selected file once per attempt, parse the same text whose exact bytes
were hashed, and recheck the full path set/content hashes after core computation.
On mismatch retry the complete collection once with the same reference clock;
second mismatch emits the canonical generic source_changed blocked model.
Explicit stdin is immutable text read once, with parsed_snapshot provenance.
Effective configuration is the invocation's in-memory snapshot, not a live watch.
This check cannot prevent edits after publication and is not filesystem atomicity.

Missing/undecodable/oversize members fail without partial read inventory output.
16 MB/file and 4 million decoded characters aggregate before parsing, shared
item/edge/expansion caps afterwards; no busy truncation. Core non-complete model
is printed but returns 1 with actionable stderr. Complete capacity failures return
0 and remain visible as unplaced, not an assertion every task fits. Argparse
usage errors return 2. Invalid estimates trigger partial per unchanged core.

Text emits every canonical row/reason/parameter with typed labels and control
escaping, including hypothetical break/buffer rows (the initial CLI has no policy
overrides, core defaults are zero). JSON preserves all fields/order; no envelope,
parser messages only on stderr. No CLI candidate filters were approved/added.

Security: explicit local reads only; no shell, external dependency/network, lock,
mutation/history/undo/proposal write. Output titles belong to selected files;
source names remain opaque hashes. No authorization claims for Web/API. Local
CLI is not a confined remote reader. Recurrence/DST/long-event limits inherited;
no change to old commands or shared core. Rollback is an additive revert.
