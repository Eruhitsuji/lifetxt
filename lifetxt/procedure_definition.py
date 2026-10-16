"""Bounded, immutable, opt-in procedure projection. No execution or writes."""

from dataclasses import dataclass

from .ids import id_value_is_safe
from .links import build_id_index

MAX_RECORDS = 10_000
MAX_STEPS = 500
MAX_DEPTH = 32
MAX_BODY_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ProcedureDiagnostic:
    code: str
    message: str
    line: int = 0
    severity: str = "error"
    source: str = ""

    def format(self):
        # repr prevents definition text from injecting terminal control sequences.
        return "%s %s line %s: %s" % (
            self.severity.upper(),
            self.code,
            self.line,
            self.message,
        )


class ProcedureError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = tuple(
            sorted(diagnostics, key=lambda row: (row.line, row.code, row.message))
        )
        super().__init__("\n".join(row.format() for row in self.diagnostics))


@dataclass(frozen=True)
class ProcedureNode:
    id: str
    title: str
    status: str
    kind: str
    body: tuple[str, ...]
    parent: str | None
    depth: int
    line: int
    source: str
    details: tuple[tuple[str, tuple[str, ...]], ...]

    def values(self, key):
        return next((values for name, values in self.details if name == key), ())


@dataclass(frozen=True)
class ProcedureProjection:
    root: ProcedureNode
    steps: tuple[ProcedureNode, ...]
    source: str
    template_revision: str
    version: str = "projection-v1"


def _values(item, key):
    return tuple(item.details.get(key, ()))


def _node(item, depth, source):
    return ProcedureNode(
        id=_values(item, "id")[0],
        title=item.title,
        status=item.status,
        kind=item.kind,
        body=_values(item, "body"),
        parent=next(iter(_values(item, "parent")), None),
        depth=depth,
        line=int(item.line or 0),
        source=source,
        details=tuple((key, tuple(values)) for key, values in item.details.items()),
    )


def project_definition(items, root_id, *, source="", template_revision="", id_key="id"):
    """Select one same-source root, retaining input order and explicit hierarchy.

    Branch semantics are validated separately by procedure_validation. No Item is
    mutated. Other well-formed roots are not included in the selected projection.
    """
    errors = []

    def error(code, message, item=None):
        errors.append(
            ProcedureDiagnostic(
                code, message, int(item.line or 0) if item else 0, source=source
            )
        )

    if id_key != "id":
        error(
            "PG001",
            "Procedure v1 requires canonical id; alternate id-key is unsupported.",
        )
    if len(items) > MAX_RECORDS:
        error("PG002", "Input exceeds %d records." % MAX_RECORDS)
    if errors:
        raise ProcedureError(errors)
    # In-memory callers must also provide one source, not merge workspace items.
    sources = {str(value) for item in items for value in _values(item, "_source_file")}
    sources.update(str(item.source) for item in items if getattr(item, "source", None))
    if len(sources) > 1:
        error("PG003", "Procedure v1 requires one source file.")
    index = build_id_index(items)
    for ident, owners in index.items():
        if len(owners) > 1:
            error("PG004", "Ambiguous id %r." % ident, owners[0])
    roots = index.get(root_id, ())
    if len(roots) != 1 or _values(roots[0], "proc_role") != ("root",):
        error("PG005", "Select exactly one explicit proc_role:root by id %r." % root_id)
    if errors:
        raise ProcedureError(errors)
    root = roots[0]
    if _values(root, "parent"):
        error("PG006", "Procedure root must not have a parent.", root)

    selected = []
    for item in items:
        role = _values(item, "proc_role")
        if not role or item is root:
            continue
        # Walk only the parent hierarchy, never relation or procedure edges.
        current, seen, depth = item, set(), 0
        while current is not root:
            if id(current) in seen:
                error("PG007", "Cyclic parent hierarchy.", item)
                break
            seen.add(id(current))
            current_role = _values(current, "proc_role")
            if current_role == ("root",):
                break  # belongs to another root
            if current_role != ("step",):
                error("PG008", "Expected proc_role:step in parent hierarchy.", item)
                break
            parents = _values(current, "parent")
            if len(parents) != 1 or len(index.get(parents[0], ())) != 1:
                error("PG009", "Step requires one unambiguous same-file parent.", item)
                break
            current = index[parents[0]][0]
            depth += 1
            if depth > MAX_DEPTH:
                error("PG010", "Parent depth exceeds %d." % MAX_DEPTH, item)
                break
        else:
            selected.append((item, depth))

    if not selected:
        error("PG011", "Selected procedure has no steps.", root)
    if len(selected) > MAX_STEPS:
        error("PG012", "Selected procedure exceeds %d steps." % MAX_STEPS, root)
    for item, _ in [(root, 0)] + selected:
        ids = _values(item, "id")
        if len(ids) != 1 or not id_value_is_safe(ids[0]):
            error(
                "PG013",
                "Procedure records require exactly one safe canonical id.",
                item,
            )
        if item.status != "[N]" or item.kind != "N":
            error("PG014", "Procedure definitions require [N] N records.", item)
        body = _values(item, "body")
        if sum(len(value.encode("utf-8")) for value in body) > MAX_BODY_BYTES:
            error("PG015", "Body exceeds %d bytes." % MAX_BODY_BYTES, item)
    if errors:
        raise ProcedureError(errors)
    return ProcedureProjection(
        _node(root, 0, source),
        tuple(_node(item, depth, source) for item, depth in selected),
        source,
        template_revision,
    )
