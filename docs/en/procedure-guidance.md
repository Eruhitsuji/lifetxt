# Human procedure guidance

Keep a reusable instruction template and a record of each occurrence separate.
The template describes work; checking a box in an occurrence does not complete
or edit the shared template. Instructions remain readable offline in an approved
text editor. This builds on the [text-editor-only workflow](text-editor-only-workflow.md).

## Text editor only

Open [procedure-template-en.txt](../../examples/procedure-template-en.txt) and
[procedure-work-en.txt](../../examples/procedure-work-en.txt) as two files. The
first uses ordinary `[N] N` records, IDs, parents and body lines only. It describes
inspection → backup → update → verification and a manual restoration branch.
The second has independent Task IDs for two occurrences: the first is complete,
while the second is paused during backup. Template IDs/statuses remain unchanged.

1. Read the template's body in the stated order; find a step by `id:`.
2. Copy the work pattern for each new occurrence, assigning new Task IDs.
   `ref:` points at a template step, not another occurrence's result.
3. Set `[ ]` → `[/]` when you start a task and `[x]` after verifying it.
4. For a pause, retain `[/]` and write what remains in its body. Use `[?]` for
   an unresolved prerequisite or decision. Before resuming, read the note and
   confirm the situation yourself; no timer or automatic resume is implied.
5. Record the chosen yes/no result manually. If verification fails, read the
   restoration instruction, perform it yourself, then check again.

These files contain no machine-evaluated conditions, automatic actions,
notifications or structured run evidence. With developer tools available,
`python -m lifetxt check examples/procedure-template-en.txt examples/procedure-work-en.txt`
checks their ordinary Format 1.0 syntax and resolves their references together.
Checking the work file alone may warn about unresolved template references.
Do not store credentials or unauthorized workplace information in either file.

## CLI definition browsing and flowcharts

For machine-readable navigation, opt in with the separate
[procedure-flow-en.txt](../../examples/procedure-flow-en.txt) example:

```sh
python -m lifetxt procedure show examples/procedure-flow-en.txt --id r
python -m lifetxt procedure graph examples/procedure-flow-en.txt --id r --format text
python -m lifetxt procedure graph examples/procedure-flow-en.txt --id r --format mermaid
python -m lifetxt procedure graph examples/procedure-flow-en.txt --id r --format dot
```

`show` includes body instructions, hierarchy and outgoing choices. `graph` emits
text or diagram source, preserving the same transitions; it does not call an
external rendering service. The sample has a retry loop with an exit, so PG201
appears on stderr while the diagram alone goes to stdout. Invalid definitions
return nonzero, diagnostic codes and source line numbers on stderr, and no
partial output. These commands never create a log, execute instructions, open
URLs, change Task statuses, or complete a run.

Exactly one explicit regular UTF-8 file and a root ID are required. Paths with
spaces may be quoted. There is no stdin, glob, directory or workspace expansion;
an alternate configured ID key is refused. Definitions are `[N] N` records:

| Field | Meaning |
| --- | --- |
| `proc_role:root proc_version:1 proc_start:STEP` | Root and single entry |
| `proc_role:step parent:ROOT proc_kind:action proc_next:STEP` | Action instruction with one next step |
| `proc_kind:decision proc_case:yes=A proc_case:no=B` | 2–16 explicit human choices, no expression evaluation |
| `proc_kind:end` | Explicit terminal step, no outgoing transition |

Each record has exactly one safe `id:`; step parents may form a hierarchy within
the same root. Display order is file order, not execution order. Choices are
case-sensitive lowercase ASCII tokens. Missing targets, duplicate IDs/labels,
unknown `proc_*` fields, unreachable steps, parent cycles and any reachable step
without a route to an end are errors. A cycle with an exit is a warning for
browsing; starting runs requires explicit acknowledgement and finite guards.

Generic `check` still treats `proc_*` as custom fields and reports W106; it does
not validate procedure semantics. `--warnings-as-errors` therefore rejects the
opt-in example. Generic serialization preserves these fields. `links`, `flow`,
`vm`, `depends_on`, `follows` and ordinary `next` retain their existing meanings.

Limits: 10 MiB / 10,000 records per file, 500 selected steps, 2,000 edges,
parent depth 32, 64 KiB body per record and 2 MiB rendered output. Outputs escape
authored control characters; diagram nodes use independent local IDs to avoid
name collisions. An exact source-byte SHA-256 is retained internally; there is
no public JSON projection/API. Local run commands are documented below.

The [approved design](procedure-guidance-design.md) describes the run/event/CAS
contract below and the remaining planned Web behavior.

## Local run navigation and evidence

