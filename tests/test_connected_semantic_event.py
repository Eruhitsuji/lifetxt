import unittest
from unittest import mock

from contrib.remote.connected_semantic_event import event_payload, send
from lifetxt.remote_client_writes import RemoteMutationConflict


class ConnectedSemanticEventTests(unittest.TestCase):
    def test_only_fixed_wan_payloads_are_allowed(self):
        self.assertEqual("WAN restored", event_payload("WAN_UP")["title"])
        self.assertEqual("E", event_payload("WAN_DOWN")["type"])
        with self.assertRaises(ValueError):
            event_payload("WAN_REBOOT")

    @mock.patch("contrib.remote.connected_semantic_event.mutate_item")
    @mock.patch("contrib.remote.connected_semantic_event.request")
    def test_capability_check_and_replay_retry_keep_same_identity(
        self, request, mutate
    ):
        request.side_effect = [
            ({"principal": {"scopes": ["read", "write"]}}, {"lifetxt_negotiated_protocol": "2"}),
            ({"features": ["item-mutations"], "mutation_policy": {"item_mutations_enabled": True}}, {"lifetxt_negotiated_protocol": "2"}),
        ]
        mutate.side_effect = [
            RemoteMutationConflict("stale", current_revision="new"),
            {"operation": "create", "replayed": True},
        ]
        result = send({"url": "https://example.test"}, "WAN_DOWN", "wan-down-1")
        self.assertTrue(result["replayed"])
        self.assertEqual(2, mutate.call_count)
        self.assertEqual("wan-down-1", mutate.call_args_list[1].kwargs["transaction_id"])
        self.assertEqual("WAN disconnected", mutate.call_args_list[1].args[2]["item"]["title"])

    @mock.patch("contrib.remote.connected_semantic_event.request")
    def test_missing_scope_or_disabled_capability_fails_before_mutation(self, request):
        request.return_value = (
            {"principal": {"scopes": ["read"]}},
            {"lifetxt_negotiated_protocol": "2"},
        )
        with self.assertRaisesRegex(RuntimeError, "write scope"):
            send({"url": "https://example.test"}, "WAN_UP", "wan-up-1")

    def test_transaction_id_is_required_and_safe(self):
        with self.assertRaises(ValueError):
            send({}, "WAN_UP", "")
        with self.assertRaises(ValueError):
            send({}, "WAN_UP", "bad value")


if __name__ == "__main__":
    unittest.main()
