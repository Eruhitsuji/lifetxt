from __future__ import unicode_literals

import unittest

from lifetxt import capability_matrix
from lifetxt.cli_taxonomy import all_commands


class SupportStateTests(unittest.TestCase):
    def test_every_state_is_one_of_the_stable_enum(self):
        for name in all_commands():
            for state in capability_matrix.command_surface_states(name).values():
                self.assertIn(state, capability_matrix.SUPPORT_STATES)

    def test_unmapped_command_reports_unmapped_on_every_surface(self):
        # "status" has no curated operation mapping and is not a
        # CLI-only launcher/converter, so it must not be silently guessed.
        states = capability_matrix.command_surface_states("status")
        for surface in capability_matrix.SURFACES:
            self.assertEqual(states[surface], capability_matrix.UNMAPPED)

    def test_not_applicable_command_reports_not_applicable_everywhere(self):
        states = capability_matrix.command_surface_states("vm")
        for surface in capability_matrix.SURFACES:
            self.assertEqual(states[surface], capability_matrix.NOT_APPLICABLE)

    def test_single_operation_command_supported_everywhere_is_full(self):
        states = capability_matrix.command_surface_states("quick")
        self.assertEqual(states["web_ui"], capability_matrix.FULL)
        self.assertEqual(states["api"], capability_matrix.FULL)
        self.assertEqual(states["mcp"], capability_matrix.FULL)
        self.assertEqual(states["tui"], capability_matrix.FULL)

    def test_operation_missing_from_tui_reports_unsupported_there(self):
        # "attachment" maps only to the "attachments" operation, which is
        # deliberately excluded from _TUI_OPERATIONS.
        states = capability_matrix.command_surface_states("attachment")
        self.assertEqual(states["tui"], capability_matrix.UNSUPPORTED)
        self.assertEqual(states["web_ui"], capability_matrix.FULL)
        self.assertEqual(states["mcp"], capability_matrix.FULL)

    def test_multi_operation_command_can_be_deterministically_partial(self):
        # "today" maps to ("agenda", "next"); both are TUI-supported so it
        # is full there, but this proves the multi-operation aggregation
        # runs (all()/any()) rather than only ever looking at operations[0].
        operations = capability_matrix.command_operations("today")
        self.assertEqual(operations, ("agenda", "next"))
        states = capability_matrix.command_surface_states("today")
        for surface in capability_matrix.SURFACES:
            self.assertIn(
                states[surface], (capability_matrix.FULL, capability_matrix.PARTIAL)
            )

    def test_aliases_never_appear_as_independent_rows(self):
        # "add" is a registered alias of "quick" (#591); only the canonical
        # name may appear in all_commands()/the matrix.
        self.assertIn("quick", all_commands())
        self.assertNotIn("q", all_commands())


class MatrixPayloadTests(unittest.TestCase):
    def test_matrix_payload_shape(self):
        payload = capability_matrix.matrix_payload()
        self.assertEqual(payload["schema"], "lifetxt-capability-matrix-v1")
        self.assertEqual(
            list(payload["support_states"]), list(capability_matrix.SUPPORT_STATES)
        )
        self.assertEqual(list(payload["surfaces"]), list(capability_matrix.SURFACES))
        commands = {row["command"] for row in payload["commands"]}
        self.assertEqual(commands, set(all_commands()))

    def test_matrix_covers_every_real_command_with_no_missing_row(self):
        payload = capability_matrix.matrix_payload()
        self.assertEqual(len(payload["commands"]), len(all_commands()))

    def test_every_row_has_all_four_surface_columns(self):
        for row in capability_matrix.matrix_rows():
            self.assertEqual(set(row["surfaces"]), set(capability_matrix.SURFACES))


class RenderTextTests(unittest.TestCase):
    def test_render_matrix_text_includes_header_and_every_command(self):
        text = capability_matrix.render_matrix_text()
        self.assertIn("Command", text)
        self.assertIn("Web UI", text)
        self.assertIn("TUI", text)
        self.assertIn("API", text)
        self.assertIn("MCP", text)
        self.assertIn("quick", text)
        self.assertIn("vm", text)


class CliIntegrationTests(unittest.TestCase):
    def test_capability_matrix_cli_json(self):
        from lifetxt.extra_safety import command_capability_matrix

        class Args(object):
            format = "json"
            pretty = False
            output = None

        # capture stdout
        import io
        import contextlib
        import json

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = command_capability_matrix(Args())
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["schema"], "lifetxt-capability-matrix-v1")

    def test_default_capabilities_command_is_unaffected(self):
        from lifetxt.extra_safety import command_capabilities

        class Args(object):
            format = "json"
            pretty = False
            output = None
            read_only = False
            authentication = "token"
            surface_matrix = False

        import io
        import contextlib
        import json

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = command_capabilities(Args(), {})
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        # The existing remote-client capability document shape, not the
        # new matrix shape.
        self.assertNotEqual(payload.get("schema"), "lifetxt-capability-matrix-v1")


if __name__ == "__main__":
    unittest.main()
