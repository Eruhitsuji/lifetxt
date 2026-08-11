"""Child-process transaction interruption drills.

The drill uses ``os._exit`` at named durable boundaries. It demonstrates abrupt
interpreter termination and explicit recovery behavior. It does not claim
physical power-loss or filesystem portability.
"""

from __future__ import unicode_literals

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict

from .multi_target import apply_multi_target, delete_plan, text_plan
from .mutation import read_text_snapshot
from .transaction_journal import (
    abandon_with_backup,
    cleanup_terminal,
    compensate,
    inspect_journal,
    list_journals,
    restore_backup,
    resume,
)
from .transaction_policy import fault_injection

SUPPORTED_POINTS = (
    "before_transaction_directory",
    "after_transaction_directory",
    "before_before_artifact",
    "after_before_artifact",
    "before_after_artifact",
    "after_after_artifact",
    "before_journal_publish",
    "after_journal_publish",
    "before_target_commit",
    "after_target_commit",
    "before_target_delete",
    "after_target_delete",
    "before_target_verify",
    "after_target_verify",
    "before_compensation_target_write",
    "after_compensation_target_write",
    "before_compensation_verify",
    "after_compensation_verify",
    "before_file_fsync",
    "after_file_fsync",
    "before_file_replace",
    "after_file_replace",
    "before_parent_fsync",
    "after_parent_fsync",
    "before_terminal_cleanup",
    "after_terminal_cleanup",
    "before_backup_copy",
    "after_backup_copy",
    "before_restore_working_copy",
    "after_restore_working_copy",
)
PRE_JOURNAL_POINTS = frozenset(
    (
        "before_transaction_directory",
        "after_transaction_directory",
        "before_before_artifact",
        "after_before_artifact",
        "before_after_artifact",
        "after_after_artifact",
        "before_journal_publish",
        "before_file_fsync",
        "after_file_fsync",
        "before_file_replace",
        "after_file_replace",
        "before_parent_fsync",
        "after_parent_fsync",
    )
)
EXIT_CODE = 91

DELETE_POINTS = frozenset(("before_target_delete", "after_target_delete"))
COMPENSATION_POINTS = frozenset(
    (
        "before_compensation_target_write",
        "after_compensation_target_write",
        "before_compensation_verify",
        "after_compensation_verify",
    )
)
CLEANUP_POINTS = frozenset(("before_terminal_cleanup", "after_terminal_cleanup"))
BACKUP_POINTS = frozenset(("before_backup_copy", "after_backup_copy"))
RESTORE_POINTS = frozenset(
    ("before_restore_working_copy", "after_restore_working_copy")
)


