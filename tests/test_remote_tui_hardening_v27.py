import io
import unittest
from unittest import mock

from lifetxt.remote_client_writes import interactive_tui


class RemoteTuiHardeningV27Tests(unittest.TestCase):
    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_non_visible_ticket_does_not_exit_session(self, permissions, snapshot):
        permissions.return_value = {
            "principal": {"id": "reader", "role": "reader"},
            "scopes": ["read"],
            "grants": {},
            "can_write": False,
            "ticket_operations": [],
        }
        snapshot.return_value = {"revision": "r1", "tickets": []}
        answers = iter(["show", "PRIVATE-1", "quit"])
        output = io.StringIO()
        value = interactive_tui(
            {"url": "https://example.test"},
            input_fn=lambda prompt: next(answers),
            output=output,
        )
        self.assertEqual(value["error"], "REMOTE_TICKET_NOT_VISIBLE")
        self.assertIn("REMOTE_TICKET_NOT_VISIBLE", output.getvalue())

    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_keyboard_interrupt_is_safe_cancel(self, permissions, snapshot):
        permissions.return_value = {
            "principal": {"id": "editor", "role": "editor"},
            "scopes": ["read", "write"],
            "grants": {},
            "can_write": True,
            "ticket_operations": ["edit"],
        }
        snapshot.return_value = {"revision": "r1", "tickets": []}

        def interrupted(prompt):
            raise KeyboardInterrupt()

        output = io.StringIO()
        value = interactive_tui(
            {"url": "https://example.test"},
            input_fn=interrupted,
            output=output,
        )
        self.assertTrue(value["cancelled"])
        self.assertEqual(value["reason"], "interrupted")
        self.assertIn("cancelled", output.getvalue())

    @mock.patch("lifetxt.remote_client_writes.mutate_ticket")
    @mock.patch("lifetxt.remote_client_writes.snapshot")
    @mock.patch("lifetxt.remote_client_writes.remote_permissions")
    def test_eof_during_confirmation_never_mutates(self, permissions, snapshot, mutate):
        permissions.return_value = {
            "principal": {"id": "editor", "role": "editor"},
            "scopes": ["read", "write"],
            "grants": {},
            "can_write": True,
            "ticket_operations": ["comment"],
        }
        snapshot.return_value = {"revision": "r1", "tickets": []}
        calls = iter(["comment", "T-1", "hello"])

        def answers(prompt):
            try:
                return next(calls)
            except StopIteration:
                raise EOFError()

        output = io.StringIO()
        # Confirmation is cancelled, then the next operation prompt receives EOF
        # and terminates the session safely.
        value = interactive_tui(
            {"url": "https://example.test"},
            input_fn=answers,
            output=output,
        )
        self.assertTrue(value["cancelled"])
        mutate.assert_not_called()
        self.assertIn("confirmation cancelled", output.getvalue())


if __name__ == "__main__":
    unittest.main()
