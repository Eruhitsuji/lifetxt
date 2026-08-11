from __future__ import unicode_literals

import os
import json
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.multi_target import apply_multi_target, text_plan
from lifetxt.transaction_admin import TransactionAuthorizationError, authorize_operator
from lifetxt.transaction_journal import (
    abandon_with_backup,
    restore_backup,
    verify_backup,
)
from lifetxt.transaction_policy import TransactionPolicyError


class BackupRestoreV6Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.first = os.path.join(self.root, "first.txt")
        self.second = os.path.join(self.root, "second.txt")
        for path, text in (
            (self.first, "before-first\n"),
            (self.second, "before-second\n"),
        ):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        self.journals = os.path.join(self.root, "journals")
        result = apply_multi_target(
            [
                text_plan(
                    self.first,
                    lambda _value: "after-first\n",
                    mutation.read_text_snapshot(self.first).content_hash,
                ),
                text_plan(
                    self.second,
                    lambda _value: "after-second\n",
                    mutation.read_text_snapshot(self.second).content_hash,
                ),
            ],
            operation="restore.test",
            journal_dir=self.journals,
            transaction_id="restore-test",
        )
        self.backups = os.path.join(self.root, "backups")
        abandoned = abandon_with_backup(result.journal_path, self.backups)
        self.backup = abandoned["backup_path"]
        self.config = {
            "transactions": {
                "require_operator_authorization": True,
                "authorized_operators": ["alice"],
            }
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_restore_compensation_uses_verified_working_copy(self):
        report = restore_backup(
            self.backup,
            action="compensate",
            operator="alice",
            config=self.config,
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["original_backup_unchanged"])
        self.assertTrue(verify_backup(self.backup)["ok"])
        with open(self.first, encoding="utf-8") as handle:
            self.assertEqual("before-first\n", handle.read())
        with open(self.second, encoding="utf-8") as handle:
            self.assertEqual("before-second\n", handle.read())
        self.assertTrue(os.path.exists(report["working_manifest"]))

    def test_inspect_does_not_create_working_copy(self):
        report = restore_backup(
            self.backup,
            action="inspect",
            operator="alice",
            config=self.config,
        )
        self.assertTrue(report["ok"])
        self.assertIsNone(report["working_dir"])
        self.assertTrue(report["original_backup_unchanged"])

    def test_operator_authorization_is_enforced(self):
        with self.assertRaises(TransactionPolicyError):
            authorize_operator(self.config, "mallory", action="restore")
        with self.assertRaises(TransactionPolicyError):
            restore_backup(
                self.backup, action="inspect", operator="mallory", config=self.config
            )

    def test_remote_restore_uses_authenticated_context_identity(self):
        config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {"id": "alice"},
                    {"id": "bob"},
                ],
            },
            "transactions": {
                "recovery_authorized_roles": ["recovery-admin"],
                "recovery_required_scopes": ["recovery"],
                "recovery_allowed_projects": ["default"],
                "require_destructive_recovery_approval": True,
            },
        }
        context = {
            "authenticated": True,
            "principal": {
                "id": "alice",
                "roles": ["recovery-admin"],
                "scopes": ["recovery", "recovery:compensate"],
                "project": "default",
            },
            "session": {"active": True},
        }
        report = restore_backup(
            self.backup,
            action="compensate",
            operator="mallory",
            config=config,
            authorization_context=context,
            approval={"approved": True, "approved_by": "bob"},
            audit_file=os.path.join(self.root, "admin-audit.json"),
        )
        self.assertTrue(report["ok"])
        self.assertEqual("alice", report["authorization"]["operator"])
        self.assertTrue(report["authorization"]["authenticated_required"])
        self.assertEqual("bob", report["authorization"]["approved_by"])
        with open(
            os.path.join(self.root, "admin-audit.json"), encoding="utf-8"
        ) as handle:
            audit = json.load(handle)
        self.assertEqual("alice", audit["events"][-1]["operator"])

    def test_remote_restore_denies_caller_supplied_identity(self):
        config = {
            "remote": {"enabled": True, "principals": [{"id": "alice"}]},
            "transactions": {"recovery_authorized_roles": ["recovery-admin"]},
        }
        with self.assertRaises(TransactionAuthorizationError) as caught:
            restore_backup(
                self.backup,
                action="inspect",
                operator="alice",
                config=config,
                authorization_context={},
            )
        self.assertIn(
            "unauthenticated_context", caught.exception.report["denial_reasons"]
        )

    def test_remote_restore_denies_stale_session(self):
        config = {
            "remote": {"enabled": True, "principals": [{"id": "alice"}]},
            "transactions": {"recovery_authorized_roles": ["recovery-admin"]},
        }
        context = {
            "authenticated": True,
            "principal": {"id": "alice", "roles": ["recovery-admin"]},
            "session": {"active": False},
        }
        with self.assertRaises(TransactionAuthorizationError) as caught:
            restore_backup(
                self.backup,
                action="inspect",
                config=config,
                authorization_context=context,
            )
        self.assertIn("stale_session", caught.exception.report["denial_reasons"])

    def test_remote_restore_denies_scope_and_project_mismatch_before_mutation(self):
        config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {"id": "alice"},
                    {"id": "bob"},
                ],
            },
            "transactions": {
                "recovery_authorized_roles": ["recovery-admin"],
                "recovery_required_scopes": ["recovery"],
                "recovery_allowed_projects": ["default"],
                "require_destructive_recovery_approval": True,
            },
        }
        context = {
            "authenticated": True,
            "principal": {
                "id": "alice",
                "roles": ["recovery-admin"],
                "scopes": ["recovery"],
                "project": "other",
            },
            "session": {"active": True},
        }
        denied_working_dir = os.path.join(self.root, "restore-denied")
        with self.assertRaises(TransactionAuthorizationError) as caught:
            restore_backup(
                self.backup,
                action="compensate",
                working_dir=denied_working_dir,
                config=config,
                authorization_context=context,
                approval={"approved": True, "approved_by": "bob"},
            )
        reasons = caught.exception.report["denial_reasons"]
        self.assertIn("scope_mismatch", reasons)
        self.assertIn("project_scope_mismatch", reasons)
        self.assertFalse(os.path.exists(denied_working_dir))

    def test_destructive_restore_requires_separate_approval(self):
        config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {"id": "alice"},
                    {"id": "bob"},
                ],
            },
            "transactions": {
                "recovery_authorized_roles": ["recovery-admin"],
                "recovery_required_scopes": ["recovery"],
                "require_destructive_recovery_approval": True,
            },
        }
        context = {
            "authenticated": True,
            "principal": {
                "id": "alice",
                "roles": ["recovery-admin"],
                "scopes": ["recovery", "recovery:compensate"],
            },
            "session": {"active": True},
        }
        with self.assertRaises(TransactionAuthorizationError) as caught:
            restore_backup(
                self.backup,
                action="compensate",
                config=config,
                authorization_context=context,
                approval={"approved": True, "approved_by": "alice"},
            )
        self.assertIn(
            "approval_separation_required", caught.exception.report["denial_reasons"]
        )


if __name__ == "__main__":
    unittest.main()
