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

import urllib.parse
from collections import OrderedDict


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

    def poll_changed(self):
        """Cheap check for #680's bounded background polling: has the
        workspace changed since the last successful :meth:`load_items` or
        :meth:`poll_changed` call? Raises on a connection failure so the
        caller can distinguish "unreachable" from "unchanged". The base/
        local implementation always reports no change: local mode has its
        own, separate 0.25s file-change monitor and never uses this path.
        """
        return False


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


#: Stable virtual "source" every item fetched from one remote connection
#: carries, so ``lifetxt.tui_app``'s existing row grouping/undo machinery
#: (which keys on ``(row["source"], row["line"])``) treats every remote
#: item as belonging to one workspace, matching how a single local file
#: behaves today. Never a real filesystem path.
REMOTE_SOURCE_PREFIX = "remote:"


def remote_source_label(connection):
    return REMOTE_SOURCE_PREFIX + connection.host


class RemoteTuiBackend(TuiBackend):
    """Web API-backed backend: reads/writes an ordinary ``lifetxt serve``
    deployment's items over HTTP instead of local files (#679).

    Reuses the server's existing item read/write REST routes and its
    existing whole-file revision-precondition contract (``GET
    /api/revision`` / ``If-Match`` / 409 ``CONFLICT``) rather than adding a
    parallel protocol or a second server route: those already refuse a
    stale write, which is exactly the "never silently overwrite a
    concurrent change" guarantee #677 requires. No route in
    ``lifetxt/webapp.py`` needed to change for this backend to exist.

    Bulk edits spanning more than one grouped source
    (:meth:`apply_semantic_changes` receiving more than one path) are not
    supported here, since a remote connection only ever represents one
    workspace; per-item edits within that one workspace are applied as a
    sequence of individually revision-checked ``PUT`` calls rather than one
    atomic local-file transaction -- a deliberate, documented MVP
    limitation (#677's own scope explicitly allows this), not a silent
    behavior substitution: a conflict on any item in the sequence raises
    immediately rather than continuing to apply the rest.
    """

    is_remote = True

    def __init__(self, connection):
        self.connection = connection
        self._items_by_id = {}

    @classmethod
    def from_args(cls, args):
        from .tui_remote_client import RemoteTuiConnection

        url = getattr(args, "remote_url", None)
        if not url:
            raise ValueError("--remote-url is required for remote TUI mode.")
        username = getattr(args, "remote_user", None)
        password = None
        if username:
            import os

            password_env = (
                getattr(args, "remote_password_env", None)
                or "LIFETXT_REMOTE_TUI_PASSWORD"
            )
            password = os.environ.get(password_env)
        connection = RemoteTuiConnection(
            url,
            username=username,
            password=password,
            allow_insecure_http=bool(
                getattr(args, "allow_insecure_remote_http", False)
            ),
        )
        return cls(connection)

    def load_items(self):
        from .parser import parse_text

        try:
            payload = self.connection.request("GET", "/api/items")
        except Exception as exc:  # RemoteTuiError subclasses and any other failure
            return None, str(exc)
        source = remote_source_label(self.connection)
        items = []
        by_id = {}
        for raw in (payload or {}).get("items", []):
            text = raw.get("text") or ""
            parsed, diagnostics = parse_text(text + "\n")
            if not parsed:
                continue
            item = parsed[0]
            item.source = source
            item.line = raw.get("line")
            item.generated = bool(raw.get("generated"))
            items.append(item)
            item_id = raw.get("id")
            if item_id:
                by_id[str(item_id)] = item
        self._items_by_id = by_id
        return items, None

    def apply_semantic_changes(self, grouped, before, id_key, journal_dir=None):
        if len(grouped) != 1:
            raise NotImplementedError(
                "Remote TUI mode edits one remote workspace at a time; "
                "multi-file bulk edits are local-only."
            )
        path = next(iter(grouped))
        for change in grouped[path]:
            item_id = change.get("id")
            if not item_id:
                raise ValueError("Remote edits require an id: to target.")
            if change.get("delete"):
                self.delete_item(item_id)
                continue
            current_item = self._items_by_id.get(str(item_id))
            if current_item is None:
                raise ValueError(
                    "Item id:%s is not loaded from the remote workspace. "
                    "Reload and try again." % item_id
                )
            payload = _merged_update_payload(current_item, change)
            self.connection.request(
                "PUT",
                "/api/items/id/%s" % urllib.parse.quote(str(item_id), safe=""),
                json_body=payload,
                if_match=self.connection.file_revision,
            )
        return {path: self.connection.file_revision}

    def create_item(self, payload):
        """Create a new item on the remote workspace (#677 MVP: quick capture)."""
        return self.connection.request(
            "POST",
            "/api/items",
            json_body=payload,
            if_match=self.connection.file_revision,
        )

    def delete_item(self, item_id):
        """Delete one item on the remote workspace (#677 MVP: delete)."""
        return self.connection.request(
            "DELETE",
            "/api/items/id/%s" % urllib.parse.quote(str(item_id), safe=""),
            if_match=self.connection.file_revision,
        )

    def connection_label(self):
        return self.connection.describe()

    def poll_changed(self):
        """Cheap ``GET /api/revision``-only check (#680): far lighter than
        re-fetching and re-parsing every item, so the background poll
        loop can run every 1-2 seconds without a full reload on every
        tick. Raises the underlying ``RemoteTuiError`` on a connection
        failure -- callers must not treat that the same as "no change".
        """
        previous = self.connection.file_revision
        current = self.connection.get_revision()
        return previous is not None and current != previous


def _merged_update_payload(item, change):
    """Translate a `_mutate_rows`-style change dict into the full-replace
    payload ``PUT /api/items/id/{id}`` expects, by merging it onto the
    last-known item state -- the same merge
    ``lifetxt.write_operations.mutate_items`` performs locally, computed
    here client-side since the remote PUT route replaces details wholesale
    rather than merging.
    """
    details = OrderedDict((key, list(values)) for key, values in item.details.items())
    set_details = change.get("set_details") or {}
    for key, values in set_details.items():
        if not values:
            details.pop(key, None)
        else:
            details[key] = [str(value) for value in values]
    return {
        "status": change.get("status", item.status),
        "type": item.kind,
        "title": item.title,
        "details": details,
    }
