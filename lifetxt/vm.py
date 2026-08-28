"""lifetxt VM: an opt-in, Turing-complete execution model encoded in valid
life.txt records.

``life.txt`` Format 1.0 itself is not, and is not made, a programming
language. This module adds a separate, explicitly opt-in interpretation
layer on top of the existing parser: a handful of already-legal custom
detail keys (``value:``, ``op:``, ``var:``, ``next:``, ``zero:``,
``nonzero:``) are read as a program only when a caller explicitly builds and
runs one through this module. Every other command -- ``check``, ``agenda``,
``filter``, the Web API, MCP, the TUI -- parses the very same records as
ordinary items with unrecognized custom keys and never executes anything.

The instruction set is intentionally minimal: increment a non-negative
arbitrary-precision counter, or decrement-and-jump-if-zero. Combined with
:mod:`lifetxt`'s existing ``id:``-addressed control flow, two or more such
counters are enough to encode a 2-counter Minsky machine, which is
Turing-complete as a computation model -- see
`Minsky machines <https://en.wikipedia.org/wiki/Counter_machine>`_. The VM
has no filesystem, network, shell, ``eval``/``exec``, or plugin access: the
only state it can read or change is the program counter and the counters
declared in the program.

Two phases:

- :func:`build_program` scans already-parsed :class:`~lifetxt.model.Item`
  objects for VM records (anything carrying ``value:`` or ``op:``),
  constructs :class:`Counter`/instruction objects from them, and validates
  every VM-specific constraint the issue's acceptance criteria list --
  singleton details, known opcodes, resolvable ``var:``/``next:``/``zero:``/
  ``nonzero:`` references -- before returning.
- :func:`run_program` validates the requested entry id, then executes
  instructions against a fresh, in-memory runtime state (never written back
  to any file) until ``op:halt`` is reached or ``max_steps`` is exhausted.
"""

from __future__ import unicode_literals

import re
from collections import OrderedDict


class VMProgramError(ValueError):
    """A VM program failed validation, or execution reached an invalid state."""


class VMStepLimitExceeded(RuntimeError):
    """Execution reached ``max_steps`` without hitting ``op:halt``."""

    def __init__(self, max_steps, pc, state):
        self.max_steps = max_steps
        self.pc = pc
        self.state = OrderedDict(state)
        RuntimeError.__init__(
            self,
            "Step limit (%d) reached before HALT, at id %r; state: %s. "
            "Pass --max-steps 0 to run without a limit."
            % (max_steps, pc, _format_state(self.state)),
        )


#: Default bound on executed instructions. Chosen to be generous for small
#: hand-written or compiled programs while still failing loudly, quickly,
#: and deterministically on a non-terminating one by default.
DEFAULT_MAX_STEPS = 100000

_INTEGER_RE = re.compile(r"^-?[0-9]+$")


class Counter(object):
    """A VM counter declared by a ``value:`` record.

    ``initial_value`` is the value execution starts from; it is never read
    from or written back to the source file after :func:`build_program`
    returns.
    """

    __slots__ = ("id", "initial_value", "source", "line")

    def __init__(self, counter_id, initial_value, source=None, line=None):
        self.id = counter_id
        self.initial_value = initial_value
        self.source = source
        self.line = line


class IncInstruction(object):
    """``op:inc`` -- increment ``var`` by one, then jump to ``next``."""

    __slots__ = ("id", "var", "next", "source", "line")
    op = "inc"

    def __init__(self, instr_id, var, next_id, source=None, line=None):
        self.id = instr_id
        self.var = var
        self.next = next_id
        self.source = source
        self.line = line


class DecJzInstruction(object):
    """``op:dec_jz`` -- decrement ``var`` and jump to ``nonzero``, or jump
    to ``zero`` without decrementing when ``var`` is already zero."""

    __slots__ = ("id", "var", "nonzero", "zero", "source", "line")
    op = "dec_jz"

    def __init__(self, instr_id, var, nonzero, zero, source=None, line=None):
        self.id = instr_id
        self.var = var
        self.nonzero = nonzero
        self.zero = zero
        self.source = source
        self.line = line


