"""Revision-safe external editor sessions.

Editors work on a temporary copy.  The authored file is updated only after the
editor exits, the replacement parses, and the original revision (or a
conservative non-overlapping three-way reconciliation) is still valid.
"""

from __future__ import unicode_literals

import difflib
import os
import shutil
import subprocess
import tempfile
from collections import OrderedDict

from . import mutation
from .parser import parse_text


class EditorSafetyError(RuntimeError):
    pass


class EditorReconcileConflict(EditorSafetyError):
    pass


def safe_edit(
    path,
    editor,
    line=1,
    expected_revision=None,
    review_only=False,
    reconcile=False,
    keep_temp=False,
    runner=None,
    validate=True,
    operation="editor.safe_apply",
):
    """Run ``editor`` against a temporary copy and revision-check the apply.

    ``reconcile`` performs a conservative line-based three-way merge.  It only
    accepts edits whose base ranges do not overlap changes made to the source
    while the editor was open.
    """
    absolute = os.path.abspath(path)
    before = mutation.read_text_snapshot(absolute)
    if (
        expected_revision not in (None, "")
        and str(expected_revision) != before.content_hash
    ):
        raise mutation.MutationConflict(
            absolute,
            str(expected_revision),
            before.content_hash,
            operation,
        )

    directory = tempfile.mkdtemp(prefix="lifetxt-edit-")
    temp_path = os.path.join(directory, os.path.basename(absolute) or "life.txt")
    shutil.copyfile(absolute, temp_path)
    command = _editor_command(editor, temp_path, line)
    run = runner or subprocess.call
    try:
        return_code = int(run(command))
        if return_code != 0:
            raise EditorSafetyError("Editor exited with status %d." % return_code)
        edited = mutation.read_text_snapshot(temp_path)
        if validate:
            _validate_life_text(edited.text)
        current = mutation.read_text_snapshot(absolute)
        source_changed = current.content_hash != before.content_hash
        if source_changed:
            if not reconcile:
                raise mutation.MutationConflict(
                    absolute,
                    before.content_hash,
                    current.content_hash,
                    operation,
                )
            replacement = reconcile_text(before.text, edited.text, current.text)
        else:
            replacement = edited.text
        changed = replacement != current.text
        diff = unified_diff(current.text, replacement, absolute)
        result = OrderedDict(
            (
                ("path", absolute),
                ("temporary_path", temp_path if keep_temp else None),
                ("command", command),
                ("before_revision", before.content_hash),
                ("current_revision", current.content_hash),
                ("edited_revision", edited.content_hash),
                ("source_changed_while_editing", source_changed),
                ("reconciled", bool(source_changed and reconcile)),
                ("changed", changed),
                ("review_only", bool(review_only)),
                ("diff", diff),
                ("written", False),
            )
        )
        if changed and not review_only:
            write_result = mutation.write_text(
                absolute,
                replacement,
                expected_hash=current.content_hash,
                operation=operation,
                create=False,
            )
            result["written"] = True
            result["after_revision"] = write_result.after_hash
        else:
            result["after_revision"] = current.content_hash
        return result
    finally:
        if not keep_temp:
            shutil.rmtree(directory, ignore_errors=True)


def reconcile_text(base, edited, current):
    """Return a conservative non-overlapping three-way line merge."""
    if current == base:
        return edited
    if edited == base:
        return current
    editor_changes = _changes(base, edited)
    current_changes = _changes(base, current)
    for left in editor_changes:
        for right in current_changes:
            if _overlap(left, right):
                if left == right:
                    continue
                raise EditorReconcileConflict(
                    "The editor and source changed the same line range (%d:%d)."
                    % (left[0] + 1, max(left[1], left[0] + 1))
                )
    merged = base.splitlines(keepends=True)
    for start, end, replacement in sorted(
        editor_changes + current_changes, key=lambda row: (row[0], row[1]), reverse=True
    ):
        merged[start:end] = replacement
    return "".join(merged)


def unified_diff(before, after, path):
    if before == after:
        return ""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path + " (before)",
            tofile=path + " (after)",
        )
    )


def _changes(base, variant):
    base_lines = base.splitlines(keepends=True)
    variant_lines = variant.splitlines(keepends=True)
    rows = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, base_lines, variant_lines
    ).get_opcodes():
        if tag != "equal":
            rows.append((i1, i2, variant_lines[j1:j2]))
    return rows


def _overlap(left, right):
    l1, l2, _ = left
    r1, r2, _ = right
    if l1 == l2 and r1 == r2:
        return l1 == r1
    if l1 == l2:
        return r1 <= l1 < r2
    if r1 == r2:
        return l1 <= r1 < l2
    return max(l1, r1) < min(l2, r2)


def _validate_life_text(text):
    _items, diagnostics = parse_text(text, check_ids=False, check_references=False)
    errors = [row for row in diagnostics if row.severity == "error"]
    if errors:
        raise EditorSafetyError(errors[0].format())


def _editor_command(editor, path, line):
    from .fzf_helper import editor_command

    command = editor_command(editor, path, line)
    if not command:
        raise EditorSafetyError("Editor command is empty.")
    return command
