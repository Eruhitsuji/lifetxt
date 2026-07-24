"""Child-process transaction interruption drills.

These drills use ``os._exit`` at a named durable boundary. They prove that an
abrupt Python process termination leaves inspectable recovery evidence; they do
not claim power-loss or filesystem portability.
"""

from __future__ import unicode_literals

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import OrderedDict

from .multi_target import apply_multi_target, text_plan
from .mutation import read_text_snapshot
from .transaction_journal import compensate, inspect_journal, list_journals, resume
from .transaction_policy import fault_injection

SUPPORTED_POINTS = (
    "before_journal_publish",
    "after_journal_publish",
    "before_target_commit",
    "after_target_commit",
    "before_file_replace",
    "after_file_replace",
    "before_parent_fsync",
    "after_parent_fsync",
)
EXIT_CODE = 91


def run_fault_drill(point, workspace=None, recovery="inspect", timeout=20.0, keep=False):
    if point not in SUPPORTED_POINTS:
        raise ValueError("Unsupported transaction fault point: %s" % point)
    if recovery not in ("inspect", "resume", "compensate"):
        raise ValueError("recovery must be inspect, resume, or compensate.")
    owned = workspace is None
    root = os.path.abspath(workspace or tempfile.mkdtemp(prefix="lifetxt-fault-drill-"))
    os.makedirs(root, exist_ok=True)
    command = [sys.executable, "-m", "lifetxt.fault_drill", "--child", root, "--point", point]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=float(timeout), text=True)
    journal_root = os.path.join(root, "journals")
    rows = list_journals(journal_root, include_terminal=True)
    journal_path = rows[0]["journal_path"] if rows else None
    before = _state(root, journal_path)
    stale_locks = []
    if journal_path and recovery != "inspect":
        # The killed child cannot release sidecar locks. Age the locks beyond the
        # documented stale threshold so normal PID/host validation performs the
        # same cleanup an operator would authorize after confirming the process is gone.
        old = max(0.0, __import__("time").time() - 301.0)
        for name in ("first.txt.lifetxt.lock", "second.txt.lifetxt.lock"):
            lock_path = os.path.join(root, name)
            if os.path.exists(lock_path):
                os.utime(lock_path, (old, old))
                stale_locks.append(lock_path)
    recovery_result = None
    recovery_error = None
    if journal_path and recovery != "inspect":
        try:
            recovery_result = resume(journal_path) if recovery == "resume" else compensate(journal_path)
        except Exception as exc:
            recovery_error = str(exc)
    after = _state(root, journal_path)
    report = OrderedDict(
        (
            ("ok", completed.returncode == EXIT_CODE and bool(journal_path) and recovery_error is None),
            ("point", point),
            ("exit_code", completed.returncode),
            ("expected_exit_code", EXIT_CODE),
            ("workspace", root),
            ("journal_path", journal_path),
            ("recovery", recovery),
            ("aged_stale_locks", stale_locks),
            ("before_recovery", before),
            ("recovery_result", recovery_result),
            ("recovery_error", recovery_error),
            ("after_recovery", after),
            ("stdout", completed.stdout),
            ("stderr", completed.stderr),
            ("scope", "abrupt interpreter termination; not power-loss portability evidence"),
        )
    )
    if owned and not keep:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
        report["workspace"] = None
    return report


def child_main(root, point):
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    first = os.path.join(root, "first.txt")
    second = os.path.join(root, "second.txt")
    from .atomic import atomic_write_text
    for path, text in ((first, "before-first\n"), (second, "before-second\n")):
        atomic_write_text(path, text)
    first_revision = read_text_snapshot(first).content_hash
    second_revision = read_text_snapshot(second).content_hash
    seen = {"count": 0}

    def handler(name, details):
        if name != point:
            return
        # Commit boundaries occur for each target. Exit at the first occurrence
        # so the drill is deterministic across sorted paths.
        seen["count"] += 1
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


def _state(root, journal_path):
    files = OrderedDict()
    for name in ("first.txt", "second.txt"):
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                files[name] = handle.read()
        else:
            files[name] = None
    record = None
    if journal_path:
        try:
            record = inspect_journal(journal_path)
        except Exception as exc:
            record = {"error": str(exc)}
    return OrderedDict((("files", files), ("journal", record)))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    parser.add_argument("--point", required=True, choices=SUPPORTED_POINTS)
    parser.add_argument("--recovery", choices=("inspect", "resume", "compensate"), default="inspect")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    if args.child:
        return child_main(args.child, args.point)
    report = run_fault_drill(args.point, recovery=args.recovery, keep=args.keep)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
