import re
from collections import OrderedDict

from .ids import duplicate_id_diagnostics
from .links import reference_diagnostics
from .model import Diagnostic, Item, VALID_STATUSES, VALID_TYPES
from .validator import validate_item


_DIRECTIVE_RE = re.compile(r"^#!\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$")
_KNOWN_DIRECTIVE_KEYS = frozenset(("self", "timezone", "project"))


def parse_directives(text):
    """Extract #! KEY: VALUE directives from the top of a life.txt file.

    Returns an OrderedDict. The block ends at the first line that is not a
    ``#! KEY: VALUE`` line (blank lines, item lines, and regular ``#`` comments
    all terminate the block).
    """
    directives = OrderedDict()
    for line in text.splitlines():
        stripped = line.rstrip("\r\n")
        if not stripped.strip():
            break
        m = _DIRECTIVE_RE.match(stripped)
        if m:
            directives[m.group(1)] = m.group(2)
        else:
            break
    return directives


def parse_text(text, id_key="id", check_ids=True, check_references=True):
    """Parse a full life.txt document.

    Returns ``(items, diagnostics)``. Blank lines and comment lines are ignored.
    Lines that start with ``|`` continue the previous item as a multiline
    ``body:`` detail. A trailing ``\`` joins the following physical line into
    the current logical line before parsing. Item lines may be indented with
    spaces to express a visual hierarchy; when possible, the parser adds an
    implicit ``parent:`` detail that points to the nearest less-indented
    ancestor's ID.
    """
    items = []
    diagnostics = []
    current_item = None
    current_has_error = False
    current_body_continuation = False
    hierarchy_stack = []

    def finish_current():
        nonlocal current_item, current_has_error, current_body_continuation
        if current_item is None:
            return
        items.append(current_item)
        if not current_has_error:
            diagnostics.extend(validate_item(current_item))
        current_item = None
        current_has_error = False
        current_body_continuation = False

    logical_lines, continuation_diagnostics = _logical_lines(text)
    diagnostics.extend(continuation_diagnostics)

    for line_no, end_line, line in logical_lines:
        leading_spaces = len(line) - len(line.lstrip(" "))
        stripped_line = line[leading_spaces:]
        if stripped_line.startswith("|"):
            if current_item is None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E019",
                        "Continuation lines must follow a life.txt item.",
                        line_no,
                        1,
                    )
                )
                continue
            if current_item.details.get("body") and not current_body_continuation:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E022",
                        "A body continuation cannot follow an inline body: detail. Use either one inline body:value or only | continuation lines.",
                        line_no,
                        leading_spaces + 1,
                    )
                )
                current_has_error = True
                continue
            _append_body_continuation(current_item, stripped_line)
            current_body_continuation = True
            current_item.end_line = end_line
            if current_item.source_text is None:
                current_item.source_text = line
            else:
                current_item.source_text += "\n" + line
            continue

        finish_current()
        item, line_diagnostics = parse_line(line, line_no)
        diagnostics.extend(line_diagnostics)
        if item is not None:
            _apply_hierarchy(item, hierarchy_stack, diagnostics, id_key)
            finish_current()
            item.end_line = end_line
            current_item = item
            current_has_error = _has_error(line_diagnostics)
            current_body_continuation = False
            _push_hierarchy_item(item, hierarchy_stack)
        elif _has_error(line_diagnostics):
            current_item = None
            current_has_error = False
            current_body_continuation = False
    finish_current()
    if check_ids:
        diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
    if check_references:
        diagnostics.extend(reference_diagnostics(items, key=id_key))
    return items, diagnostics


def _logical_lines(text):
    diagnostics = []
    physical_lines = text.splitlines()
    logical_lines = []
    index = 0
    while index < len(physical_lines):
        start_line = index + 1
        end_line = start_line
        current = physical_lines[index]
        parts = []

        while True:
            stripped_trailing = current.rstrip(" ")
            if stripped_trailing.endswith("\\"):
                parts.append(stripped_trailing[:-1])
                if index + 1 >= len(physical_lines):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E020",
                            "Line continuation backslash must be followed by another line.",
                            end_line,
                            len(stripped_trailing),
                        )
                    )
                    break

                index += 1
                end_line = index + 1
                current = physical_lines[index].lstrip(" ")
                if current.startswith("|"):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E021",
                            "Line continuation cannot continue into a body continuation line.",
                            end_line,
                            1,
                        )
                    )
                continue

            parts.append(current)
            break

        logical_lines.append((start_line, end_line, "".join(parts)))
        index += 1

    return logical_lines, diagnostics