class HaltInstruction(object):
    """``op:halt`` -- execution stops here."""

    __slots__ = ("id", "source", "line")
    op = "halt"

    def __init__(self, instr_id, source=None, line=None):
        self.id = instr_id
        self.source = source
        self.line = line


class VMProgram(object):
    """A validated VM program: its counters and instructions, by id."""

    __slots__ = ("counters", "instructions", "id_key")

    def __init__(self, counters, instructions, id_key):
        self.counters = counters
        self.instructions = instructions
        self.id_key = id_key


class VMResult(object):
    """The outcome of a completed (halted) VM run."""

    __slots__ = ("state", "steps", "pc")

    def __init__(self, state, steps, pc):
        self.state = state
        self.steps = steps
        self.pc = pc


def _location(source, line, fallback):
    if source:
        return "%s:%s" % (source, line if line is not None else "?")
    if line is not None:
        return "line %s" % line
    return fallback


def _format_state(state):
    return ", ".join("%s=%s" % (cid, value) for cid, value in state.items()) or "(none)"


def _require_single(values, key, where):
    if not values:
        raise VMProgramError("%s is missing required detail %r." % (where, key))
    if len(values) > 1:
        raise VMProgramError(
            "%s has %d values for %r; exactly one is required."
            % (where, len(values), key)
        )
    return values[0]


def build_program(items, id_key="id"):
    """Build and validate a :class:`VMProgram` from already-parsed items.

    Only items carrying a ``value:`` or ``op:`` detail are considered VM
    records; every other item (a normal Task, Note, Event, ...) is silently
    ignored, so a VM program file may freely mix VM records with ordinary
    life.txt content. Raises :class:`VMProgramError` describing the first
    problem found -- a missing/duplicate id, an unknown opcode, a missing
    required detail, a non-integer or negative counter value, or a
    transition (``var:``/``next:``/``zero:``/``nonzero:``) that does not
    resolve to a declared counter or instruction.
    """
    counters = OrderedDict()
    instructions = OrderedDict()
    defined_at = {}

    for item in items:
        details = item.details
        has_value = "value" in details
        has_op = "op" in details
        if not has_value and not has_op:
            continue
        where = _location(item.source, item.line, repr(item.title))
        if has_value and has_op:
            raise VMProgramError(
                "%s has both value: and op:; a VM record must be either a "
                "counter (value:) or an instruction (op:), not both." % where
            )

        record_id = _require_single(details.get(id_key), id_key, where)
        if record_id in defined_at:
            raise VMProgramError(
                "Duplicate VM id %r at %s (already defined at %s)."
                % (record_id, where, defined_at[record_id])
            )

        if has_value:
            raw_value = _require_single(details.get("value"), "value", where)
            if not _INTEGER_RE.match(raw_value.strip()):
                raise VMProgramError(
                    "Counter %r has a non-integer value: %r; expected a "
                    "decimal integer." % (record_id, raw_value)
                )
            value = int(raw_value)
            if value < 0:
                raise VMProgramError(
                    "Counter %r has a negative value: %r; counters must be "
                    "non-negative." % (record_id, raw_value)
                )
            counters[record_id] = Counter(
                record_id, value, source=item.source, line=item.line
            )
        else:
            op_value = _require_single(details.get("op"), "op", where)
            if op_value == "inc":
                var = _require_single(details.get("var"), "var", where)
                next_id = _require_single(details.get("next"), "next", where)
                instructions[record_id] = IncInstruction(
                    record_id, var, next_id, source=item.source, line=item.line
                )
            elif op_value == "dec_jz":
                var = _require_single(details.get("var"), "var", where)
                nonzero = _require_single(details.get("nonzero"), "nonzero", where)
                zero = _require_single(details.get("zero"), "zero", where)
                instructions[record_id] = DecJzInstruction(
                    record_id,
                    var,
                    nonzero,
                    zero,
                    source=item.source,
                    line=item.line,
                )
            elif op_value == "halt":
                instructions[record_id] = HaltInstruction(
                    record_id, source=item.source, line=item.line
                )
            else:
                raise VMProgramError(
                    "%s has unknown op %r; expected inc, dec_jz, or halt."
                    % (where, op_value)
                )

        defined_at[record_id] = where

    program = VMProgram(counters, instructions, id_key)
    _validate_transitions(program)
    return program


