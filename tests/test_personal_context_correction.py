import datetime
import json
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt.model import Item
from lifetxt.personal_context import correction_details, stage_memory_correction
from lifetxt.timezone_policy import UTC


class PersonalContextCorrectionTests(unittest.TestCase):
    def note(self, title, **details):
        normalized = OrderedDict()
        for key, value in details.items():
            values = value if isinstance(value, (list, tuple)) else [value]
            normalized[key] = [str(entry) for entry in values]
        return Item(status="[ ]", kind="N", title=title, details=normalized)

    def test_correction_details_preserve_context_and_generate_unique_id(self):
        now = datetime.datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
        target = self.note(
            "Old",
            id="memory-old",
            person="self",
            tag=["preference", "editor"],
            project="dotfiles",
            source="user",
        )
        existing = self.note("Existing", id="note_20260824100000", person="self")
        details = correction_details(
            target,
            [target, existing],
            config={},
            source="manual",
            now_value=now,
        )
        self.assertEqual(details["corrects"], ["memory-old"])
        self.assertEqual(details["person"], ["self"])
        self.assertEqual(details["tag"], ["preference", "editor"])
        self.assertEqual(details["project"], ["dotfiles"])
        self.assertEqual(details["source"], ["manual"])
        self.assertEqual(details["id"], ["note_20260824100000_2"])
        self.assertEqual(details["updated"], ["2026-08-24T10:00:00+00:00"])

    def test_stage_memory_correction_uses_unified_inbox(self):
        with tempfile.TemporaryDirectory() as directory:
            target_path = os.path.join(directory, "life.txt")
            proposals_path = os.path.join(directory, "proposals.json")
            config = {
                "paths": [target_path],
                "write_file": target_path,
                "inbox": {"proposals_file": proposals_path},
            }
            target = self.note(
                "Old",
                id="memory-old",
                person="self",
                tag="preference",
                source="user",
            )
            report = stage_memory_correction(
                config,
                [target],
                "memory-old",
                "New preference",
                source="manual",
                now_value=datetime.datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
            )
            self.assertTrue(os.path.exists(proposals_path))
            with open(proposals_path, "r", encoding="utf-8") as handle:
                proposals = json.load(handle)
            self.assertEqual(len(proposals), 1)
            change = proposals[0]["changes"][0]
            self.assertEqual(change["op"], "create")
            self.assertEqual(change["kind"], "N")
            self.assertEqual(change["title"], "New preference")
            self.assertEqual(change["details"]["corrects"], ["memory-old"])
            self.assertEqual(report["proposal_id"], proposals[0]["id"])
            self.assertFalse(os.path.exists(target_path))


if __name__ == "__main__":
    unittest.main()