def parse_line(line, line_no=1):
    """Parse one life.txt line.

    Returns ``(item, diagnostics)``. Blank/comment lines return ``None`` as the
    item.
    """
    text = line.rstrip("\r\n")
    diagnostics = []
    indent = len(text) - len(text.lstrip(" "))
    item_text = text[indent:]

    if text.strip(" \t") == "":
        if "\t" in text:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W001",
                    "Blank lines should contain spaces only, not tabs.",
                    line_no,
                    text.index("\t") + 1,
                )
            )
        return None, diagnostics

    if text.startswith("#"):
        return None, diagnostics

    if item_text.startswith("#"):
        diagnostics.append(
            Diagnostic(
                "warning",
                "W002",
                "Comment lines should start with # in column 1.",
                line_no,
                len(text) - len(text.lstrip(" ")) + 1,
            )
        )
        return None, diagnostics

    if "\t" in text:
        diagnostics.append(
            Diagnostic(
                "error",
                "E001",
                "Tabs are not valid separators; use single spaces.",
                line_no,
                text.index("\t") + 1,
            )
        )

    if len(item_text) < 3 or item_text[0] != "[":
        diagnostics.append(
            Diagnostic(
                "error",
                "E002",
                "Expected a status such as [ ], [/], [x], [-], [>], [?], or [N].",
                line_no,
                indent + 1,
            )
        )
        return None, diagnostics

    text = item_text

    status = text[:3]
    if status not in VALID_STATUSES:
        diagnostics.append(
            Diagnostic(
                "error",
                "E003",
                "Invalid status %r." % status,
                line_no,
                indent + 1,
            )
        )

    pos = 3
    pos = _consume_required_space(
        text,
        pos,
        line_no,
        diagnostics,
        "after status",
        column_offset=indent,
    )
    if pos is None:
        return None, diagnostics

    if pos >= len(text):
        diagnostics.append(
            Diagnostic("error", "E004", "Expected an item type.", line_no, indent + pos + 1)
        )
        return None, diagnostics

    kind = text[pos]
    if kind not in VALID_TYPES:
        diagnostics.append(
            Diagnostic(
                "error",
                "E005",
                "Invalid type %r. Use T, E, D, R, H, N, S, M, or J." % kind,
                line_no,
                indent + pos + 1,
            )
        )
    pos += 1

    pos = _consume_required_space(
        text,
        pos,
        line_no,
        diagnostics,
        "after type",
        column_offset=indent,
    )
    if pos is None:
        return None, diagnostics

    title, pos = _parse_string(text, pos, line_no, diagnostics, "title", column_offset=indent)
    if title is None:
        return None, diagnostics

    details = OrderedDict()
    while pos < len(text):
        if text[pos] != " ":
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E006",
                    "Expected a space before the next detail.",
                    line_no,
                    indent + pos + 1,
                )
            )
            break
        pos = _consume_required_space(
            text,
            pos,
            line_no,
            diagnostics,
            "before detail",
            column_offset=indent,
        )
        if pos is None or pos >= len(text):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W003",
                    "Trailing spaces are not part of the life.txt grammar.",
                    line_no,
                    indent + len(text),
                )
            )
            break
        key, value, pos = _parse_detail(text, pos, line_no, diagnostics, column_offset=indent)
        if key is not None:
            details.setdefault(key, []).append(value)

    return Item(status, kind, title, details, line_no, source_text=line.rstrip("\r\n"), indent=indent), diagnostics


def _append_body_continuation(item, line):
    if line.startswith("| "):
        value = line[2:]
    else:
        value = line[1:]
    existing = item.details.get("body")
    if existing:
        existing[0] = existing[0] + "\n" + value
    else:
        item.details["body"] = [value]


def _apply_hierarchy(item, hierarchy_stack, diagnostics, id_key):
    indent = int(getattr(item, "indent", 0) or 0)
    if indent <= 0:
        return

    while hierarchy_stack and hierarchy_stack[-1][0] >= indent:
        hierarchy_stack.pop()

    if item.details.get("parent"):
        return

    if not hierarchy_stack:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W220",
                "Indented item has no less-indented parent item; add parent: explicitly or move it to column 1.",
                item.line,
                indent + 1,
            )
        )
        return

    parent = hierarchy_stack[-1][1]
    parent_ids = parent.details.get(id_key, [])
    if not parent_ids:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W221",
                "Indented item could not infer parent:%s because the parent item has no %s: detail."
                % ("VALUE", id_key),
                item.line,
                indent + 1,
            )
        )
        return
    item.details.setdefault("parent", []).append(parent_ids[0])


def _push_hierarchy_item(item, hierarchy_stack):
    indent = int(getattr(item, "indent", 0) or 0)
    while hierarchy_stack and hierarchy_stack[-1][0] >= indent:
        hierarchy_stack.pop()
    hierarchy_stack.append((indent, item))


