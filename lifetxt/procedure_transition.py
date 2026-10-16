"""Pure, bounded human transitions. No clock, files, commands or network."""

from dataclasses import dataclass, replace

from .procedure_definition import ProcedureDiagnostic, ProcedureError
from .procedure_validation import (
    MAX_HOPS,
    MAX_VISITS,
    ValidatedProcedure,
    validate_definition,
)


def refuse(code, message):
    raise ProcedureError([ProcedureDiagnostic(code, message)])


@dataclass(frozen=True)
class Cursor:
    step: str
    status: str
    hops: int
    visits: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Transition:
    cursor: Cursor
    from_step: str
    to_step: str
    choice: str | None
    version: str = "transition-v1"


def checked_graph(graph):
    if not isinstance(graph, ValidatedProcedure):
        refuse("PR101", "A validated procedure graph is required.")
    checked = validate_definition(graph.projection)
    if checked != graph:
        refuse("PR101", "Graph differs from its validated definition.")
    return checked


def initial_cursor(graph, allow_loops=False):
    checked_graph(graph)
    if type(allow_loops) is not bool or (graph.cyclic and not allow_loops):
        refuse(
            "PR102", "Cyclic procedures require explicit --allow-loops acknowledgement."
        )
    return Cursor(graph.start, "active", 0, ((graph.start, 1),))


def advance(graph, cursor, operation, *, choice=None, template_revision=None):
    """Validate caller inputs, then decide exactly one explicit operation."""
    checked_graph(graph)
    if not isinstance(cursor, Cursor):
        refuse("PR103", "A valid run cursor is required.")
    counts = dict(cursor.visits)
    if (
        cursor.status not in {"active", "paused", "completed", "abandoned"}
        or type(cursor.hops) is not int
        or not 0 <= cursor.hops <= MAX_HOPS
        or len(counts) != len(cursor.visits)
        or cursor.step not in counts
        or any(
            k not in dict(graph.step_kinds)
            or type(v) is not int
            or not 1 <= v <= MAX_VISITS
            for k, v in counts.items()
        )
        or sum(counts.values()) != cursor.hops + 1
    ):
        refuse("PR103", "Invalid run cursor or guard counters.")
    return _advance(
        graph, cursor, operation, choice=choice, template_revision=template_revision
    )


def _advance(graph, cursor, operation, *, choice=None, template_revision=None):
    """Reducer-only fast path: graph/cursor were already validated."""
    if template_revision != graph.projection.template_revision and operation not in {
        "pause",
        "abandon",
    }:
        refuse(
            "PR104",
            "Template revision changed; inspect or explicitly abandon the original run.",
        )
    if cursor.status in {"completed", "abandoned"}:
        refuse("PR105", "Terminal runs are read-only.")
    if operation != "choose" and choice is not None:
        refuse("PR106", "A choice is allowed only with choose.")
    if operation == "abandon":
        result = replace(cursor, status="abandoned")
    elif operation == "pause" and cursor.status == "active":
        result = replace(cursor, status="paused")
    elif operation == "resume" and cursor.status == "paused":
        result = replace(cursor, status="active")
    elif cursor.status != "active":
        refuse(
            "PR107", "This operation requires an active run (or resume from paused)."
        )
    else:
        kind = dict(graph.step_kinds)[cursor.step]
        if operation == "finish" and kind == "end":
            result = replace(cursor, status="completed")
        elif (operation == "next" and kind == "action") or (
            operation == "choose" and kind == "decision"
        ):
            label = "next" if operation == "next" else choice
            targets = [
                edge.target
                for edge in graph.edges
                if edge.source == cursor.step and edge.label == label
            ]
            if len(targets) != 1:
                refuse(
                    "PR108",
                    "Choose one exact, case-sensitive choice token; no default is selected.",
                )
            target = targets[0]
            counts = dict(cursor.visits)
            if cursor.hops >= MAX_HOPS or counts.get(target, 0) >= MAX_VISITS:
                refuse(
                    "PR109", "Run traversal limit reached; inspect, pause or abandon."
                )
            counts[target] = counts.get(target, 0) + 1
            result = Cursor(target, "active", cursor.hops + 1, tuple(counts.items()))
        else:
            refuse("PR110", "Operation does not match the current step kind/state.")
    return Transition(result, cursor.step, result.step, choice)