def run_fault_drill(
    point,
    workspace=None,
    recovery="inspect",
    timeout=20.0,
    keep=False,
    repeat_recovery=False,
):
    if point not in SUPPORTED_POINTS:
        raise ValueError("Unsupported transaction fault point: %s" % point)
    if recovery == "auto":
        if point == "before_transaction_directory":
            recovery = "inspect"
        elif point in CLEANUP_POINTS:
            recovery = "cleanup-terminal"
        elif point in COMPENSATION_POINTS:
            recovery = "compensate"
        elif point in BACKUP_POINTS or point in RESTORE_POINTS:
            recovery = "inspect"
        else:
            recovery = "cleanup-orphan" if point in PRE_JOURNAL_POINTS else "resume"
    if recovery not in (
        "inspect",
        "resume",
        "compensate",
        "cleanup-orphan",
        "cleanup-terminal",
    ):
        raise ValueError(
            "recovery must be inspect, resume, compensate, cleanup-orphan, "
            "cleanup-terminal, or auto."
        )
    owned = workspace is None
    root = os.path.abspath(workspace or tempfile.mkdtemp(prefix="lifetxt-fault-drill-"))
    os.makedirs(root, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "lifetxt.fault_drill",
        "--child",
        root,
        "--point",
        point,
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=float(timeout),
        universal_newlines=True,
    )
    journal_root = os.path.join(root, "journals")
    tx_dir = os.path.join(journal_root, "drill-%s" % point.replace("_", "-"))
    rows = list_journals(journal_root, include_terminal=True)
    journal_path = rows[0]["journal_path"] if rows else None
    before = _state(root, journal_path, tx_dir)
    stale_locks = []
    recovery_result = None
    recovery_error = None
    repeated_result = None
    repeated_error = None

    if recovery in ("resume", "compensate") and journal_path:
        stale_locks = _age_dead_child_locks(root)
        try:
            recovery_result = (
                resume(journal_path)
                if recovery == "resume"
                else compensate(journal_path)
            )
        except Exception as exc:
            recovery_error = str(exc)
        if repeat_recovery and recovery_error is None:
            try:
                repeated_result = (
                    resume(journal_path)
                    if recovery == "resume"
                    else compensate(journal_path)
                )
            except Exception as exc:
                repeated_error = str(exc)
    elif recovery == "cleanup-orphan":
        try:
            recovery_result = cleanup_orphan_transaction(root, tx_dir)
        except Exception as exc:
            recovery_error = str(exc)
    elif recovery == "cleanup-terminal":
        try:
            recovery_result = cleanup_terminal(
                journal_root, older_than_days=0, force=True
            )
        except Exception as exc:
            recovery_error = str(exc)
    elif recovery in ("resume", "compensate") and not journal_path:
        recovery_error = (
            "journal was not published; use cleanup-orphan after verifying targets"
        )

    after = _state(
        root, journal_path if os.path.exists(journal_path or "") else None, tx_dir
    )
    journal_expected = _journal_expected_after_child(point)
    evidence_matches = bool(journal_path) == journal_expected
    recovery_ok = recovery_error is None and repeated_error is None
    if recovery == "cleanup-orphan":
        recovery_ok = recovery_ok and bool(
            recovery_result and recovery_result.get("removed")
        )
    report = OrderedDict(
        (
            (
                "ok",
                completed.returncode == EXIT_CODE and evidence_matches and recovery_ok,
            ),
            ("point", point),
            (
                "boundary_phase",
                _boundary_phase(point),
            ),
            ("exit_code", completed.returncode),
            ("expected_exit_code", EXIT_CODE),
            ("workspace", root),
            ("transaction_directory", tx_dir),
            ("journal_expected", journal_expected),
            ("journal_path", journal_path),
            ("recovery", recovery),
            ("repeat_recovery", bool(repeat_recovery)),
            ("aged_stale_locks", stale_locks),
            ("before_recovery", before),
            ("recovery_result", recovery_result),
            ("recovery_error", recovery_error),
            ("repeated_recovery_result", repeated_result),
            ("repeated_recovery_error", repeated_error),
            ("after_recovery", after),
            ("stdout", completed.stdout),
            ("stderr", completed.stderr),
            (
                "scope",
                "simulated subprocess termination; not physical power-loss evidence",
            ),
        )
    )
    if owned and not keep:
        shutil.rmtree(root, ignore_errors=True)
        report["workspace"] = None
        report["transaction_directory"] = None
    return report


def run_fault_matrix(points=None, recovery="inspect", keep=False):
    selected = list(points or SUPPORTED_POINTS)
    results = []
    for point in selected:
        chosen_recovery = recovery
        if recovery == "auto":
            if point == "before_transaction_directory":
                chosen_recovery = "inspect"
            elif point in CLEANUP_POINTS:
                chosen_recovery = "cleanup-terminal"
            elif point in COMPENSATION_POINTS:
                chosen_recovery = "compensate"
            elif point in BACKUP_POINTS or point in RESTORE_POINTS:
                chosen_recovery = "inspect"
            else:
                chosen_recovery = (
                    "cleanup-orphan" if point in PRE_JOURNAL_POINTS else "resume"
                )
        results.append(run_fault_drill(point, recovery=chosen_recovery, keep=keep))
    return OrderedDict(
        (
            ("ok", all(row.get("ok") for row in results)),
            ("point_count", len(results)),
            ("passed", sum(1 for row in results if row.get("ok"))),
            ("failed", sum(1 for row in results if not row.get("ok"))),
            ("results", results),
            (
                "scope",
                "subprocess termination matrix; not physical power-loss evidence",
            ),
        )
    )


