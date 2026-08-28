# lifetxt VM (opt-in Turing-complete execution model)

`lifetxt vm run` interprets a small, already-legal subset of `life.txt`
custom keys as a 2-counter Minsky machine: an arbitrary-precision counter
machine that is Turing-complete as a computation model. It exists as an
independent, experimental extension, not as a core lifetxt use case.

> `life.txt` Format 1.0 itself is not a programming language. `lifetxt vm`
> is an opt-in Turing-complete execution model encoded using valid
> `life.txt` records.

## Why this is safe to add

Format 1.0 already tolerates unknown custom detail keys: the parser keeps
them in `Item.details` and `check` reports them as non-blocking style
warnings (`W106`), never errors. `lifetxt vm` adds no new grammar. It reads
`value:`, `op:`, `var:`, `next:`, `zero:`, and `nonzero:` -- ordinary custom
keys -- as instructions only when a caller explicitly builds and runs a
program through this module.

**No other command executes VM records.** `check`, `agenda`, `filter`,
`search`, the Web API, MCP, and the TUI all parse the same file as ordinary
items with unrecognized custom keys. Execution is reachable only through
`lifetxt vm run`.

## Usage

```console
$ lifetxt vm run program.life.txt --entry s1
HALT after 7 steps
x=0
y=3

$ lifetxt vm run program.life.txt --entry s1 --json
{
  "halted": true,
  "entry": "s1",
  "steps": 7,
  "state": {
    "x": 0,
    "y": 3
  }
}
```

| Option | Meaning |
|---|---|
| `path ...` | One or more life.txt files, or `-` for stdin. VM records may be freely mixed with ordinary Task/Event/Note/... content; only records carrying `value:` or `op:` are read as part of the program. |
| `--entry ID` | Required. The `id:` of the instruction to start execution at. |
| `--max-steps N` | Bound on executed instructions before failing loudly instead of looping forever. Default `100000`. `0` means unlimited -- an explicit opt-in. |
| `--json` | Emit the final state as JSON instead of text. |

Exit code `0` means the program halted within the step limit. A non-zero
exit means validation failed, the step limit was reached before `HALT`, or
execution was interrupted with `Ctrl+C`.

## Instruction set (v0)

Three instructions, addressed by the existing `id:` key:

```text
INC(var, next)
DEC_JZ(var, nonzero, zero)
HALT
```

### Counter

```life.txt
[N] N Counter_X id:x value:3
```

`value:` is the counter's value when execution *starts*. Execution state
lives only in memory; `lifetxt vm run` never writes back to the source
file. Required: one `id:`, one `value:` that is a non-negative decimal
integer (arbitrary precision -- no fixed bit width).

### `INC`

```life.txt
[N] N Increment_Y id:s2 op:inc var:y next:s1
```

```text
state[y] = state[y] + 1
pc = s1
```

Required: `id:`, `op:inc`, `var:`, `next:`.

### `DEC_JZ`

```life.txt
[N] N Check_X id:s1 op:dec_jz var:x nonzero:s2 zero:halt
```

```text
if state[x] == 0:
    pc = halt
else:
    state[x] = state[x] - 1
    pc = s2
```

Required: `id:`, `op:dec_jz`, `var:`, `nonzero:`, `zero:`.

### `HALT`

```life.txt
[N] N Halt id:halt op:halt
```

Execution stops. Required: `id:`, `op:halt`.

## Control flow

`next:`, `zero:`, and `nonzero:` each name the `id:` of another instruction
in the same program. There is no separate address space: the existing
`id:`/reference mechanism `lifetxt links` already understands is reused
directly as the VM's control-flow graph.

## Visualizing a program: `lifetxt vm graph`

`lifetxt vm graph` renders a validated program's counters and instructions
as a directed graph, reusing the same node-id sanitization and quoting
primitives `lifetxt links --format mermaid|dot` already uses:

