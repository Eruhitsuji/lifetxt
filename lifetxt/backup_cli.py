"""CLI orchestration for `lifetxt backup` (#836/#842/#843/#844/#847).

Thin wiring over the format/verify/restore/prune core in
:mod:`lifetxt.backup` and the rclone adapter in
:mod:`lifetxt.backup_remote`: no archive-format or transfer logic is
duplicated here. This module also owns the small local status file
(``<destination>/.lifetxt-backup-status.json``) that lets `backup status`
report the latest local/remote attempt and result without a database, and
the single ``run_scheduled`` entry point every unattended invocation
(manual cron, or the systemd timer #844 generates) goes through.
"""

from __future__ import annotations

import json
import os

from .atomic import atomic_write_json
from .backup import (
    BackupError,
    create_backup,
    default_backup_filename,
    list_backups,
    prune_backups,
    restore_backup,
    utc_now_iso as _utc_now_iso,
    verify_backup,
)
from .backup_remote import RcloneError, upload_backup

__all__ = [
    "BackupCliError",
    "resolve_destination",
    "resolve_sources",
    "read_status",
    "run_create",
    "run_status",
    "run_verify",
    "run_verify_latest",
    "run_restore",
    "run_prune",
    "run_scheduled",
]

_STATUS_FILENAME = ".lifetxt-backup-status.json"
_LOCK_FILENAME = ".lifetxt-backup.lock"


class BackupCliError(ValueError):
    """A CLI-level backup configuration/argument error (missing
    destination, no sources, an in-progress concurrent run, ...)."""


def _backup_config(config):
    return (config or {}).get("backup") or {}


def resolve_destination(config, explicit=None):
    """Resolve the local backup directory: an explicit CLI value wins,
    otherwise ``backup.destination`` from config. Raises
    :class:`BackupCliError` when neither is set -- there is no implicit
    default destination, since silently picking one would risk writing
    backups nobody asked for into an unexpected place."""
    destination = explicit or _backup_config(config).get("destination")
    if not destination:
        raise BackupCliError(
            "No backup destination configured. Pass --destination or set "
            "backup.destination in config."
        )
    return destination


def resolve_sources(config, explicit=None):
    """Resolve the list of source paths to back up: explicit CLI paths
    win, otherwise ``backup.sources`` from config. Raises
    :class:`BackupCliError` when neither is set."""
    sources = (
        list(explicit)
        if explicit
        else list(_backup_config(config).get("sources") or [])
    )
    if not sources:
        raise BackupCliError(
            "No backup sources configured. Pass source paths or set "
            "backup.sources in config."
        )
    return sources


def _status_path(destination):
    return os.path.join(destination, _STATUS_FILENAME)


def read_status(destination):
    """Return the persisted status dict for ``destination``, or an empty
    dict when no run has ever recorded one yet."""
    path = _status_path(destination)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _update_status(destination, **fields):
    os.makedirs(destination, exist_ok=True)
    current = read_status(destination)
    current.update(fields)
    atomic_write_json(_status_path(destination), current)
    return current