def cleanup_orphan_transaction(root, tx_dir):
    """Remove an unpublished transaction directory only when targets are unchanged."""
    root = os.path.abspath(root)
    tx_dir = os.path.abspath(tx_dir)
    journal_root = os.path.join(root, "journals")
    if os.path.commonpath([journal_root, tx_dir]) != journal_root:
        raise ValueError("Orphan transaction directory escapes the drill journal root.")
    if not os.path.isdir(tx_dir):
        raise ValueError("Orphan transaction directory does not exist.")
    if os.path.exists(os.path.join(tx_dir, "journal.json")):
        raise ValueError("Published journals require resume, compensate, or abandon.")
    files = _read_target_files(root)
    expected = {
        "first.txt": "before-first\n",
        "second.txt": "before-second\n",
        "delete.txt": None,
    }
    if files != expected:
        raise ValueError("Refusing orphan cleanup because target contents changed.")
    evidence = sorted(os.listdir(tx_dir))
    shutil.rmtree(tx_dir)
    return OrderedDict(
        (
            ("removed", True),
            ("transaction_directory", tx_dir),
            ("evidence_files", evidence),
            ("targets_verified_unchanged", True),
        )
    )


def _age_dead_child_locks(root):
    stale_locks = []
    # Epoch-near metadata is unambiguously older than the stale threshold and
    # avoids adding another direct host-clock boundary to the release baseline.
    old = 1.0
    for name in (
        "first.txt.lifetxt.lock",
        "second.txt.lifetxt.lock",
        "delete.txt.lifetxt.lock",
    ):
        lock_path = os.path.join(root, name)
        if os.path.exists(lock_path):
            os.utime(lock_path, (old, old))
            stale_locks.append(lock_path)
    return stale_locks


def child_main(root, point):
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    scenario = _scenario_for_point(point)

    if scenario == "delete":
        return _child_delete(root, point)
    if scenario == "compensation":
        return _child_compensation(root, point)
    if scenario == "cleanup":
        return _child_cleanup(root, point)
    if scenario == "backup":
        return _child_backup(root, point)
    if scenario == "restore":
        return _child_restore(root, point)

    first = os.path.join(root, "first.txt")
    second = os.path.join(root, "second.txt")
    from .atomic import atomic_write_text

    for path, text in ((first, "before-first\n"), (second, "before-second\n")):
        atomic_write_text(path, text)
    first_revision = read_text_snapshot(first).content_hash
    second_revision = read_text_snapshot(second).content_hash

    def handler(name, details):
        if name == point:
            os._exit(EXIT_CODE)

    with fault_injection(handler):
        apply_multi_target(
            [
                text_plan(first, lambda _text: "after-first\n", first_revision),
                text_plan(second, lambda _text: "after-second\n", second_revision),
            ],
            operation="fault_drill.%s" % point,
            journal_dir=os.path.join(root, "journals"),
            transaction_id="drill-%s" % point.replace("_", "-"),
        )
    return 0


def _install_exit_fault(point):
    def handler(name, details):
        if name == point:
            os._exit(EXIT_CODE)

    return fault_injection(handler)


def _write_fixture_files(root):
    from .atomic import atomic_write_text

    first = os.path.join(root, "first.txt")
    second = os.path.join(root, "second.txt")
    for path, text in ((first, "before-first\n"), (second, "before-second\n")):
        atomic_write_text(path, text)
    return first, second


def _child_delete(root, point):
    delete_target = os.path.join(root, "delete.txt")
    from .atomic import atomic_write_text

    atomic_write_text(delete_target, "delete-me\n")
    revision = read_text_snapshot(delete_target).content_hash
    with _install_exit_fault(point):
        apply_multi_target(
            [delete_plan(delete_target, revision, kind="text")],
            operation="fault_drill.%s" % point,
            journal_dir=os.path.join(root, "journals"),
            transaction_id="drill-%s" % point.replace("_", "-"),
        )
    return 0


def _child_compensation(root, point):
    first, second = _write_fixture_files(root)
    first_revision = read_text_snapshot(first).content_hash
    second_revision = read_text_snapshot(second).content_hash

    def fail_later(phase, _plan, index):
        if phase == "before_commit" and index == 1:
            raise RuntimeError("simulated second-target failure")

    with _install_exit_fault(point):
        apply_multi_target(
            [
                text_plan(first, lambda _text: "after-first\n", first_revision),
                text_plan(second, lambda _text: "after-second\n", second_revision),
            ],
            operation="fault_drill.%s" % point,
            journal_dir=os.path.join(root, "journals"),
            transaction_id="drill-%s" % point.replace("_", "-"),
            failure_hook=fail_later,
        )
    return 0


