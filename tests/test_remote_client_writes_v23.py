import io
import json
import unittest
from unittest import mock

from lifetxt.remote_client_writes import (
    RemoteMutationConflict,
    _cmd_edit,
    create_ticket,
    edit_ticket,
    interactive_tui,
    remote_permissions,
    ticket_detail,
)


class RemoteClientWritesTests(unittest.TestCase):
    @mock.patch("lifetxt.remote_client_writes.request")
    def test_permissions_expose_effective_write_access_and_grants(self, request):
        request.side_effect = [
            (
                {"principal": {
                    "id": "alice", "role": "editor",
                    "scopes": ["read", "write"],
                    "projects": ["web"], "visibilities": ["shared"],
                }},
                {"lifetxt_negotiated_protocol": 2},
            ),
            (
                {"mutation_policy": {
                    "ticket_mutations_enabled": True,
                    "ticket_operations": ["create", "edit"],
                }},
                {
                    "lifetxt_negotiated_protocol": 2,
                    "X-Lifetxt-Remote-Capability-Revision": "cap-1",
                },
            ),
        ]
        value = remote_permissions({"url": "https://example.test"})
        self.assertTrue(value["can_write"])
        self.assertEqual(value["ticket_operations"], ["create", "edit"])
        self.assertEqual(value["grants"]["projects"], ["web"])
        self.assertEqual(value["grants"]["visibilities"], ["shared"])
        self.assertEqual(value["capability_revision"], "cap-1")
        self.assertEqual(value["denial_reasons"], [])

    @mock.patch("lifetxt.remote_client_writes.request")
    def test_permissions_explain_denied_writes(self, request):
        request.side_effect = [
            ({"principal": {"id": "reader", "scopes": ["read"]}}, {}),
            ({"mutation_policy": {"ticket_mutations_enabled": False}}, {}),
        ]
        value = remote_permissions({"url": "https://example.test"})
        self.assertFalse(value["can_write"])
        self.assertIn("principal_missing_write_scope", value["denial_reasons"])
        self.assertIn("ticket_mutations_disabled", value["denial_reasons"])

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
        payload = mutate.call_args[0][2]
        self.assertEqual(payload["set"], {"priority": "high"})
        self.assertEqual(payload["unset"], ["milestone"])

    def test_ticket_detail_uses_filtered_snapshot(self):
        value = ticket_detail(
            {"url": "https://example.test"},
            "T-1",
            {"revision": "r1", "tickets": [{"id": "T-1", "title": "Visible"}]},
        )
        self.assertEqual(value["revision"], "r1")
        self.assertEqual(value["ticket"]["title"], "Visible")
        with self.assertRaises(KeyError):
            ticket_detail(
                {"url": "https://example.test"},
                "PRIVATE-1",
                {"revision": "r1", "tickets": []},
            )

    @mock.patch("lifetxt.remote_client_writes.request")
    @mock.patch("lifetxt.remote_client_writes.snapshot")
    def test_revision_conflict_refreshes_without_retry(self, snapshot, request):
        snapshot.side_effect = [
            {"revision": "old", "tickets": [{"id": "T-1", "priority": "low"}]},
            {"revision": "new", "tickets": [{"id": "T-1", "priority": "urgent"}]},
        ]
        request.side_effect = RuntimeError(json.dumps({"error": "REVISION_CONFLICT"}))
        with self.assertRaises(RemoteMutationConflict) as caught:
            edit_ticket(
                {"url": "https://example.test"},
                "T-1",
                {"priority": "high"},
                transaction_id="tx-conflict",
            )
        value = caught.exception.as_dict()
        self.assertEqual(value["requested_revision"], "old")
        self.assertEqual(value["current_revision"], "new")
        self.assertFalse(value["automatic_retry"])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(value["comparison"][1]["current"], "urgent")
        self.assertEqual(value["comparison"][1]["requested"], "high")

    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_interactive_tui_is_read_only_but_can_show(self, permissions, snapshot):
        permissions.return_value = {
            "principal": {"id": "reader", "role": "reader"},
            "scopes": ["read"],
            "grants": {},
            "can_write": False,
            "ticket_operations": [],
        }
        snapshot.return_value = {
            "revision": "r",
            "tickets": [{"id": "T-1", "title": "Read", "status": "open"}],
        }
        answers = iter(["show", "T-1", "quit"])
        output = io.StringIO()
        value = interactive_tui(
            {"url": "https://example.test"},
            input_fn=lambda prompt: next(answers),
            output=output,
        )
        self.assertEqual(value["ticket"]["id"], "T-1")
        self.assertIn("status", output.getvalue())
        self.assertNotIn("apply authoritative mutation", output.getvalue())

    @mock.patch("lifetxt.remote_client_writes.mutate_ticket")
    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_interactive_tui_confirms_before_write(self, permissions, snapshot, mutate):
        permissions.return_value = {
            "principal": {"id": "editor", "role": "editor"},
            "scopes": ["read", "write"],
            "grants": {},
            "can_write": True,
            "ticket_operations": ["comment"],
        }
        snapshot.return_value = {"revision": "r", "tickets": []}
        mutate.return_value = {"operation": "comment", "replayed": False}
        answers = iter(["comment", "T-1", "hello", "yes", "quit"])
        output = io.StringIO()
        value = interactive_tui(
            {"url": "https://example.test"},
            input_fn=lambda prompt: next(answers),
            output=output,
        )
        self.assertEqual(value["operation"], "comment")
        self.assertIn("proposed mutation", output.getvalue())
        mutate.assert_called_once()

    @mock.patch("lifetxt.remote_client_writes.edit_ticket")
    @mock.patch("lifetxt.remote_client_writes.get_profile")
    def test_cli_conflict_returns_stable_exit_code(self, get_profile, edit):
        get_profile.return_value = {"url": "https://example.test"}
        edit.side_effect = RemoteMutationConflict(
            "conflict", requested_revision="old", current_revision="new")
        args = mock.Mock(
            profile="home", profiles_file=None, ticket_id="T-1",
            set=["priority=high"], unset=[], comment=None,
            transaction_id="tx", dry_run=False,
        )
        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            code = _cmd_edit(args)
        self.assertEqual(code, 3)
        self.assertIn("REMOTE_MUTATION_CONFLICT", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
