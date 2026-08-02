from __future__ import unicode_literals

import unittest

from lifetxt.fault_drill import EXIT_CODE, run_fault_drill


class FaultDrillTests(unittest.TestCase):
    def test_after_journal_publish_leaves_recoverable_evidence(self):
        report = run_fault_drill("after_journal_publish", recovery="resume")
        self.assertTrue(report["ok"])
        self.assertEqual(EXIT_CODE, report["exit_code"])
        self.assertTrue(report["journal_path"])
        self.assertEqual(
            "after-first\n", report["after_recovery"]["files"]["first.txt"]
        )
        self.assertEqual(
            "after-second\n", report["after_recovery"]["files"]["second.txt"]
        )

    def test_after_first_target_commit_can_compensate(self):
        report = run_fault_drill("after_target_commit", recovery="compensate")
        self.assertTrue(report["ok"])
        self.assertEqual(
            "before-first\n", report["after_recovery"]["files"]["first.txt"]
        )
        self.assertEqual(
            "before-second\n", report["after_recovery"]["files"]["second.txt"]
        )


if __name__ == "__main__":
    unittest.main()
