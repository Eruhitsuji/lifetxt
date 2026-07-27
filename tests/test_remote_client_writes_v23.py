import io
import unittest
from unittest import mock

from lifetxt.remote_client_writes import (
    create_ticket,
    edit_ticket,
    interactive_tui,
    remote_permissions,
)


class RemoteClientWritesTests(unittest.TestCase):
    @mock.patch("lifetxt.remote_client_writes.request")
    def test_permissions_expose_effective_write_access(self, request):
        request.side_effect = [
            ({"principal": {"id": "alice", "role": "editor", "scopes": ["read", "write"]}}, {}),
            ({"mutation_policy": {"ticket_mutations_enabled": True, "ticket_operations": ["create", "edit"]}}, {}),
        ]
        value = remote_permissions({"url": "https://example.test"})
        self.assertTrue(value["can_write"])
        self.assertEqual(value["ticket_operations"], ["create", "edit"])

    @mock.patch("lifetxt.remote_client_writes.request")
    @mock.patch("lifetxt.remote_client_writes.snapshot")
    def test_create_uses_snapshot_revision_and_transaction_id(self, snapshot, request):
        snapshot.return_value = {"revision": "a" * 64}
        request.return_value = ({"operation": "create", "replayed": False}, {})
        value = create_ticket(
            {"url": "https://example.test"},
            "WEB-1",
            "Remote issue",
            transaction_id="tx-web-1",
        )
        self.assertEqual(value["operation"], "create")
        args, kwargs = request.call_args
        self.assertEqual(args[1:3], ("POST", "/api/remote/v1/ticket-mutations"))
        self.assertEqual(kwargs["revision"], "a" * 64)
        self.assertEqual(kwargs["payload"]["transaction_id"], "tx-web-1")

    @mock.patch("lifetxt.remote_client_writes.mutate_ticket")
    def test_edit_parses_fields(self, mutate):
        edit_ticket({"url": "https://example.test"}, "WEB-2", {"priority": "high"}, ["milestone"])
        payload = mutate.call_args.args[2]
        self.assertEqual(payload["set"], {"priority": "high"})
        self.assertEqual(payload["unset"], ["milestone"])

    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_interactive_tui_is_read_only_without_permission(self, permissions, snapshot):
        permissions.return_value = {
            "principal": {"id": "reader", "role": "reader"},
            "scopes": ["read"],
            "can_write": False,
            "ticket_operations": [],
        }
        snapshot.return_value = {"revision": "r", "tickets": [{"id": "T-1", "title": "Read"}]}
        output = io.StringIO()
        value = interactive_tui({"url": "https://example.test"}, output=output)
        self.assertEqual(value["mode"], "read-only")
        self.assertIn("T-1", output.getvalue())
        self.assertIn("read-only", output.getvalue())

    @mock.patch("lifetxt.remote_client_writes.mutate_ticket")
    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_interactive_tui_confirms_before_write(self, permissions, snapshot, mutate):
        permissions.return_value = {
            "principal": {"id": "editor", "role": "editor"},
            "scopes": ["read", "write"],
            "can_write": True,
            "ticket_operations": ["comment"],
        }
        snapshot.return_value = {"revision": "r", "tickets": []}
        mutate.return_value = {"operation": "comment", "replayed": False}
        answers = iter(["comment", "T-1", "hello", "yes"])
        value = interactive_tui(
            {"url": "https://example.test"},
            input_fn=lambda prompt: next(answers),
            output=io.StringIO(),
        )
        self.assertEqual(value["operation"], "comment")
        mutate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
