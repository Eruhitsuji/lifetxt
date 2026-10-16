"""Deterministic, escaped procedure renderers. Output never executes a step."""

import unicodedata

from .links import _dot_quote
from .procedure_definition import ProcedureDiagnostic, ProcedureError

MAX_OUTPUT_BYTES = 2 * 1024 * 1024


def console_text(value):
    """Display control characters literally, not as terminal escape sequences."""
    return "".join(
        ("\\u%04x" % ord(char)) if unicodedata.category(char).startswith("C") else char
        for char in str(value)
    )


def _mermaid_label(value):
    # Mermaid supports decimal entities (#34;); escape punctuation including
    # ampersand/hash/backslash/brackets so user text never becomes a directive.
    return "".join(
        char if char.isalnum() or char == " " else "#%d;" % ord(char)
        for char in console_text(value)
    )


def _bounded(text):
    if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ProcedureError(
            [
                ProcedureDiagnostic(
                    "PG301", "Procedure output exceeds %d bytes." % MAX_OUTPUT_BYTES
                )
            ]
        )
    return text


def render_procedure(graph, output_format="text", *, include_body=True):
    projection = graph.projection
    kinds = dict(graph.step_kinds)
    if output_format == "text":
        lines = [
            "Procedure %s: %s (definition only)"
            % (console_text(projection.root.id), console_text(projection.root.title)),
            "Start: %s" % console_text(graph.start),
        ]
        if include_body:
            for body in projection.root.body:
                lines.extend("  | " + console_text(line) for line in body.splitlines())
        outgoing = {node.id: [] for node in projection.steps}
        for edge in graph.edges:
            outgoing[edge.source].append(edge)
        for node in projection.steps:
            prefix = "  " * node.depth
            lines.append(
                "%s%s [%s] %s (line %d)"
                % (
                    prefix,
                    console_text(node.id),
                    kinds[node.id],
                    console_text(node.title),
                    node.line,
                )
            )
            if include_body:
                for body in node.body:
                    lines.extend(
                        prefix + "  | " + console_text(line)
                        for line in body.splitlines()
                    )
            for edge in outgoing[node.id]:
                lines.append(
                    "%s  %s -> %s" % (prefix, edge.label, console_text(edge.target))
                )
        return _bounded("\n".join(lines) + "\n")
    identifiers = {node.id: "p%d" % i for i, node in enumerate(projection.steps)}
    if output_format == "mermaid":
        lines = ["flowchart TD"]
        for node in projection.steps:
            label = _mermaid_label("%s: %s" % (node.id, node.title))
            ident = identifiers[node.id]
            if kinds[node.id] == "decision":
                lines.append('  %s{"%s"}' % (ident, label))
            elif kinds[node.id] == "end":
                lines.append('  %s(["%s"])' % (ident, label))
            else:
                lines.append('  %s["%s"]' % (ident, label))
        for edge in graph.edges:
            lines.append(
                '  %s -->|"%s"| %s'
                % (
                    identifiers[edge.source],
                    _mermaid_label(edge.label),
                    identifiers[edge.target],
                )
            )
    elif output_format == "dot":
        lines = ["digraph procedure {", "  rankdir=TB;"]
        for node in projection.steps:
            shape = {"action": "box", "decision": "diamond", "end": "oval"}[
                kinds[node.id]
            ]
            label = _dot_quote(console_text("%s: %s" % (node.id, node.title)))
            lines.append(
                "  %s [label=%s, shape=%s];" % (identifiers[node.id], label, shape)
            )
        for edge in graph.edges:
            lines.append(
                "  %s -> %s [label=%s];"
                % (
                    identifiers[edge.source],
                    identifiers[edge.target],
                    _dot_quote(edge.label),
                )
            )
        lines.append("}")
    else:
        raise ValueError("Unsupported procedure graph format.")
    return _bounded("\n".join(lines) + "\n")
