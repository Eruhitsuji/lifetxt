import html
import re
from collections import OrderedDict
from urllib.parse import urlparse


_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_UNORDERED_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_ORDERED_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_TABLE_ROW_RE = re.compile(r"^\|")
_TABLE_SEP_CELL_RE = re.compile(r"^:?-+:?$")
_SAFE_LINK_SCHEMES = {"http", "https", "mailto"}


def markdown_to_html(text, inline=False):
    """Render the safe life.txt Markdown subset to HTML."""
    text = "" if text is None else str(text)
    if inline:
        return render_inline_markdown(text)
    return render_block_markdown(text)


def markdown_to_plain(text):
    """Strip the supported Markdown markers while preserving readable text."""
    text = "" if text is None else str(text)
    text = _strip_fence_markers(text)
    text = re.sub(r"(?m)^#{1,3}\s+", "", text)
    text = _strip_inline_markers(text)
    text = _render_plain_tables(text)
    return text


def _strip_inline_markers(text):
    text = _LINK_RE.sub(lambda match: match.group(1), text)
    text = _CODE_RE.sub(lambda match: match.group(1), text)
    text = _BOLD_RE.sub(lambda match: match.group(1), text)
    text = _ITALIC_RE.sub(lambda match: match.group(1), text)
    return text


def item_markdown_payload(item):
    """Return sanitized Markdown HTML for fields likely to contain Markdown."""
    details = OrderedDict()
    for key in ("body", "note"):
        values = item.details.get(key) or []
        if values:
            details[key] = [markdown_to_html(value) for value in values]

    return OrderedDict(
        [
            ("title", markdown_to_html(item.title, inline=True)),
            ("details", details),
        ]
    )


def render_inline_markdown(text):
    text = "" if text is None else str(text)
    placeholders = []

    def stash(value):
        token = "\x00MD%d\x00" % len(placeholders)
        placeholders.append(value)
        return token

    def replace_code(match):
        return stash("<code>%s</code>" % html.escape(match.group(1), quote=True))

    def replace_link(match):
        label = render_inline_markdown(match.group(1))
        url = match.group(2)
        if not _is_safe_link(url):
            return stash(label)
        href = html.escape(url, quote=True)
        return stash(
            '<a href="%s" rel="noopener noreferrer" target="_blank">%s</a>'
            % (href, label)
        )

    text = _CODE_RE.sub(replace_code, text)
    text = _LINK_RE.sub(replace_link, text)
    escaped = html.escape(text, quote=True)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC_RE.sub(r"<em>\1</em>", escaped)

    for index, value in enumerate(placeholders):
        escaped = escaped.replace("\x00MD%d\x00" % index, value)
    return escaped


def render_block_markdown(text):
    text = "" if text is None else str(text)
    lines = text.splitlines()
    output = []
    paragraph = []
    list_type = None
    in_code = False
    code_lines = []
    table_lines = []

    def close_paragraph():
        if paragraph:
            joined = " ".join(line.strip() for line in paragraph)
            output.append("<p>%s</p>" % render_inline_markdown(joined))
            paragraph[:] = []

    def close_list():
        nonlocal list_type
        if list_type:
            output.append("</%s>" % list_type)
            list_type = None

    def ensure_list(kind):
        nonlocal list_type
        if list_type == kind:
            return
        close_paragraph()
        close_list()
        output.append("<%s>" % kind)
        list_type = kind

    def close_code():
        if code_lines:
            output.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_lines)))
            code_lines[:] = []
        else:
            output.append("<pre><code></code></pre>")

    def close_table():
        if table_lines:
            output.append(_render_table(table_lines))
            table_lines[:] = []

    for line in lines:
        if line.strip().startswith("```"):
            close_paragraph()
            close_list()
            close_table()
            if in_code:
                close_code()
                in_code = False
            else:
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            close_paragraph()
            close_list()
            close_table()
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            close_paragraph()
            close_list()
            close_table()
            level = len(heading.group(1))
            output.append(
                "<h%d>%s</h%d>"
                % (level, render_inline_markdown(heading.group(2)), level)
            )
            continue

        unordered = _UNORDERED_RE.match(line)
        if unordered:
            close_table()
            ensure_list("ul")
            output.append("<li>%s</li>" % render_inline_markdown(unordered.group(1)))
            continue

        ordered = _ORDERED_RE.match(line)
        if ordered:
            close_table()
            ensure_list("ol")
            output.append("<li>%s</li>" % render_inline_markdown(ordered.group(1)))
            continue

        if _TABLE_ROW_RE.match(line):
            close_paragraph()
            close_list()
            table_lines.append(line)
            continue

        close_list()
        close_table()
        paragraph.append(line)

    if in_code:
        close_code()
    close_paragraph()
    close_list()
    close_table()
    return "\n".join(output)


