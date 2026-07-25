from __future__ import unicode_literals

import contextlib
import io
import json
import os
import shlex
import sys
import tempfile
import unittest

from lifetxt import extra_cli, mutation
from lifetxt.multi_target import apply_multi_target, text_plan
from lifetxt.transaction_journal import abandon_with_backup


class P0CliV6Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.life = os.path.join(self.root, "life.txt")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Before id:t1\n")

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = extra_cli.main(argv)
        self.assertEqual(0, code, output.getvalue())
        return json.loads(output.getvalue())

    def test_delegated_prepare_inspect_and_apply_cli(self):
        script = os.path.join(self.root, "edit.py")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(
                "import pathlib,sys\n"
                "pathlib.Path(sys.argv[1]).write_text('[ ] T After id:t1\\n', encoding='utf-8')\n"
            )
        proposal = os.path.join(self.root, "proposal.json")
        command = "%s %s {file}" % (shlex.quote(sys.executable), shlex.quote(script))
        prepared = self.run_cli([
            "safety", "delegated", "prepare", "--path", self.life,
            "--proposal", proposal, "--command", command,
        ])
        self.assertTrue(prepared["changed"])
        inspected = self.run_cli([
            "safety", "delegated", "inspect", "--proposal", proposal,
        ])
        self.assertEqual("prepared", inspected["state"])
        applied = self.run_cli([
            "safety", "delegated", "apply", "--proposal", proposal,
            "--expected-proposal-revision", inspected["proposal_revision"],
        ])
        self.assertTrue(applied["applied"])
        with open(self.life, encoding="utf-8") as handle:
            self.assertIn("After", handle.read())

    def test_fault_drill_cli_auto_recovery_and_repeat(self):
        report = self.run_cli([
            "safety", "transactions", "drill",
            "--point", "after_journal_publish",
            "--recovery", "auto", "--repeat-recovery",
        ])
        self.assertTrue(report["ok"])
        self.assertEqual("resume", report["recovery"])
        self.assertTrue(report["repeat_recovery"])
        self.assertIsNotNone(report["repeated_recovery_result"])

    def test_restore_backup_inspect_cli(self):
        other = os.path.join(self.root, "other.txt")
        with open(other, "w", encoding="utf-8") as handle:
            handle.write("before-other\n")
        journals = os.path.join(self.root, "journals")
        result = apply_multi_target([
            text_plan(
                self.life, lambda _value: "[x] T After id:t1\n",
                mutation.read_text_snapshot(self.life).content_hash,
            ),
            text_plan(
                other, lambda _value: "after-other\n",
                mutation.read_text_snapshot(other).content_hash,
            ),
        ], operation="cli.restore", journal_dir=journals, transaction_id="cli-restore")
        backup_root = os.path.join(self.root, "backups")
        abandoned = abandon_with_backup(result.journal_path, backup_root)
        report = self.run_cli([
            "safety", "transactions", "restore-backup",
            "--backup-dir", abandoned["backup_path"],
            "--restore-action", "inspect", "--operator", "alice",
        ])
        self.assertTrue(report["ok"])
        self.assertIsNone(report["working_dir"])


if __name__ == "__main__":
    unittest.main()
