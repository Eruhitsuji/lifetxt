import json
import os
import tempfile
import unittest

from lifetxt.workspace_diagnostics import (
    extended_file_diagnostics,
    stable_file_diagnostics,
    workspace_diagnostics,
)


class WorkspaceDiagnosticsV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name):
        return os.path.join(self.temp_dir.name, name)

    def write(self, name, text):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def codes(self, report):
        return {row["code"] for row in report["diagnostics"]}

    def test_file_diagnostics_detect_malformed_directive_indent_and_timezone(self):
        path = self.write(
            "life.txt",
            "#! broken\n#! timezone: Not/A_Zone\n\t[ ] T Tabbed\n [ ] T Odd\n",
        )
        rows = extended_file_diagnostics(path)
        codes = {row["code"] for row in rows}
        self.assertTrue({"F111", "F112", "F113", "F114"}.issubset(codes))
        stable = stable_file_diagnostics(path)
        self.assertFalse(stable["ok"])
        self.assertEqual(
            sorted(
                stable["diagnostics"],
                key=lambda row: (
                    row.get("source") or "",
                    row.get("line") or 0,
                    row.get("column") or 0,
                    {"error": 0, "warning": 1, "info": 2}.get(row.get("severity"), 9),
                    row.get("code") or "",
                    row.get("message") or "",
                ),
            ),
            stable["diagnostics"],
        )

    def test_duplicate_ids_across_active_and_archive_are_errors(self):
        active = self.write("active.txt", "[ ] T Active id:X\n")
        archive = self.write("archive.txt", "[x] T Archived id:X\n")
        report = workspace_diagnostics([active], archive_paths=[archive])
        self.assertIn("F115", self.codes(report))
        self.assertFalse(report["ok"])

    def test_dangling_links_missing_parent_and_dependency_cycle(self):
        first = self.write(
            "a.txt",
            "[ ] T First id:A depends_on:B ref:MISSING parent:NO-PARENT\n",
        )
        second = self.write("b.txt", "[ ] T Second id:B depends_on:A\n")
        report = workspace_diagnostics([first, second])
        codes = self.codes(report)
        self.assertIn("F116", codes)
        self.assertIn("F117", codes)
        self.assertIn("F118", codes)
        cycle_messages = [
            row["message"] for row in report["diagnostics"] if row["code"] == "F118"
        ]
        self.assertEqual(1, len(cycle_messages))

    def test_corrupt_timer_state_is_reported(self):
        life = self.write("life.txt", "[ ] T Task id:T-1\n")
        timer = self.write("timer.json", "not json\n")
        report = workspace_diagnostics([life], timer_paths=[timer])
        self.assertIn("F119", self.codes(report))

    def test_unsafe_write_target_and_windows_drive_relative_are_reported(self):
        life = self.write("life.txt", "[ ] T Task id:T-1\n")
        other = self.path("other.txt")
        report = workspace_diagnostics([life], write_path=other)
        self.assertIn("F120", self.codes(report))
        drive = workspace_diagnostics([life], write_path="C:relative\\life.txt")
        rows = [row for row in drive["diagnostics"] if row["code"] == "F120"]
        self.assertEqual("error", rows[0]["severity"])

    def test_persisted_revision_usage_and_corruption_are_diagnostics(self):
        life = self.write("life.txt", "[ ] T Task id:T-1\n")
        metrics = self.write(
            "metrics.json",
            json.dumps({"legacy_fallback_total": 3}) + "\n",
        )
        report = workspace_diagnostics([life], revision_metrics_path=metrics)
        self.assertIn("F121", self.codes(report))
        self.write("metrics.json", "broken\n")
        corrupt = workspace_diagnostics([life], revision_metrics_path=metrics)
        self.assertIn("F122", self.codes(corrupt))

    def test_severity_counts_and_deduplication_are_stable(self):
        life = self.write("life.txt", "#! broken\n[ ] T Task id:T-1 ref:MISSING\n")
        report = workspace_diagnostics([life])
        self.assertEqual(len(report["diagnostics"]), report["diagnostic_count"])
        self.assertEqual(
            report["diagnostic_count"],
            sum(report["severity_counts"].values()),
        )
        keys = [
            (row["source"], row["line"], row["column"], row["code"], row["message"])
            for row in report["diagnostics"]
        ]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
