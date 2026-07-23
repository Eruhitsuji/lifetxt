import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint, mutation
from lifetxt.multi_target import apply_multi_target, text_plan


class RecoveryCliV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.journals = os.path.join(self.temp.name, "transactions")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def make_transaction(self):
        return apply_multi_target(
            [text_plan(self.life, lambda _text: "[/] T Task id:t1\n", mutation.read_text_snapshot(self.life).content_hash)],
            operation="cli.recovery",
            journal_dir=self.journals,
        )

    def test_list_inspect_export_and_compensate(self):
        result = self.make_transaction()
        code, out, err = self.run_command(["safety", "transactions", "list", "--journal-dir", self.journals, "--pretty"])
        self.assertEqual(0, code, err)
        self.assertEqual(1, json.loads(out)["count"])
        code, out, err = self.run_command(["safety", "transactions", "inspect", "--journal-dir", self.journals, "--journal", result.transaction_id, "--pretty"])
        self.assertEqual(0, code, err)
        self.assertEqual("committed", json.loads(out)["state"])
        evidence = os.path.join(self.temp.name, "evidence.json")
        code, out, err = self.run_command(["safety", "transactions", "export", "--journal-dir", self.journals, "--journal", result.transaction_id, "--output", evidence, "--pretty"])
        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(evidence))
        code, out, err = self.run_command(["safety", "transactions", "compensate", "--journal-dir", self.journals, "--journal", result.transaction_id, "--pretty"])
        self.assertEqual(0, code, err)
        self.assertEqual("compensated", json.loads(out)["state"])

    def test_doctor_support_bundle_redacts_paths_and_content(self):
        self.make_transaction()
        output = os.path.join(self.temp.name, "support.json")
        code, out, err = self.run_command([
            "doctor", "--workspace-safety", self.life,
            "--journal-dir", self.journals,
            "--support-bundle", output,
            "--pretty",
        ])
        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(output))
        with open(output, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(self.temp.name, text)
        self.assertNotIn("Task id:t1", text)
        self.assertIn("<path:", text)
        self.assertTrue(json.loads(out)["support_bundle"]["redacted"])

    def test_revision_metrics_relocate_and_export_cli(self):
        metrics = os.path.join(self.temp.name, "metrics.json")
        relocated = os.path.join(self.temp.name, "moved", "metrics.json")
        evidence = os.path.join(self.temp.name, "metrics-evidence.json")
        from lifetxt.revision_telemetry import RevisionMetricsStore
        store = RevisionMetricsStore(metrics)
        store.ensure()
        revision = store.content_hash()
        code, out, err = self.run_command([
            "safety", "revisions", self.life,
            "--metrics-path", metrics,
            "--relocate", relocated,
            "--expected-hash", revision,
            "--export-evidence", evidence,
            "--pretty",
        ])
        self.assertEqual(0, code, err)
        report = json.loads(out)
        self.assertTrue(report["relocated"])
        self.assertTrue(os.path.exists(relocated))
        self.assertTrue(os.path.exists(evidence))


if __name__ == "__main__":
    unittest.main()
