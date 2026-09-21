import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "deployment" / "ubuntu-server.md"
FORMAT_DOC = ROOT / "docs" / "en" / "backup-format-v1.md"


class UbuntuServerBackupDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runbook = RUNBOOK.read_text(encoding="utf-8")
        cls.format_doc = FORMAT_DOC.read_text(encoding="utf-8")

    def test_runbook_covers_generated_schedule_and_operations(self):
        required = (
            '"backup_schedule"',
            '"destination": "/srv/lifetxt/backups/disaster-recovery"',
            '"keep_last": 14',
            '"backend": "rclone"',
            "lifetxt-backup.service",
            "lifetxt-backup.timer",
            "lifetxt backup status",
            "lifetxt backup verify",
            "lifetxt backup restore",
            "--dry-run",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, self.runbook)

    def test_runbook_preserves_the_important_safety_boundaries(self):
        self.assertIn("complete local", self.runbook)
        self.assertIn("never `sync`", self.runbook)
        self.assertIn("does not delete remote objects", self.runbook)
        self.assertIn("Restore into a new staging directory first", self.runbook)
        self.assertIn("Git-commit worker", self.runbook)
        self.assertIn("server-update", self.runbook)

    def test_runbook_covers_no_new_privileges_compatible_remote_dispatch(self):
        required = (
            '"remote_backup_polkit_rule_path"',
            '"service_command": ["/bin/systemctl", "--no-ask-password"]',
            "NoNewPrivileges=true",
            "only the configured service user",
            "`start lifetxt-backup.service`",
            "no stop, restart",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, self.runbook)

    def test_format_doc_links_to_the_existing_runbook_not_a_missing_page(self):
        self.assertNotIn("(backups.md)", self.format_doc)
        self.assertIn(
            "../deployment/ubuntu-server.md#5-backup-and-restore",
            self.format_doc,
        )


if __name__ == "__main__":
    unittest.main()