`procedure run` guides a human through explicit operations. It never performs
the written maintenance, launches commands/URLs, sends HTTP/MCP requests, or
changes the Note template/ordinary Tasks. Each deliberately started run gets a
new ID and its own state. The separate run log is the only authority; state is
replayed from ordered native `record:procedure_event` Notes, not a mutable status
file. The existing transaction journal supplies recovery artifacts, not a second
run-state authority.

First inspect the exact definition and log revisions. `show` with no run ID
lists this source/root's runs and displays the start step; a missing log is not
created. Use a log path whose parent already exists.

```sh
python -m lifetxt procedure run show examples/procedure-flow-en.txt --id r --log runs.txt
python -m lifetxt procedure run start examples/procedure-flow-en.txt --id r --log runs.txt --actor local --request-id start-001 --template-revision TEMPLATE_SHA --log-revision "<missing>" --step a --sequence 0 --allow-loops
```

Replace `TEMPLATE_SHA` with the displayed Template revision. The example has an
exit-capable retry loop, so `--allow-loops` acknowledges it; guards remain fixed
at 1,000 edge traversals and 20 visits per step. For an existing log, copy its
exact Log revision instead of `<missing>`. Start returns a new Run ID, Sequence 1
and the current instruction. `--actor` is a bounded local attribution token,
**not authentication**; local file permissions remain the access boundary.

Inspect again before each later operation and review the current instruction:

```sh
python -m lifetxt procedure run show examples/procedure-flow-en.txt --id r --log runs.txt --run-id RUN_ID
python -m lifetxt procedure run next examples/procedure-flow-en.txt --id r --log runs.txt --run-id RUN_ID --actor local --request-id next-001 --template-revision BOUND_SHA --log-revision LOG_SHA --step a --sequence 1
python -m lifetxt procedure run choose examples/procedure-flow-en.txt --id r --log runs.txt --run-id RUN_ID --actor local --request-id choice-001 --template-revision BOUND_SHA --log-revision NEW_LOG_SHA --step q --sequence 2 --choice yes
```

Replace `RUN_ID`, `BOUND_SHA`, `LOG_SHA`, `NEW_LOG_SHA`, step and sequence from the
latest reviewed output. Bound template revision stays the original start binding;
log revision/sequence change after each committed event. These are explicit
preconditions, never automatically upgraded or retried. Choice tokens are exact
and case-sensitive; no stdin prompt or default choice is used. Actor and request
IDs use 1–64 ASCII letters/digits/underscore/dot/hyphen, starting with a letter or
digit. Request IDs must be unique across the whole log.

| Operation | Allowed state / result |
| --- | --- |
| `next` | active action: advance one edge |
| `choose --choice TOKEN` | active decision: follow exactly the selected edge |
| `pause` | active → paused, same step and traversal counts |
| `resume` | paused → active, same step; original template must match |
| `finish` | active end → completed; reaching end alone does not complete |
| `abandon` | active/paused → abandoned, retaining the chain |

All writes use the same required actor/request/revision/step/sequence flags.
There is no back/undo; repeat work in a new run. Completed and abandoned runs
remain inspectable but refuse mutation. An invalid operation, stale form or
unknown choice returns nonzero with stderr diagnostics and no successful output
or event append. Guard exhaustion still permits pause/abandon if the event cap
has not been reached.

### Changed definitions, unknown outcomes and recovery

Any source-byte edit, including comments or BOM/newline changes, blocks next,
choose, resume and finish. `show --run-id` still replays the frozen control plan
(step IDs, kinds and edges only); it does not show a changed definition's body as
an old instruction. Pause/abandon remain available with the original Bound
template revision. To continue, an operator must restore the exact original
source bytes from a trusted backup, or abandon and start a new run. There is no
automatic template migration, body snapshot or frozen execution of external work.
A source path is bound by a canonical-path SHA-256 handle; moving/copying a file
does not silently rebind the run. Hashes are not a guarantee of path anonymity.

After a lost/uncertain response, **do not automatically submit the operation
again**. Inspect the original request ID:

```sh
python -m lifetxt procedure run show examples/procedure-flow-en.txt --id r --log runs.txt --request-id next-001
```

A matching receipt reports its original event/sequence and the run's current
state. An absent request refuses without replay; inspect transaction recovery
before deciding on a new explicit request. Reusing a committed request ID never
appends a duplicate, even across two runs. Two writers sharing a log must refresh
its file revision explicitly; separate runs are logically independent but share
that CAS boundary.

