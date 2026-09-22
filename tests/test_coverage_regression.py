import json
import tempfile
import unittest
from pathlib import Path
from scripts.check_coverage_regression import check

class CoverageRegressionTests(unittest.TestCase):
    def test_accepts_floor(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "coverage.json"
            floor = root / "baseline.json"
            report.write_text(json.dumps({"totals": {"percent_branches": 80}}))
            floor.write_text(json.dumps({"minimum_branch_percent": 80}))
            self.assertEqual((True, "branch coverage: 80.00% (minimum: 80.00%)"), check(report, floor))

    def test_rejects_regression(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "coverage.json"
            floor = root / "baseline.json"
            report.write_text(json.dumps({"totals": {"percent_branches": 79.9}}))
            floor.write_text(json.dumps({"minimum_branch_percent": 80}))
            passed, _ = check(report, floor)
            self.assertFalse(passed)
