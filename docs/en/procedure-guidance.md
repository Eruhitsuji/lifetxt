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
browsing; future runs require explicit acknowledgement and finite guards.

Generic `check` still treats `proc_*` as custom fields and reports W106; it does
not validate procedure semantics. `--warnings-as-errors` therefore rejects the
opt-in example. Generic serialization preserves these fields. `links`, `flow`,
`vm`, `depends_on`, `follows` and ordinary `next` retain their existing meanings.

Limits: 10 MiB / 10,000 records per file, 500 selected steps, 2,000 edges,
parent depth 32, 64 KiB body per record and 2 MiB rendered output. Outputs escape
authored control characters; diagram nodes use independent local IDs to avoid
name collisions. An exact source-byte SHA-256 is retained internally; there is
no public JSON projection/schema or run command in this stage.

The [approved design](procedure-guidance-design.md) describes planned run/event/
CAS and Web behavior. Those later stages are not implemented by these commands.
