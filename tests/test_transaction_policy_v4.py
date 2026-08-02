import os
import tempfile
import unittest
from unittest import mock

from lifetxt.transaction_policy import (
    TransactionPolicyError,
    build_integrity_manifest,
    enforce_capacity,
    ensure_private_tree,
    fault_injection,
    fault_point,
    journal_usage,
    permission_report,
    policy_from_config,
    verify_integrity_manifest,
    version_compatibility,
    write_integrity_manifest,
)


class TransactionPolicyV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_policy_config_is_bounded_and_typed(self):
        policy = policy_from_config(
            {
                "transactions": {
                    "terminal_retention_days": "7",
                    "max_transactions": "3",
                    "max_total_bytes": "4096",
                    "max_transaction_bytes": "2048",
                    "require_private_permissions": "false",
                }
            }
        )
        self.assertEqual(7.0, policy["terminal_retention_days"])
        self.assertEqual(3, policy["max_transactions"])
        self.assertFalse(policy["require_private_permissions"])

    def test_windows_private_tree_ignores_posix_mode_bits(self):
        root = os.path.join(self.temp.name, "transactions")
        with mock.patch("lifetxt.transaction_policy.os.name", "nt"):
            report = ensure_private_tree(root, require_private=True)
        self.assertEqual([], report["problems"])
        self.assertTrue(report["private"])

    def test_capacity_rejects_count_total_and_single_transaction_limits(self):
        root = os.path.join(self.temp.name, "transactions")
        tx = os.path.join(root, "tx1")
        os.makedirs(tx)
        with open(os.path.join(tx, "journal.json"), "wb") as handle:
            handle.write(b"{}")
        usage = journal_usage(root)
        self.assertEqual(1, usage["transactions"])
        with self.assertRaises(TransactionPolicyError):
            enforce_capacity(root, dict(policy_from_config(), max_transactions=1), 0)
        with self.assertRaises(TransactionPolicyError):
            enforce_capacity(
                root, dict(policy_from_config(), max_total_bytes=1024), 4096
            )
        with self.assertRaises(TransactionPolicyError):
            enforce_capacity(
                root, dict(policy_from_config(), max_transaction_bytes=1024), 2048
            )

    def test_integrity_manifest_detects_tampering(self):
        root = os.path.join(self.temp.name, "backup")
        os.makedirs(root)
        target = os.path.join(root, "journal.json")
        with open(target, "wb") as handle:
            handle.write(b"original")
        path, manifest = write_integrity_manifest(root)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(1, len(manifest["files"]))
        self.assertTrue(verify_integrity_manifest(root)["ok"])
        with open(target, "wb") as handle:
            handle.write(b"tampered")
        self.assertFalse(verify_integrity_manifest(root)["ok"])

    def test_manifest_order_is_deterministic(self):
        root = os.path.join(self.temp.name, "backup")
        os.makedirs(root)
        for name in ("b.txt", "a.txt"):
            with open(os.path.join(root, name), "wb") as handle:
                handle.write(name.encode("ascii"))
        paths = [row["path"] for row in build_integrity_manifest(root)["files"]]
        self.assertEqual(["a.txt", "b.txt"], paths)

    def test_fault_hook_receives_boundary_and_details(self):
        observed = []
        with fault_injection(lambda point, details: observed.append((point, details))):
            fault_point("before_file_replace", path="/tmp/a")
        self.assertEqual("before_file_replace", observed[0][0])
        self.assertEqual("/tmp/a", observed[0][1]["path"])

    def test_version_compatibility_is_read_only_for_noncurrent_versions(self):
        self.assertTrue(version_compatibility({"schema_version": 1}, 1)["writable"])
        self.assertFalse(version_compatibility({"schema_version": 2}, 1)["writable"])
        self.assertEqual(
            "newer", version_compatibility({"schema_version": 2}, 1)["state"]
        )
        self.assertEqual("invalid", version_compatibility({}, 1)["state"])

    @unittest.skipUnless(os.name != "nt", "POSIX mode bits required")
    def test_permission_report_flags_group_or_other_bits(self):
        root = os.path.join(self.temp.name, "journal")
        os.makedirs(root, mode=0o700)
        os.chmod(root, 0o755)
        report = permission_report(root, require_private=True)
        self.assertFalse(report["private"])
        self.assertTrue(report["problems"])


if __name__ == "__main__":
    unittest.main()
