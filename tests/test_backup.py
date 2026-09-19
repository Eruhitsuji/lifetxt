"""Tests for the disaster-recovery backup core (#836/#841/#845/#846/#847):
lifetxt/backup.py's create/verify/restore/prune contract."""

import json
import os
import tempfile
import unittest
import zipfile

from lifetxt.backup import (
    BACKUP_FORMAT_VERSION,
    BackupError,
    create_backup,
    list_backups,
    prune_backups,
    restore_backup,
    verify_backup,
)


class CreateBackupTests(unittest.TestCase):
    def test_creates_a_valid_backup_from_a_single_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task id:t1\n")
            out = os.path.join(d, "backup.ltbackup")
            result = create_backup([src], out, lifetxt_version="9.9.9")
            self.assertTrue(os.path.isfile(out))
            self.assertEqual(BACKUP_FORMAT_VERSION, result.manifest["format"])
            self.assertEqual("complete", result.manifest["status"])
            self.assertEqual(1, result.manifest["file_count"])

    def test_multi_file_workspace_capture_records_relative_paths(self):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "workspace")
            os.makedirs(os.path.join(base, "sub"))
            a = os.path.join(base, "life.txt")
            b = os.path.join(base, "sub", "work.life.txt")
            for p, content in ((a, "[ ] T A\n"), (b, "[ ] T B\n")):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)
            out = os.path.join(d, "backup.ltbackup")
            result = create_backup([a, b], out, base_dir=base)
            paths = sorted(entry["path"] for entry in result.manifest["files"])
            self.assertEqual(["life.txt", "sub/work.life.txt"], paths)

    def test_every_file_has_a_sha256_digest(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            out = os.path.join(d, "backup.ltbackup")
            result = create_backup([src], out)
            entry = result.manifest["files"][0]
            self.assertEqual(64, len(entry["sha256"]))
            self.assertEqual(entry["size"], os.path.getsize(src))

    def test_missing_source_files_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            missing = os.path.join(d, "does-not-exist.txt")
            out = os.path.join(d, "backup.ltbackup")
            result = create_backup([src, missing], out)
            self.assertEqual(1, result.manifest["file_count"])

    def test_no_existing_source_paths_raises_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "does-not-exist.txt")
            out = os.path.join(d, "backup.ltbackup")
            with self.assertRaises(BackupError):
                create_backup([missing], out)
            self.assertFalse(os.path.exists(out))

    def test_repeated_backups_never_mutate_the_source(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            original = "[ ] T Task id:t1\n"
            with open(src, "w", encoding="utf-8") as f:
                f.write(original)
            create_backup([src], os.path.join(d, "b1.ltbackup"))
            create_backup([src], os.path.join(d, "b2.ltbackup"))
            with open(src, encoding="utf-8") as f:
                self.assertEqual(original, f.read())

    def test_failure_cleanup_leaves_no_partial_destination(self):
        # atomic_write_bytes always writes to a sibling temp file first;
        # a failure to even build the archive (no valid source) must
        # never create the destination file at all.
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "backup.ltbackup")
            with self.assertRaises(BackupError):
                create_backup([os.path.join(d, "nope.txt")], out)
            self.assertEqual([], [n for n in os.listdir(d) if not n.startswith(".")])

    def test_refuses_to_overwrite_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            out = os.path.join(d, "backup.ltbackup")
            create_backup([src], out)
            with open(out, "rb") as f:
                original_bytes = f.read()
            with self.assertRaises(BackupError):
                create_backup([src], out)
            with open(out, "rb") as f:
                self.assertEqual(original_bytes, f.read())

    def test_secret_bearing_paths_are_excluded_by_never_being_requested(self):
        # create_backup only ever archives exactly what it is given --
        # confirmed here by requesting only the life.txt source and
        # asserting a sibling "credentials" file never appears in the
        # manifest even though it exists on disk right next to it.
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "life.txt")
            secret = os.path.join(d, "rclone.conf")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            with open(secret, "w", encoding="utf-8") as f:
                f.write("[app]\ntoken = super-secret\n")
            out = os.path.join(d, "backup.ltbackup")
            result = create_backup([src], out)
            names = [entry["path"] for entry in result.manifest["files"]]
            self.assertEqual(["life.txt"], names)


