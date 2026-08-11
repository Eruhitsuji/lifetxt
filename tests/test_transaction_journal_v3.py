import json
import os
import errno
import shutil
import tempfile
import unittest
from unittest import mock

from lifetxt import mutation, transaction_journal
from lifetxt.multi_target import MultiTargetCommitError, apply_multi_target, text_plan
from lifetxt.transaction_journal import (
    TransactionJournalConflict,
    abandon_with_backup,
    archive_terminal,
    cleanup_terminal,
    compensate,
    export_evidence,
    inspect_journal,
    journal_version_matrix,
    list_journals,
    resume,
)
from lifetxt.transaction_policy import TransactionPolicyError, fault_injection


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

    def temporary_names(self, directory):
        return sorted(
            name for name in os.listdir(directory) if name.startswith(".lifetxt-tx-")
        )

    def force_journal_state(self, journal_path, state):
        with open(journal_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        record["state"] = state
        with open(journal_path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        return record

    def test_durable_write_retries_transient_replace_permission_refusal(self):
        target = self.write("journal.json", "old\n")
        attempts = []

        def fail_twice(point, details):
            if point != "before_file_replace":
                return
            attempts.append(details["attempt"])
            if len(attempts) <= 2:
                raise PermissionError(5, "simulated WinError 5")

        with (
            mock.patch.object(
                transaction_journal,
                "_REPLACE_PERMISSION_RETRY_OS_NAMES",
                frozenset((os.name,)),
            ),
            mock.patch.object(
                transaction_journal,
                "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS",
                (0.0, 0.0, 0.0),
            ),
            mock.patch.object(transaction_journal.time, "sleep") as sleep,
            fault_injection(fail_twice),
        ):
            transaction_journal._write_bytes_durable(target, b"new\n")

        self.assertEqual("new\n", self.read(target))
        self.assertEqual([1, 2, 3], attempts)
        self.assertEqual(2, sleep.call_count)
        self.assertEqual([], self.temporary_names(os.path.dirname(target)))

    def test_replace_permission_retry_is_platform_scoped(self):
        target = self.write("journal.json", "old\n")
        attempts = []

        def fail(point, details):
            if point == "before_file_replace":
                attempts.append(details["attempt"])
                raise PermissionError(5, "simulated WinError 5")

        with (
            mock.patch.object(
                transaction_journal,
                "_REPLACE_PERMISSION_RETRY_OS_NAMES",
                frozenset(),
            ),
            mock.patch.object(
                transaction_journal,
                "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS",
                (0.0, 0.0),
            ),
            mock.patch.object(transaction_journal.time, "sleep") as sleep,
            fault_injection(fail),
        ):
            with self.assertRaises(PermissionError):
                transaction_journal._write_bytes_durable(target, b"new\n")

        self.assertEqual("old\n", self.read(target))
        self.assertEqual([1], attempts)
        sleep.assert_not_called()
        self.assertEqual([], self.temporary_names(os.path.dirname(target)))

    def test_exhausted_journal_replace_retry_leaves_transaction_recoverable(self):
        target = self.write("one.txt", "one\n")
        revision = mutation.read_text_snapshot(target).content_hash
        journal_attempts = []

        def fail_journal_state_update(point, details):
            if point != "before_file_replace":
                return
            if os.path.basename(details["path"]) != "journal.json":
                return
            journal_attempts.append(details["attempt"])
            if len(journal_attempts) >= 2:
                raise PermissionError(5, "simulated WinError 5")

        with (
            mock.patch.object(
                transaction_journal,
                "_REPLACE_PERMISSION_RETRY_OS_NAMES",
                frozenset((os.name,)),
            ),
            mock.patch.object(
                transaction_journal,
                "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS",
                (0.0, 0.0),
            ),
            mock.patch.object(transaction_journal.time, "sleep") as sleep,
            fault_injection(fail_journal_state_update),
        ):
            with self.assertRaises(PermissionError):
                apply_multi_target(
                    [
                        text_plan(
                            target,
                            lambda _text: "ONE\n",
                            revision,
                        )
                    ],
                    operation="journal.replace-refusal",
                    journal_dir=self.journal_dir,
                    transaction_id="replace-refusal",
                )

        self.assertEqual([1, 1, 2, 3], journal_attempts)
        self.assertEqual(2, sleep.call_count)
        self.assertEqual("one\n", self.read(target))
        journal_path = os.path.join(self.journal_dir, "replace-refusal", "journal.json")
        report = inspect_journal(journal_path)
        self.assertEqual("prepared", report["state"])
        self.assertTrue(report["recovery_required"])
        self.assertEqual(
            ["before"], [row["relation"] for row in report["observed_targets"]]
        )
        self.assertIn("resume", report["available_actions"])
        self.assertIn("compensate", report["available_actions"])
        self.assertIn("abandon", report["available_actions"])

        resumed = resume(journal_path)
        self.assertEqual("committed", resumed["state"])
        self.assertEqual("ONE\n", self.read(target))

    def test_capacity_policy_refuses_before_publication_without_authoritative_change(
        self,
    ):
        target = self.write("one.txt", "one\n")
        with self.assertRaisesRegex(TransactionPolicyError, "per-transaction limit"):
            apply_multi_target(
                [
                    text_plan(
                        target,
                        lambda _text: "ONE\n",
                        mutation.read_text_snapshot(target).content_hash,
                    )
                ],
                operation="journal.capacity-preflight",
                journal_dir=self.journal_dir,
                transaction_policy=dict(
                    transaction_journal.policy_from_config(),
                    max_transaction_bytes=1024,
                ),
            )

        self.assertEqual("one\n", self.read(target))
        self.assertEqual([], list_journals(self.journal_dir))

    def test_disk_full_before_journal_publication_leaves_no_success_or_target_change(
        self,
    ):
        target = self.write("one.txt", "one\n")

        def fail_before_publish(point, details):
            if point != "before_file_fsync":
                return
            if os.path.basename(details["path"]) == "journal.json":
                raise OSError(errno.ENOSPC, "simulated disk full")

        with fault_injection(fail_before_publish):
            with self.assertRaisesRegex(OSError, "simulated disk full"):
                apply_multi_target(
                    [
                        text_plan(
                            target,
                            lambda _text: "ONE\n",
                            mutation.read_text_snapshot(target).content_hash,
                        )
                    ],
                    operation="journal.disk-full-before-publish",
                    journal_dir=self.journal_dir,
                    transaction_id="disk-full-before-publish",
                )

        self.assertEqual("one\n", self.read(target))
        self.assertEqual([], list_journals(self.journal_dir))
        tx_dir = os.path.join(self.journal_dir, "disk-full-before-publish")
        self.assertTrue(os.path.isdir(tx_dir))
        self.assertFalse(os.path.exists(os.path.join(tx_dir, "journal.json")))
        self.assertEqual([], self.temporary_names(tx_dir))

    def test_quota_failure_after_publication_is_inspectable_then_recoverable(self):
        target = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    target,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(target).content_hash,
                )
            ],
            operation="journal.quota-recovery",
            journal_dir=self.journal_dir,
        )
        report = inspect_journal(result.journal_path)
        target_record = report["targets"][0]
        with open(
            os.path.join(
                os.path.dirname(result.journal_path), target_record["before_artifact"]
            ),
            "rb",
        ) as handle:
            mutation.atomic_write_bytes(target, handle.read())
        self.force_journal_state(result.journal_path, "committing")
        failures = []

        def fail_once_on_recovery_write(point, _details):
            if point == "before_recovery_target_write" and not failures:
                failures.append(point)
                raise OSError(getattr(errno, "EDQUOT", errno.ENOSPC), "simulated quota")

        with fault_injection(fail_once_on_recovery_write):
            with self.assertRaisesRegex(OSError, "simulated quota"):
                resume(result.journal_path)

        failed = inspect_journal(result.journal_path)
        self.assertEqual("resume_failed", failed["state"])
        self.assertIn("Storage capacity failure", failed["last_error"])
        self.assertEqual("before", failed["observed_targets"][0]["relation"])

        restored = resume(result.journal_path)
        self.assertEqual("committed", restored["state"])
        self.assertEqual("ONE\n", self.read(target))

    def test_permission_failure_during_compensation_is_diagnostic_and_repeatable(self):
        target = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    target,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(target).content_hash,
                )
            ],
            operation="journal.permission-compensation",
            journal_dir=self.journal_dir,
        )
        failures = []

        def deny_compensation(point, _details):
            if point == "before_recovery_target_write":
                failures.append(point)
                raise PermissionError(errno.EACCES, "simulated permission denied")

        for _attempt in range(2):
            with fault_injection(deny_compensation):
                with self.assertRaisesRegex(PermissionError, "simulated permission"):
                    compensate(result.journal_path)
            failed = inspect_journal(result.journal_path)
            self.assertEqual("compensation_failed", failed["state"])
            self.assertIn("Storage permission failure", failed["last_error"])
            self.assertEqual("after", failed["observed_targets"][0]["relation"])
            self.assertEqual("ONE\n", self.read(target))

        restored = compensate(result.journal_path)
        self.assertEqual("compensated", restored["state"])
        self.assertEqual("one\n", self.read(target))
        self.assertEqual(2, len(failures))

    @unittest.skipUnless(os.name == "nt", "Windows byte-range locking evidence only")
    def test_windows_locked_target_refuses_replace_then_recovers_after_release(self):
        import msvcrt

        target = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    target,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(target).content_hash,
                )
            ],
            operation="journal.windows-lock-interference",
            journal_dir=self.journal_dir,
        )
        self.assertEqual("ONE\n", self.read(target))

        report = inspect_journal(result.journal_path)
        before_path = os.path.join(
            os.path.dirname(result.journal_path),
            report["targets"][0]["before_artifact"],
        )
        with open(before_path, "rb") as handle:
            mutation.atomic_write_bytes(target, handle.read())
        self.force_journal_state(result.journal_path, "committing")

        with open(target, "r+b") as locked:
            msvcrt.locking(locked.fileno(), msvcrt.LK_LOCK, 1)
            try:
                with self.assertRaises(PermissionError):
                    resume(result.journal_path)
            finally:
                msvcrt.locking(locked.fileno(), msvcrt.LK_UNLCK, 1)

        failed = inspect_journal(result.journal_path)
        self.assertEqual("resume_failed", failed["state"])
        self.assertIn("Storage permission failure", failed["last_error"])
        self.assertEqual("before", failed["observed_targets"][0]["relation"])
        self.assertEqual("one\n", self.read(target))

        recovered = resume(result.journal_path)
        self.assertEqual("committed", recovered["state"])
        self.assertEqual("ONE\n", self.read(target))

    def test_successful_transaction_records_exact_artifacts_and_terminal_state(self):
        first = self.write("one.txt", "one\n")
        second = self.write("two.txt", "two\n")
        result = apply_multi_target(
            [
                text_plan(
                    first,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(first).content_hash,
                ),
                text_plan(
                    second,
                    lambda _text: "TWO\n",
                    mutation.read_text_snapshot(second).content_hash,
                ),
            ],
            operation="journal.success",
            journal_dir=self.journal_dir,
        )
        self.assertTrue(result.transaction_id)
        self.assertTrue(os.path.exists(result.journal_path))
        report = inspect_journal(result.journal_path)
        self.assertEqual("committed", report["state"])
        self.assertFalse(report["recovery_required"])
        self.assertEqual(
            ["after", "after"], [row["relation"] for row in report["observed_targets"]]
        )
        self.assertEqual(2, len(report["targets"]))
        for target in report["targets"]:
            self.assertEqual("verified", target["commit_state"])
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        os.path.dirname(result.journal_path), target["before_artifact"]
                    )
                )
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        os.path.dirname(result.journal_path), target["after_artifact"]
                    )
                )
            )

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
                    text_plan(
                        first,
                        lambda _text: "ONE\n",
                        mutation.read_text_snapshot(first).content_hash,
                    ),
                    text_plan(
                        second,
                        lambda _text: "TWO\n",
                        mutation.read_text_snapshot(second).content_hash,
                    ),
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
                text_plan(
                    first,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(first).content_hash,
                ),
                text_plan(
                    second,
                    lambda _text: "TWO\n",
                    mutation.read_text_snapshot(second).content_hash,
                ),
            ],
            operation="journal.resume",
            journal_dir=self.journal_dir,
        )
        report = inspect_journal(result.journal_path)
        # Simulate a crash after restoring the first target to its before artifact.
        first_target = report["targets"][0]
        before_path = os.path.join(
            os.path.dirname(result.journal_path), first_target["before_artifact"]
        )
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
                text_plan(
                    first,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(first).content_hash,
                ),
                text_plan(
                    second,
                    lambda _text: "TWO\n",
                    mutation.read_text_snapshot(second).content_hash,
                ),
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
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
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
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.abandon",
            journal_dir=self.journal_dir,
        )
        backup_root = self.path("recovery-backups")
        report = abandon_with_backup(result.journal_path, backup_root)
        self.assertEqual("abandoned", report["state"])
        self.assertTrue(
            os.path.isfile(os.path.join(report["backup_path"], "journal.json"))
        )
        if os.name != "nt":
            self.assertEqual(0, os.stat(report["backup_path"]).st_mode & 0o077)

    def test_archive_backup_and_restore_use_declared_evidence_storage_boundary(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.profile-boundary",
            journal_dir=self.journal_dir,
        )
        archive_root = self.path("archives")
        archived = archive_terminal(
            self.journal_dir, archive_root, older_than_days=0, force=True
        )
        self.assertEqual(1, len(archived["archived"]))
        backup_dir = archived["archived"][0]["archive_path"]
        if os.name != "nt":
            self.assertEqual(0, os.stat(archive_root).st_mode & 0o077)
        report = transaction_journal.restore_backup(backup_dir, action="inspect")
        self.assertTrue(report["ok"])
        self.assertTrue(report["verification"]["ok"])

    def test_unsupported_evidence_storage_profile_refuses_before_journal_mutation(self):
        path = self.write("one.txt", "one\n")
        with self.assertRaisesRegex(
            TransactionPolicyError, "Unusable evidence storage profile"
        ):
            apply_multi_target(
                [
                    text_plan(
                        path,
                        lambda _text: "ONE\n",
                        mutation.read_text_snapshot(path).content_hash,
                    )
                ],
                operation="journal.unsupported-profile",
                journal_dir=self.journal_dir,
                transaction_policy=dict(
                    transaction_journal.policy_from_config(
                        {"transactions": {"evidence_storage_profile": "encrypted-v1"}}
                    )
                ),
            )
        self.assertEqual("one\n", self.read(path))
        self.assertEqual([], list_journals(self.journal_dir))

    def test_export_evidence_excludes_artifact_payloads(self):
        path = self.write("one.txt", "secret payload\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "changed\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
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
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.cleanup",
            journal_dir=self.journal_dir,
        )
        skipped = cleanup_terminal(self.journal_dir, older_than_days=0, force=False)
        self.assertTrue(os.path.exists(result.journal_path))
        self.assertEqual("--force is required", skipped["skipped"][0]["reason"])
        removed = cleanup_terminal(self.journal_dir, older_than_days=0, force=True)
        self.assertEqual([result.journal_path], removed["removed"])
        self.assertFalse(os.path.exists(result.journal_path))

    def test_missing_journal_metadata_is_distinct_from_missing_payload_artifact(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.missing-evidence",
            journal_dir=self.journal_dir,
        )
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            missing_metadata = json.load(handle)
        missing_metadata.pop("state")
        metadata_path = self.path("missing-state-journal.json")
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(missing_metadata, handle)
        with self.assertRaisesRegex(
            transaction_journal.TransactionJournalError, "missing state"
        ):
            inspect_journal(metadata_path)

        report = inspect_journal(result.journal_path)
        target = report["targets"][0]
        before_path = os.path.join(
            os.path.dirname(result.journal_path), target["before_artifact"]
        )
        with open(before_path, "rb") as handle:
            mutation.atomic_write_bytes(path, handle.read())
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            recovery_record = json.load(handle)
        recovery_record["state"] = "committing"
        with open(result.journal_path, "w", encoding="utf-8") as handle:
            json.dump(recovery_record, handle)
        os.unlink(os.path.join(os.path.dirname(result.journal_path), "after-000.bin"))
        with self.assertRaisesRegex(
            transaction_journal.TransactionJournalError, "Missing recovery artifact"
        ):
            resume(result.journal_path)
        self.assertEqual("one\n", self.read(path))

    def test_corrupted_recovery_artifacts_are_rejected_before_mutation(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.corrupt-artifact",
            journal_dir=self.journal_dir,
        )
        report = inspect_journal(result.journal_path)
        target = report["targets"][0]
        tx_dir = os.path.dirname(result.journal_path)
        before_path = os.path.join(tx_dir, target["before_artifact"])
        after_path = os.path.join(tx_dir, target["after_artifact"])
        with open(before_path, "rb") as handle:
            mutation.atomic_write_bytes(path, handle.read())
        with open(after_path, "wb") as handle:
            handle.write(b"corrupted\n")
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            recovery_record = json.load(handle)
        recovery_record["state"] = "committing"
        with open(result.journal_path, "w", encoding="utf-8") as handle:
            json.dump(recovery_record, handle)

        first_message = None
        for _attempt in range(2):
            with self.assertRaisesRegex(
                transaction_journal.TransactionJournalError,
                "Recovery artifact hash mismatch",
            ) as caught:
                resume(result.journal_path)
            if first_message is None:
                first_message = str(caught.exception)
            else:
                self.assertEqual(first_message, str(caught.exception))
            self.assertEqual("one\n", self.read(path))

        inspected = inspect_journal(result.journal_path)
        self.assertTrue(inspected["recovery_required"])
        self.assertEqual("before", inspected["observed_targets"][0]["relation"])
        self.assertIn("resume", inspected["available_actions"])

    def test_journal_version_matrix_and_newer_refusal_are_explicit(self):
        matrix = journal_version_matrix()
        self.assertEqual("unsupported", matrix["older"]["migration"])
        self.assertEqual("supported", matrix[1]["mutation"])
        self.assertEqual(
            ["inspect", "export"],
            transaction_journal.available_actions({"schema_version": 99}),
        )
        path = self.write("versioned.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.newer-version",
            journal_dir=self.journal_dir,
        )
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        record["schema_version"] = 99
        with open(result.journal_path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        inspected = inspect_journal(result.journal_path)
        self.assertTrue(inspected["read_only"])
        self.assertEqual("newer", inspected["version_compatibility"]["state"])
        self.assertEqual(["inspect", "export"], inspected["available_actions"])
        with self.assertRaisesRegex(
            transaction_journal.TransactionJournalError, "Unsupported"
        ):
            resume(result.journal_path)
        self.assertEqual("ONE\n", self.read(path))

    def test_corrupted_compensation_artifact_keeps_committed_state_unchanged(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.corrupt-compensate",
            journal_dir=self.journal_dir,
        )
        report = inspect_journal(result.journal_path)
        before_path = os.path.join(
            os.path.dirname(result.journal_path),
            report["targets"][0]["before_artifact"],
        )
        with open(before_path, "wb") as handle:
            handle.write(b"corrupted\n")

        with self.assertRaisesRegex(
            transaction_journal.TransactionJournalError,
            "Recovery artifact hash mismatch",
        ):
            compensate(result.journal_path)
        self.assertEqual("ONE\n", self.read(path))

    def test_corrupted_backup_manifest_is_rejected_before_restore_mutates_targets(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.corrupt-backup",
            journal_dir=self.journal_dir,
        )
        backup_root = self.path("corrupt-backups")
        backup = abandon_with_backup(result.journal_path, backup_root)
        manifest = os.path.join(backup["backup_path"], "integrity-manifest.json")
        with open(manifest, "a", encoding="utf-8") as handle:
            handle.write("corrupted\n")

        with self.assertRaisesRegex(
            transaction_journal.TransactionJournalError,
            "Backup integrity verification failed",
        ):
            transaction_journal.restore_backup(
                backup["backup_path"], action="compensate"
            )
        self.assertEqual("ONE\n", self.read(path))

    def test_missing_backup_manifest_is_rejected_as_backup_integrity_failure(self):
        path = self.write("one.txt", "one\n")
        result = apply_multi_target(
            [
                text_plan(
                    path,
                    lambda _text: "ONE\n",
                    mutation.read_text_snapshot(path).content_hash,
                )
            ],
            operation="journal.missing-backup-manifest",
            journal_dir=self.journal_dir,
        )
        backup_root = self.path("missing-manifest-backups")
        backup = abandon_with_backup(result.journal_path, backup_root)
        os.unlink(os.path.join(backup["backup_path"], "integrity-manifest.json"))

        with self.assertRaisesRegex(
            transaction_journal.TransactionJournalError,
            "Backup integrity verification failed",
        ):
            transaction_journal.restore_backup(
                backup["backup_path"], action="compensate"
            )
        self.assertEqual("ONE\n", self.read(path))
        shutil.rmtree(backup["backup_path"], ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
