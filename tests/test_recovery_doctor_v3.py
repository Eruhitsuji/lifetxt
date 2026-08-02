import json
import os
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.doctor import doctor_report
from lifetxt.multi_target import apply_multi_target, text_plan
from lifetxt.workspace_diagnostics import workspace_diagnostics


class RecoveryDoctorV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.journals = os.path.join(self.temp.name, "transactions")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")

    def make_committed(self):
        return apply_multi_target(
            [
                text_plan(
                    self.life,
                    lambda _text: "[/] T Task id:t1\n",
                    mutation.read_text_snapshot(self.life).content_hash,
                )
            ],
            operation="doctor.test",
            journal_dir=self.journals,
        )

    def test_terminal_transaction_is_reported_without_hard_failure(self):
        self.make_committed()
        report = doctor_report([self.life], journal_dir=self.journals)
        self.assertEqual(1, report["transactions"]["count"])
        self.assertFalse(report["transactions"]["recovery_required"])
        self.assertNotIn("transaction_recovery", report["hard_failures"])

    def test_interrupted_transaction_is_hard_failure_and_f124(self):
        result = self.make_committed()
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        record["state"] = "committing"
        with open(result.journal_path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        report = doctor_report([self.life], journal_dir=self.journals)
        self.assertIn("transaction_recovery", report["hard_failures"])
        self.assertIn(
            "F124", [row["code"] for row in report["diagnostics"]["diagnostics"]]
        )

    def test_diverged_target_adds_f126(self):
        result = self.make_committed()
        with open(result.journal_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        record["state"] = "committing"
        with open(result.journal_path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        mutation.atomic_write_bytes(self.life, b"third party\n")
        report = workspace_diagnostics([self.life], journal_dir=self.journals)
        codes = [row["code"] for row in report["diagnostics"]]
        self.assertIn("F124", codes)
        self.assertIn("F126", codes)

    def test_corrupt_journal_adds_f123(self):
        directory = os.path.join(self.journals, "bad")
        os.makedirs(directory)
        with open(
            os.path.join(directory, "journal.json"), "w", encoding="utf-8"
        ) as handle:
            handle.write("not json")
        report = workspace_diagnostics([self.life], journal_dir=self.journals)
        self.assertIn("F123", [row["code"] for row in report["diagnostics"]])


if __name__ == "__main__":
    unittest.main()
