"""Bounded, read-only identity for a particular effective Web workspace.

Internal scaffolding for contextual Preview (#1182), not an HTTP token
or multi-file transaction. Readers must parse captured text via
WorkspaceContext.text_for_path rather than opening files again.
A Web instance whose source list was expanded at startup must enable
check_manifest for configured dynamic manifests/globs or explicitly restrict
its claim to the fixed source list actually used.

No raw paths, source contents or config in fingerprint metadata or change
descriptions. A fingerprint is a change detector, not an authorization token.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from . import mutation
from .workspace import DEFAULT_MAX_TOTAL_SOURCE_BYTES, MAX_SOURCES, resolve_workspace


class WorkspaceContextUnavailable(ValueError):
    """No reliable context could be read; reason is safe for a user-facing UI."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _canonical(path):
    if not isinstance(path, (str, os.PathLike)) or os.fspath(path) == "-":
        raise WorkspaceContextUnavailable("source_resolution_required")
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def _digest(value):
    try:
        encoded = json.dumps(
            value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise WorkspaceContextUnavailable("invalid_config") from None
    return hashlib.sha256(encoded).hexdigest()


def _path_id(path):
    return hashlib.sha256(path.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkspaceContext:
    """Opaque identity, safe change metadata, and private read evidence.

    The private texts are excluded from repr/comparisons, are server-only
    and must never be serialized to a browser or placed in logs. Future
    contextual Preview can pass text_for_path to the shared Core read helper.
    """

    fingerprint: str
    workspace: str
    scope: str
    source_revisions: tuple
    writable_identity: str
    writable_revision: str
    config_revision: str
    _texts: tuple = field(repr=False, compare=False)

    def text_for_path(self, path):
        identity = _path_id(_canonical(path))
        for key, text in self._texts:
            if key == identity:
                return text
        raise WorkspaceContextUnavailable("source_not_in_snapshot")


def _checked_paths(paths, config, check_manifest):
    try:
        actual = tuple(_canonical(p) for p in paths)
    except (TypeError, ValueError, OSError):
        raise WorkspaceContextUnavailable("source_resolution_required") from None
    if not actual:
        raise WorkspaceContextUnavailable("no_sources")
    if len(actual) > MAX_SOURCES:
        raise WorkspaceContextUnavailable("source_count_exceeded")
    if len(set(actual)) != len(actual):
        raise WorkspaceContextUnavailable("duplicate_source")
    # Callers supply the same expanded paths that downstream Core uses.
    if any(any(char in os.fspath(p) for char in "*?[") or os.path.isdir(p) for p in paths):
        raise WorkspaceContextUnavailable("source_resolution_required")
    if check_manifest:
        try:
            resolved = resolve_workspace(config, name=config.get("_active_workspace") or None)
        except (OSError, ValueError, TypeError):
            raise WorkspaceContextUnavailable("manifest_unavailable") from None
        if not resolved["ok"]:
            raise WorkspaceContextUnavailable("manifest_unavailable")
        try:
            expected = tuple(_canonical(p) for p in resolved["input_paths"])
        except (OSError, ValueError, TypeError):
            raise WorkspaceContextUnavailable("manifest_unavailable") from None
        if expected != actual:
            raise WorkspaceContextUnavailable("source_membership_changed")
    return actual


def _scan(paths, writable, config, check_manifest, optional, max_bytes):
    actual = _checked_paths(paths, config, check_manifest)
    entries, texts, found = [], [], {}
    total = 0
    for path in (*actual, writable):
        if path in found:
            continue
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            stat = None
        except OSError:
            raise WorkspaceContextUnavailable("source_unavailable") from None
        if stat is not None and stat.st_size > max_bytes:
            raise WorkspaceContextUnavailable("source_too_large")
        try:
            shot = mutation.read_text_snapshot(path, allow_missing=True)
        except (OSError, UnicodeError, mutation.MutationError):
            raise WorkspaceContextUnavailable("source_unavailable") from None
        if not shot.exists and path not in optional and path != writable:
            raise WorkspaceContextUnavailable("source_unavailable")
        if shot.size > max_bytes:
            raise WorkspaceContextUnavailable("source_too_large")
        found[path] = shot
        total += shot.size
        if total > max_bytes:
            raise WorkspaceContextUnavailable("workspace_too_large")
    for path in actual:
        shot = found[path]
        identity = _path_id(path)
        entries.append((identity, shot.exists, shot.content_hash))
        texts.append((identity, shot.text))
    write_shot = found[writable]
    name = str(config.get("_active_workspace") or config.get("default_workspace") or "default")
    scope = "checked_manifest" if check_manifest else "fixed_paths"
    config_revision = _digest(config)
    write_id = _path_id(writable)
    fingerprint = _digest((
        "workspace-context-v1", name, scope, config_revision, entries,
        write_id, write_shot.exists, write_shot.content_hash,
    ))
    return WorkspaceContext(
        fingerprint, name, scope, tuple(entries), write_id,
        write_shot.content_hash, config_revision, tuple(texts),
    )


def read_workspace_context(
    paths, writable_path, config=None, *, check_manifest=False,
    optional_paths=(), attempts=2, max_bytes=DEFAULT_MAX_TOTAL_SOURCE_BYTES,
):
    """Capture exact-byte revisions with bounded repeated reads.

    paths are the ordered effective paths read by Web. Manifest mode resolves
    configured workspace sources *again on each scan*; membership changes
    cause fail-closed source_membership_changed (restart required if Web
    expanded globs at startup). Without it only fixed-path scope is claimed.
    Optional missing sources are part of the identity as explicitly absent.

    Two scans detect observed instability; external writers can still change
    another source immediately after the final scan. No global atomicity.
    """
    config = {} if config is None else config
    if not isinstance(config, dict):
        raise WorkspaceContextUnavailable("invalid_config")
    if not isinstance(attempts, int) or not 1 <= attempts <= 3:
        raise ValueError("attempts must be between 1 and 3")
    if not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if paths is None or writable_path is None:
        raise WorkspaceContextUnavailable("source_resolution_required")
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    try:
        paths = tuple(paths)
        optional = frozenset(_canonical(p) for p in optional_paths)
        writable = _canonical(writable_path)
    except (OSError, TypeError, ValueError):
        raise WorkspaceContextUnavailable("source_resolution_required") from None
    for _ in range(attempts):
        before = _scan(paths, writable, config, check_manifest, optional, max_bytes)
        after = _scan(paths, writable, config, check_manifest, optional, max_bytes)
        if before.fingerprint == after.fingerprint:
            return after
    raise WorkspaceContextUnavailable("snapshot_unstable")


def describe_workspace_context_change(before, after):
    """Return non-sensitive categories, not paths or contents."""
    categories = []
    if before.workspace != after.workspace or before.scope != after.scope:
        categories.append("workspace_changed")
    if before.config_revision != after.config_revision:
        categories.append("validation_config_changed")
    previous = {entry[0]: entry[1:] for entry in before.source_revisions}
    current = {entry[0]: entry[1:] for entry in after.source_revisions}
    if tuple(previous) != tuple(current):
        categories.append("source_membership_changed")
    common = previous.keys() & current.keys()
    if any(previous[key][0] != current[key][0] for key in common):
        categories.append("source_presence_changed")
    if any(previous[key][1] != current[key][1] for key in common):
        categories.append("source_content_changed")
    if (
        before.writable_identity != after.writable_identity
        or before.writable_revision != after.writable_revision
    ):
        categories.append("writable_changed")
    if before.fingerprint != after.fingerprint and not categories:
        categories.append("context_changed")
    return tuple(categories)
