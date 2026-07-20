import datetime
import os
import tempfile
import unittest

from lifetxt.mutation import MutationConflict, read_text_snapshot, write_text
from lifetxt.parser import parse_text
from lifetxt.presence import active_status_items, status_transition_file


class PresenceMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write(
                "[/] S Busy from:2026-07-20T09:00 state:busy person:self id:status_busy\n"
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_status_transition_file_uses_shared_hash_contract(self):
        snapshot = read_text_snapshot(self.path)
        result = status_transition_file(
            self.path,
            expected_hash=snapshot.content_hash,
            state="away",
            person="self",
            moment=datetime.datetime(2026, 7, 20, 10, 30),
            item_id="status_away",
        )
        self.assertTrue(result.mutation.changed)
        self.assertEqual(snapshot.content_hash, result.mutation.before_hash)
        self.assertEqual(1, len(result.transition.closed))
        self.assertIn("state:away", result.transition.opened)

        with open(self.path, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        items, diagnostics = parse_text(text)
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        active = active_status_items(items, person="self")
        self.assertEqual(1, len(active))
        self.assertEqual("away", active[0].details["state"][0])
        self.assertIn("to", items[0].details)

    def test_status_transition_file_rejects_stale_snapshot(self):
        snapshot = read_text_snapshot(self.path)
        write_text(
            self.path,
            snapshot.text + "[N] N External_Edit id:external\n",
            expected_hash=snapshot.content_hash,
            operation="external test edit",
        )
        with self.assertRaises(MutationConflict):
            status_transition_file(
                self.path,
                expected_hash=snapshot.content_hash,
                state="away",
                person="self",
                moment=datetime.datetime(2026, 7, 20, 10, 30),
                item_id="status_away",
            )
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertIn("External_Edit", handle.read())


if __name__ == "__main__":
    unittest.main()