def _child_cleanup(root, point):
    first, second = _write_fixture_files(root)
    result = apply_multi_target(
        [
            text_plan(
                first,
                lambda _text: "after-first\n",
                read_text_snapshot(first).content_hash,
            ),
            text_plan(
                second,
                lambda _text: "after-second\n",
                read_text_snapshot(second).content_hash,
            ),
        ],
        operation="fault_drill.%s.prepare" % point,
        journal_dir=os.path.join(root, "journals"),
        transaction_id="drill-%s" % point.replace("_", "-"),
    )
    with _install_exit_fault(point):
        cleanup_terminal(os.path.dirname(os.path.dirname(result.journal_path)), 0, True)
    return 0


def _child_backup(root, point):
    result = _committed_fixture_transaction(root, point)
    with _install_exit_fault(point):
        abandon_with_backup(result.journal_path, os.path.join(root, "backups"))
    return 0


def _child_restore(root, point):
    result = _committed_fixture_transaction(root, point)
    abandoned = abandon_with_backup(result.journal_path, os.path.join(root, "backups"))
    with _install_exit_fault(point):
        restore_backup(
            abandoned["backup_path"],
            action="compensate",
            operator="alice",
            config={
                "transactions": {
                    "require_operator_authorization": True,
                    "authorized_operators": ["alice"],
                }
            },
            working_dir=os.path.join(root, "restore-work"),
        )
    return 0


def _committed_fixture_transaction(root, point):
    first, second = _write_fixture_files(root)
    return apply_multi_target(
        [
            text_plan(
                first,
                lambda _text: "after-first\n",
                read_text_snapshot(first).content_hash,
            ),
            text_plan(
                second,
                lambda _text: "after-second\n",
                read_text_snapshot(second).content_hash,
            ),
        ],
        operation="fault_drill.%s.prepare" % point,
        journal_dir=os.path.join(root, "journals"),
        transaction_id="drill-%s" % point.replace("_", "-"),
    )


def _scenario_for_point(point):
    if point in DELETE_POINTS:
        return "delete"
    if point in COMPENSATION_POINTS:
        return "compensation"
    if point in CLEANUP_POINTS:
        return "cleanup"
    if point in BACKUP_POINTS:
        return "backup"
    if point in RESTORE_POINTS:
        return "restore"
    return "commit"


def _journal_expected_after_child(point):
    if point in PRE_JOURNAL_POINTS:
        return False
    if point == "after_terminal_cleanup":
        return False
    return True


def _boundary_phase(point):
    if point in PRE_JOURNAL_POINTS:
        return "pre-journal"
    if point in DELETE_POINTS:
        return "delete"
    if point in COMPENSATION_POINTS:
        return "compensation"
    if point in CLEANUP_POINTS:
        return "terminal-cleanup"
    if point in BACKUP_POINTS:
        return "backup-copy"
    if point in RESTORE_POINTS:
        return "restore-working-copy"
    if point in ("before_target_verify", "after_target_verify"):
        return "verification"
    return "journal-or-commit"


def _read_target_files(root):
    files = OrderedDict()
    for name in ("first.txt", "second.txt", "delete.txt"):
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                files[name] = handle.read()
        else:
            files[name] = None
    return files


def _state(root, journal_path, tx_dir):
    record = None
    if journal_path:
        try:
            record = inspect_journal(journal_path)
        except Exception as exc:
            record = {"error": str(exc)}
    artifacts = []
    if tx_dir and os.path.isdir(tx_dir):
        artifacts = sorted(os.listdir(tx_dir))
    return OrderedDict(
        (
            ("files", _read_target_files(root)),
            ("transaction_directory_exists", bool(tx_dir and os.path.isdir(tx_dir))),
            ("artifact_names", artifacts),
            ("journal", record),
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    parser.add_argument("--point", choices=SUPPORTED_POINTS)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument(
        "--recovery",
        choices=(
            "inspect",
            "resume",
            "compensate",
            "cleanup-orphan",
            "cleanup-terminal",
            "auto",
        ),
        default="inspect",
    )
    parser.add_argument("--repeat-recovery", action="store_true")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    if args.child:
        if not args.point:
            parser.error("--child requires --point")
        return child_main(args.child, args.point)
    if args.matrix:
        report = run_fault_matrix(recovery=args.recovery, keep=args.keep)
    else:
        if not args.point:
            parser.error("--point is required unless --matrix is used")
        report = run_fault_drill(
            args.point,
            recovery=args.recovery,
            keep=args.keep,
            repeat_recovery=args.repeat_recovery,
        )
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
