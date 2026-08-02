import os
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.editor_safety import EditorReconcileConflict, safe_edit


class EditorSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T One id:t1\n[ ] T Two id:t2\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_applies_editor_copy_with_revision(self):
        def runner(command):
            target = command[-1]
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("[x] T One id:t1\n[ ] T Two id:t2\n")
            return 0

        result = safe_edit(self.path, "cat", runner=runner)
        self.assertTrue(result["written"])

        with open(self.path, encoding="utf-8") as handle:
            self.assertIn("[x]", handle.read())
        self.assertTrue(result["diff"])

    def test_review_only_does_not_write(self):
        def runner(command):
            with open(command[-1], "a", encoding="utf-8") as handle:
                handle.write("[ ] N Note id:n1\n")
            return 0

        result = safe_edit(self.path, "cat", runner=runner, review_only=True)
        self.assertFalse(result["written"])

        with open(self.path, encoding="utf-8") as handle:
            self.assertNotIn("Note", handle.read())

    def test_source_change_is_rejected(self):
        def runner(command):
            with open(command[-1], "a", encoding="utf-8") as handle:
                handle.write("[ ] N Edited id:n1\n")
            snap = mutation.read_text_snapshot(self.path)
            mutation.write_text(
                self.path,
                snap.text + "[ ] N External id:n2\n",
                expected_hash=snap.content_hash,
            )
            return 0

        with self.assertRaises(mutation.MutationConflict):
            safe_edit(self.path, "cat", runner=runner)

    def test_non_overlapping_reconcile(self):
        def runner(command):
            target = command[-1]
            with open(target, "r", encoding="utf-8") as handle:
                text = handle.read()
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text.replace("One", "Edited_One"))
            snap = mutation.read_text_snapshot(self.path)
            mutation.write_text(
                self.path,
                snap.text.replace("Two", "External_Two"),
                expected_hash=snap.content_hash,
            )
            return 0

        result = safe_edit(self.path, "cat", runner=runner, reconcile=True)
        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("Edited_One", text)
        self.assertIn("External_Two", text)
        self.assertTrue(result["reconciled"])

    def test_overlapping_reconcile_is_rejected(self):
        def runner(command):
            target = command[-1]
            with open(target, "r", encoding="utf-8") as handle:
                text = handle.read()
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text.replace("One", "Edited"))
            snap = mutation.read_text_snapshot(self.path)
            mutation.write_text(
                self.path,
                snap.text.replace("One", "External"),
                expected_hash=snap.content_hash,
            )
            return 0

        with self.assertRaises(EditorReconcileConflict):
            safe_edit(self.path, "cat", runner=runner, reconcile=True)


if __name__ == "__main__":
    unittest.main()