class VerifyBackupTests(unittest.TestCase):
    def _make_backup(self, d, content="[ ] T Task id:t1\n"):
        src = os.path.join(d, "life.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write(content)
        out = os.path.join(d, "backup.ltbackup")
        create_backup([src], out)
        return out

    def test_a_valid_backup_verifies_ok(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            result = verify_backup(out)
            self.assertTrue(result.ok, result.errors)

    def test_a_payload_byte_change_fails_verification(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with zipfile.ZipFile(out, "a") as z:
                pass
            # Rewrite the archive with a tampered files/0 member.
            with zipfile.ZipFile(out, "r") as z:
                manifest_bytes = z.read("manifest.json")
                names = z.namelist()
            with zipfile.ZipFile(out, "w") as z:
                for name in names:
                    if name == "files/0":
                        z.writestr(name, b"TAMPERED")
                    elif name == "manifest.json":
                        z.writestr(name, manifest_bytes)
            result = verify_backup(out)
            self.assertFalse(result.ok)
            self.assertTrue(any("mismatch" in e for e in result.errors), result.errors)

    def test_a_same_length_byte_change_fails_checksum_verification(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d, content="[ ] T Task id:t1\n")
            with zipfile.ZipFile(out, "r") as z:
                manifest_bytes = z.read("manifest.json")
                original = z.read("files/0")
                names = z.namelist()
            tampered = bytearray(original)
            tampered[0] ^= 0xFF
            with zipfile.ZipFile(out, "w") as z:
                for name in names:
                    if name == "files/0":
                        z.writestr(name, bytes(tampered))
                    elif name == "manifest.json":
                        z.writestr(name, manifest_bytes)
            result = verify_backup(out)
            self.assertFalse(result.ok)
            self.assertTrue(any("checksum mismatch" in e for e in result.errors))

    def test_a_non_zip_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "not-a-backup.ltbackup")
            with open(out, "wb") as f:
                f.write(b"not a zip file")
            result = verify_backup(out)
            self.assertFalse(result.ok)

    def test_a_missing_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "backup.ltbackup")
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("files/0", b"data")
            result = verify_backup(out)
            self.assertFalse(result.ok)

    def test_an_incomplete_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with zipfile.ZipFile(out, "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                names = z.namelist()
                members = {n: z.read(n) for n in names if n != "manifest.json"}
            manifest["status"] = "in-progress"
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("manifest.json", json.dumps(manifest))
                for name, data in members.items():
                    z.writestr(name, data)
            result = verify_backup(out)
            self.assertFalse(result.ok)
            self.assertTrue(any("not marked complete" in e for e in result.errors))

    def test_an_unsupported_future_format_version_is_a_distinct_error(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with zipfile.ZipFile(out, "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                members = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
            manifest["format"] = "lifetxt-backup-v99"
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("manifest.json", json.dumps(manifest))
                for name, data in members.items():
                    z.writestr(name, data)
            result = verify_backup(out)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("Unsupported backup format" in e for e in result.errors)
            )

    def test_a_path_traversal_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with zipfile.ZipFile(out, "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                members = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
            manifest["files"][0]["path"] = "../../evil.txt"
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("manifest.json", json.dumps(manifest))
                for name, data in members.items():
                    z.writestr(name, data)
            result = verify_backup(out)
            self.assertFalse(result.ok)
            self.assertTrue(any("path traversal" in e for e in result.errors))

    def test_a_truncated_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with open(out, "rb") as f:
                data = f.read()
            with open(out, "wb") as f:
                f.write(data[: len(data) // 2])
            result = verify_backup(out)
            self.assertFalse(result.ok)

    def test_verification_never_mutates_the_archive(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            before = os.path.getsize(out)
            with open(out, "rb") as f:
                before_bytes = f.read()
            verify_backup(out)
            with open(out, "rb") as f:
                after_bytes = f.read()
            self.assertEqual(before, os.path.getsize(out))
            self.assertEqual(before_bytes, after_bytes)


class RestoreBackupTests(unittest.TestCase):
    def _make_backup(self, d):
        base = os.path.join(d, "src")
        os.makedirs(os.path.join(base, "sub"))
        a = os.path.join(base, "life.txt")
        b = os.path.join(base, "sub", "work.life.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("[ ] T A\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("[ ] T B\n")
        out = os.path.join(d, "backup.ltbackup")
        create_backup([a, b], out, base_dir=base)
        return out

    def test_restores_into_an_empty_destination(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            dest = os.path.join(d, "restored")
            result = restore_backup(out, dest)
            self.assertTrue(result.ok)
            self.assertEqual(2, len(result.restored))
            with open(os.path.join(dest, "life.txt"), encoding="utf-8") as f:
                self.assertEqual("[ ] T A\n", f.read())
            with open(
                os.path.join(dest, "sub", "work.life.txt"), encoding="utf-8"
            ) as f:
                self.assertEqual("[ ] T B\n", f.read())

    def test_existing_file_conflict_is_refused_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            dest = os.path.join(d, "restored")
            os.makedirs(dest)
            with open(os.path.join(dest, "life.txt"), "w", encoding="utf-8") as f:
                f.write("PRE-EXISTING\n")
            result = restore_backup(out, dest)
            self.assertFalse(result.ok)
            self.assertEqual(1, len(result.conflicts))
            with open(os.path.join(dest, "life.txt"), encoding="utf-8") as f:
                self.assertEqual("PRE-EXISTING\n", f.read())

    def test_explicit_overwrite_replaces_the_conflicting_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            dest = os.path.join(d, "restored")
            os.makedirs(dest)
            with open(os.path.join(dest, "life.txt"), "w", encoding="utf-8") as f:
                f.write("PRE-EXISTING\n")
            result = restore_backup(out, dest, overwrite=True)
            self.assertTrue(result.ok)
            with open(os.path.join(dest, "life.txt"), encoding="utf-8") as f:
                self.assertEqual("[ ] T A\n", f.read())

    def test_dry_run_previews_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            dest = os.path.join(d, "restored")
            result = restore_backup(out, dest, dry_run=True)
            self.assertEqual(2, len(result.restored))
            self.assertFalse(os.path.isdir(dest))

    def test_corrupted_backup_is_refused_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with zipfile.ZipFile(out, "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                members = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
            manifest["files"][0]["sha256"] = "0" * 64
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("manifest.json", json.dumps(manifest))
                for name, data in members.items():
                    z.writestr(name, data)
            dest = os.path.join(d, "restored")
            with self.assertRaises(BackupError):
                restore_backup(out, dest)
            self.assertFalse(os.path.isdir(dest))

    def test_unsafe_path_entry_is_refused_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._make_backup(d)
            with zipfile.ZipFile(out, "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                members = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
            manifest["files"][0]["path"] = "../escape.txt"
            with zipfile.ZipFile(out, "w") as z:
                z.writestr("manifest.json", json.dumps(manifest))
                for name, data in members.items():
                    z.writestr(name, data)
            dest = os.path.join(d, "restored")
            with self.assertRaises(BackupError):
                restore_backup(out, dest)
            self.assertFalse(os.path.exists(os.path.join(d, "escape.txt")))


class ListAndPruneBackupsTests(unittest.TestCase):
    def _backup_at(self, d, name, created_at):
        src = os.path.join(d, "life.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("[ ] T Task\n")
        out = os.path.join(d, name)
        create_backup([src], out, created_at=created_at)
        return out

    def test_list_backups_orders_newest_first_by_manifest_created_at(self):
        with tempfile.TemporaryDirectory() as d:
            self._backup_at(d, "b1.ltbackup", "2026-01-01T00:00:00Z")
            self._backup_at(d, "b2.ltbackup", "2026-03-01T00:00:00Z")
            self._backup_at(d, "b3.ltbackup", "2026-02-01T00:00:00Z")
            rows = list_backups(d)
            self.assertEqual(
                ["b2.ltbackup", "b3.ltbackup", "b1.ltbackup"],
                [name for name, _r in rows],
            )

    def test_prune_keeps_exactly_the_newest_n(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(5):
                self._backup_at(
                    d, "b%d.ltbackup" % i, "2026-01-0%dT00:00:00Z" % (i + 1)
                )
            result = prune_backups(d, keep_last=2)
            self.assertEqual(["b4.ltbackup", "b3.ltbackup"], result.kept)
            self.assertEqual(3, len(result.deleted))
            remaining = sorted(n for n in os.listdir(d) if n.endswith(".ltbackup"))
            self.assertEqual(["b3.ltbackup", "b4.ltbackup"], remaining)

    def test_prune_keep_last_1(self):
        with tempfile.TemporaryDirectory() as d:
            self._backup_at(d, "old.ltbackup", "2026-01-01T00:00:00Z")
            self._backup_at(d, "new.ltbackup", "2026-02-01T00:00:00Z")
            result = prune_backups(d, keep_last=1)
            self.assertEqual(["new.ltbackup"], result.kept)
            self.assertEqual(["old.ltbackup"], result.deleted)

    def test_prune_dry_run_lists_intended_deletions_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            self._backup_at(d, "old.ltbackup", "2026-01-01T00:00:00Z")
            self._backup_at(d, "new.ltbackup", "2026-02-01T00:00:00Z")
            result = prune_backups(d, keep_last=1, dry_run=True)
            self.assertEqual(["old.ltbackup"], result.deleted)
            self.assertTrue(os.path.exists(os.path.join(d, "old.ltbackup")))

    def test_incomplete_backups_are_never_counted_or_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            out = self._backup_at(d, "good.ltbackup", "2026-01-01T00:00:00Z")
            broken = os.path.join(d, "broken.ltbackup")
            with open(broken, "wb") as f:
                f.write(b"not a zip")
            result = prune_backups(d, keep_last=1)
            self.assertEqual(["good.ltbackup"], result.kept)
            self.assertEqual([], result.deleted)
            self.assertEqual(["broken.ltbackup"], result.ignored)
            self.assertTrue(os.path.exists(broken))

    def test_unrelated_files_in_the_directory_are_never_touched(self):
        with tempfile.TemporaryDirectory() as d:
            self._backup_at(d, "b1.ltbackup", "2026-01-01T00:00:00Z")
            unrelated = os.path.join(d, "readme.txt")
            with open(unrelated, "w", encoding="utf-8") as f:
                f.write("hello\n")
            result = prune_backups(d, keep_last=1)
            self.assertEqual([], result.deleted)
            self.assertTrue(os.path.exists(unrelated))

    def test_equal_or_close_timestamps_still_keep_exactly_n(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                self._backup_at(d, "b%d.ltbackup" % i, "2026-01-01T00:00:00Z")
            result = prune_backups(d, keep_last=2)
            self.assertEqual(2, len(result.kept))
            self.assertEqual(1, len(result.deleted))

    def test_keep_last_must_be_a_positive_integer(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(BackupError):
                prune_backups(d, keep_last=0)
            with self.assertRaises(BackupError):
                prune_backups(d, keep_last=-1)


if __name__ == "__main__":
    unittest.main()
