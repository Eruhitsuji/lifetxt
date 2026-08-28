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
    if entry not in program.instructions:
        if entry in program.counters:
            raise VMProgramError(
                "Entry id %r refers to a counter, not an instruction." % entry
            )
        raise VMProgramError("Entry id %r does not exist." % entry)

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
