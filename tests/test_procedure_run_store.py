from concurrent.futures import ThreadPoolExecutor
import codecs
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lifetxt.procedure_definition import ProcedureError
from lifetxt.procedure_run_store import inspect_run, write_run, read_log, source_handle
from lifetxt.transaction_journal import journal_directory, list_journals, resume
from lifetxt.multi_target import MultiTargetCommitError
from tests.test_procedure_definition import SAMPLE


class RunStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.txt"
        self.log = self.root / "run.txt"
        self.source.write_text(SAMPLE)
        self.counter = 0

    def arguments(self, verb, run_id=None):
        snap = inspect_run(self.source, "r", self.log, run_id)
        state = snap.state
        self.counter += 1
        return dict(
            actor="alice",
            request_id="req%d" % self.counter,
            expected_template_revision=state.template_revision
            if state
            else snap.template_revision,
            expected_log_revision=snap.log_revision,
            expected_step=state.cursor.step if state else snap.start_step,
            expected_sequence=state.sequence if state else 0,
            run_id=run_id,
            allow_loops=verb == "start",
        )

    def write(self, verb, run_id=None, **changes):
        args = self.arguments(verb, run_id)
        args.update(changes)
        return write_run(self.source, "r", self.log, verb, **args)

    def test_full_lifecycle_restart_two_runs_and_template_unchanged(self):
        original = self.source.read_bytes()
        first = self.write("start").state.run_id
        second = self.write("start").state.run_id
        self.write("next", first)
        self.write("choose", first, choice="yes")
        self.write("pause", first)
        state = inspect_run(self.source, "r", self.log, first).state
        self.assertEqual(("paused", "e"), (state.cursor.status, state.cursor.step))
        self.write("resume", first)
        done = self.write("finish", first)
        self.assertEqual("completed", done.state.cursor.status)
        self.assertEqual("a", read_log(self.log).states[second].cursor.step)
        self.assertEqual(original, self.source.read_bytes())
        self.assertTrue(list_journals(journal_directory(writable_path=self.log)))

    def test_stale_log_step_sequence_actor_template_and_duplicate_requests(self):
        run = self.write("start").state.run_id
        args = self.arguments("next", run)
        result = write_run(self.source, "r", self.log, "next", **args)
        before = self.log.read_bytes()
        for change in (
            {},
            {"expected_log_revision": result.log_revision},
            {
                "expected_log_revision": result.log_revision,
                "request_id": "new",
                "expected_sequence": 0,
            },
            {
                "expected_log_revision": result.log_revision,
                "request_id": "new",
                "actor": "bob",
            },
            {
                "expected_log_revision": result.log_revision,
                "request_id": "new",
                "expected_template_revision": "f" * 64,
            },
        ):
            bad = dict(args)
            bad.update(change)
            with self.subTest(change=change), self.assertRaises(ProcedureError):
                write_run(self.source, "r", self.log, "next", **bad)
            self.assertEqual(before, self.log.read_bytes())

    def test_source_edit_blocks_continuation_but_preserves_disposition_and_inspection(
        self,
    ):
        run = self.write("start").state.run_id
        self.source.write_text("invalid changed definition")
        snap = inspect_run(self.source, "r", self.log, run)
        self.assertTrue(snap.blocked)
        with self.assertRaises(ProcedureError):
            self.write("next", run)
        self.write("pause", run)
        with self.assertRaises(ProcedureError):
            self.write("resume", run)
        self.assertEqual("abandoned", self.write("abandon", run).state.cursor.status)
        self.source.unlink()
        self.assertTrue(inspect_run(self.source, "r", self.log, run).blocked)

    def test_source_recheck_before_commit_and_postcommit_blocked_result(self):
        run = self.write("start").state.run_id
        before = self.log.read_bytes()

        def edit_before(phase, *_):
            if phase == "before_commit":
                self.source.write_text(SAMPLE + "# edited\n")

        with self.assertRaises(MultiTargetCommitError):
            self.write("next", run, failure_hook=edit_before)
        self.assertEqual(before, self.log.read_bytes())
        self.source.write_text(SAMPLE)

        def edit_after(phase, *_):
            if phase == "after_commit":
                self.source.write_text(SAMPLE + "# edited after\n")

        result = self.write("next", run, failure_hook=edit_after)
        self.assertTrue(result.blocked)
        self.assertEqual(2, result.state.sequence)

    def test_duplicate_writer_cas_one_winner(self):
        run = self.write("start").state.run_id
        args = self.arguments("next", run)

        def attempt(index):
            values = dict(args, request_id="writer%d" % index)
            try:
                return write_run(self.source, "r", self.log, "next", **values)
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, (1, 2)))
        self.assertEqual(1, sum(r is not None for r in results))
        self.assertEqual(2, read_log(self.log).states[run].sequence)

    def test_throw_after_commit_compensates_and_crash_requires_explicit_recovery(self):
        run = self.write("start").state.run_id
        before = self.log.read_bytes()

        def fail(phase, *_):
            if phase == "after_commit":
                raise RuntimeError("synthetic failure")

        with self.assertRaises(MultiTargetCommitError):
            self.write("next", run, failure_hook=fail)
        self.assertEqual(before, self.log.read_bytes())

        class Crash(BaseException):
            pass

        def crash(phase, *_):
            if phase == "after_commit":
                raise Crash()

        with self.assertRaises(Crash):
            self.write("next", run, failure_hook=crash)
        self.assertEqual(2, read_log(self.log).states[run].sequence)
        with self.assertRaises(ProcedureError):
            self.write("choose", run, choice="yes")
        pending = list_journals(
            journal_directory(writable_path=self.log), include_terminal=False
        )
        self.assertEqual(1, len(pending))
        resume(pending[0]["journal_path"])
        self.assertEqual("e", self.write("choose", run, choice="yes").state.cursor.step)

    def test_real_process_crash_resume_does_not_duplicate_event(self):
        run = self.write("start").state.run_id
        args = self.arguments("next", run)
        import json

        code = """import json,os,sys
from lifetxt.procedure_run_store import write_run
def crash(phase,*args):
 if phase=='after_commit':os._exit(23)
write_run(sys.argv[1],'r',sys.argv[2],'next',failure_hook=crash,**json.loads(sys.argv[3]))
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                str(self.source),
                str(self.log),
                json.dumps(args),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(23, result.returncode, result.stderr)
        with self.assertRaises(ProcedureError):
            self.write("choose", run, choice="yes")
        # Synthetic operator recovery: age the dead process's lock, then use
        # the existing journal resume contract (never silently clean real data).
        from lifetxt.mutation import FileLock

        lock = Path(FileLock(self.log).lock_path)
        if lock.exists():
            os.utime(lock, (0, 0))
        pending = list_journals(
            journal_directory(writable_path=self.log), include_terminal=False
        )
        resume(pending[0]["journal_path"])
        self.assertEqual(2, read_log(self.log).states[run].sequence)
        self.assertEqual("e", self.write("choose", run, choice="yes").state.cursor.step)

    def test_corrupt_or_ordinary_log_readonly_generated_aliases_refuse(self):
        for content in (
            "[ ] T ordinary\n",
            "[N] N procedure_event record:procedure_event\n",
        ):
            self.log.write_text(content)
            before = self.log.read_bytes()
            with self.assertRaises(ProcedureError):
                self.write("start")
            self.assertEqual(before, self.log.read_bytes())
        self.log.unlink()
        snap = inspect_run(self.source, "r", self.log)
        args = dict(
            actor="alice",
            request_id="req",
            expected_template_revision=snap.template_revision,
            expected_log_revision=snap.log_revision,
            expected_step="a",
            expected_sequence=0,
            allow_loops=True,
        )
        with self.assertRaises(ProcedureError):
            write_run(
                self.source,
                "r",
                self.log,
                "start",
                config={"generated_paths": [str(self.log)]},
                **args,
            )
        with self.assertRaises(ProcedureError):
            inspect_run(self.source, "r", self.source)
        if hasattr(os, "link"):
            os.link(self.source, self.log)
            with self.assertRaises(ProcedureError):
                inspect_run(self.source, "r", self.log)
            self.log.unlink()
        self.write("start")
        self.log.chmod(0o444)
        with self.assertRaises(ProcedureError):
            self.write("start")
        self.log.chmod(0o644)

    def test_bom_crlf_bounds_and_no_secret_in_journal_payload(self):
        self.source.write_text(
            SAMPLE.replace("Read this instruction.", "PRIVATE_BODY_SECRET")
        )
        first = self.write("start").state.run_id
        self.log.write_bytes(
            codecs.BOM_UTF8 + self.log.read_bytes().replace(b"\n", b"\r\n")
        )
        self.write("next", first)
        self.assertTrue(self.log.read_bytes().startswith(codecs.BOM_UTF8))
        self.assertIn(b"\r\n", self.log.read_bytes())
        for file in self.root.rglob("*"):
            if file.is_file() and file != self.source:
                self.assertNotIn(b"PRIVATE_BODY_SECRET", file.read_bytes())
        before = self.log.read_bytes()
        with patch("lifetxt.procedure_run_store.MAX_LOG_BYTES", len(before)):
            with self.assertRaises(ProcedureError):
                self.write("choose", first, choice="yes")
        self.assertEqual(before, self.log.read_bytes())

    def test_different_source_same_body_cannot_rebind_run(self):
        run = self.write("start").state.run_id
        other = self.root / "other.txt"
        other.write_text(SAMPLE)
        self.assertNotEqual(source_handle(other), source_handle(self.source))
        with self.assertRaises(ProcedureError):
            inspect_run(other, "r", self.log, run)

    def test_uncertain_request_lookup_is_readonly_and_keeps_original_sequence(self):
        result = self.write("start")
        run = result.state.run_id
        self.write("next", run)
        before = self.log.read_bytes()
        snapshot = inspect_run(self.source, "r", self.log, request_id="req1")
        self.assertEqual(
            (run, 1, "start"),
            (
                snapshot.receipt.run_id,
                snapshot.receipt.sequence,
                snapshot.receipt.event,
            ),
        )
        self.assertEqual(2, snapshot.state.sequence)
        self.assertEqual(before, self.log.read_bytes())
        with self.assertRaises(ProcedureError):
            inspect_run(self.source, "r", self.log, request_id="never-committed")

    def test_log_symlink_refused_and_oversized_source_can_be_abandoned(self):
        run = self.write("start").state.run_id
        other = self.root / "linked-log.txt"
        try:
            other.symlink_to(self.log)
        except (NotImplementedError, OSError):
            pass
        else:
            with self.assertRaises(ProcedureError):
                inspect_run(self.source, "r", other, run)
        with patch("lifetxt.procedure_run_store.MAX_SOURCE_BYTES", 2):
            self.assertTrue(inspect_run(self.source, "r", self.log, run).blocked)
            self.assertEqual(
                "abandoned", self.write("abandon", run).state.cursor.status
            )

    def test_atomic_write_failure_leaves_before_log_recoverable(self):
        run = self.write("start").state.run_id
        before = self.log.read_bytes()
        with patch(
            "lifetxt.mutation.atomic_write_bytes",
            side_effect=OSError("synthetic write failure"),
        ):
            with self.assertRaises(MultiTargetCommitError):
                self.write("next", run)
        self.assertEqual(before, self.log.read_bytes())
        self.assertEqual(1, read_log(self.log).states[run].sequence)

    def test_log_event_count_guard_refuses_without_change(self):
        run = self.write("start").state.run_id
        self.write("next", run)
        before = self.log.read_bytes()
        with patch("lifetxt.procedure_run_store.MAX_LOG_EVENTS", 2):
            with self.assertRaises(ProcedureError):
                self.write("choose", run, choice="yes")
        self.assertEqual(before, self.log.read_bytes())
