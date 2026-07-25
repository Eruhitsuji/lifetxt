from __future__ import unicode_literals

import unittest

from lifetxt.fault_drill import PRE_JOURNAL_POINTS, SUPPORTED_POINTS, run_fault_drill, run_fault_matrix


class FaultMatrixV6Tests(unittest.TestCase):
    def test_all_boundaries_have_deterministic_evidence(self):
        report = run_fault_matrix(recovery="auto")
        self.assertTrue(report["ok"], [
            (row["point"], row["recovery_error"], row["stderr"])
            for row in report["results"] if not row["ok"]
        ])
        self.assertEqual(len(SUPPORTED_POINTS), report["point_count"])
        self.assertEqual(report["point_count"], report["passed"])

    def test_pre_journal_orphan_cleanup_requires_unchanged_targets(self):
        report = run_fault_drill("after_after_artifact", recovery="cleanup-orphan", keep=True)
        self.assertTrue(report["ok"])
        self.assertFalse(report["after_recovery"]["transaction_directory_exists"])
        self.assertTrue(report["recovery_result"]["targets_verified_unchanged"])
        import shutil
        shutil.rmtree(report["workspace"], ignore_errors=True)

    def test_recovery_is_repeatable_after_published_journal(self):
        report = run_fault_drill("after_target_commit", recovery="compensate", repeat_recovery=True)
        self.assertTrue(report["ok"])
        self.assertIsNone(report["repeated_recovery_error"])
        self.assertEqual("compensated", report["repeated_recovery_result"]["state"])


if __name__ == "__main__":
    unittest.main()
