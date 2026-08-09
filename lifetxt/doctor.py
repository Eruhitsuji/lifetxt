"""Integrated workspace doctor and conservative stale-lock cleanup."""

from __future__ import unicode_literals

import importlib.util
import os

from .revision_telemetry import store_from_config
from .transaction_journal import (
    cleanup_terminal,
    inspect_journal,
    journal_directory,
    journal_policy_report,
    list_journals,
)
from .safety_foundation import inspect_locks, read_text_exact, serve_target_diagnostic
from .timezone_policy import policy_report
from .workspace_diagnostics import workspace_diagnostics


def _config_recovery_report(config):
    from .config_writer import rejected_candidates

    path = config.get("_path") if isinstance(config, dict) else None
    retained = rejected_candidates(path)
    if not retained:
        return None
    return {
        "path": os.path.abspath(path) if path else "",
        "rejected_candidate_count": len(retained),
        "rejected_candidates": [
            {
                "path": candidate,
                "severity": "info",
                "message": (
                    "Refused configuration write retained for manual review; "
                    "review and delete when no longer needed."
                ),
            }
            for candidate in retained
        ],
    }


def doctor_report(
    paths,
    config=None,
    write_path=None,
    timer_paths=None,
    archive_paths=None,
    revision_metrics_path=None,
    journal_dir=None,
    cleanup_transactions=False,
    transaction_retention_days=30.0,
    cli_timezone=None,
    fold_policy="error",
    gap_policy="error",
    stale_after=300.0,
    cleanup_stale=False,
    force=False,
):
    config = config or {}
    paths = [os.path.abspath(path) for path in (paths or []) if path and path != "-"]
    write_path = (
        os.path.abspath(write_path) if write_path else (paths[0] if paths else "")
    )
    text = ""
    if paths and os.path.exists(paths[0]):
        text, _raw, _bom = read_text_exact(paths[0])
    timezone = policy_report(
        config,
        text=text,
        cli_timezone=cli_timezone,
        fold_policy=fold_policy,
        gap_policy=gap_policy,
    )
    store = store_from_config(config, writable_path=write_path or None)
    if revision_metrics_path:
        store.path = os.path.abspath(revision_metrics_path)
    revision = store.snapshot()
    if not timer_paths:
        try:
            from .timer import timer_state_file

            timer_paths = [timer_state_file(config)]
        except Exception:
            timer_paths = []
    resolved_journal_dir = os.path.abspath(
        journal_dir or journal_directory(config, writable_path=write_path or None)
    )
    transaction_section = (
        config.get("transactions")
        if isinstance(config.get("transactions"), dict)
        else {}
    )
    configured_backups = transaction_section.get("backup_dirs") or []
    if isinstance(configured_backups, str):
        configured_backups = [configured_backups]
    transaction_backup_paths = [
        os.path.abspath(os.path.expanduser(str(value))) for value in configured_backups
    ]
    transaction_policy = journal_policy_report(resolved_journal_dir, config=config)
    transaction_rows = list_journals(resolved_journal_dir, include_terminal=True)
    transaction_details = []
    for row in transaction_rows:
        if row.get("state") == "corrupt":
            transaction_details.append(row)
            continue
        try:
            transaction_details.append(inspect_journal(row["journal_path"]))
        except Exception as exc:
            broken = dict(row)
            broken.update(
                {"state": "corrupt", "recovery_required": True, "error": str(exc)}
            )
            transaction_details.append(broken)
    transaction_cleanup = (
        cleanup_terminal(
            resolved_journal_dir,
            older_than_days=transaction_retention_days,
            force=bool(force and cleanup_transactions),
            config=config,
        )
        if cleanup_transactions
        else {
            "journal_dir": resolved_journal_dir,
            "requested": False,
            "removed": [],
            "skipped": [],
            "errors": [],
        }
    )
    locks_before = inspect_locks(
        paths + list(timer_paths or []), stale_after=stale_after
    )
    cleanup = cleanup_stale_locks(
        locks_before,
        stale_after=stale_after,
        enabled=cleanup_stale,
        force=force,
    )
    locks_after = inspect_locks(
        paths + list(timer_paths or []), stale_after=stale_after
    )
    target = serve_target_diagnostic(paths, write_path)
    diagnostics = workspace_diagnostics(
        paths,
        archive_paths=archive_paths,
        timer_paths=timer_paths,
        write_path=write_path,
        revision_metrics_path=store.path,
        journal_dir=resolved_journal_dir,
        config=config,
        transaction_backup_paths=transaction_backup_paths,
    )
    dependencies = optional_dependency_report()
    hard_failures = []
    if not timezone.get("valid"):
        hard_failures.append("timezone")
    if target.get("windows_drive_relative"):
        hard_failures.append("write_target")
    if not diagnostics.get("ok"):
        hard_failures.append("diagnostics")
    if cleanup.get("errors"):
        hard_failures.append("lock_cleanup")
    if transaction_cleanup.get("errors"):
        hard_failures.append("transaction_cleanup")
    if any(
        row.get("recovery_required") or row.get("state") == "corrupt"
        for row in transaction_details
    ):
        hard_failures.append("transaction_recovery")
    if not transaction_policy.get("ok"):
        hard_failures.append("transaction_policy")
    report = {
        "ok": not hard_failures,
        "hard_failures": hard_failures,
        "workspace": {
            "paths": paths,
            "write_path": write_path,
            "archive_paths": [os.path.abspath(path) for path in (archive_paths or [])],
            "timer_paths": [os.path.abspath(path) for path in (timer_paths or [])],
        },
        "timezone": timezone,
        "write_target": target,
        "revision_migration": revision,
        "locks": {
            "before": locks_before,
            "cleanup": cleanup,
            "after": locks_after,
        },
        "diagnostics": diagnostics,
        "transactions": {
            "journal_dir": resolved_journal_dir,
            "count": len(transaction_details),
            "recovery_required": any(
                row.get("recovery_required") or row.get("state") == "corrupt"
                for row in transaction_details
            ),
            "records": transaction_details,
            "cleanup": transaction_cleanup,
            "policy": transaction_policy,
            "backup_paths": transaction_backup_paths,
        },
        "optional_dependencies": dependencies,
    }
    config_recovery = _config_recovery_report(config)
    if config_recovery is not None:
        report["config"] = config_recovery
    return report


