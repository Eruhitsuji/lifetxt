"""Rich, human-readable text rendering of stable `Diagnostic` objects
(#639): a source-line snippet, a span caret/range when a precise end
position is known, the diagnostic's own `hint` text, and a trailing
error/warning summary.

This is a presentation layer only. It reads no new information the parser
and validator did not already attach to each `Diagnostic` (see
`lifetxt/model.py`'s `Diagnostic`/`lifetxt/diagnostic_contract.py`), adds no
new diagnostic codes, and never changes `check --format json`'s existing
stable field set -- that path keeps calling `diagnostic_to_output_dict()`
directly and never touches this module.
"""

from __future__ import unicode_literals


def _read_source_line(path, line_no):
    """Best-effort read of one 1-indexed line from `path`.

    Returns ``None`` on any failure (missing file, unreadable, out-of-range
    line number, or no path/line at all) so the caller can fall back to a
    compact, snippet-free rendering rather than raising.
    """
    if not path or path == "-" or not line_no or line_no < 1:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for index, text_line in enumerate(handle, start=1):
                if index == line_no:
                    return text_line.rstrip("\r\n")
                if index > line_no:
                    break
    except OSError:
        return None
    return None


def _caret_marker(column, end_line, line_no, end_column, line_length):
    """Build a `^~~~` marker string positioned under `column` (1-indexed).

    Only claims a multi-character range when the diagnostic's own
    ``end_line``/``end_column`` place the end on the *same* line as
    ``column`` -- a cross-line span, or no end position at all, renders a
    single caret rather than a fabricated range.
    """
    if not column or column < 1:
        return None
    start = column - 1
    width = 1
    if end_column and (end_line is None or end_line == line_no) and end_column > column:
        width = min(end_column - column, max(1, line_length - start))
    return " " * start + "^" + "~" * max(0, width - 1)


def render_diagnostic_rich(diagnostic):
    """One diagnostic's multi-line rich text block (no trailing newline)."""
    header_parts = []
    if diagnostic.source:
        header_parts.append(str(diagnostic.source))
    if diagnostic.line is not None:
        header_parts.append(str(diagnostic.line))
    if diagnostic.column is not None:
        header_parts.append(str(diagnostic.column))
    header = ":".join(header_parts)
    severity = (diagnostic.severity or "").upper()
    code = diagnostic.code or ""
    lines = []
    if header:
        lines.append("%s  %s %s  %s" % (header, severity, code, diagnostic.message))
    else:
        lines.append("%s %s  %s" % (severity, code, diagnostic.message))

    source_line = _read_source_line(diagnostic.source, diagnostic.line)
    if source_line is not None:
        gutter = "%d | " % diagnostic.line
        lines.append("")
        lines.append(gutter + source_line)
        caret = _caret_marker(
            diagnostic.column,
            diagnostic.end_line,
            diagnostic.line,
            diagnostic.end_column,
            len(source_line),
        )
        if caret:
            lines.append(" " * len(gutter) + caret)

    if diagnostic.hint:
        lines.append("")
        lines.append("Hint: %s" % diagnostic.hint)

    return "\n".join(lines)


def render_diagnostics_summary(diagnostics):
    """The trailing "N problems: X error(s), Y warning(s)" line."""
    total = len(diagnostics)
    errors = sum(1 for d in diagnostics if d.severity == "error")
    warnings = sum(1 for d in diagnostics if d.severity == "warning")

    def _plural(n, word):
        return "%d %s%s" % (n, word, "" if n == 1 else "s")

    return "%s: %s, %s" % (
        _plural(total, "problem"),
        _plural(errors, "error"),
        _plural(warnings, "warning"),
    )