def _check_counter_ref(program, counter_id, instr, where):
    if counter_id not in program.counters:
        raise VMProgramError(
            "Instruction %r (%s) at %s references unknown counter %r via var:."
            % (instr.id, instr.op, where, counter_id)
        )


def _check_transition(program, target_id, field, instr, where):
    if target_id not in program.instructions:
        if target_id in program.counters:
            raise VMProgramError(
                "Instruction %r (%s) at %s has %s: %r, which is a counter, "
                "not an instruction." % (instr.id, instr.op, where, field, target_id)
            )
        raise VMProgramError(
            "Instruction %r (%s) at %s has %s: %r, which does not exist."
            % (instr.id, instr.op, where, field, target_id)
        )


def _validate_transitions(program):
    for instr in program.instructions.values():
        where = _location(instr.source, instr.line, "id %r" % instr.id)
        if isinstance(instr, IncInstruction):
            _check_counter_ref(program, instr.var, instr, where)
            _check_transition(program, instr.next, "next", instr, where)
        elif isinstance(instr, DecJzInstruction):
            _check_counter_ref(program, instr.var, instr, where)
            _check_transition(program, instr.nonzero, "nonzero", instr, where)
            _check_transition(program, instr.zero, "zero", instr, where)


def _check_entry(program, entry):
    """Validate that ``entry`` names a declared instruction in ``program``.

    Shared between :func:`run_program` (which requires a valid entry to
    execute from) and the optional ``entry`` highlight accepted by
    :func:`program_to_mermaid`/:func:`program_to_dot`, so both paths raise
    the identical, already-tested message for an unknown or counter-typed
    entry id.
    """
    if entry not in program.instructions:
        if entry in program.counters:
            raise VMProgramError(
                "Entry id %r refers to a counter, not an instruction." % entry
            )
        raise VMProgramError("Entry id %r does not exist." % entry)


def run_program(program, entry, max_steps=DEFAULT_MAX_STEPS):
    """Execute ``program`` starting at instruction ``entry``.

    ``max_steps`` bounds the number of executed (non-``halt``) instructions;
    ``0`` means unlimited, an explicit opt-in a caller must request
    deliberately. Raises :class:`VMProgramError` if ``entry`` does not name
    a declared instruction, or :class:`VMStepLimitExceeded` if the bound is
    reached before ``op:halt``. Runtime state is independent of any source
    file and is never written back.
    """
    if max_steps < 0:
        raise VMProgramError(
            "max_steps must be >= 0 (0 means unlimited); got %r." % (max_steps,)
        )
    _check_entry(program, entry)

    state = OrderedDict((cid, c.initial_value) for cid, c in program.counters.items())
    pc = entry
    steps = 0
    while True:
        instr = program.instructions[pc]
        if instr.op == "halt":
            return VMResult(state, steps, pc)
        if max_steps and steps >= max_steps:
            raise VMStepLimitExceeded(max_steps, pc, state)
        steps += 1
        if instr.op == "inc":
            state[instr.var] += 1
            pc = instr.next
        else:  # dec_jz
            if state[instr.var] == 0:
                pc = instr.zero
            else:
                state[instr.var] -= 1
                pc = instr.nonzero


def _instruction_label(instr):
    if isinstance(instr, IncInstruction):
        return "%s: inc %s" % (instr.id, instr.var)
    if isinstance(instr, DecJzInstruction):
        return "%s: dec_jz %s" % (instr.id, instr.var)
    return "%s: halt" % instr.id


