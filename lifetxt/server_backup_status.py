"""Safe, read-only projection of disaster-recovery backup state.

The backup CLI remains authoritative for destination resolution, artifact
listing, and persisted run status.  This module only narrows that internal
status into a browser-safe operational contract: filesystem paths, remote
targets, and raw adapter errors never cross the server API boundary.
"""

from __future__ import annotations

import datetime
import re

from .backup import BackupError
from .backup_cli import BackupCliError, resolve_destination, run_status


def _result(value):
    if value is True:
        return "success"
    if value is False:
        return "failure"
    return "never_run"


def _safe_backup_name(value):
    if not isinstance(value, str) or not value:
        return None
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    if not re.fullmatch(
        r"lifetxt-\d{4}-\d{2}-\d{2}T\d{6}(?:\.\d{6})?Z\.ltbackup", name
    ):
        return None
    return name


def _safe_timestamp(value):
    """Return only bounded, timezone-aware ISO timestamps from status state."""
    if not isinstance(value, str) or not value or len(value) > 64:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return value


def backup_status_payload(config):
    """Return a normalized, secret-free server backup status payload."""
    backup = (config or {}).get("backup")
    backup = backup if isinstance(backup, dict) else {}
    enabled = backup.get("enabled") is True
    sources_configured = bool(backup.get("sources"))
    remote = backup.get("remote")
    remote = remote if isinstance(remote, dict) else {}
    remote_configured = bool(remote.get("backend") == "rclone" and remote.get("target"))

    try:
        destination = resolve_destination(config or {})
    except BackupCliError:
        destination = None

    configured = bool(destination and sources_configured)
    payload = {
        "configured": configured,
        "enabled": enabled,
        "state": "unconfigured",
        "backup_count": 0,
        "latest_local_backup": None,
        "local": {
            "last_attempt_at": None,
            "last_attempt_ok": None,
            "last_attempt_result": "never_run",
            "last_success_at": None,
            "last_success_backup": None,
        },
        "remote": {
            "configured": remote_configured,
            "last_upload_at": None,
            "last_upload_ok": None,
            "last_upload_result": (
                "never_run" if remote_configured else "not_configured"
            ),
            "last_error_summary": None,
        },
        "next_scheduled_run": None,
    }
    # Do not inspect a destination until configuration is complete and the
    # unattended operation is explicitly enabled. Besides preserving the
    # useful unconfigured/disabled states, this avoids touching an arbitrary
    # partial destination value supplied by otherwise incomplete config.
    if not configured:
        return payload
    if not enabled:
        payload["state"] = "disabled"
        return payload

    try:
        status = run_status(destination)
    except (BackupError, OSError, ValueError):
        payload["state"] = "unavailable"
        return payload

    local_ok = status.get("last_attempt_ok")
    remote_ok = status.get("last_remote_upload_ok")
    payload.update(
        {
            "backup_count": status.get("backup_count", 0),
            "latest_local_backup": _safe_backup_name(status.get("latest_local_backup")),
            "local": {
                "last_attempt_at": _safe_timestamp(status.get("last_attempt_at")),
                "last_attempt_ok": local_ok,
                "last_attempt_result": _result(local_ok),
                "last_success_at": _safe_timestamp(status.get("last_success_at")),
                "last_success_backup": _safe_backup_name(
                    status.get("last_success_path")
                ),
            },
            "remote": {
                "configured": remote_configured,
                "last_upload_at": _safe_timestamp(status.get("last_remote_upload_at")),
                "last_upload_ok": remote_ok,
                "last_upload_result": (
                    _result(remote_ok) if remote_configured else "not_configured"
                ),
                # Adapter errors can contain remote names, filesystem paths,
                # or command details.  The CLI/log remains the diagnostic
                # surface; the browser receives only an actionable summary.
                "last_error_summary": (
                    "Remote upload failed; inspect server-side backup status and logs."
                    if remote_configured and remote_ok is False
                    else None
                ),
            },
            "next_scheduled_run": _safe_timestamp(status.get("next_scheduled_run")),
        }
    )

    if local_ok is False:
        payload["state"] = "local_failure"
    elif remote_configured and remote_ok is False:
        payload["state"] = "remote_failure"
    elif local_ok is None and payload["backup_count"] == 0:
        payload["state"] = "never_run"
    else:
        payload["state"] = "healthy"
    return payload
