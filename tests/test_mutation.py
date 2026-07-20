import codecs
import json
import os
import socket
import tempfile
import threading
import time
import unittest

from lifetxt.mutation import (
    FileLock,
    LockTimeout,
    MISSING_HASH,
    MutationConflict,
    MutationOperation,
    apply_text_mutation,
    hash_bytes,
    hash_text,
    mutate_json,
    mutate_text,
    read_text_snapshot,
    write_text,
)


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_raw(self, data):
        with open(self.path, "wb") as handle:
            handle.write(data)

    def test_hash_helpers_use_exact_bytes(self):
        self.assertEqual(hash_bytes(b"abc"), hash_text("abc"))
        self.assertNotEqual(hash_text("abc"), hash_text("abc", bom=True))

    def test_missing_snapshot_has_explicit_hash(self):
        snapshot = read_text_snapshot(self.path, allow_missing=True)
        self.assertFalse(snapshot.exists)
        self.assertEqual(MISSING_HASH, snapshot.content_hash)

    def test_create_requires_create_policy(self):
        with self.assertRaises(FileNotFoundError):
            mutate_text(self.path, lambda text: "created\n")
        result = mutate_text(
            self.path,
            lambda text: text + "created\n",
            expected_hash=MISSING_HASH,
            operation="create",
            create=True,
        )
        self.assertTrue(result.created)
        self.assertTrue(result.changed)
        self.assertEqual("created\n", result.snapshot.text)

    def test_expected_hash_allows_one_update_and_rejects_stale_writer(self):
        self.write_raw(b"one\n")
        snapshot = read_text_snapshot(self.path)
        first = write_text(
            self.path,
            "two\n",
            expected_hash=snapshot.content_hash,
            operation="first",
        )
        self.assertTrue(first.changed)
        with self.assertRaises(MutationConflict) as caught:
            write_text(
                self.path,
                "three\n",
                expected_hash=snapshot.content_hash,
                operation="second",
            )
        self.assertEqual(snapshot.content_hash, caught.exception.expected_hash)
        self.assertEqual(first.after_hash, caught.exception.actual_hash)
        self.assertEqual("two\n", read_text_snapshot(self.path).text)

    def test_concurrent_writers_with_same_hash_have_single_winner(self):
        self.write_raw(b"base\n")
        expected = read_text_snapshot(self.path).content_hash
        barrier = threading.Barrier(3)
        successes = []
        conflicts = []

        def writer(value):
            barrier.wait()
            try:
                result = write_text(
                    self.path,
                    value,
                    expected_hash=expected,
                    operation="concurrent",
                    lock_timeout=2.0,
                )
                successes.append(result)
            except MutationConflict as exc:
                conflicts.append(exc)

        threads = [
            threading.Thread(target=writer, args=("writer-a\n",)),
            threading.Thread(target=writer, args=("writer-b\n",)),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual(1, len(successes))
        self.assertEqual(1, len(conflicts))
        self.assertIn(
            read_text_snapshot(self.path).text,
            ("writer-a\n", "writer-b\n"),
        )

    def test_noop_does_not_replace_file(self):
        self.write_raw(b"same\n")
        before = os.stat(self.path)
        result = write_text(self.path, "same\n", operation="noop")
        after = os.stat(self.path)
        self.assertFalse(result.changed)
        self.assertEqual(before.st_ino, after.st_ino)
        self.assertEqual(result.before_hash, result.after_hash)

    def test_validator_and_transform_error_preserve_original(self):
        self.write_raw(b"safe\n")
        with self.assertRaises(ValueError):
            mutate_text(
                self.path,
                lambda text: "invalid\n",
                validate=lambda text: (_ for _ in ()).throw(ValueError("bad")),
            )
        self.assertEqual("safe\n", read_text_snapshot(self.path).text)
        with self.assertRaises(RuntimeError):
            mutate_text(
                self.path,
                lambda text: (_ for _ in ()).throw(RuntimeError("boom")),
            )
        self.assertEqual("safe\n", read_text_snapshot(self.path).text)

    def test_operation_contract_reports_before_and_after_hashes(self):
        self.write_raw(b"a\n")
        operation = MutationOperation("append", lambda text: text + "b\n")
        result = apply_text_mutation(self.path, operation)
        self.assertEqual("append", result.operation)
        self.assertNotEqual(result.before_hash, result.after_hash)
        self.assertEqual(result.after_hash, result.snapshot.content_hash)

    def test_lock_timeout_reports_owner(self):
        lock = FileLock(self.path, operation="holder", timeout=0.1)
        lock.acquire()
        try:
            with self.assertRaises(LockTimeout) as caught:
                FileLock(
                    self.path,
                    operation="waiter",
                    timeout=0.05,
                    poll_interval=0.01,
                    stale_after=None,
                ).acquire()
            self.assertEqual("holder", caught.exception.owner.get("operation"))
            self.assertEqual(os.getpid(), caught.exception.owner.get("pid"))
        finally:
            lock.release()

    def test_stale_dead_owner_lock_is_recovered(self):
        lock_path = self.path + ".lifetxt.lock"
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": 1,
                    "token": "stale",
                    "pid": 99999999,
                    "host": socket.gethostname(),
                    "operation": "abandoned",
                },
                handle,
            )
        old = time.time() - 60
        os.utime(lock_path, (old, old))
        with FileLock(
            self.path,
            operation="recovery",
            timeout=0.2,
            poll_interval=0.01,
            stale_after=0.01,
        ) as lock:
            self.assertTrue(lock._owned)
        self.assertFalse(os.path.exists(lock_path))

    def test_utf8_bom_is_preserved(self):
        self.write_raw(codecs.BOM_UTF8 + "hello\n".encode("utf-8"))
        before = read_text_snapshot(self.path)
        self.assertTrue(before.bom)
        result = mutate_text(
            self.path,
            lambda text: text.replace("hello", "world"),
        )
        with open(self.path, "rb") as handle:
            data = handle.read()
        self.assertTrue(data.startswith(codecs.BOM_UTF8))
        self.assertEqual("world\n", result.snapshot.text)

    def test_crlf_text_is_not_normalized(self):
        self.write_raw(b"one\r\ntwo\r\n")
        snapshot = read_text_snapshot(self.path)
        self.assertEqual("\r\n", snapshot.newline)
        mutate_text(self.path, lambda text: text + "three\r\n")
        with open(self.path, "rb") as handle:
            self.assertEqual(b"one\r\ntwo\r\nthree\r\n", handle.read())

    def test_json_create_and_update_share_cas(self):
        created = mutate_json(
            self.path,
            lambda value: {"count": value["count"] + 1},
            expected_hash=MISSING_HASH,
            operation="json create",
            create=True,
            default={"count": 0},
        )
        updated = mutate_json(
            self.path,
            lambda value: {"count": value["count"] + 1},
            expected_hash=created.after_hash,
            operation="json update",
        )
        self.assertEqual({"count": 2}, json.loads(updated.snapshot.text))

    def test_external_edit_during_transform_is_not_overwritten(self):
        self.write_raw(b"base\n")

        def transform(text):
            with open(self.path, "wb") as handle:
                handle.write(b"external\n")
            return "ours\n"

        with self.assertRaises(MutationConflict):
            mutate_text(self.path, transform, operation="race")
        self.assertEqual("external\n", read_text_snapshot(self.path).text)

    @unittest.skipIf(
        os.name == "nt",
        "POSIX permission bits are not stable on Windows",
    )
    def test_atomic_replacement_preserves_permissions(self):
        self.write_raw(b"private\n")
        os.chmod(self.path, 0o640)
        write_text(self.path, "updated\n")
        self.assertEqual(0o640, os.stat(self.path).st_mode & 0o777)

    def test_lock_is_removed_when_transform_raises(self):
        self.write_raw(b"safe\n")
        with self.assertRaises(RuntimeError):
            mutate_text(
                self.path,
                lambda text: (_ for _ in ()).throw(RuntimeError("boom")),
            )
        self.assertFalse(os.path.exists(self.path + ".lifetxt.lock"))


if __name__ == "__main__":
    unittest.main()
