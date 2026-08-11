from __future__ import unicode_literals

import unittest

from lifetxt.fault_drill import (
    PRE_JOURNAL_POINTS,
    SUPPORTED_POINTS,
    run_fault_drill,
    run_fault_matrix,
)


class FaultMatrixV6Tests(unittest.TestCase):
    def test_all_boundaries_have_deterministic_evidence(self):
        report = run_fault_matrix(recovery="auto")
        self.assertTrue(
            report["ok"],
            [
                (row["point"], row["recovery_error"], row["stderr"])
                for row in report["results"]
                if not row["ok"]
            ],
        )
        self.assertEqual(len(SUPPORTED_POINTS), report["point_count"])
        self.assertEqual(report["point_count"], report["passed"])

    def test_pre_journal_orphan_cleanup_requires_unchanged_targets(self):
        report = run_fault_drill(
            "after_after_artifact", recovery="cleanup-orphan", keep=True
        )
        self.assertTrue(report["ok"])
        self.assertFalse(report["after_recovery"]["transaction_directory_exists"])
        self.assertTrue(report["recovery_result"]["targets_verified_unchanged"])
        import shutil

        shutil.rmtree(report["workspace"], ignore_errors=True)

    def test_recovery_is_repeatable_after_published_journal(self):
        report = run_fault_drill(
            "after_target_commit", recovery="compensate", repeat_recovery=True
        )
        self.assertTrue(report["ok"])
        self.assertIsNone(report["repeated_recovery_error"])
        self.assertEqual("compensated", report["repeated_recovery_result"]["state"])

    def test_delete_boundary_resume_is_recoverable_and_reported_as_simulated(self):
        report = run_fault_drill("after_target_delete", recovery="auto")
        self.assertTrue(report["ok"], report["recovery_error"])
        self.assertEqual("delete", report["boundary_phase"])
        self.assertEqual("committed", report["recovery_result"]["state"])
        self.assertIsNone(report["after_recovery"]["files"]["delete.txt"])
        self.assertIn("subprocess", report["scope"])
        self.assertIn("not physical power-loss", report["scope"])

    def test_terminal_cleanup_boundary_is_repeatable_to_absent_journal(self):
        report = run_fault_drill("before_terminal_cleanup", recovery="auto")
        self.assertTrue(report["ok"], report["recovery_error"])
        self.assertEqual("terminal-cleanup", report["boundary_phase"])
        self.assertTrue(report["before_recovery"]["transaction_directory_exists"])
        self.assertFalse(report["after_recovery"]["transaction_directory_exists"])
        self.assertEqual(1, len(report["recovery_result"]["removed"]))

        repeated = run_fault_drill("after_terminal_cleanup", recovery="auto")
        self.assertTrue(repeated["ok"], repeated["recovery_error"])
        self.assertFalse(repeated["after_recovery"]["transaction_directory_exists"])
        self.assertEqual([], repeated["recovery_result"]["removed"])

    def test_backup_and_restore_boundaries_do_not_report_incomplete_success(self):
        backup = run_fault_drill("after_backup_copy", recovery="auto")
        self.assertTrue(backup["ok"], backup["recovery_error"])
        self.assertEqual("backup-copy", backup["boundary_phase"])
        self.assertEqual(backup["expected_exit_code"], backup["exit_code"])
        self.assertTrue(backup["before_recovery"]["transaction_directory_exists"])

        restore = run_fault_drill("after_restore_working_copy", recovery="auto")
        self.assertTrue(restore["ok"], restore["recovery_error"])
        self.assertEqual("restore-working-copy", restore["boundary_phase"])
        self.assertEqual(restore["expected_exit_code"], restore["exit_code"])
        self.assertTrue(restore["before_recovery"]["transaction_directory_exists"])


if __name__ == "__main__":
    unittest.main()
