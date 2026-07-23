import contextlib
import io
import json
import os
import socket
import tempfile
import time
import unittest

from lifetxt import entrypoint
from lifetxt.extra_cli import _build_parser
from lifetxt.revision_telemetry import RevisionMetricsStore


class DoctorCliV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.metrics = os.path.join(self.temp_dir.name, "metrics.json")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("#! timezone: Asia/Tokyo\n[ ] T Task id:T-1\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_parsers_register_doctor_revisions_and_timezone_policies(self):
        doctor = _build_parser("doctor").parse_args(
            ["--workspace-safety", self.life, "--fold-policy", "later", "--gap-policy", "next"]
        )
        self.assertTrue(doctor.workspace_safety)
        self.assertEqual("later", doctor.fold_policy)
        self.assertEqual("next", doctor.gap_policy)
        revisions = _build_parser("safety").parse_args(
            ["revisions", self.life, "--metrics-path", self.metrics]
        )
        self.assertEqual("revisions", revisions.safety_action)
        timezone = _build_parser("safety").parse_args(
            ["timezone", self.life, "--sample", "2026-07-23T12:00"]
        )
        self.assertEqual("2026-07-23T12:00", timezone.sample)

    def test_doctor_returns_integrated_json_report(self):
        code, stdout, stderr = self.run_command(
            [
                "doctor",
                "--workspace-safety",
                self.life,
                "--revision-metrics",
                self.metrics,
                "--format",
                "json",
                "--pretty",
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertTrue(report["ok"], report)
        self.assertEqual("Asia/Tokyo", report["timezone"]["timezone"])
        self.assertIn("revision_migration", report)
        self.assertIn("locks", report)
        self.assertIn("diagnostics", report)
        self.assertIn("optional_dependencies", report)

    def test_safety_revisions_show_and_revision_checked_reset(self):
        store = RevisionMetricsStore(self.metrics)
        store.ensure()
        store.record_legacy_fallback("/api/items")
        code, stdout, stderr = self.run_command(
            [
                "safety",
                "revisions",
                self.life,
                "--metrics-path",
                self.metrics,
                "--pretty",
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual(1, report["legacy_fallback_total"])
        revision = report["metrics_revision"]
        code, stdout, stderr = self.run_command(
            [
                "safety",
                "revisions",
                self.life,
                "--metrics-path",
                self.metrics,
                "--reset",
                "--expected-hash",
                revision,
                "--pretty",
            ]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(0, json.loads(stdout)["legacy_fallback_total"])
        code, stdout, stderr = self.run_command(
            [
                "safety",
                "revisions",
                self.life,
                "--metrics-path",
                self.metrics,
                "--reset",
                "--expected-hash",
                revision,
            ]
        )
        self.assertEqual(1, code)
        conflict = json.loads(stdout)
        self.assertEqual("CONFLICT", conflict["error"])
        self.assertEqual(revision, conflict["expected_revision"])
        self.assertRegex(conflict["current_revision"], r"^[0-9a-f]{64}$")

    def test_safety_timezone_can_interpret_sample(self):
        code, stdout, stderr = self.run_command(
            [
                "safety",
                "timezone",
                self.life,
                "--sample",
                "2026-07-23T12:00",
                "--pretty",
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual("2026-07-23T12:00:00+09:00", report["sample"]["output"])

    def test_stale_lock_cleanup_requires_force(self):
        lock = self.life + ".lifetxt.lock"
        with open(lock, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": 99999999,
                    "host": socket.gethostname(),
                    "operation": "test",
                    "target": self.life,
                },
                handle,
            )
        old = time.time() - 600
        os.utime(lock, (old, old))
        code, stdout, stderr = self.run_command(
            [
                "doctor",
                "--workspace-safety",
                self.life,
                "--cleanup-stale",
                "--stale-after",
                "1",
                "--pretty",
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertTrue(os.path.exists(lock))
        self.assertEqual("--force is required", report["locks"]["cleanup"]["skipped"][0]["reason"])
        code, stdout, stderr = self.run_command(
            [
                "doctor",
                "--workspace-safety",
                self.life,
                "--cleanup-stale",
                "--force",
                "--stale-after",
                "1",
                "--pretty",
            ]
        )
        self.assertEqual(0, code, stderr)
        self.assertFalse(os.path.exists(lock))
        self.assertEqual([lock], json.loads(stdout)["locks"]["cleanup"]["removed"])


if __name__ == "__main__":
    unittest.main()
