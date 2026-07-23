import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import mutation
from lifetxt.multi_target import MultiTargetCommitError, apply_multi_target, text_plan
from lifetxt.transaction_journal import (
    TransactionJournalConflict,
    abandon_with_backup,
    cleanup_terminal,
    compensate,
    export_evidence,
    inspect_journal,
    list_journals,
    resume,
)


class TransactionJournalV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.journal_dir = os.path.join(self.root, "transactions")

    def tearDown(self):
        self.temp.cleanup()

    def path(self, name):
        return os.path.join(self.root, name)

    def write(self, name, value):
        path = self.path(name)
        os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(value)
        return path

    def read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_successful_transaction_records_exact_artifacts_and_terminal_state(self):
        first = self.write("one.txt", "one\n")
        second = self.write("two.txt", "two\n")
        result = apply_multi_target(
            [
                text_plan(first, lambda _text: "ONE\n", mutation.read_text_snapshot(first).content_hash),
                text_plan(second, lambda _text: "TWO\n", mutation.read_text_snapshot(second).content_hash),
            ],
            operation="journal.success",
            journal_dir=self.journal_dir,
        )
        self.assertTrue(result.transaction_id)
        self.assertTrue(os.path.exists(result.journal_path))
        report = inspect_journal(result.journal_path)
        self.assertEqual("committed", report["state"])
        self.assertFalse(report["recovery_required"])
        self.assertEqual(["after", "after"], [row["relation"] for row in report["observed_targets"]])
        self.assertEqual(2, len(report["targets"]))
        for target in report["targets"]:
            self.assertEqual("verified", target["commit_state"])
            self.assertTrue(os.path.exists(os.path.join(os.path.dirname(result.journal_path), target["before_artifact"])))
            self.assertTrue(os.path.exists(os.path.join(os.path.dirname(result.journal_path), target["after_artifact"])))

    def test_partial_failure_is_compensated_and_journal_is_terminal(self):
        first = self.write("one.txt", "one\n")
        second = self.write("two.txt", "two\n")
        calls = []

        def fail(phase, _plan, index):
            calls.append((phase, index))
            if phase == "before_commit" and index == 1:
                raise RuntimeError("boom")

        with self.assertRaises(MultiTargetCommitError):
            apply_multi_target(
                [
                    text_plan(first, lambda _text: "ONE\n", mutation.read_text_snapshot(first).content_hash),
                    text_plan(second, lambda _text: "TWO\n", mutation.read_text_snapshot(second).content_hash),
                ],
                operation="journal.compensate",
                journal_dir=self.journal_dir,
                failure_hook=fail,
            )
        self.assertEqual("one\n", self.read(first))
        self.assertEqual("two\n", self.read(second))
        journals = list_journals(self.journal_dir)
        self.assertEqual(1, len(journals))
        self.assertEqual("compensated", journals[0]["state"])
        self.assertFalse(journals[0]["recovery_required"])

    def test_resume_finishes_an_interrupted_prepared_transaction(self):
        first = self.write("one.txt", "one\n")
        second = self.write("two.txt", "two\n")
        result = apply_multi_target(
            [
                text_plan(first, lambda _text: "ONE\n", mutation.read_text_snapshot(first).content_hash),
                text_plan(second, lambda _text: "TWO\n", mutation.read_text_snapshot(second).content_hash),
            ],
            operation="journal.resume",
            journal_dir=self.journal_dir,
        )
        report = inspect_journal(result.journal_path)
        # Simulate a crash after restoring the first target to its before artifact.
        first_target = report["targets"][0]
        before_path = os.path.join(os.path.dirname(result.journal_path), first_target["before_artifact"])
        with open(before_path, "rb") as handle:
            mutation.atomic_write_bytes(first_target["path"], handle.read())
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data["state"] = "committing"
        with open(result.journal_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        resumed = resume(result.journal_path)
        self.assertEqual("committed", resumed["state"])
        self.assertEqual("ONE\n", self.read(first))
        self.assertEqual("TWO\n", self.read(second))

    def test_compensate_restores_all_targets_from_committed_state(self):
        first = self.write("one.txt", "one\n")
        second = self.write("two.txt", "two\n")
        result = apply_multi_target(
            [
                text_plan(first, lambda _text: "ONE\n", mutation.read_text_snapshot(first).content_hash),
                text_plan(second, lambda _text: "TWO\n", mutation.read_text_snapshot(second).content_hash),
            ],
            operation="journal.manual-compensate",
            journal_dir=self.journal_dir,
        )
        report = compensate(result.journal_path)
        self.assertEqual("compensated", report["state"])
        self.assertEqual("one\n", self.read(first))
        self.assertEqual("two\n", self.read(second))

    def test_recovery_refuses_diverged_target(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [text_plan(path, lambda _text: "ONE\n", mutation.read_text_snapshot(path).content_hash)],
            operation="journal.diverged",
            journal_dir=self.journal_dir,
        )
        mutation.atomic_write_bytes(path, b"third-party\n")
        with self.assertRaises(TransactionJournalConflict):
            compensate(result.journal_path)
        self.assertEqual("third-party\n", self.read(path))

    def test_abandon_requires_and_creates_a_complete_backup(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [text_plan(path, lambda _text: "ONE\n", mutation.read_text_snapshot(path).content_hash)],
            operation="journal.abandon",
            journal_dir=self.journal_dir,
        )
        backup_root = self.path("recovery-backups")
        report = abandon_with_backup(result.journal_path, backup_root)
        self.assertEqual("abandoned", report["state"])
        self.assertTrue(os.path.isfile(os.path.join(report["backup_path"], "journal.json")))

    def test_export_evidence_excludes_artifact_payloads(self):
        path = self.write("one.txt", "secret payload\n")
        result = apply_multi_target(
            [text_plan(path, lambda _text: "changed\n", mutation.read_text_snapshot(path).content_hash)],
            operation="journal.export",
            journal_dir=self.journal_dir,
        )
        output = self.path("evidence.json")
        evidence = export_evidence(result.journal_path, output)
        self.assertEqual(result.transaction_id, evidence["transaction_id"])
        text = self.read(output)
        self.assertNotIn("secret payload", text)
        self.assertIn("before_hash", text)

    def test_cleanup_only_removes_old_terminal_journals_with_force(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [text_plan(path, lambda _text: "ONE\n", mutation.read_text_snapshot(path).content_hash)],
            operation="journal.cleanup",
            journal_dir=self.journal_dir,
        )
        skipped = cleanup_terminal(self.journal_dir, older_than_days=0, force=False)
        self.assertTrue(os.path.exists(result.journal_path))
        self.assertEqual("--force is required", skipped["skipped"][0]["reason"])
        removed = cleanup_terminal(self.journal_dir, older_than_days=0, force=True)
        self.assertEqual([result.journal_path], removed["removed"])
        self.assertFalse(os.path.exists(result.journal_path))


if __name__ == "__main__":
    unittest.main()
