import json
import os
import tempfile
import unittest

from lifetxt.clock_contract import audit_host_clocks, clock_boundary_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ClockContractV4Tests(unittest.TestCase):
    def test_repository_clock_baseline_has_no_new_findings(self):
        report = clock_boundary_report(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual([], report["new_findings"])
        self.assertGreater(report["finding_count"], 0)

    def test_unclassified_direct_clock_is_detected(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "lifetxt"))
            with open(os.path.join(root, "lifetxt", "sample.py"), "w", encoding="utf-8") as handle:
                handle.write("import time\nvalue = time.time()\n")
            os.makedirs(os.path.join(root, "config", "release"))
            with open(os.path.join(root, "config", "release", "clock-boundary-baseline-v1.json"), "w", encoding="utf-8") as handle:
                json.dump({"baseline_version": 1, "allowed": []}, handle)
            report = clock_boundary_report(root)
            self.assertFalse(report["ok"])
            self.assertEqual("time.time", report["new_findings"][0]["call"])
            self.assertEqual(1, len(audit_host_clocks(root)))


if __name__ == "__main__":
    unittest.main()