Each update stages one complete event-log replacement under the existing lock,
CAS and durable transaction-journal policy. Before/after log bytes are retained
in the protected journal; template bodies are never journal targets. Crashes or
unresolved/corrupt journals block new writes. Use the existing
[transaction recovery tools](transaction-recovery-and-strict-timers.md), inspect
before/after revisions and choose operator recovery explicitly. No new automatic
repair/rollback/archive command is added. An operator restoring a verified backup
must preserve the damaged log for investigation. A software downgrade/revert must
retain logs; older clients can read Notes but cannot safely update runs.

The template is rechecked immediately before log commit. External editors do not
share its lock: there is no portable atomic transaction across template and log.
A source edit observed after commit is reported as blocked while retaining the
committed event; every later operation rechecks bindings. Recovery journals and
local actor IDs require the same privacy/access protections as the run log.

Run limits: 5,000 events per run, 50,000 per log, 32 MiB including UTF-8 BOM, and
2 MiB per event JSON. Persisted IDs are at most 256 characters. The log must be a
separate regular file: template aliases, hardlinks, symlink log targets,
generated/read-only destinations, malformed records, unknown schemas, duplicate
or missing sequence/digest/request IDs and actor/source mismatches are refused.
Run logs contain only closed single-line `procedure_event` records (comments are
allowed). There is no automatic rotation; keep complete active chains together.
At 20,000 journal entries, operator archival is required before more writes.

The exact [event contract](../../.ai/project/changes/procedure-guidance/procedure-event-v1.schema.json)
is stored with the change package. It is not a new generic Format/schema-catalog
entry. `event_data` contains a closed `procedure-event-v1` JSON envelope with a
canonical digest chain. It copies no title/body/secret/URL/command output or free
notes. Hash chaining detects accidental corruption, **not authenticated tamper-proof
audit or proof that real work occurred**. A valid prefix alone cannot prove that
trailing events were never removed; use trusted backup/journal evidence when
assessing completeness, and never invent missing events. Runtime also checks graph semantics,
valid calendar timestamps, guard counts and exact event ordering. Replay is
bounded by log/event/control-plan sizes; traversals use the bounded graph.

Web run controls, server-authenticated actor ownership, Remote/MCP access and
external action execution are not part of this stage. Web is the final planned PR;
arbitrary automatic action execution remains outside the Epic.

## Web definition browser (stage 3 read-only)

Start the usual local Web server with the definition file among its inputs:

```sh
python -m lifetxt serve examples/procedure-flow-en.txt
```

Open **More → Procedures / 手順書**, or `/procedures`. Select a definition to
read the hierarchy, plain-text instructions, incoming/outgoing transitions and
warnings. The flowchart links to the full step list. Up to 80 steps / 160 edges
are drawn as SVG; larger supported definitions use the complete text alternative
(up to 500 steps). The format selector shows the same Text/Mermaid/DOT as the CLI.
No external renderer, CDN, Markdown, URL action or instruction is executed.

The URL retains `source` (an opaque configured-source token), `id` (root ID) and
optional `lang=en|ja`. Reload obtains the current source revision. Source tokens
select only server-configured inputs; they are identifiers, not authorization or
anonymity guarantees. A record link uses the existing `/?id=...` route; duplicate
workspace IDs remain subject to the existing record route's ambiguity checks.
The source/root-specific procedure URL disambiguates definitions across files.

| GET route | Result |
| --- | --- |
| `/procedures` | Dedicated browser with desktop/mobile and keyboard text alternatives |
| `/api/procedures` | `procedure-catalog-v1`: roots, validity, warnings, opaque sources and unavailable sources |
| `/api/procedures/{source}/{root_id}` | `procedure-v1`: definition-only root/steps/edges, template revision, diagnostics and CLI renderings |

Existing Web Bearer authentication applies to all three routes when configured;
this page does not introduce a separate login or persist credentials. It follows
the same authenticated deployment arrangement as the existing Planner page.
Read-only servers can browse definitions. Invalid definitions fail closed (422),
unknown source tokens return 404, and unsafe methods are rejected (405, or the
existing read-only/auth guard's 403/401). No template, Task or procedure-event log
is written. Existing server startup metrics are independent of these GET routes.

Limits: 64 configured sources, 100 roots in the catalog, 1 MiB catalog JSON,
2 MiB detail JSON, and the existing 10 MiB source / 10,000 records / 500 steps /
2,000 edges / depth 32 admission bounds. Reduce configured inputs or split large
definitions on a limit error. Catalog sources with invalid syntax are shown as
unavailable; profile-invalid roots remain listed with diagnostics. Missing API
support displays a message and leaves the existing Items and Planner available.

Web run controls remain gated on owner decision W1 in the
[server actor/ownership proposal](../../.ai/project/changes/procedure-guidance/web-write-contract.md).
They are not included in this draft. After approval the same final PR will add
them; the existing explicit CLI run operations remain available now.