def program_to_mermaid(program, entry=None):
    """Render ``program`` as a Mermaid ``graph LR`` control-flow diagram.

    One node is emitted per counter (stadium shape) and per instruction
    (rectangle), covering every declared counter/instruction regardless of
    reachability. Control-flow transitions (``next:``/``zero:``/``nonzero:``)
    are solid, labeled edges between instructions; each instruction's
    ``var:`` reference to the counter it reads/writes is a separate, dashed
    edge, so the two relations stay visually distinct. When ``entry`` is
    given, it is validated the same way :func:`run_program` validates it
    (raising :class:`VMProgramError` identically) and the matching node is
    marked with the ``entry`` CSS class.
    """
    from .links import _mermaid_node_id

    if entry is not None:
        _check_entry(program, entry)

    lines = ["graph LR"]
    if not program.counters and not program.instructions:
        lines.append("")
        return "\n".join(lines)

    for counter_id, counter in program.counters.items():
        node = _mermaid_node_id(counter_id)
        label = ("%s=%s" % (counter_id, counter.initial_value)).replace('"', "'")
        lines.append('    %s(["%s"])' % (node, label))
    for instr_id, instr in program.instructions.items():
        node = _mermaid_node_id(instr_id)
        label = _instruction_label(instr).replace('"', "'")
        entry_cls = ":::entry" if instr_id == entry else ""
        lines.append('    %s["%s"]%s' % (node, label, entry_cls))

    lines.append("")
    for instr_id, instr in program.instructions.items():
        node = _mermaid_node_id(instr_id)
        var_id = getattr(instr, "var", None)
        if var_id is not None:
            lines.append("    %s -. var .-> %s" % (node, _mermaid_node_id(var_id)))
        if isinstance(instr, IncInstruction):
            lines.append("    %s -- next --> %s" % (node, _mermaid_node_id(instr.next)))
        elif isinstance(instr, DecJzInstruction):
            lines.append(
                "    %s -- nonzero --> %s" % (node, _mermaid_node_id(instr.nonzero))
            )
            lines.append("    %s -- zero --> %s" % (node, _mermaid_node_id(instr.zero)))

    if entry is not None:
        lines.append("")
        lines.append("    classDef entry stroke-width:3px")

    lines.append("")
    return "\n".join(lines)


def program_to_dot(program, entry=None):
    """Render ``program`` as a Graphviz DOT digraph.

    Mirrors :func:`program_to_mermaid`'s node/edge model: counters are
    ``shape=ellipse``, instructions are ``shape=box``, control-flow
    transitions are solid labeled edges, and each instruction's ``var:``
    reference is a separate dashed edge. ``entry`` is validated identically
    to :func:`run_program` and rendered with ``peripheries=2``.
    """
    from .links import _dot_quote

    if entry is not None:
        _check_entry(program, entry)

    lines = ["digraph vm {"]
    for counter_id, counter in program.counters.items():
        attrs = "shape=ellipse, label=%s" % _dot_quote(
            "%s=%s" % (counter_id, counter.initial_value)
        )
        lines.append("    %s [%s];" % (_dot_quote(counter_id), attrs))
    for instr_id, instr in program.instructions.items():
        attrs = "shape=box, label=%s" % _dot_quote(_instruction_label(instr))
        if instr_id == entry:
            attrs += ", peripheries=2"
        lines.append("    %s [%s];" % (_dot_quote(instr_id), attrs))

    for instr_id, instr in program.instructions.items():
        var_id = getattr(instr, "var", None)
        if var_id is not None:
            lines.append(
                "    %s -> %s [style=dashed, label=var];"
                % (_dot_quote(instr_id), _dot_quote(var_id))
            )
        if isinstance(instr, IncInstruction):
            lines.append(
                "    %s -> %s [label=next];"
                % (_dot_quote(instr_id), _dot_quote(instr.next))
            )
        elif isinstance(instr, DecJzInstruction):
            lines.append(
                "    %s -> %s [label=nonzero];"
                % (_dot_quote(instr_id), _dot_quote(instr.nonzero))
            )
            lines.append(
                "    %s -> %s [label=zero];"
                % (_dot_quote(instr_id), _dot_quote(instr.zero))
            )

    lines.append("}")
    lines.append("")
    return "\n".join(lines)
