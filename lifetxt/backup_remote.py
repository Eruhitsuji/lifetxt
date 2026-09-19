"""Provider-independent off-host backup upload via rclone (#836/#843).

rclone owns provider authentication/protocol support (Google Drive,
OneDrive, S3, and everything else it already speaks); this module owns
only invoking it safely and orchestrating one file transfer. No
provider-specific code, no cloud vendor SDK, and no rclone credential
file is ever read, embedded, or logged by this module -- lifetxt treats
an rclone ``remote:path`` target exactly as an opaque, externally
configured string.

Every rclone invocation uses a structured argument list passed directly
to :func:`subprocess.run` (``shell=False``); no shell is ever involved, so
there is no shell-injection surface regardless of what a remote target or
file path contains.

This is upload/copy-only: never ``rclone sync``, never a delete driven by
local absence. A local file that has since vanished must never cause this
module to delete anything remote -- see :func:`upload_backup` and
:func:`delete_remote_backup` (used only by #847's explicit retention
pruning, never by upload).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

__all__ = [
    "RcloneError",
    "RcloneResult",
    "rclone_available",
    "upload_backup",
    "list_remote_backups",
    "delete_remote_backup",
]

_DEFAULT_TIMEOUT_SECONDS = 300


class RcloneError(RuntimeError):
    """Raised for an actionable rclone failure: the binary is missing, the
    remote/target is invalid, authentication failed, or the transfer
    itself failed. Never raised for "nothing to do"."""


class RcloneResult:
    """The outcome of one rclone invocation."""

    __slots__ = ("ok", "stdout", "stderr", "returncode")

    def __init__(self, ok, stdout, stderr, returncode):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _argv_prefix(rclone_bin):
    """Normalize ``rclone_bin`` to an argv prefix list. Tests pass a list
    (e.g. ``[sys.executable, "fake_rclone.py"]``) to run a controlled,
    local, dependency-free stand-in for the real ``rclone`` binary without
    needing real cloud credentials; production code passes the default
    bare ``"rclone"`` string."""
    if isinstance(rclone_bin, (list, tuple)):
        return list(rclone_bin)
    return [rclone_bin]


def rclone_available(rclone_bin="rclone"):
    """Return whether the configured rclone executable can be found.

    For the bare-string production form this checks PATH via
    :func:`shutil.which`; for a test-double argv-prefix list, the last
    element is treated as the script/executable path to check for
    existence directly (the earlier elements, e.g. an interpreter, are
    assumed to already be on PATH).
    """
    argv = _argv_prefix(rclone_bin)
    if len(argv) == 1:
        return shutil.which(argv[0]) is not None

    return shutil.which(argv[0]) is not None and os.path.isfile(argv[-1])


def _run(argv_prefix, args, timeout):
    try:
        completed = subprocess.run(
            argv_prefix + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RcloneError("rclone is not installed or not on PATH: %s" % exc) from exc
    except subprocess.TimeoutExpired as exc:
        raise RcloneError(
            "rclone timed out after %ss running %r" % (timeout, args)
        ) from exc
    return RcloneResult(
        completed.returncode == 0,
        completed.stdout,
        completed.stderr,
        completed.returncode,
    )


def _validate_target(remote_target):
    if not remote_target or not isinstance(remote_target, str):
        raise RcloneError("A remote target must be a non-empty string.")
    remote, sep, remainder = remote_target.partition(":")
    if not sep:
        raise RcloneError(
            "Remote target %r does not look like an rclone target "
            "('remote:path'); refusing to guess at one." % remote_target
        )
    if not remote:
        raise RcloneError(
            "Remote target %r has no remote name before ':'; refusing an "
            "ambiguous/empty remote." % remote_target
        )
    # A bare `remote:` with no path at all is very easy to type by
    # accident and is the shape most likely to mean "the whole remote's
    # root" -- refuse it explicitly rather than silently uploading into
    # (or, worse, later pruning from) the remote's top level.
    if not remainder.strip("/"):
        raise RcloneError(
            "Remote target %r has no path component after the remote "
            "name; refusing to use the remote's root as a backup "
            "destination. Configure a dedicated subdirectory, e.g. "
            "'%sbackups'." % (remote_target, remote_target)
        )


def upload_backup(
    local_path, remote_target, *, rclone_bin="rclone", timeout=_DEFAULT_TIMEOUT_SECONDS
):
    """Upload ``local_path`` (a completed #841 ``.ltbackup`` file) to
    ``remote_target`` (an rclone ``remote:path`` string configured outside
    lifetxt). Uses ``rclone copyto``, an explicit single-file copy -- never
    ``sync``/``move`` -- so a failed or retried upload can never delete
    anything already present on the remote, and a source file that has
    since disappeared locally can never cause a remote deletion (this
    function never removes anything).

    Raises :class:`RcloneError` for a missing rclone binary, an
    unusable-looking remote target, or a non-zero rclone exit (which
    itself covers authentication failures, network failures, and a
    missing/misconfigured remote) -- always with rclone's own stderr
    included, and never with the target's credential material, since this
    module never reads or forwards any credential file itself.
    """
    _validate_target(remote_target)
    if not rclone_available(rclone_bin):
        raise RcloneError(
            "rclone is not installed or not on PATH (looked for %r)." % rclone_bin
        )
    remote_destination = (
        remote_target.rstrip("/")
        + "/"
        + local_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    )
    result = _run(
        _argv_prefix(rclone_bin),
        ["copyto", local_path, remote_destination],
        timeout,
    )
    if not result.ok:
        raise RcloneError(
            "rclone upload to %r failed (exit %d): %s"
            % (remote_target, result.returncode, result.stderr.strip())
        )
    return result


def list_remote_backups(
    remote_target, *, rclone_bin="rclone", timeout=_DEFAULT_TIMEOUT_SECONDS
):
    """List backup object names under ``remote_target`` via ``rclone
    lsjson``, restricted to the exact configured backup prefix/path --
    never the remote's root. Returns a list of filenames (not full remote
    paths); raises :class:`RcloneError` on any rclone failure."""
    _validate_target(remote_target)
    if not rclone_available(rclone_bin):
        raise RcloneError(
            "rclone is not installed or not on PATH (looked for %r)." % rclone_bin
        )
    result = _run(_argv_prefix(rclone_bin), ["lsjson", remote_target], timeout)
    if not result.ok:
        raise RcloneError(
            "rclone listing of %r failed (exit %d): %s"
            % (remote_target, result.returncode, result.stderr.strip())
        )

    try:
        entries = json.loads(result.stdout or "[]")
    except ValueError as exc:
        raise RcloneError(
            "rclone lsjson for %r returned unparseable output: %s"
            % (remote_target, exc)
        ) from exc
    return [
        entry.get("Name")
        for entry in entries
        if isinstance(entry, dict) and not entry.get("IsDir") and entry.get("Name")
    ]


def delete_remote_backup(
    remote_target, filename, *, rclone_bin="rclone", timeout=_DEFAULT_TIMEOUT_SECONDS
):
    """Delete exactly one named object under ``remote_target`` (used only
    by #847's explicit, plan-first retention pruning -- never by
    :func:`upload_backup`, and never as remote mirror/sync behavior).
    ``filename`` must be a bare filename with no path separators, so this
    can only ever target one object directly under the configured backup
    prefix, never an arbitrary remote path."""
    _validate_target(remote_target)
    if not filename or "/" in filename or "\\" in filename or filename in (".", ".."):
        raise RcloneError(
            "Refusing to delete an unsafe remote object name: %r" % filename
        )
    if not rclone_available(rclone_bin):
        raise RcloneError(
            "rclone is not installed or not on PATH (looked for %r)." % rclone_bin
        )
    target = remote_target.rstrip("/") + "/" + filename
    result = _run(_argv_prefix(rclone_bin), ["deletefile", target], timeout)
    if not result.ok:
        raise RcloneError(
            "rclone delete of %r failed (exit %d): %s"
            % (target, result.returncode, result.stderr.strip())
        )
    return result
