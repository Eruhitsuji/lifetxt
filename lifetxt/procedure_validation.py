"""Strict opt-in profile and graph validation, separate from generic check."""

from collections import deque
from dataclasses import dataclass
import re

from .ids import id_value_is_safe
from .procedure_definition import (
    ProcedureDiagnostic,
    ProcedureError,
    ProcedureProjection,
)

MAX_EDGES = 2_000
MAX_CHOICES = 16
MAX_HOPS = 1_000
MAX_VISITS = 20
_CHOICE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_KEYS = {
    "proc_role",
    "proc_version",
    "proc_start",
    "proc_kind",
    "proc_next",
    "proc_case",
}


@dataclass(frozen=True)
class ProcedureEdge:
    source: str
    target: str
    label: str


@dataclass(frozen=True)
class ValidatedProcedure:
    projection: ProcedureProjection
    start: str
    edges: tuple[ProcedureEdge, ...]
    step_kinds: tuple[tuple[str, str], ...]
    diagnostics: tuple[ProcedureDiagnostic, ...]
    cyclic: bool


def _walk(start, adjacency):
    found, pending = set(), list(start)
    while pending:
        node = pending.pop()
        if node not in found:
            found.add(node)
            pending.extend(adjacency.get(node, ()))
    return found


def validate_definition(projection):
    """Return an immutable graph only when every reachable step can reach an end."""
    errors, edges, kinds = [], [], []
    root = projection.root

    def error(code, message, node):
        errors.append(ProcedureDiagnostic(code, message, node.line, source=node.source))

    def single(node, key, allowed=None):
        values = node.values(key)
        if len(values) != 1 or (allowed is not None and values[0] not in allowed):
            error(
                "PG101",
                "%s requires exactly one valid %s." % (repr(node.id), key),
                node,
            )
            return None
        return values[0]

    for node in (root,) + projection.steps:
        unknown = {key for key, _ in node.details if key.startswith("proc_")} - _KEYS
        if unknown:
            error("PG102", "Unknown procedure fields: %r." % sorted(unknown), node)
        if node is root:
            permitted = {"proc_role", "proc_version", "proc_start"}
        else:
            permitted = {"proc_role", "proc_kind", "proc_next", "proc_case"}
        if any(
            key.startswith("proc_") and key not in permitted for key, _ in node.details
        ):
            error("PG103", "Procedure field belongs to a different record role.", node)
    single(root, "proc_role", {"root"})
    single(root, "proc_version", {"1"})
    start = single(root, "proc_start")
    for node in projection.steps:
        single(node, "proc_role", {"step"})
        kind = single(node, "proc_kind", {"action", "decision", "end"})
        if kind is None:
            continue
        kinds.append((node.id, kind))
        next_values, cases = node.values("proc_next"), node.values("proc_case")
        if (kind != "action" and next_values) or (kind != "decision" and cases):
            error(
                "PG104",
                "proc_next belongs to action; proc_case belongs to decision.",
                node,
            )
        if kind == "action":
            target = single(node, "proc_next")
            if target is not None:
                edges.append(ProcedureEdge(node.id, target, "next"))
        elif kind == "decision":
            if not 2 <= len(cases) <= MAX_CHOICES:
                error("PG105", "Decision requires 2–%d choices." % MAX_CHOICES, node)
            labels = set()
            for value in cases[:MAX_CHOICES]:
                label, separator, target = value.partition("=")
                if (
                    not separator
                    or not _CHOICE.fullmatch(label)
                    or not id_value_is_safe(target)
                ):
                    error(
                        "PG106", "Invalid choice %r; use label=STEP_ID." % value, node
                    )
                    continue
                if label in labels:
                    error("PG107", "Duplicate choice label %r." % label, node)
                labels.add(label)
                edges.append(ProcedureEdge(node.id, target, label))
    if len(edges) > MAX_EDGES:
        error("PG108", "Procedure exceeds %d edges." % MAX_EDGES, root)
    nodes = {node.id: node for node in projection.steps}
    if start not in nodes:
        error("PG109", "Start must name a step in the selected root.", root)
    for edge in edges:
        if edge.target not in nodes or not id_value_is_safe(edge.target):
            error(
                "PG110",
                "Target %r must name a step in the selected root." % edge.target,
                nodes[edge.source],
            )
    if errors:
        raise ProcedureError(errors)

    adjacency = {ident: [] for ident in nodes}
    reverse = {ident: [] for ident in nodes}
    indegree = {ident: 0 for ident in nodes}
    for edge in edges:
        adjacency[edge.source].append(edge.target)
        reverse[edge.target].append(edge.source)
        indegree[edge.target] += 1
    reachable = _walk([start], adjacency)
    terminating = _walk([ident for ident, kind in kinds if kind == "end"], reverse)
    for node in projection.steps:
        if node.id not in reachable:
            error("PG111", "Step %r is unreachable from start." % node.id, node)
        elif node.id not in terminating:
            error("PG112", "Step %r has no route to an end." % node.id, node)
    if errors:
        raise ProcedureError(errors)
    # Kahn's algorithm detects cycles without recursion; parallel choice edges
    # are counted separately so a decision with a shared target is not a cycle.
    ready = deque(ident for ident, count in indegree.items() if count == 0)
    removed = 0
    while ready:
        ident = ready.popleft()
        removed += 1
        for target in adjacency[ident]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    cyclic = removed != len(nodes)
    warnings = ()
    if cyclic:
        warnings = (
            ProcedureDiagnostic(
                "PG201",
                "Cycle with an exit: execution requires explicit acknowledgement; limits are %d hops / %d visits per step."
                % (MAX_HOPS, MAX_VISITS),
                root.line,
                "warning",
                root.source,
            ),
        )
    return ValidatedProcedure(
        projection, start, tuple(edges), tuple(kinds), warnings, cyclic
    )
