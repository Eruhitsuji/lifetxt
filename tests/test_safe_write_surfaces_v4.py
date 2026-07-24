import json
import os
import tempfile
import threading
import unittest

from lifetxt import mutation
from lifetxt.write_operations import (
    SemanticWriteError,
    append_life_records,
    merge_tag_and_alias,
    mutate_item_files,
    mutate_items,
    restore_text,
)


class SemanticWriteSurfaceV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T One id:t1 tag:old\n[ ] T Two id:t2\n")

    def revision(self, path=None):
        return mutation.read_text_snapshot(path or self.life).content_hash

    def test_mutate_items_updates_current_in_lock_text(self):
        result = mutate_items(
            self.life,
            [{"id": "t1", "status": "[x]", "set_details": {"done": ["2026-07-24"]}}],
            expected_revision=self.revision(),
            operation="test.semantic",
        )
        self.assertTrue(result.changed)
        with open(self.life, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("[x] T One", text)
        self.assertIn("done:2026-07-24", text)
        self.assertIn("[ ] T Two", text)

    def test_stale_revision_is_rejected(self):
        stale = self.revision()
        with open(self.life, "a", encoding="utf-8") as handle:
            handle.write("[ ] N External id:n1\n")
        with self.assertRaises(mutation.MutationConflict):
            mutate_items(
                self.life,
                [{"id": "t1", "status": "[x]"}],
                expected_revision=stale,
            )

    def test_same_revision_has_one_winner_and_one_conflict(self):
        expected = self.revision()
        barrier = threading.Barrier(2)
        outcomes = []

        def worker(status):
            try:
                barrier.wait()
                mutate_items(
                    self.life,
                    [{"id": "t1", "status": status}],
                    expected_revision=expected,
                )
                outcomes.append("winner")
            except mutation.MutationConflict:
                outcomes.append("conflict")

        threads = [
            threading.Thread(target=worker, args=("[x]",)),
            threading.Thread(target=worker, args=("[/]",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(["conflict", "winner"], sorted(outcomes))

    def test_append_records_validates_result(self):
        result = append_life_records(
            self.life,
            "[N] N Captured id:n1",
            expected_revision=self.revision(),
            operation="quick.capture",
        )
        self.assertTrue(result.changed)
        with open(self.life, encoding="utf-8") as handle:
            self.assertIn("Captured id:n1", handle.read())

    def test_multi_file_changes_are_journal_backed(self):
        other = os.path.join(self.temp.name, "other.txt")
        with open(other, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Other id:t3\n")
        journal_dir = os.path.join(self.temp.name, "transactions")
        result = mutate_item_files(
            {
                self.life: {
                    "expected_revision": self.revision(),
                    "changes": [{"id": "t1", "status": "[x]"}],
                },
                other: {
                    "expected_revision": mutation.read_text_snapshot(other).content_hash,
                    "changes": [{"id": "t3", "status": "[/]"}],
                },
            },
            operation="tui.multi_edit",
            journal_dir=journal_dir,
        )
        self.assertTrue(result.transaction_id)
        self.assertTrue(os.path.exists(result.journal_path))
        self.assertEqual(2, len(result.targets))

    def test_tag_and_alias_merge_is_all_or_none(self):
        config_path = os.path.join(self.temp.name, "config.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump({"tag_aliases": {}}, handle)
        result, count = merge_tag_and_alias(
            self.life,
            "old",
            "new",
            config_path=config_path,
            life_revision=self.revision(),
            config_revision=mutation.read_text_snapshot(config_path).content_hash,
            journal_dir=os.path.join(self.temp.name, "transactions"),
        )
        self.assertEqual(1, count)
        self.assertTrue(result.transaction_id)
        with open(config_path, encoding="utf-8") as handle:
            self.assertEqual("new", json.load(handle)["tag_aliases"]["old"])
        with open(self.life, encoding="utf-8") as handle:
            self.assertIn("tag:new", handle.read())

    def test_restore_requires_revision_after_external_edit(self):
        before = mutation.read_text_snapshot(self.life)
        mutate_items(
            self.life,
            [{"id": "t1", "status": "[x]"}],
            expected_revision=before.content_hash,
        )
        changed_revision = self.revision()
        with open(self.life, "a", encoding="utf-8") as handle:
            handle.write("[ ] N External id:n2\n")
        with self.assertRaises(mutation.MutationConflict):
            restore_text(self.life, before.text, expected_revision=changed_revision)

    def test_duplicate_change_is_rejected(self):
        with self.assertRaises(SemanticWriteError):
            mutate_items(
                self.life,
                [{"id": "t1", "status": "[x]"}, {"id": "t1", "delete": True}],
                expected_revision=self.revision(),
            )


if __name__ == "__main__":
    unittest.main()
