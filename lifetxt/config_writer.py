"""Validated, atomic configuration writes with a bounded backup record.

Every configuration write (``config set``, ``config unset``, ``config migrate``)
routes through :func:`write_config`. It validates the proposed document before
committing, refuses unsupported-version or invalid documents, keeps a bounded
rotation of ``.bak`` backups next to the file, and writes atomically so an
interrupted write can never truncate a good configuration.

Writes are also compare-and-set aware. Configuration decides remote access,
integrations, workspace sources, and automatic writes, so losing an edit to a
concurrent writer is not cosmetic: pass ``expected_revision`` and a write that
would clobber someone else's change is refused instead of winning silently. The
revision is the same SHA-256 of raw file bytes that record mutations use --
:func:`lifetxt.mutation.read_text_snapshot` -- rather than a second scheme.

A refused write does not throw the caller's document away. The rejected
candidate is retained beside the file in a bounded rotation, because the whole
point of refusing is that the edit still matters.
"""

from __future__ import unicode_literals

import json
import os
import shutil
from collections import OrderedDict

from . import mutation
from .atomic import atomic_write_text
from .config_validation import is_supported_version, validate_config
from .surface_runtime import normalize_revision


class ConfigWriteError(ValueError):
    """Raised when a configuration write is refused."""


class StaleConfigRevision(ConfigWriteError):
    """Raised when the file changed since the caller read it.

    Carries both revisions and the path of the retained candidate so a caller
    can explain the conflict without re-reading anything.
    """

    def __init__(self, message, expected=None, current=None, retained=None):
        ConfigWriteError.__init__(self, message)
        self.expected = expected
        self.current = current
        self.retained = retained


class ConfigRevisionRequired(ConfigWriteError):
    """Raised when a revision was mandatory for this write and absent."""


DEFAULT_MAX_BACKUPS = 3
DEFAULT_MAX_REJECTED = 3

#: Revision reported for a configuration file that does not exist yet, so a
#: first write can still be expressed as a compare-and-set.
MISSING_REVISION = mutation.MISSING_HASH


def config_revision(path):
    """Exact revision of the configuration file at ``path``.

    Returns :data:`MISSING_REVISION` when the file does not exist, so "create
    only if still absent" is expressible with the same token as every other
    precondition.
    """
    if not path:
        return MISSING_REVISION
    return mutation.read_text_snapshot(path, allow_missing=True).content_hash


def serialize_config(data):
    clean = OrderedDict(
        (key, value)
        for key, value in (data or {}).items()
        if key not in ("_path", "_active_workspace")
    )
    return json.dumps(clean, ensure_ascii=False, indent=2) + "\n"


def _rotate_backups(path, max_backups):
    if max_backups <= 0 or not os.path.exists(path):
        return None
    # Shift older backups: file.bak2 <- file.bak1 <- file.bak
    for index in range(max_backups - 1, 0, -1):
        older = "%s.bak%d" % (path, index)
        newer = "%s.bak%d" % (path, index + 1)
        if os.path.exists(older):
            try:
                if os.path.exists(newer):
                    os.remove(newer)
                os.replace(older, newer)
            except OSError:
                pass
    backup = "%s.bak1" % path
    try:
        if os.path.exists(backup):
            os.remove(backup)
        shutil.copy2(path, backup)
        return backup
    except OSError:
        return None


def _retain_rejected(path, text, max_rejected=DEFAULT_MAX_REJECTED):
    """Keep a refused candidate so the caller's edit is recoverable.

    Backups preserve what was already on disk; this preserves what was about to
    be written. Without it, refusing a stale write would protect the file by
    discarding the user's work, which is the wrong trade.
    """
    if max_rejected <= 0:
        return None
    for index in range(max_rejected - 1, 0, -1):
        older = "%s.rejected%d" % (path, index)
        newer = "%s.rejected%d" % (path, index + 1)
        if os.path.exists(older):
            try:
                if os.path.exists(newer):
                    os.remove(newer)
                os.replace(older, newer)
            except OSError:
                pass
    target = "%s.rejected1" % path
    try:
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, exist_ok=True)
        atomic_write_text(target, text)
        return target
    except OSError:
        return None


