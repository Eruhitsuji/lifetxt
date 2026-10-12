# Counter-Machine Design: Current VM and Historical Proposal

Status: current implementation guide with a retained historical proposal.

The optional computation runtime was implemented by
[#560](https://github.com/Eruhitsuji/lifetxt/issues/560). It is an experimental
interpretation of already-valid custom life.txt details, not a change to
Format 1.0 or a core task-management requirement.

The user contracts are [English VM documentation](../en/vm.md) and
[Japanese VM documentation](../ja/vm.md). Behavior is implemented in
[lifetxt/vm.py](../../lifetxt/vm.py) and the `vm` CLI in
[lifetxt/cli.py](../../lifetxt/cli.py). Do not implement or review against the
superseded proposal as though it were the current specification.

## Historical Proposal

The [pre-VM design](archive/counter-machine-pre-vm.md) is preserved unchanged
from commit `c989a16b505ffe369f57d55928d31a60392c92f6`. It originated in #56
after #51 separated roadmap ideas from rules. Its "not implemented yet" text,
planned module names, diagnostics, syntax, output contracts, and strict
validation guarantees are historical proposals, not current promises.

Relative references in that raw snapshot retain their historical spelling;
use [the original at the fixed commit](https://github.com/Eruhitsuji/lifetxt/blob/c989a16b505ffe369f57d55928d31a60392c92f6/docs/design/counter-machine.md)
for their original context. Adopting a missing part of that proposal requires
a separately scoped issue and decision.

## Implemented Contract

| Area | Current implementation |
| --- | --- |
| Entry points | `lifetxt vm run` executes; `lifetxt vm graph` exports a static Mermaid/DOT graph without executing. |
| Record discovery | Only records carrying `value:` or `op:` are interpreted by `build_program`; `machine:` is not a selector. Note records remain the recommended examples, not a VM-enforced item-type restriction. |
| Counters | `id:x value:3`; non-negative arbitrary-precision decimal integer state. |
| Instructions | `op:inc var:x next:ID`; `op:dec_jz var:x nonzero:ID zero:ID`; `op:halt`. |
| Input | Shared CLI parsing/path/configuration resolution, supporting multiple paths and `-` for stdin. With no positional paths, normal configured/default source resolution applies, finally falling back to `life.txt`. This is not the old single-explicit-file contract. |
| Entry | Required `--entry ID` for run; optional validated entry highlight for graph. The ID key is resolved from configuration. |
| Limit | Default `--max-steps 100000`; `0` explicitly requests unlimited local execution; negative values fail. No fixed stderr warning is promised for unlimited mode. |
| Step counting | Every `inc` or `dec_jz` counts once, including the zero branch. `halt` counts zero and is checked before the limit. |
| Run output | Text state on stdout, or `--json` with `halted`, `entry`, `steps`, and `state` after a successful halt. No run `--format life\|json` or `-o` option. |
| Failure | `ERROR: ...` on stderr; validation/step-limit failures return 1. CLI parsing failures use the normal argument-parser exit. Interrupted execution returns 130. |
| Validation | `build_program` validates recognized records and transitions; entry is checked before execution. It reports the first VM problem, not a collected `C001`–`C012` diagnostic bundle. |
| Mutation | Runtime counters live only in memory. The source program is never updated by execution. |

A transfer program with initial `x=3`, `y=0` takes **7 steps**, finishes with
`x=0`, `y=3`, and emits the JSON state when `--json` is selected. An
entry-at-halt program finishes with zero steps.

## Validation Boundaries

The implementation checks singleton values for the fields it consumes, rejects
`value:` combined with `op:`, rejects duplicate IDs among recognized VM
records, validates opcodes/counter values/references, and validates the entry.
It does not promise that every extra operation-inapplicable detail is rejected,
that ordinary non-VM item IDs share the VM uniqueness check, or that machine
records are automatically excluded from every other report.

Ordinary parsing stays permissive. Only explicit VM commands interpret the
custom details as a program. A normal `check` is not an implicit machine
validator and no normal Task, Event, Note, Web, TUI, or MCP operation executes
these records.

## Safety and Non-Goals

The interpreter has no I/O instructions, clock, randomness, network, shell,
plugin, or in-place source mutation. Input loading belongs to the invoking CLI;
the execution loop operates only on the validated in-memory program.

Turing completeness assumes at least two unbounded non-negative counters and
unbounded computation steps. Real runs still consume finite CPU and memory.
The step limit is not a memory quota or a remote execution isolation boundary.

Execution remains opt-in, local, and CLI-only. Tracing, checkpoints, resumption,
alternate instructions, macros, compilation, and Web/TUI/MCP/Remote execution
remain separate proposals. Static `vm graph` export and successful-run JSON
state are already implemented and must not be listed as future features.

## Verification and Traceability

- Requirement: `req-vm-design-documentation-consistency`.
- Capability: `cap-lifetxt-vm`.
- Investigation: #1269; documentation task:
  [#1272](https://github.com/Eruhitsuji/lifetxt/issues/1272).
- Existing evidence: [VM tests](../../tests/test_vm.py) and
  [VM CLI tests](../../tests/test_vm_cli.py), including step-limit boundaries,
  successful JSON output, graph export, and inert normal check.
- This update aligns documentation; it introduces no runtime behavior.