def _consume_required_space(text, pos, line_no, diagnostics, context, column_offset=0):
    if pos >= len(text):
        diagnostics.append(
            Diagnostic(
                "error",
                "E007",
                "Expected a space %s." % context,
                line_no,
                column_offset + pos + 1,
            )
        )
        return None
    if text[pos] != " ":
        diagnostics.append(
            Diagnostic(
                "error",
                "E008",
                "Expected a space %s." % context,
                line_no,
                column_offset + pos + 1,
            )
        )
        return None
    start = pos
    while pos < len(text) and text[pos] == " ":
        pos += 1
    if pos - start > 1:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W004",
                "Multiple spaces found %s; the grammar uses one space." % context,
                line_no,
                column_offset + start + 1,
            )
        )
    return pos


def _parse_detail(text, pos, line_no, diagnostics, column_offset=0):
    key_start = pos
    while pos < len(text) and text[pos] not in (" ", ":"):
        pos += 1

    if pos == key_start:
        diagnostics.append(
            Diagnostic("error", "E009", "Expected a detail key.", line_no, column_offset + pos + 1)
        )
        return None, None, _skip_token(text, pos)

    if pos >= len(text) or text[pos] != ":":
        token_end = _skip_token(text, key_start)
        diagnostics.append(
            Diagnostic(
                "error",
                "E010",
                "Expected detail in key:value form.",
                line_no,
                column_offset + key_start + 1,
            )
        )
        return None, None, token_end

    key = text[key_start:pos]
    if '"' in key:
        diagnostics.append(
            Diagnostic(
                "error",
                "E011",
                "Detail keys must not contain double quotes.",
                line_no,
                column_offset + key_start + 1,
            )
        )

    pos += 1
    if pos >= len(text):
        diagnostics.append(
            Diagnostic(
                "error",
                "E012",
                "Detail value must not be empty.",
                line_no,
                column_offset + pos + 1,
            )
        )
        return key, "", pos

    value, pos = _parse_string(
        text,
        pos,
        line_no,
        diagnostics,
        "detail value",
        column_offset=column_offset,
    )
    return key, value, pos


def _parse_string(text, pos, line_no, diagnostics, role, column_offset=0):
    if pos >= len(text):
        diagnostics.append(
            Diagnostic("error", "E013", "Expected %s." % role, line_no, column_offset + pos + 1)
        )
        return None, pos

    if text[pos] == '"':
        return _parse_quoted_string(
            text,
            pos,
            line_no,
            diagnostics,
            role,
            column_offset=column_offset,
        )

    start = pos
    saw_quote = False
    while pos < len(text) and text[pos] != " ":
        if text[pos] == '"':
            saw_quote = True
        pos += 1

    value = text[start:pos]
    if value == "":
        diagnostics.append(
            Diagnostic(
                "error",
                "E014",
                "Bare %s must not be empty." % role,
                line_no,
                column_offset + start + 1,
            )
        )
    if saw_quote:
        diagnostics.append(
            Diagnostic(
                "error",
                "E015",
                "Bare %s must not contain double quotes; quote the entire string."
                % role,
                line_no,
                column_offset + start + 1,
            )
        )
    return value, pos


def _parse_quoted_string(text, pos, line_no, diagnostics, role, column_offset=0):
    start = pos
    pos += 1
    chars = []
    while pos < len(text):
        ch = text[pos]
        if ch == '"':
            pos += 1
            if pos < len(text) and text[pos] not in (" ",):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E016",
                        "Quoted %s must be followed by a space or end of line." % role,
                        line_no,
                        column_offset + pos + 1,
                    )
                )
                pos = _skip_token(text, pos)
            return "".join(chars), pos
        if ch == "\\":
            if pos + 1 >= len(text):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E017",
                        "Backslash at end of quoted %s is not a valid escape." % role,
                        line_no,
                        column_offset + pos + 1,
                    )
                )
                chars.append("\\")
                return "".join(chars), len(text)
            next_ch = text[pos + 1]
            if next_ch not in ('"', "\\"):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "W005",
                        "Only \\\" and \\\\ escapes are defined by the specification.",
                        line_no,
                        column_offset + pos + 1,
                    )
                )
            chars.append(next_ch)
            pos += 2
            continue
        chars.append(ch)
        pos += 1

    diagnostics.append(
        Diagnostic(
            "error",
            "E018",
            "Unclosed quoted %s." % role,
            line_no,
            column_offset + start + 1,
        )
    )
    return "".join(chars), len(text)


def _skip_token(text, pos):
    while pos < len(text) and text[pos] != " ":
        pos += 1
    return pos


def _has_error(diagnostics):
    for diagnostic in diagnostics:
        if diagnostic.severity == "error":
            return True
    return False