def rejected_candidates(path):
    """Retained candidates from refused writes, newest first.

    Nothing removes these automatically: discarding a candidate is the user's
    decision, because it is the only remaining copy of an edit that was refused.
    They are surfaced by ``config check`` so they cannot sit unnoticed beside the
    configuration and be mistaken for it.
    """
    if not path:
        return []
    found = []
    for index in range(1, DEFAULT_MAX_REJECTED + 1):
        candidate = "%s.rejected%d" % (path, index)
        if os.path.exists(candidate):
            found.append(os.path.abspath(candidate))
    return found


def _stale_message(expected, current):
    return (
        "Configuration changed since it was read (expected %s, found %s). "
        "Re-read the configuration and reapply the change." % (expected, current)
    )


def write_config(
    path,
    data,
    validate=True,
    max_backups=DEFAULT_MAX_BACKUPS,
    allow_unsupported=False,
    expected_revision=None,
    require_revision=False,
    dry_run=False,
    max_rejected=DEFAULT_MAX_REJECTED,
):
    """Validate and atomically write ``data`` to ``path``.

    ``expected_revision`` makes the write a compare-and-set: when it does not
    match the file's current revision the write is refused, the file is left
    byte-identical, and the rejected candidate is retained. Pass
    :data:`MISSING_REVISION` to require that the file does not exist yet.

    The comparison happens **inside** the shared sidecar lock, delegated to
    :func:`lifetxt.mutation.write_text`. Comparing here and writing afterwards
    would leave a window in which another writer commits between the two and is
    silently overwritten -- the very failure this precondition exists to stop.

    ``require_revision`` refuses a write that supplied no revision at all, for
    callers that must not fall back to last-write-wins.

    ``dry_run`` validates and reports the revision the write would produce
    without touching the filesystem. Its revision check is necessarily advisory:
    nothing is written, so nothing is locked.

    Returns a report describing the write. Raises ``ConfigWriteError`` (or its
    ``StaleConfigRevision`` / ``ConfigRevisionRequired`` subclasses) when the
    write is refused.
    """
    if not path:
        raise ConfigWriteError("No configuration path to write.")

    diagnostics = []
    if validate:
        diagnostics = validate_config(data)
        errors = [row for row in diagnostics if row["severity"] == "error"]
        if errors:
            summary = "; ".join(row["message"] for row in errors[:5])
            raise ConfigWriteError(
                "Refusing to write invalid configuration: %s" % summary
            )
    if not allow_unsupported and not is_supported_version(data):
        raise ConfigWriteError(
            "Refusing to write an unsupported config_version. Upgrade lifetxt first."
        )

    text = serialize_config(data)
    expected = normalize_revision(
        expected_revision, supplied=expected_revision is not None
    )
    if require_revision and expected is None:
        raise ConfigRevisionRequired(
            "This configuration write requires an expected revision. "
            "Read the current revision and retry."
        )

    report = OrderedDict(
        (
            ("path", os.path.abspath(path)),
            ("backup", None),
            ("bytes", len(text.encode("utf-8"))),
            ("before_revision", None),
            ("revision", None),
            ("written", not dry_run),
            ("warnings", [row for row in diagnostics if row["severity"] != "error"]),
        )
    )

    if dry_run:
        before = config_revision(path)
        if expected is not None and expected != before:
            # No candidate is retained: a dry run had nothing to lose.
            raise StaleConfigRevision(
                _stale_message(expected, before), expected=expected, current=before
            )
        report["before_revision"] = before
        report["revision"] = mutation.hash_bytes(text.encode("utf-8"))
        return report

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    backup = {"path": None}

    def _replace(_current):
        # Runs inside the lock, after the precondition passed, while the file
        # still holds the previous content -- the only correct moment to snapshot
        # it. A refused write therefore never churns the backup chain.
        backup["path"] = _rotate_backups(path, max_backups)
        return text

    try:
        result = mutation.write_text(
            path,
            transform=_replace,
            expected_hash=expected,
            operation="config.write",
            create=True,
        )
    except mutation.MutationConflict as exc:
        # Validation ran first on purpose: an invalid document is refused as
        # invalid rather than retained as a recoverable candidate.
        retained = _retain_rejected(path, text, max_rejected)
        raise StaleConfigRevision(
            _stale_message(exc.expected_hash, exc.actual_hash),
            expected=exc.expected_hash,
            current=exc.actual_hash,
            retained=os.path.abspath(retained) if retained else None,
        )

    report["backup"] = os.path.abspath(backup["path"]) if backup["path"] else None
    report["before_revision"] = result.before_hash
    report["revision"] = result.after_hash
    return report
