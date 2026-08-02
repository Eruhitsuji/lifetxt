from __future__ import unicode_literals

import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt.mutation import MISSING_HASH, MutationConflict, read_text_snapshot
from lifetxt.transaction_admin import (
    POLICY_VERSION,
    TransactionPolicyVersionError,
    append_admin_audit,
    migrate_policy_file,
    policy_document,
    preflight_report,
    read_policy_document,
    rotate_archives,
    write_policy_document,
)
from lifetxt.transaction_policy import policy_from_config


class TransactionAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.journal = os.path.join(self.root, "journals")
        os.makedirs(self.journal, mode=0o700)
        self.policy_path = os.path.join(self.journal, "policy.json")
        self.audit_path = os.path.join(self.journal, "audit.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_policy_write_is_versioned_revision_checked_and_runtime_loaded(self):
        document = policy_document(operator="alice")
        document["policy"]["max_transactions"] = 12
        result = write_policy_document(
            self.policy_path,
            document,
            expected_revision=MISSING_HASH,
            operator="alice",
            audit_file=self.audit_path,
        )
        self.assertEqual(POLICY_VERSION, result["document"]["policy_version"])
        self.assertEqual(
            12,
            policy_from_config({"transactions": {"policy_file": self.policy_path}})[
                "max_transactions"
            ],
        )
        self.assertEqual("alice", read_policy_document(self.policy_path)["updated_by"])
        with self.assertRaises(MutationConflict):
            write_policy_document(
                self.policy_path, document, expected_revision=MISSING_HASH
            )

    def test_legacy_policy_migration_and_newer_refusal(self):
        with open(self.policy_path, "w", encoding="utf-8") as handle:
            json.dump({"max_transactions": 7}, handle)
        revision = read_text_snapshot(self.policy_path).content_hash
        result = migrate_policy_file(
            self.policy_path, expected_revision=revision, operator="bob"
        )
        self.assertEqual(0, result["document"]["migrated_from"])
        self.assertEqual(7, result["document"]["policy"]["max_transactions"])
        with open(self.policy_path, "w", encoding="utf-8") as handle:
            json.dump({"policy_version": 99, "policy": {}}, handle)
        with self.assertRaises(TransactionPolicyVersionError):
            migrate_policy_file(self.policy_path)

    def test_preflight_reports_current_migration_and_capacity(self):
        missing = preflight_report(self.journal)
        self.assertTrue(missing["ok"])
        self.assertEqual("missing", missing["policy_file"]["state"])
        with open(self.policy_path, "w", encoding="utf-8") as handle:
            json.dump({"max_transactions": 1}, handle)
        migration = preflight_report(self.journal)
        self.assertFalse(migration["ok"])
        self.assertEqual("migration_required", migration["policy_file"]["state"])

    def test_audit_is_bounded_and_private(self):
        for index in range(5):
            append_admin_audit(
                self.audit_path,
                "event",
                operator="op",
                details={"index": index},
                max_events=3,
            )
        with open(self.audit_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(
            [2, 3, 4], [row["details"]["index"] for row in record["events"]]
        )
        if os.name != "nt":
            self.assertEqual(0, os.stat(self.audit_path).st_mode & 0o077)

    def test_archive_rotation_is_dry_run_until_force(self):
        archive = os.path.join(self.root, "archive")
        os.makedirs(archive)
        for index in range(3):
            child = os.path.join(archive, "tx%d" % index)
            os.makedirs(child)
            with open(
                os.path.join(child, "journal.json"), "w", encoding="utf-8"
            ) as handle:
                handle.write("x" * (index + 1))
            with open(
                os.path.join(child, "integrity-manifest.json"), "w", encoding="utf-8"
            ) as handle:
                handle.write("{}")
            os.utime(child, (index + 1, index + 1))
        dry = rotate_archives(archive, max_archives=1, force=False)
        self.assertFalse(dry["ok"])
        self.assertEqual(2, len(dry["would_remove"]))
        done = rotate_archives(
            archive,
            max_archives=1,
            force=True,
            audit_file=self.audit_path,
            operator="admin",
        )
        self.assertTrue(done["ok"])
        self.assertEqual(2, len(done["removed"]))
        self.assertEqual(
            ["tx2"],
            sorted(name for name in os.listdir(archive) if name.startswith("tx")),
        )


if __name__ == "__main__":
    unittest.main()
