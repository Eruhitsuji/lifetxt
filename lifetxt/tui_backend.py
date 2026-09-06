"""TUI data-source/backend boundary (#678).

Isolates the interactive curses TUI's storage/domain calls behind one small
contract so the same presentation layer (:mod:`lifetxt.tui_app`) can later
operate against either local files or a remote ``lifetxt serve`` Web API
(#679/#680) without scattering ``if remote:`` branches through rendering,
command handling, and mutation code.

This module is deliberately transport-free: :class:`LocalTuiBackend` is the
only implementation here, and it wraps today's existing local-file
read/parse/mutation behavior unchanged -- it does not add a new local
storage mechanism, it only gives the existing one a name other backends can
implement instead of.

The contract is semantic (list items, apply a small set of item-level
edits), not a fake filesystem API: a future :class:`RemoteTuiBackend`
implements the same methods against HTTP endpoints without pretending a
remote server is a local file.

Two seams are wired through this contract today:

- reading the item set for the dashboard model and Command Center
  (:meth:`TuiBackend.load_items`);
- committing the disk write for a semantic row-level edit
  (:meth:`TuiBackend.apply_semantic_changes`), the single choke point
  ``lifetxt.tui_app._mutate_rows`` already funneled every row mutation
  through before this extraction.

Everything else -- grouping selected rows by source file, building the
per-row change dict, undo-stack bookkeeping, reload-after-write -- stays in
``tui_app.py`` exactly as before; only the "read items" and "commit this
already-built change set to disk" steps moved behind this boundary, since
those are the only two the Remote Web backend genuinely needs to replace.
Bulk/marked-row edits spanning many files at once
(:meth:`apply_semantic_changes` receiving more than one grouped path) are
explicitly out of scope for the Remote Web backend's first MVP slice (#679)
and remain local-only; a remote backend may raise ``NotImplementedError``
for that case rather than silently degrading it.
"""

from __future__ import unicode_literals


class TuiBackend(object):
    """Base contract for local/remote TUI data access.

    Not an abstract base class in the ``abc`` sense (this codebase's other
    duck-typed contracts, e.g. the delegated-mutation adapters, follow the
    same plain-class-with-``NotImplementedError`` pattern) -- callers rely on
    the method contract below, not on ``isinstance`` checks.
    """

    #: Whether this backend talks to a remote server. Local presentation
    #: code (bulk row edits, the local file-change monitor, $EDITOR
    #: suspension) checks this before assuming a local file exists.
    is_remote = False

    def load_items(self):
        """Return ``(items, diagnostics)``.

        ``items`` is a list of :class:`lifetxt.model.Item`-shaped objects
        (each carrying its own ``.source``), or ``None`` on failure.
        ``diagnostics`` is an optional human-readable string describing a
        problem the caller should surface without necessarily treating it
        as fatal (mirrors the existing local ``WorkspaceState.load()``
        error-handling shape).
        """
        raise NotImplementedError

    def apply_semantic_changes(self, grouped, before, id_key, journal_dir=None):
        """Commit a pre-built, per-source-file set of item changes.

        ``grouped`` is ``{source_path: [change_dict, ...]}`` in the exact
        shape ``lifetxt.write_operations.mutate_items``/``mutate_item_files``
        already accept. ``before`` is ``{source_path: read_text_snapshot
        result}``, used as the expected-revision precondition for each
        file. Returns ``{source_path: after_content_hash}``.
        """
        raise NotImplementedError

    def connection_label(self):
        """Short, credential-safe status string for the TUI header."""
        return "local"


class LocalTuiBackend(TuiBackend):
    """Wraps today's existing local-file TUI read/write behavior unchanged."""

    is_remote = False

    def __init__(self, args):
        self.args = args

    def load_items(self):
        from .tui import load_items as _load_items

        return _load_items(self.args.paths), None

    def apply_semantic_changes(self, grouped, before, id_key, journal_dir=None):
        from .write_operations import mutate_item_files, mutate_items

        after = {}
        if len(grouped) == 1:
            path = next(iter(grouped))
            result = mutate_items(
                path,
                grouped[path],
                id_key=id_key,
                expected_revision=before[path].content_hash,
                operation="tui.semantic",
            )
            after[path] = result.after_hash
        else:
            specs = {}
            for path in grouped:
                specs[path] = {
                    "changes": grouped[path],
                    "expected_revision": before[path].content_hash,
                }
            result = mutate_item_files(
                specs,
                id_key=id_key,
                operation="tui.semantic.multi",
                journal_dir=journal_dir,
            )
            for target in result.targets:
                after[target.path] = target.after_hash
        return after

    def connection_label(self):
        return "local"
