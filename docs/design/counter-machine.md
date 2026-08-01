# Counter-Machine Design

Status: planned internal design specification.

This document defines the initial counter-machine runtime. The runtime is not
implemented yet. User-facing English and Japanese documentation stays on the
roadmap until the feature exists; this file is the internal specification that
implementation and review must use.

The optional runtime must not change the life.txt grammar or ordinary item
behavior. The first implementation is local, dependency-free, CLI-only,
read-only with respect to its input, deterministic, and limited to `inc`,
`decjz`, and `halt`.

Moved from `todo.md` by #56, as #51 Part 2.

## Destination Decision

The specification lives in `docs/design/counter-machine.md`, English only.

Rationale:

- The counter-machine is unimplemented behavior, so this is a design
  specification rather than user documentation.
- `docs/en/` and `docs/ja/` are for user-facing documentation. Placing the
  design there would create an English/Japanese parity obligation for behavior
  users cannot run.
- A top-level file beside the roadmap archive would make `docs/` a mixed bag of
  archival and active design material. A dedicated `docs/design/` location gives
  internal specifications a stable home.

## Principles

- Represent optional counter-machine data with normal Note records plus
  `machine:` details. Do not reuse Status (`S`) or Reminder (`R`) types for
  counters or instructions because those types already participate in presence
  and notification behavior.
- Keep the minimal computation runtime deterministic and side-effect free: no
  clock, randomness, network, subprocesses, parallel execution, implicit file
  discovery, or mutation of the input program.
- Treat unlimited execution as an explicit local CLI opt-in. Never make it the
  default or expose it automatically through Web, MCP, TUI, remote, integration,
  or automation surfaces.

The general parsing guarantee lives in `.ai/project/RULES.md`: normal life.txt
parsing stays permissive, and unknown custom keys remain valid. The
counter-machine-specific half of that split belongs here: machine validation and
machine-specific errors appear only when the user explicitly invokes machine
validation or execution.

## Record Model

- Represent every counter and instruction as a normal Note item using `[N] N`,
  not Status (`S`) or Reminder (`R`), so presence, reminder, agenda,
  notification, and command-center behavior is not triggered accidentally.
- Define counters as `[N] N TITLE id:ID machine:counter value:INTEGER`. Require
  exactly one `id`, `machine`, and `value`; require ASCII decimal digits only;
  reject signs, decimal/exponent/hex/underscore forms; require a non-negative
  value; and use arbitrary-precision integers with no language-level upper
  bound.
- Define instructions as
  `[N] N TITLE id:ID machine:instruction op:OPERATION ...`. Treat instruction
  IDs as jump labels and require exactly one scalar value for every operation
  field.
- Define `inc` as `op:inc target:COUNTER_ID next:NEXT_ID`; increment the target
  by one and move the program counter to `next` within the same in-memory step.
- Define `decjz` as
  `op:decjz target:COUNTER_ID zero:ZERO_ID nonzero:NONZERO_ID`; when the counter
  is zero, preserve its value and jump to `zero`; otherwise decrement once and
  jump to `nonzero` within the same in-memory step.
- Define `halt` as `op:halt` with no target/jump details. Count execution of
  `halt` as one step, set `last_instruction` to the halt ID, set
  `next_instruction` to `null`, and return `halted: true`.
- Use one input-wide ID namespace for counters, instructions, and other items
  visible to machine references. Reject duplicate IDs, including a counter and
  instruction sharing the same ID. Do not infer or create missing labels,
  counters, or jump targets.
- Preserve input definition order for counters in life and JSON output.
  Internal maps may optimize lookup but must not change deterministic
  serialization order.

## Validation and Diagnostics

- Implement `lifetxt/counter_machine_validator.py` to collect machine records
  and validate the complete program before executing any instruction.
- Define `C001` missing entry instruction, `C002` invalid counter value, `C003`
  unknown operation, `C004` missing required detail, `C005` missing target
  counter, `C006` missing target instruction, `C007` maximum step count
  exceeded, `C008` duplicate ID, `C009` repeated scalar detail, `C010` output
  resolves to the input file, `C011` invalid `machine:` record composition, and
  `C012` negative step limit.
- Require exactly one scalar value for `id`, `machine`, `value`, `op`, `target`,
  `next`, `zero`, and `nonzero` wherever applicable. Reject repeated values
  instead of applying first-value or last-value semantics.
- Reject operation-inapplicable details in strict machine validation, such as
  `target` on `halt`, `zero` on `inc`, or `next` on `decjz`, so typographical
  mistakes cannot be silently ignored.
- Report every deterministic pre-execution validation error that can safely be
  collected, ordered by source line, code, and item ID. Do not execute partially
  valid programs and do not auto-correct references.
- Keep machine-specific errors appearing only when the user explicitly invokes
  machine validation or execution.

## Runtime Semantics

- Implement `lifetxt/counter_machine.py` with immutable program definitions,
  mutable in-memory counter state, a current instruction ID, step count, and
  structured result. Keep parsing/validation separate from execution.
- Define the step-limit boundary precisely: before each instruction, if
  `max_steps > 0` and `steps >= max_steps`, do not execute the pending
  instruction; return `C007`, `halted: false`, the current counters, the last
  executed instruction or `null`, and the pending `next_instruction`. After a
  permitted instruction executes, increment `steps` once.
- Set the CLI default to `--max-steps 100000`. Interpret `--max-steps 0` as an
  explicit unlimited local mode, emit one fixed stderr warning, and document
  that a non-halting program may never return. Reject negative values as `C012`.
- Guarantee the same result for the same input bytes, entry ID, step limit, and
  output format. Prohibit time access, randomness, network access, subprocesses,
  environment-dependent branching, implicit file reads, writes during execution,
  and parallel instruction execution.
