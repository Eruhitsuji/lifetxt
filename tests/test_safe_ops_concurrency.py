import json
import os
import tempfile
import threading
import unittest

from lifetxt.mutation import MutationConflict, read_text_snapshot
from lifetxt.safe_ops import (
    ExpectedRevisionRequired,
    archive,
    item_update,
    mcp_write,
    notification_acknowledgement,
    quick_capture,
    timer_state,
    undo,
)


class SafeOperationConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name="life.txt"):
        return os.path.join(self.temp_dir.name, name)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def race(self, first, second):
        barrier = threading.Barrier(3)
        successes = []
        conflicts = []
        failures = []

        def runner(call):
            barrier.wait()
            try:
                successes.append(call())
            except MutationConflict as exc:
                conflicts.append(exc)
            except Exception as exc:  # pragma: no cover - reported with useful detail
                failures.append(exc)

        threads = [
            threading.Thread(target=runner, args=(first,)),
            threading.Thread(target=runner, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual([], failures)
        self.assertEqual(1, len(successes))
        self.assertEqual(1, len(conflicts))
        self.assertIn("Reload the file and retry", str(conflicts[0]))
        return successes[0]

    def test_quick_capture_rejects_one_stale_writer(self):
        path = self.path()
        self.write(path, "[ ] T Base id:T-0\n")
        expected = read_text_snapshot(path).content_hash
        self.race(
            lambda: quick_capture(path, "[ ] T A id:T-A", expected),
            lambda: quick_capture(path, "[ ] T B id:T-B", expected),
        )
        text = read_text_snapshot(path).text
        self.assertEqual(2, len(text.splitlines()))
        self.assertNotEqual(text.find("T-A"), text.find("T-B"))
        self.assertTrue(("T-A" in text) ^ ("T-B" in text))

    def test_item_update_rejects_one_stale_writer(self):
        self._text_transform_race(item_update)

    def test_mcp_write_rejects_one_stale_writer(self):
        self._text_transform_race(mcp_write)

    def test_notification_acknowledgement_rejects_one_stale_writer(self):
        self._text_transform_race(notification_acknowledgement)

    def test_archive_rejects_one_stale_writer(self):
        self._text_transform_race(archive)

    def test_timer_state_rejects_one_stale_writer(self):
        path = self.path("timer.json")
        self.write(path, '{"count": 0}\n')
        expected = read_text_snapshot(path).content_hash
        self.race(
            lambda: timer_state(
                path,
                lambda value: {"count": value["count"] + 1, "writer": "a"},
                expected,
            ),
            lambda: timer_state(
                path,
                lambda value: {"count": value["count"] + 1, "writer": "b"},
                expected,
            ),
        )
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        self.assertEqual(1, value["count"])
        self.assertIn(value["writer"], ("a", "b"))

    def test_undo_rejects_one_stale_writer(self):
        path = self.path()
        self.write(path, "current\n")
        expected = read_text_snapshot(path).content_hash
        self.race(
            lambda: undo(path, "snapshot-a\n", expected),
            lambda: undo(path, "snapshot-b\n", expected),
        )
        self.assertIn(read_text_snapshot(path).text, ("snapshot-a\n", "snapshot-b\n"))

    def test_all_operations_require_expected_hash(self):
        path = self.path()
        self.write(path, "base\n")
        calls = (
            lambda: quick_capture(path, "new", None),
            lambda: item_update(path, lambda text: text, None),
            lambda: mcp_write(path, lambda text: text, None),
            lambda: notification_acknowledgement(path, lambda text: text, None),
            lambda: archive(path, lambda text: text, None),
            lambda: undo(path, "old\n", None),
            lambda: timer_state(self.path("state.json"), lambda value: value, None),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(ExpectedRevisionRequired):
                    call()

    def _text_transform_race(self, operation):
        path = self.path()
        self.write(path, "base\n")
        expected = read_text_snapshot(path).content_hash
        self.race(
            lambda: operation(path, lambda text: text + "writer-a\n", expected),
            lambda: operation(path, lambda text: text + "writer-b\n", expected),
        )
        text = read_text_snapshot(path).text
        self.assertTrue(("writer-a" in text) ^ ("writer-b" in text))


if __name__ == "__main__":
    unittest.main()
