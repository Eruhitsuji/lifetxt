import unittest
from unittest import mock

from lifetxt.remote_client_writes import remote_permissions


class RemoteClientWritesCompatibilityTests(unittest.TestCase):
    @mock.patch("lifetxt.remote_client_writes.request")
    def test_real_server_operations_key_admits_editor(self, request):
        request.side_effect = [
            (
                {"principal": {
                    "id": "alice",
                    "role": "editor",
                    "scopes": ["read", "write"],
                    "projects": ["web"],
                }},
                {"lifetxt_negotiated_protocol": 2},
            ),
            (
                {
                    "capability_revision": "body-cap-revision",
                    "mutation_policy": {
                        "admission_only": False,
                        "authoritative_remote_writes_enabled": True,
                        "ticket_mutations_enabled": True,
                        "operations": [
                            "create", "edit", "transition", "comment", "log_time"
                        ],
                        "single_writable_source_only": True,
                        "exact_revision_required": True,
                        "transaction_id_required": True,
                        "append_only_history_required": True,
                        "multi_file_mutations_enabled": False,
                    },
                },
                {},
            ),
        ]
        value = remote_permissions({"url": "https://example.test"})
        self.assertTrue(value["can_write"])
        self.assertEqual(
            value["ticket_operations"],
            ["create", "edit", "transition", "comment", "log_time"],
        )
        self.assertEqual(value["capability_revision"], "body-cap-revision")
        self.assertIn("single_writable_source_only", value["limitations"])
        self.assertIn("multi_file_mutations_disabled", value["limitations"])

    @mock.patch("lifetxt.remote_client_writes.request")
    def test_admission_only_refuses_mutations(self, request):
        request.side_effect = [
            ({"principal": {"id": "alice", "scopes": ["read", "write"]}}, {}),
            ({"mutation_policy": {
                "admission_only": True,
                "authoritative_remote_writes_enabled": False,
                "operations": ["create"],
            }}, {}),
        ]
        value = remote_permissions({"url": "https://example.test"})
        self.assertFalse(value["can_write"])
        self.assertIn("remote_write_admission_only", value["denial_reasons"])
        self.assertIn("ticket_mutations_disabled", value["denial_reasons"])


if __name__ == "__main__":
    unittest.main()