- Treat counter mutation and program-counter movement as indivisible within the
  single-threaded interpreter loop. Runtime failures must never expose a
  half-applied instruction state.
- Keep resource claims accurate: counters and step counts have no fixed
  language-level bound, but real execution remains limited by memory, process
  lifetime, and the optional step limit.

## CLI and Output

- Add `lifetxt run FILE --entry ID --max-steps N --format life|json -o FILE`
  through the unified CLI parser registry. Limit the initial command to these
  options plus normal global help/version behavior; do not add expressions,
  functions, tracing, includes, stdin programs, or mutation switches.
- Read exactly one explicit UTF-8 life.txt file through the normal parser. Do
  not load configured `paths`, workspace manifests, neighboring files, links,
  attachments, or generated sources.
- Default output to stdout. For `-o`, resolve input and output paths including
  aliases/symlinks and return `C010` if they identify the same file. Write a
  distinct output atomically; never modify the source program.
- Define JSON output as a stable object containing `halted`, nullable `code`,
  `steps`, `entry`, nullable `last_instruction`, nullable `next_instruction`,
  and ordered `counters`. Include the complete intermediate state on `C007`.
- Define life output as canonical `[N] N ... machine:counter value:...` records
  in original counter order. Require JSON for complete structured
  failure/interruption metadata; stderr may contain a fixed human-readable
  diagnostic.
- Use process exit code `0` only for normal halt, `1` for machine
  validation/runtime failure including `C007`, and `2` for CLI argument parsing
  failure. Keep process exit codes separate from `C001`-`C012`.
- Document that the initial release cannot resume automatically from an output
  state and never performs in-place counter updates. Checkpoints, resumption,
  traces, and mutation remain out of scope.

## Tests, Schemas, and Documentation

- Add the two-counter transfer sample and assert `a=0`, `b=3`, `halted=true`,
  and `steps=8` when `halt` counts as an instruction. Include zero-input and
  entry-at-halt cases.
- Test arbitrary-precision values, self-loops, finite-limit non-halting
  programs, unlimited-mode argument handling without an endless CI run,
  off-by-one step limits, missing and duplicate references, repeated scalar
  details, unknown operations, invalid decimal forms, and input/output path
  aliases.
- Test byte-identical output across repeated runs, supported Python versions,
  LF/CRLF input, unrelated ordinary Notes, input record order, different host
  clocks/timezones/locales, and hash-randomization seeds.
- Publish `counter-machine-result-v1.schema.json` plus representative success,
  validation-error, and `C007` instances. Validate real CLI JSON in tests and
  include schema/sample integrity in the release manifest.
- Add English/Japanese `counter-machine.md` documentation covering exact record
  forms, all three operations, diagnostics, step counting, output, safety
  boundaries, Turing-completeness assumptions, limitations, and complete
  examples.
- Add dependency-free tests for `counter_machine.py`,
  `counter_machine_validator.py`, and the CLI. Do not add Web, TUI, MCP,
  remote, integration, or automation execution tests because those surfaces are
  intentionally unsupported.

## Cross-Surface and Product-Boundary Rules

- Keep `lifetxt run FILE` independent from automatic workspace loading in its
  first release. The positional program file is the only input,
  `paths`/profiles/globs are ignored, and `-o` is the only result destination.
  Add a configurable default step limit only after demonstrated use; the initial
  CLI contract remains `100000`, with explicit `0` for unlimited local
  execution.
- Exclude `machine:counter` and `machine:instruction` Notes from project
  progress, health, workload, invoice, ticket, and command-center metrics unless
  a user explicitly queries those custom records.
- Keep counter-machine Note records outside ticket discovery and ticket field
  registries even when they use common detail names such as `id`, `target`, or
  `next`.
- Keep machine execution separate from ticket transitions, comments, audit
  history, time entries, timers, planning, and watcher notifications.
- Do not expose counter-machine execution through Remote CLI/TUI/Web. A future
  remote runtime requires independent CPU/time/memory/output quotas,
  cancellation, isolation, authentication, audit, and denial-of-service design.
- Keep machine execution unable to send messages or notifications; runtime
  warnings and diagnostics stay on the invoking CLI stdout/stderr or selected
  result file.
- Do not permit inbound messages, provider events, attachments, or automation
  mappings to execute counter-machine programs. `machine:` records remain inert
  until a local user explicitly invokes the CLI.
- Keep counter-machine examples and result files outside automatic ticket
  closure, CI action execution, and development-tool hooks unless a future
  explicit use case is separately designed and reviewed.
- Keep `machine:counter` and `machine:instruction` Notes out of default agenda,
  command-center attention, person/group work, project metrics, and automation
  triggers; allow explicit custom-detail queries and normal raw display.
- Keep runtime step counting in memory and independent from timers, work
  sessions, `elapsed:`, clock context, and notification watchers.
- Prove that counter-machine output is independent from host clock, timezone,
  locale, and hash-randomization seed; repeated runs with the same bytes, entry,
  step limit, and format must be byte-identical.
- Do not add a browser counter-machine runner as part of Web customization.

## Explicit Non-Goals

- Do not add arithmetic expressions, arbitrary comparisons, strings, general
  `if`, loop syntax, functions, subroutines, stacks, arrays, standard
  input/output instructions, file access, external commands, GUI/TUI execution,
  MCP execution, remote execution, or in-place source updates.
- Do not add debugger, trace, optimizer, compiler, macro, include, or alternate
  machine instructions until the three-operation runtime is implemented,
  documented, benchmarked, and proven useful.
- Do not describe Turing completeness as operational safety or practical
  performance. State that universality assumes at least two unbounded
  non-negative counters and unbounded execution steps, while real runs remain
  finite-resource processes.
