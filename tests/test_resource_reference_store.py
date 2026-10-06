import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from lifetxt.resource_reference_store import BindingStore, BindingUnavailable

H = hashlib.sha256(b"fixture").hexdigest()


class BindingStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bindings.sqlite"
        BindingStore.provision(self.path)
        self.store = BindingStore(self.path)
        self.addCleanup(self.store.close)

    def enroll(self, **kwargs):
        values = dict(
            workspace="a" * 64,
            source="b" * 64,
            item="task",
            association="file.txt",
            source_hash=H,
            source_identity=(1, 2, 3, 4),
            resource_identity=(1, 2, 5, 6),
            policy=H,
        )
        values.update(kwargs)
        return self.store.enroll(**values)

    def test_private_atomic_index_and_distinct_tokens(self):
        ref = self.enroll()
        self.assertRegex(ref, r"^att:v1:[0-9a-f]{32}$")
        row = self.store.get("a" * 64, ref)
        tokens = self.store.revisions(row, H, H, H)
        self.assertNotEqual(*tokens)
        self.assertEqual(tokens, self.store.revisions(row, H, H, H))
        for path in self.path.parent.iterdir():
            self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_restart_copy_backup_never_resurrects_reference(self):
        ref = self.enroll()
        copy = self.path.with_name("copy.sqlite")
        shutil.copyfile(self.path, copy)
        copy.chmod(0o600)
        self.store.close()
        for path in (self.path, copy):
            new = BindingStore(path)
            try:
                with self.assertRaises(BindingUnavailable):
                    new.get("a" * 64, ref)
            finally:
                new.close()

    def test_detach_recreate_new_generation(self):
        ref = self.enroll()
        self.store.detach(ref)
        fresh = self.enroll()
        self.assertNotEqual(ref, fresh)
        with self.assertRaises(BindingUnavailable):
            self.store.get("a" * 64, ref)

    def test_wrong_workspace_and_duplicate_enrollment(self):
        ref = self.enroll()
        with self.assertRaises(BindingUnavailable):
            self.store.get("c" * 64, ref)
        with self.assertRaises(BindingUnavailable):
            self.enroll()

    def test_collision_is_bounded_and_atomic(self):
        ref = self.enroll()
        with patch(
            "lifetxt.resource_reference_store.secrets.token_hex", return_value=ref[7:]
        ):
            with self.assertRaises(BindingUnavailable):
                self.enroll(item="other")
        self.assertEqual([], self.store.item_bindings("a" * 64, "b" * 64, "other"))

    def test_quota_counts_tokens_and_tombstones(self):
        self.store.max_total = 2
        ref = self.enroll()
        row = self.store.get("a" * 64, ref)
        with self.assertRaises(BindingUnavailable):
            self.store.revisions(row, H, H, H)
        self.assertEqual(
            0,
            self.store.connection.execute("SELECT count(*) FROM tokens").fetchone()[0],
        )
        self.store.detach(ref)
        self.enroll()
        with self.assertRaises(BindingUnavailable):
            self.enroll(item="third")

    def test_single_owner(self):
        with self.assertRaises(BindingUnavailable):
            BindingStore(self.path)
        self.assertIsNotNone(self.store.connection)

    def test_concurrent_unique_allocation(self):
        refs, errors = [], []

        def work(i):
            try:
                refs.append(self.enroll(item=str(i)))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual([], errors)
        self.assertEqual(8, len(set(refs)))

    def test_corrupt_lost_foreign_sidecars_and_symlink(self):
        self.store.close()
        backup = self.path.read_bytes()
        self.path.write_bytes(b"not sqlite")
        with self.assertRaises(BindingUnavailable):
            BindingStore(self.path)
        self.path.write_bytes(backup)
        for suffix in ("-wal", "-shm", "-journal"):
            side = Path(str(self.path) + suffix)
            side.write_bytes(b"restore")
            side.chmod(0o600)
            with self.assertRaises(BindingUnavailable):
                BindingStore(self.path)
            side.unlink()
        self.path.unlink()
        with self.assertRaises(BindingUnavailable):
            BindingStore(self.path)
        target = self.path.with_name("target")
        target.write_bytes(backup)
        target.chmod(0o600)
        self.path.symlink_to(target)
        with self.assertRaises(BindingUnavailable):
            BindingStore(self.path)

    def test_same_epoch_sqlite_restore_cannot_revive_detached_id(self):
        reference = self.enroll()
        backup = sqlite3.connect(":memory:")
        try:
            self.store.connection.backup(backup)
            self.store.detach(reference)
            backup.backup(self.store.connection)
            with self.assertRaises(BindingUnavailable):
                self.store.get("a" * 64, reference)
        finally:
            backup.close()

    def test_replaced_db_and_persisted_epoch_replay_fail_closed(self):
        ref = self.enroll()
        self.store.connection.execute("UPDATE meta SET value='old' WHERE key='epoch'")
        self.store.connection.commit()
        with self.assertRaises(BindingUnavailable):
            self.store.get("a" * 64, ref)

    def test_permissions_and_no_implicit_create(self):
        self.store.close()
        self.path.chmod(0o644)
        with self.assertRaises(BindingUnavailable):
            BindingStore(self.path)
        with self.assertRaises((BindingUnavailable, FileExistsError)):
            BindingStore.provision(self.path)
