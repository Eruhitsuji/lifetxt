"""Integrated workspace doctor and conservative stale-lock cleanup."""

from __future__ import unicode_literals

import importlib.util
import os

from .revision_telemetry import store_from_config
from .safety_foundation import inspect_locks, read_text_exact, serve_target_diagnostic
from .timezone_policy import policy_report
from .workspace_diagnostics import workspace_diagnostics


def doctor_report(
    paths,
    config=None,
    write_path=None,
    timer_paths=None,
    archive_paths=None,
    revision_metrics_path=None,
    cli_timezone=None,
    fold_policy="error",
    gap_policy="error",
    stale_after=300.0,
    cleanup_stale=False,
    force=False,
):
    config = config or {}
    paths = [os.path.abspath(path) for path in (paths or []) if path and path != "-"]
    write_path = os.path.abspath(write_path) if write_path else (paths[0] if paths else "")
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
    locks_before = inspect_locks(paths + list(timer_paths or []), stale_after=stale_after)
    cleanup = cleanup_stale_locks(
        locks_before,
        stale_after=stale_after,
        enabled=cleanup_stale,
        force=force,
    )
    locks_after = inspect_locks(paths + list(timer_paths or []), stale_after=stale_after)
    target = serve_target_diagnostic(paths, write_path)
    diagnostics = workspace_diagnostics(
        paths,
        archive_paths=archive_paths,
        timer_paths=timer_paths,
        write_path=write_path,
        revision_metrics_path=store.path,
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
    return {
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
        "optional_dependencies": dependencies,
    }


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


def optional_dependency_report():
    names = ("fastapi", "uvicorn", "httpx", "textual", "watchdog", "jsonschema")
    return dict((name, importlib.util.find_spec(name) is not None) for name in names)