def cleanup_stale_locks(records, stale_after=300.0, enabled=False, force=False):
    planned = []
    removed = []
    skipped = []
    errors = []
    for record in records or []:
        if not record.get("stale"):
            continue
        path = record.get("path")
        planned.append(path)
        if not enabled:
            skipped.append({"path": path, "reason": "cleanup not requested"})
            continue
        if not force:
            skipped.append({"path": path, "reason": "--force is required"})
            continue
        try:
            first = os.stat(path)
        except FileNotFoundError:
            continue
        target = record.get("target") or path[: -len(".lifetxt.lock")]
        current = inspect_locks([target], stale_after=stale_after)
        if not current or not current[0].get("stale"):
            skipped.append({"path": path, "reason": "lock is no longer proven stale"})
            continue
        try:
            second = os.stat(path)
        except FileNotFoundError:
            continue
        if (first.st_ino, first.st_size, first.st_mtime_ns) != (
            second.st_ino,
            second.st_size,
            second.st_mtime_ns,
        ):
            skipped.append({"path": path, "reason": "lock changed during verification"})
            continue
        try:
            os.unlink(path)
            removed.append(path)
        except OSError as exc:
            errors.append({"path": path, "error": str(exc)})
    return {
        "requested": bool(enabled),
        "force": bool(force),
        "planned": planned,
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
    }


#: Single source of truth for optional-dependency presence, shared by both
#: `lifetxt doctor` and `lifetxt doctor --workspace-safety` so the two
#: surfaces cannot report a different package set for the same install.
OPTIONAL_DEPENDENCY_NAMES = (
    "fastapi",
    "uvicorn",
    "httpx",
    "textual",
    "watchdog",
    "jsonschema",
    "matplotlib",
    "cryptography",
)


def optional_dependency_report():
    return dict(
        (name, importlib.util.find_spec(name) is not None)
        for name in OPTIONAL_DEPENDENCY_NAMES
    )