```console
$ lifetxt vm graph program.life.txt --entry s1
graph LR
    x(["x=3"])
    y(["y=0"])
    s1["s1: dec_jz x"]:::entry
    s2["s2: inc y"]
    halt["halt: halt"]

    s1 -. var .-> x
    s1 -- nonzero --> s2
    s1 -- zero --> halt
    s2 -. var .-> y
    s2 -- next --> s1

    classDef entry stroke-width:3px

$ lifetxt vm graph program.life.txt --format dot
digraph vm {
    x [shape=ellipse, label="x=3"];
    ...
}
```

| Option | Meaning |
|---|---|
| `path ...` | One or more life.txt files, or `-` for stdin. Same input handling as `vm run`. |
| `--entry ID` | Optional. When given, the matching instruction node is highlighted (`:::entry` in mermaid, `peripheries=2` in dot) and validated the same way `vm run --entry` is -- an unknown or counter-typed id fails loudly. |
| `--format {mermaid,dot}` | Output format. Defaults to `mermaid`. |

Every declared counter and instruction is rendered, whether or not it is
reachable from `--entry` -- this is a static export over the validated
program, never `vm run`'s execution. Counters use a stadium node shape
(`(["..."])` in mermaid, `shape=ellipse` in dot) and instructions use a
rectangle (`["..."]` / `shape=box`), so the two kinds stay visually
distinct. Two edge kinds are drawn: solid, labeled `next:`/`zero:`/
`nonzero:` control-flow transitions between instructions, and a separate
dashed `var:` edge from each instruction to the counter it reads or writes.
A program that fails `vm run`'s own validation fails identically here,
before anything is rendered.

## Worked example: move X into Y

```life.txt
[N] N Counter_X id:x value:3
[N] N Counter_Y id:y value:0

[N] N Check_X id:s1 op:dec_jz var:x nonzero:s2 zero:halt
[N] N Increment_Y id:s2 op:inc var:y next:s1

[N] N Halt id:halt op:halt
```

```console
$ lifetxt vm run program.life.txt --entry s1
HALT after 7 steps
x=0
y=3
```

Each pass through `s1` -- whether it takes the zero or the nonzero branch --
counts as one executed instruction, which is why 3 decrements plus 3
increments plus one final zero-check total 7 steps.

## Validation before execution

`lifetxt vm run` validates the whole program before any instruction runs,
separately from the normal lifetxt validator's custom-key policy. It
rejects, among other things:

- an `--entry` id that does not exist, or that names a counter instead of
  an instruction
- a VM record with no `id:`, or more than one value for a detail that must
  be singleton (`id:`, `value:`, `op:`, `var:`, `next:`, `zero:`, `nonzero:`)
- a record carrying both `value:` and `op:` (a record must be exactly one
  of "counter" or "instruction")
- a duplicate `id:` across counters and instructions
- an unknown `op:` value
- `op:inc` missing `var:` or `next:`; `op:dec_jz` missing `var:`,
  `nonzero:`, or `zero:`
- `var:` naming a counter that was never declared
- `next:`/`zero:`/`nonzero:` naming an id that does not exist, or that
  names a counter rather than an instruction
- a `value:` that is not a non-negative decimal integer

Every failure is reported as `ERROR: ...` on stderr with a non-zero exit
code and no execution attempted.

## Non-termination

The instruction set is Turing-complete, so a program can fail to halt.
`--max-steps` (default `100000`) bounds how many instructions run before
`lifetxt vm run` fails loudly with the step count and the state at that
point, rather than running forever. Pass `--max-steps 0` to opt in to
unlimited execution explicitly; `Ctrl+C` interrupts a run at any time.

## Safety boundary

The VM has no side effects beyond its own in-memory program counter and
counter state. It cannot:

- read or write the filesystem
- run a shell command or start a process
- access the network
- call Python `eval`/`exec`
- read environment variables
- call MCP, the Web API, or any plugin
- modify `life.txt` itself

## Out of scope for v0

`if`/`while`/`for`, functions, a call stack, arithmetic beyond `INC`/
`DEC_JZ`, general expression syntax, I/O instructions, state persistence,
a source-code compiler, and Web/TUI/MCP execution are all deliberately
not implemented. Future, separate issues may add `lifetxt vm check`,
single-step tracing, JSON state output, or a Brainfuck-to-lifetxt-VM
compiler as a demonstration of Turing-completeness -- none of that is part
of v0.
