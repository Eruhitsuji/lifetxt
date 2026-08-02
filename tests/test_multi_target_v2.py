import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from lifetxt import mutation
from lifetxt.multi_target import (
    MultiTargetCommitError,
    apply_multi_target,
    attachment_and_item_transaction,
    bytes_plan,
    delete_plan,
    json_plan,
    text_plan,
    timer_and_item_transaction,
)
from lifetxt.mutation import MISSING_HASH, MutationConflict, read_text_snapshot


class MultiTargetV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name):
        return os.path.join(self.temp_dir.name, name)

    def write(self, name, data, binary=False):
        path = self.path(name)
        mode = "wb" if binary else "w"
        kwargs = {} if binary else {"encoding": "utf-8", "newline": ""}
        with open(path, mode, **kwargs) as handle:
            handle.write(data)
        return path

    def read(self, path, binary=False):
        mode = "rb" if binary else "r"
        kwargs = {} if binary else {"encoding": "utf-8"}
        with open(path, mode, **kwargs) as handle:
            return handle.read()

    def test_timer_and_item_commit_together(self):
        timer = self.write("timer.json", '{"running": false}\n')
        life = self.write("life.txt", "[ ] T Focus id:T-1\n")
        result = timer_and_item_transaction(
            timer,
            lambda value: {"running": True, "item_id": "T-1"},
            read_text_snapshot(timer).content_hash,
            life,
            lambda text: text.replace("[ ]", "[/]"),
            read_text_snapshot(life).content_hash,
        )
        self.assertEqual(2, len(result.targets))
        self.assertTrue(json.loads(self.read(timer))["running"])
        self.assertIn("[/] T Focus", self.read(life))

    def test_stale_target_rejects_before_any_commit(self):
        first = self.write("a.txt", "one\n")
        second = self.write("b.txt", "two\n")
        first_hash = read_text_snapshot(first).content_hash
        second_hash = read_text_snapshot(second).content_hash
        with open(second, "w", encoding="utf-8") as handle:
            handle.write("newer\n")
        with self.assertRaises(MutationConflict):
            apply_multi_target(
                [
                    text_plan(first, lambda text: "changed\n", first_hash),
                    text_plan(second, lambda text: "changed\n", second_hash),
                ],
                operation="stale-test",
            )
        self.assertEqual("one\n", self.read(first))
        self.assertEqual("newer\n", self.read(second))

    def test_partial_commit_is_compensated_in_reverse_order(self):
        first = self.write("a.txt", "one\n")
        second = self.write("b.txt", "two\n")

        def fail(phase, plan, index):
            if phase == "before_commit" and index == 1:
                raise RuntimeError("injected second-target failure")

        with self.assertRaises(MultiTargetCommitError) as caught:
            apply_multi_target(
                [
                    text_plan(
                        first,
                        lambda text: "changed-one\n",
                        read_text_snapshot(first).content_hash,
                    ),
                    text_plan(
                        second,
                        lambda text: "changed-two\n",
                        read_text_snapshot(second).content_hash,
                    ),
                ],
                operation="compensation-test",
                failure_hook=fail,
            )
        self.assertFalse(caught.exception.rollback_errors)
        self.assertEqual("one\n", self.read(first))
        self.assertEqual("two\n", self.read(second))

    def test_rollback_failure_is_exposed_not_hidden(self):
        first = self.write("a.txt", "one\n")
        second = self.write("b.txt", "two\n")
        original = mutation.atomic_write_bytes
        calls = {"count": 0}

        def write_then_fail_rollback(path, data):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("rollback blocked")
            return original(path, data)

        def fail(phase, plan, index):
            if phase == "before_commit" and index == 1:
                raise RuntimeError("commit blocked")

        with mock.patch.object(
            mutation, "atomic_write_bytes", side_effect=write_then_fail_rollback
        ):
            with self.assertRaises(MultiTargetCommitError) as caught:
                apply_multi_target(
                    [
                        text_plan(
                            first,
                            lambda text: "changed\n",
                            read_text_snapshot(first).content_hash,
                        ),
                        text_plan(
                            second,
                            lambda text: "changed\n",
                            read_text_snapshot(second).content_hash,
                        ),
                    ],
                    failure_hook=fail,
                )
        self.assertTrue(caught.exception.rollback_errors)
        self.assertIn("compensation also failed", str(caught.exception))

    def test_attachment_create_and_item_reference_commit_together(self):
        attachment = self.path("attachments/note.bin")
        life = self.write("life.txt", "[ ] T Task id:T-1\n")
        plan = bytes_plan(
            attachment,
            lambda current: b"payload",
            MISSING_HASH,
            create=True,
            default=b"",
        )
        result = attachment_and_item_transaction(
            plan,
            life,
            lambda text: text.rstrip("\n") + " file:attachments/note.bin\n",
            read_text_snapshot(life).content_hash,
        )
        self.assertEqual(b"payload", self.read(attachment, binary=True))
        self.assertIn("file:attachments/note.bin", self.read(life))
        self.assertTrue(any(target.created for target in result.targets))

    def test_delete_plan_removes_bytes_target(self):
        attachment = self.write("note.bin", b"payload", binary=True)
        expected = mutation.hash_bytes(b"payload")
        result = apply_multi_target(
            [delete_plan(attachment, expected)], operation="delete"
        )
        self.assertFalse(os.path.exists(attachment))
        self.assertTrue(result.targets[0].deleted)

    def test_json_validator_aborts_before_commit(self):
        path = self.write("state.json", '{"value": 1}\n')
        expected = read_text_snapshot(path).content_hash
        with self.assertRaises(ValueError):
            apply_multi_target(
                [
                    json_plan(
                        path,
                        lambda value: {"value": -1},
                        expected,
                        validate=lambda value: value["value"] >= 0,
                    )
                ]
            )
        self.assertEqual({"value": 1}, json.loads(self.read(path)))

    def test_concurrent_same_revision_has_one_winner_one_conflict(self):
        first = self.write("a.txt", "one\n")
        second = self.write("b.txt", "two\n")
        expected_first = read_text_snapshot(first).content_hash
        expected_second = read_text_snapshot(second).content_hash
        barrier = threading.Barrier(2)
        results = []

        def worker(label):
            barrier.wait()
            try:
                apply_multi_target(
                    [
                        text_plan(first, lambda text: label + "-a\n", expected_first),
                        text_plan(second, lambda text: label + "-b\n", expected_second),
                    ],
                    operation="race",
                )
                results.append("success")
            except MutationConflict:
                results.append("conflict")

        threads = [
            threading.Thread(target=worker, args=(label,)) for label in ("x", "y")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(["conflict", "success"], sorted(results))


if __name__ == "__main__":
    unittest.main()