class _BackupLock:
    """Overlapping-run guard for ``run_scheduled`` (#844), independent of
    #731's own separate server-update lock. O_CREAT|O_EXCL, matching the
    established atomic-acquisition pattern already used by
    ``lifetxt.server_update.UpdateLock``/``lifetxt.git_commit_worker`` --
    reimplemented locally (rather than importing UpdateLock directly) only
    so the refusal message names backup, not an unrelated update."""

    def __init__(self, path):
        self.path = path
        self._fd = None

    def acquire(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise BackupCliError(
                "Another scheduled backup run appears to be in progress "
                "(lock file %s already exists); refusing to start a "
                "second, overlapping run." % self.path
            )
        os.write(self._fd, str(os.getpid()).encode("ascii"))

    def release(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.remove(self.path)
        except OSError:
            pass


def run_create(sources, destination, *, source_identity=None, lifetxt_version=None):
    """Create one backup under ``destination`` from ``sources``. Returns
    the :class:`~lifetxt.backup.BackupResult`. Never reports success
    before the artifact is finalized: ``create_backup`` itself only
    returns once the archive is atomically committed."""
    os.makedirs(destination, exist_ok=True)
    created_at = _utc_now_iso()
    filename = default_backup_filename(created_at)
    output_path = os.path.join(destination, filename)
    return create_backup(
        sources,
        output_path,
        source_identity=source_identity,
        lifetxt_version=lifetxt_version,
        created_at=created_at,
    )


def run_status(destination):
    """Return a status payload combining the persisted attempt/result
    history with a fresh listing of what is actually on disk right now --
    the local artifact listing is never staled by the status file, since
    it is always recomputed here rather than only reported from memory."""
    persisted = read_status(destination)
    backups = list_backups(destination) if os.path.isdir(destination) else []
    latest_complete = next((name for name, r in backups if r.ok), None)
    return {
        "destination": destination,
        "backup_count": len(backups),
        "latest_local_backup": latest_complete,
        "last_attempt_at": persisted.get("last_attempt_at"),
        "last_attempt_ok": persisted.get("last_attempt_ok"),
        "last_success_at": persisted.get("last_success_at"),
        "last_success_path": persisted.get("last_success_path"),
        "last_remote_upload_at": persisted.get("last_remote_upload_at"),
        "last_remote_upload_ok": persisted.get("last_remote_upload_ok"),
        "last_remote_error": persisted.get("last_remote_error"),
        "next_scheduled_run": persisted.get("next_scheduled_run"),
    }


def run_verify(path):
    return verify_backup(path)


def run_verify_latest(destination):
    """Verify the newest complete backup selected by manifest metadata.

    Candidate ordering and completeness come from :func:`list_backups`, the
    same authoritative listing used by status and retention.  A corrupt newest
    complete-looking archive is returned to the caller as a failed verification
    rather than silently falling back to an older generation.
    """
    rows = list_backups(destination) if os.path.isdir(destination) else []
    candidates = [
        (name, result)
        for name, result in rows
        if result.manifest and result.manifest.get("status") == "complete"
    ]
    if not candidates:
        raise BackupCliError("No complete backup candidates found in %s." % destination)
    name, result = candidates[0]
    return os.path.join(destination, name), result


def run_restore(path, destination_dir, *, overwrite=False, dry_run=False):
    return restore_backup(path, destination_dir, overwrite=overwrite, dry_run=dry_run)


def run_prune(destination, *, keep_last, dry_run=False):
    return prune_backups(destination, keep_last=keep_last, dry_run=dry_run)


def run_scheduled(config, *, sources_override=None, destination_override=None):
    """The single entry point every unattended (cron/systemd) invocation
    goes through: create a local backup, optionally upload it, and record
    both results independently in the status file -- never converting a
    failure into an apparent success, and never letting two invocations
    run concurrently against the same destination.

    Returns a result dict; raises :class:`BackupCliError`/
    :class:`~lifetxt.backup.BackupError`/
    :class:`~lifetxt.backup_remote.RcloneError` for a failure the caller
    should surface with a non-zero exit code. A local-creation failure
    still records the attempt (as failed) in the status file before the
    exception propagates, so `backup status` reflects it even when the
    caller does nothing further.
    """
    backup_config = _backup_config(config)
    if not backup_config.get("enabled"):
        raise BackupCliError(
            "backup.enabled is not set; scheduled backup is disabled. Set "
            "backup.enabled = true in config to allow run-scheduled to run."
        )

    destination = resolve_destination(config, destination_override)
    sources = resolve_sources(config, sources_override)
    lock = _BackupLock(os.path.join(destination, _LOCK_FILENAME))
    lock.acquire()
    try:
        attempt_at = _utc_now_iso()
        try:
            result = run_create(
                sources,
                destination,
                source_identity=backup_config.get("source_identity"),
            )
        except Exception:
            _update_status(
                destination, last_attempt_at=attempt_at, last_attempt_ok=False
            )
            raise

        status_update = {
            "last_attempt_at": attempt_at,
            "last_attempt_ok": True,
            "last_success_at": attempt_at,
            "last_success_path": result.path,
        }

        remote = backup_config.get("remote") or {}
        remote_target = (
            remote.get("target") if remote.get("backend") == "rclone" else None
        )
        if remote_target:
            try:
                upload_backup(
                    result.path,
                    remote_target,
                    rclone_bin=remote.get("rclone_bin", "rclone"),
                )
                status_update["last_remote_upload_at"] = _utc_now_iso()
                status_update["last_remote_upload_ok"] = True
                status_update["last_remote_error"] = None
            except RcloneError as exc:
                status_update["last_remote_upload_at"] = _utc_now_iso()
                status_update["last_remote_upload_ok"] = False
                status_update["last_remote_error"] = str(exc)

        keep_last = backup_config.get("keep_last")
        prune_result = None
        if isinstance(keep_last, int) and keep_last > 0:
            prune_result = prune_backups(destination, keep_last=keep_last)

        _update_status(destination, **status_update)
        return {
            "backup": result,
            "remote_uploaded": status_update.get("last_remote_upload_ok"),
            "remote_error": status_update.get("last_remote_error"),
            "prune": prune_result,
        }
    finally:
        lock.release()
