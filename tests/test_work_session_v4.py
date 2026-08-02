import os
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.work_session import start_work_transaction, stop_work_transaction


class WorkSessionV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.timer = os.path.join(self.temp.name, "timer.json")
        self.config = {
            "timer": {"state_file": self.timer},
            "transactions": {
                "journal_dir": os.path.join(self.temp.name, "transactions")
            },
            "defaults": {"timezone": "UTC"},
        }
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("#! timezone: UTC\n[ ] T Task id:t1 project:alpha\n")

    def item_revision(self):
        return mutation.read_text_snapshot(self.life).content_hash

    def test_start_and_stop_commit_timer_task_and_presence_together(self):
        started = start_work_transaction(
            self.life,
            "t1",
            state="busy",
            config=self.config,
            expected_item_revision=self.item_revision(),
            expected_timer_revision=mutation.MISSING_HASH,
            require_revisions=True,
        )
        self.assertTrue(started["running"])
        self.assertTrue(started["transaction_id"])
        self.assertTrue(os.path.exists(self.timer))
        with open(self.life, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("[/] T Task", text)
        self.assertIn(" S ", text)

        stopped = stop_work_transaction(
            self.life,
            done=True,
            config=self.config,
            expected_item_revision=started["item_revision"],
            expected_timer_revision=started["timer_revision"],
            require_revisions=True,
        )
        self.assertFalse(stopped["running"])
        self.assertTrue(stopped["done"])
        self.assertEqual(mutation.MISSING_HASH, stopped["timer_revision"])
        self.assertFalse(os.path.exists(self.timer))
        with open(self.life, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("[x] T Task", text)
        self.assertIn("elapsed:", text)
        self.assertIn("done:", text)

    def test_required_mode_rejects_missing_revisions(self):
        with self.assertRaises(ValueError):
            start_work_transaction(
                self.life,
                "t1",
                config=self.config,
                require_revisions=True,
            )

    def test_stale_item_revision_does_not_create_timer(self):
        stale = self.item_revision()
        with open(self.life, "a", encoding="utf-8") as handle:
            handle.write("[ ] N External id:n1\n")
        with self.assertRaises(mutation.MutationConflict):
            start_work_transaction(
                self.life,
                "t1",
                config=self.config,
                expected_item_revision=stale,
                expected_timer_revision=mutation.MISSING_HASH,
                require_revisions=True,
            )
        self.assertFalse(os.path.exists(self.timer))

    def test_start_without_timer_still_returns_timer_revision(self):
        started = start_work_transaction(
            self.life,
            "t1",
            use_timer=False,
            use_presence=True,
            config=self.config,
            expected_item_revision=self.item_revision(),
            require_revisions=True,
        )
        self.assertFalse(started["running"])
        self.assertEqual(mutation.MISSING_HASH, started["timer_revision"])
        self.assertFalse(os.path.exists(self.timer))


if __name__ == "__main__":
    unittest.main()
