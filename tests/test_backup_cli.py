"""Tests for lifetxt/backup_cli.py: the CLI orchestration layer over
lifetxt.backup/lifetxt.backup_remote (#836/#842/#843/#844/#847)."""

import os
import sys
import tempfile
import unittest

from lifetxt.backup import BackupError, list_backups
from lifetxt.backup_cli import (
    BackupCliError,
    read_status,
    resolve_destination,
    resolve_sources,
    run_create,
    run_prune,
    run_restore,
    run_scheduled,
    run_status,
    run_verify,
)


class ResolveTests(unittest.TestCase):
    def test_resolve_destination_prefers_explicit_over_config(self):
        self.assertEqual(
            "/explicit",
            resolve_destination({"backup": {"destination": "/config"}}, "/explicit"),
        )

    def test_resolve_destination_falls_back_to_config(self):
        self.assertEqual(
            "/config", resolve_destination({"backup": {"destination": "/config"}})
        )

    def test_resolve_destination_raises_when_neither_is_set(self):
        with self.assertRaises(BackupCliError):
            resolve_destination({})

    def test_resolve_sources_prefers_explicit_over_config(self):
        self.assertEqual(["a"], resolve_sources({"backup": {"sources": ["b"]}}, ["a"]))

    def test_resolve_sources_falls_back_to_config(self):
        self.assertEqual(["b"], resolve_sources({"backup": {"sources": ["b"]}}))

    def test_resolve_sources_raises_when_neither_is_set(self):
        with self.assertRaises(BackupCliError):
            resolve_sources({})


class RunCreateAndStatusTests(unittest.TestCase):
    def _source(self, d):
        src = os.path.join(d, "life.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("[ ] T Task id:t1\n")
        return src

    def test_create_writes_an_unambiguous_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            result = run_create([src], dest)
            self.assertTrue(os.path.isfile(result.path))
            self.assertTrue(result.path.startswith(dest))

    def test_status_reports_no_prior_backups_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "backups")
            status = run_status(dest)
            self.assertEqual(0, status["backup_count"])
            self.assertIsNone(status["latest_local_backup"])
            self.assertIsNone(status["last_attempt_at"])

    def test_status_reflects_a_completed_backup(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            run_create([src], dest)
            status = run_status(dest)
            self.assertEqual(1, status["backup_count"])
            self.assertIsNotNone(status["latest_local_backup"])


class RunVerifyRestorePruneTests(unittest.TestCase):
    def test_verify_delegates_to_the_shared_core(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            dest = os.path.join(d, "backups")
            result = run_create([src], dest)
            verify_result = run_verify(result.path)
            self.assertTrue(verify_result.ok)

    def test_restore_and_prune_delegate_to_the_shared_core(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            dest = os.path.join(d, "backups")
            result = run_create([src], dest)
            restore_dir = os.path.join(d, "restored")
            restore_result = run_restore(result.path, restore_dir)
            self.assertTrue(restore_result.ok)
            prune_result = run_prune(dest, keep_last=1)
            self.assertEqual(1, len(prune_result.kept))


class RunScheduledTests(unittest.TestCase):
    def _source(self, d):
        src = os.path.join(d, "life.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("[ ] T Task id:t1\n")
        return src

    def test_disabled_by_default_raises_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            config = {"backup": {"sources": [src], "destination": dest}}
            with self.assertRaises(BackupCliError):
                run_scheduled(config)
            self.assertFalse(os.path.isdir(dest))

    def test_enabled_run_creates_a_backup_and_records_success_status(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            config = {
                "backup": {
                    "enabled": True,
                    "sources": [src],
                    "destination": dest,
                }
            }
            outcome = run_scheduled(config)
            self.assertTrue(os.path.isfile(outcome["backup"].path))
            status = read_status(dest)
            self.assertTrue(status["last_attempt_ok"])
            self.assertIsNotNone(status["last_success_at"])

    def test_a_failed_local_creation_still_records_the_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "backups")
            config = {
                "backup": {
                    "enabled": True,
                    "sources": [os.path.join(d, "does-not-exist.txt")],
                    "destination": dest,
                }
            }
            with self.assertRaises(BackupError):
                run_scheduled(config)
            status = read_status(dest)
            self.assertFalse(status["last_attempt_ok"])

    def test_overlapping_runs_are_refused(self):
        from lifetxt.backup_cli import _BackupLock, _LOCK_FILENAME

        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            os.makedirs(dest)
            lock = _BackupLock(os.path.join(dest, _LOCK_FILENAME))
            lock.acquire()
            try:
                config = {
                    "backup": {"enabled": True, "sources": [src], "destination": dest}
                }
                with self.assertRaises(BackupCliError):
                    run_scheduled(config)
            finally:
                lock.release()

    def test_lock_is_released_after_a_successful_run_allowing_a_second_run(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            config = {
                "backup": {"enabled": True, "sources": [src], "destination": dest}
            }
            run_scheduled(config)
            # A second run must not be blocked by a stale lock from the first.
            run_scheduled(config)
            self.assertEqual(2, len(list_backups(dest)))

    def test_keep_last_applies_retention_after_a_successful_run(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            config = {
                "backup": {
                    "enabled": True,
                    "sources": [src],
                    "destination": dest,
                    "keep_last": 1,
                }
            }
            run_scheduled(config)
            run_scheduled(config)
            self.assertEqual(1, len(list_backups(dest)))

    def test_no_keep_last_never_deletes_anything(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            config = {
                "backup": {"enabled": True, "sources": [src], "destination": dest}
            }
            run_scheduled(config)
            run_scheduled(config)
            self.assertEqual(2, len(list_backups(dest)))

    def test_remote_upload_failure_is_recorded_independently_of_local_success(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            dest = os.path.join(d, "backups")
            config = {
                "backup": {
                    "enabled": True,
                    "sources": [src],
                    "destination": dest,
                    "remote": {
                        "backend": "rclone",
                        "target": "fakeremote:" + os.path.join(d, "faildest"),
                        "rclone_bin": [
                            sys.executable,
                            os.path.join(d, "no-such-fake-rclone.py"),
                        ],
                    },
                }
            }
            outcome = run_scheduled(config)
            # Local backup still succeeded even though remote upload failed.
            self.assertTrue(os.path.isfile(outcome["backup"].path))
            self.assertFalse(outcome["remote_uploaded"])
            status = read_status(dest)
            self.assertTrue(status["last_attempt_ok"])
            self.assertFalse(status["last_remote_upload_ok"])
            self.assertIsNotNone(status["last_remote_error"])


if __name__ == "__main__":
    unittest.main()
