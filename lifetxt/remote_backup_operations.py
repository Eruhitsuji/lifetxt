"""Bounded Remote Safe Mode admission for the fixed backup systemd service."""

from __future__ import unicode_literals

import subprocess
import threading
import time
import uuid
from collections import OrderedDict

from .backup_cli import resolve_destination, run_status
from .remote_access import RemoteAccessError

SERVICE = "lifetxt-backup.service"
DEFAULT_COOLDOWN_SECONDS = 900
MIN_COOLDOWN_SECONDS = 900
MAX_OPERATIONS = 100


def settings(config):
    remote = (config or {}).get("remote") or {}
    value = remote.get("backup_run") or {}
    return value if isinstance(value, dict) else {}


def configured(config):
    value = settings(config)
    command = value.get("service_command")
    backup = (config or {}).get("backup") or {}
    remote = (config or {}).get("remote") or {}
    return bool(
        value.get("enabled")
        and backup.get("enabled")
        and remote.get("audit_log")
        and isinstance(command, list)
        and command
        and all(isinstance(part, str) and part for part in command)
    )


def cooldown_seconds(config):
    raw = settings(config).get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise RemoteAccessError(
            "BACKUP_RUN_UNAVAILABLE", "Backup run admission is unavailable.", 503
        )
    if value < MIN_COOLDOWN_SECONDS:
        raise RemoteAccessError(
            "BACKUP_RUN_UNAVAILABLE", "Backup run admission is unavailable.", 503
        )
    return value


def validate_idempotency_key(value):
    value = str(value or "")
    if (
        not value
        or len(value) > 128
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
    ):
        raise RemoteAccessError(
            "IDEMPOTENCY_KEY_REQUIRED",
            "A printable Idempotency-Key of at most 128 characters is required.",
            400,
        )
    return value


def _public(operation):
    return OrderedDict(
        (
            ("schema", "remote-backup-run-operation-v1.schema.json"),
            ("operation_id", operation["operation_id"]),
            ("status", operation["status"]),
            ("local", dict(operation["local"])),
            ("remote", dict(operation["remote"])),
            (
                "status_url",
                "/api/remote/v1/operations/backup-runs/%s" % operation["operation_id"],
            ),
            ("cooldown_seconds", operation["cooldown_seconds"]),
        )
    )


class BackupRunStore(object):
    """Process-local, bounded admission state for one systemd one-shot."""

    def __init__(self, clock=None, runner=None):
        self._clock = clock or time.monotonic
        self._runner = runner or subprocess.run
        self._lock = threading.Lock()
        self._operations = OrderedDict()
        self._keys = {}
        self._last_admitted = {}
        self._active = None

    def _trim(self):
        while len(self._operations) > MAX_OPERATIONS:
            operation_id, operation = self._operations.popitem(last=False)
            self._keys.pop(
                (operation["principal_id"], operation["idempotency_key"]), None
            )

    def admit(self, principal_id, idempotency_key, config):
        if not configured(config):
            raise RemoteAccessError(
                "BACKUP_RUN_UNAVAILABLE", "Backup run admission is unavailable.", 503
            )
        key = (str(principal_id), validate_idempotency_key(idempotency_key))
        cooldown = cooldown_seconds(config)
        now = float(self._clock())
        with self._lock:
            duplicate = self._keys.get(key)
            if duplicate:
                return _public(self._operations[duplicate]), True
            if self._active:
                raise RemoteAccessError(
                    "BACKUP_RUN_IN_PROGRESS", "A backup run is already admitted.", 409
                )
            last = self._last_admitted.get(key[0])
            if last is not None and now - last < cooldown:
                retry_after = max(1, int(cooldown - (now - last)))
                raise RemoteAccessError(
                    "BACKUP_RUN_RATE_LIMITED",
                    "Backup run cooldown is active.",
                    429,
                    {"retry_after_seconds": retry_after},
                )
            operation_id = uuid.uuid4().hex
            operation = {
                "operation_id": operation_id,
                "principal_id": key[0],
                "idempotency_key": key[1],
                "status": "admitted",
                "local": {"status": "pending"},
                "remote": {"status": "pending"},
                "cooldown_seconds": cooldown,
            }
            self._operations[operation_id] = operation
            self._keys[key] = operation_id
            self._last_admitted[key[0]] = now
            self._active = operation_id
            self._trim()
            return _public(operation), False

    def start(self, operation_id, config, audit_callback=None):
        thread = threading.Thread(
            target=self._execute,
            args=(operation_id, config, audit_callback),
            daemon=True,
        )
        thread.start()

    def abandon(self, operation_id):
        """Roll back an admission when the required audit write fails."""
        with self._lock:
            operation = self._operations.pop(str(operation_id), None)
            if not operation:
                return
            self._keys.pop(
                (operation["principal_id"], operation["idempotency_key"]), None
            )
            self._last_admitted.pop(operation["principal_id"], None)
            if self._active == operation_id:
                self._active = None

    def _execute(self, operation_id, config, audit_callback=None):
        with self._lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return
            operation["status"] = "running"
        if audit_callback:
            audit_callback("started", operation_id)
        try:
            destination = resolve_destination(config)
            before = run_status(destination)
        except (OSError, TypeError, ValueError):
            destination = None
            before = None
        command = list(settings(config)["service_command"]) + ["start", SERVICE]
        dispatch_ok = False
        try:
            if destination is not None:
                result = self._runner(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=int(settings(config).get("runner_timeout_seconds") or 3600),
                )
                dispatch_ok = result.returncode == 0
        except (OSError, subprocess.SubprocessError, TypeError, ValueError):
            pass
        try:
            status = run_status(destination) if destination is not None else None
        except (OSError, TypeError, ValueError):
            status = None
        local_ok = status.get("last_attempt_ok") if status is not None else None
        remote_configured = bool(
            ((config.get("backup") or {}).get("remote") or {}).get("target")
        )
        remote_ok = status.get("last_remote_upload_ok") if status is not None else None
        fresh_attempt = bool(
            before is not None
            and status is not None
            and status.get("last_attempt_at")
            and status.get("last_attempt_at") != before.get("last_attempt_at")
        )
        with self._lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return
            operation["local"] = {
                "status": "succeeded"
                if dispatch_ok and fresh_attempt and local_ok is True
                else "failed"
            }
            if remote_configured and dispatch_ok and fresh_attempt:
                operation["remote"] = {
                    "status": "succeeded" if remote_ok is True else "failed"
                }
            else:
                operation["remote"] = {
                    "status": "not_configured" if not remote_configured else "unknown"
                }
            operation["status"] = (
                "completed" if dispatch_ok and fresh_attempt else "failed"
            )
            if self._active == operation_id:
                self._active = None
            outcome = operation["status"]
        if audit_callback:
            audit_callback(outcome, operation_id)

    def get(self, operation_id, principal_id):
        with self._lock:
            operation = self._operations.get(str(operation_id))
            if not operation or operation["principal_id"] != str(principal_id):
                raise RemoteAccessError(
                    "BACKUP_RUN_NOT_FOUND", "Backup run operation was not found.", 404
                )
            return _public(operation)