def _is_safe_link(url):
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _SAFE_LINK_SCHEMES:
        return False
    if parsed.scheme.lower() in ("http", "https") and not parsed.netloc:
        return False
    return True


def _strip_fence_markers(text):
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _render_plain_tables(text):
    result = []
    table_lines = []

    def flush_table():
        if table_lines:
            result.extend(_render_plain_table_lines(table_lines))
            table_lines[:] = []

    for line in text.splitlines():
        if _TABLE_ROW_RE.match(line):
            table_lines.append(line)
            continue
        flush_table()
        result.append(line)
    flush_table()
    return "\n".join(result)


def _render_plain_table_lines(table_lines):
    if len(table_lines) < 2 or not _is_separator_row(table_lines[1]):
        return _strip_pipe_lines(table_lines)

    rows = [_parse_table_cells(table_lines[0])] + [
        _parse_table_cells(line) for line in table_lines[2:]
    ]
    sep_cells = _parse_table_cells(table_lines[1])
    column_count = max([len(sep_cells)] + [len(row) for row in rows])
    alignments = _table_alignments(sep_cells, column_count)
    normalized = [_pad_row(row, column_count) for row in rows]
    widths = []
    for index in range(column_count):
        widths.append(max(3, max(len(row[index]) for row in normalized)))

    output = [_format_plain_table_row(normalized[0], widths, alignments)]
    output.append(_format_plain_table_separator(widths))
    for row in normalized[1:]:
        output.append(_format_plain_table_row(row, widths, alignments))
    return output


def _strip_pipe_lines(lines):
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            result.append(line)
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(_TABLE_SEP_CELL_RE.match(c) for c in cells if c):
            continue  # drop separator rows
        result.append("  ".join(c for c in cells if c))
    return result


def _is_separator_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(_TABLE_SEP_CELL_RE.match(c) for c in cells if c)


def _parse_table_cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _render_table(table_lines):
    if len(table_lines) < 2 or not _is_separator_row(table_lines[1]):
        return "\n".join(
            "<p>%s</p>" % render_inline_markdown(line.strip()) for line in table_lines
        )

    sep_cells = _parse_table_cells(table_lines[1])
    alignments = _table_alignments(sep_cells, len(sep_cells))

    def cell_style(i):
        align = alignments[i] if i < len(alignments) else None
        return ' style="text-align:%s"' % align if align else ""

    parts = ["<table>", "<thead>", "<tr>"]
    for i, cell in enumerate(_parse_table_cells(table_lines[0])):
        parts.append("<th%s>%s</th>" % (cell_style(i), render_inline_markdown(cell)))
    parts += ["</tr>", "</thead>"]

    body_rows = table_lines[2:]
    if body_rows:
        parts.append("<tbody>")
        for row_line in body_rows:
            parts.append("<tr>")
            for i, cell in enumerate(_parse_table_cells(row_line)):
                parts.append("<td%s>%s</td>" % (cell_style(i), render_inline_markdown(cell)))
            parts.append("</tr>")
        parts.append("</tbody>")

    parts.append("</table>")
    return "\n".join(parts)


def _table_alignments(sep_cells, column_count):
    alignments = []
    for index in range(column_count):
        cell = sep_cells[index] if index < len(sep_cells) else ""
        if cell.startswith(":") and cell.endswith(":"):
            alignments.append("center")
        elif cell.endswith(":"):
            alignments.append("right")
        elif cell.startswith(":"):
            alignments.append("left")
        else:
            alignments.append(None)
    return alignments


def _pad_row(row, column_count):
    padded = list(row)
    while len(padded) < column_count:
        padded.append("")
    return padded[:column_count]


def _format_plain_table_row(row, widths, alignments):
    cells = []
    for index, value in enumerate(row):
        cells.append(_align_plain_cell(value, widths[index], alignments[index]))
    return "| " + " | ".join(cells) + " |"


def _format_plain_table_separator(widths):
    return "| " + " | ".join("-" * width for width in widths) + " |"


def _align_plain_cell(value, width, alignment):
    if alignment == "right":
        return value.rjust(width)
    if alignment == "center":
        return value.center(width)
    return value.ljust(width)
