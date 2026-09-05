"""Unit tests for the bounded, TTY-only CLI error guidance helper (#643):
`lifetxt/cli_error_guidance.py`'s pure rendering functions, exercised
directly against synthetic exceptions and a monkeypatched `sys.stderr`.
CLI/entrypoint-level integration is covered separately in
`tests/test_cli_error_recovery.py`.
"""

import io
import unittest
from unittest import mock

from lifetxt import cli_error_guidance


class _FakeTty(io.StringIO):
    def isatty(self):
        return True


class _FakeNonTty(io.StringIO):
    def isatty(self):
        return False


class UnknownCommandTextTests(unittest.TestCase):
    def test_non_tty_shows_only_the_bare_error_line(self):
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeNonTty()):
            text = cli_error_guidance.unknown_command_text("todya")
        self.assertEqual("ERROR: Unknown command: 'todya'\n", text)

    def test_tty_adds_a_unique_suggestion_and_a_see_also_line(self):
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.unknown_command_text("todya")
        self.assertIn("ERROR: Unknown command: 'todya'", text)
        self.assertIn("Did you mean 'today'?", text)
        self.assertIn("lifetxt help beginner", text)

    def test_tty_with_no_close_match_shows_no_fabricated_candidate(self):
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.unknown_command_text("xyzzy_totally_unrelated")
        self.assertNotIn("Did you mean", text)
        self.assertIn("lifetxt help beginner", text)


class RenderValueErrorTextTests(unittest.TestCase):
    def test_unknown_workspace_non_tty_is_unchanged(self):
        exc = ValueError("Unknown workspace 'reseach'. Available: personal, research")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeNonTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertEqual(
            "ERROR: Unknown workspace 'reseach'. Available: personal, research\n", text
        )

    def test_unknown_workspace_tty_adds_suggestion_and_available_list(self):
        exc = ValueError("Unknown workspace 'reseach'. Available: personal, research")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertIn("Did you mean 'research'?", text)
        self.assertIn("Available:", text)
        self.assertIn("  personal", text)
        self.assertIn("  research", text)

    def test_unknown_workspace_with_no_configured_workspaces(self):
        exc = ValueError("Unknown workspace 'anything'. Available: (none)")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertIn("No workspaces are configured yet.", text)
        self.assertNotIn("Did you mean", text)

    def test_invalid_config_tty_suggests_doctor(self):
        exc = ValueError(
            "Could not read config: /tmp/x/.lifetxt.json\nReason: invalid JSON (boom)"
        )
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertIn("Try:", text)
        self.assertIn("lifetxt doctor", text)

    def test_invalid_config_non_tty_is_unchanged(self):
        exc = ValueError(
            "Could not read config: /tmp/x/.lifetxt.json\nReason: invalid JSON (boom)"
        )
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeNonTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertEqual(
            "ERROR: Could not read config: /tmp/x/.lifetxt.json\n"
            "Reason: invalid JSON (boom)\n",
            text,
        )

    def test_missing_config_option_value_shows_usage(self):
        exc = ValueError("--config requires a path.")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertIn("Usage: --config PATH", text)

    def test_missing_workspace_option_value_shows_usage(self):
        exc = ValueError("--workspace requires a name.")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertIn("Usage: --workspace NAME", text)

    def test_unrecognized_value_error_shows_only_the_bare_line(self):
        exc = ValueError("Something else entirely went wrong.")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_value_error_text(exc)
        self.assertEqual("ERROR: Something else entirely went wrong.\n", text)


class RenderOsErrorTextTests(unittest.TestCase):
    def test_missing_input_path_tty_adds_guidance(self):
        exc = OSError(2, "No such file or directory")
        exc.filename = "/no/such/file.txt"
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_os_error_text(exc)
        self.assertIn("Could not read: /no/such/file.txt", text)
        self.assertIn("lifetxt path", text)

    def test_missing_input_path_non_tty_is_unchanged(self):
        exc = OSError(2, "No such file or directory")
        exc.filename = "/no/such/file.txt"
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeNonTty()):
            text = cli_error_guidance.render_os_error_text(exc)
        self.assertEqual("ERROR: %s\n" % exc, text)

    def test_os_error_with_no_filename_shows_only_the_bare_line(self):
        exc = OSError("generic failure")
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.render_os_error_text(exc)
        self.assertEqual("ERROR: generic failure\n", text)


class LocalizationTests(unittest.TestCase):
    """#643's own "#631/#633 が利用可能なら固定文言はそこへ接続する" design
    principle: the TTY-only guidance lines (never the leading "ERROR: ..."
    line, which stays locale-independent) render through #631's shared
    localization catalog. A CodeX review finding against the #631-660
    batch noted this module still hardcoded every guidance string in
    English even after #631 landed in the same batch.
    """

    def test_unknown_command_guidance_is_localized_to_japanese(self):
        from lifetxt import i18n

        with i18n.locale_context("ja"):
            with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
                text = cli_error_guidance.unknown_command_text("todya")
        # The leading ERROR line stays English/locale-independent.
        self.assertTrue(text.startswith("ERROR: Unknown command: 'todya'\n"))
        self.assertIn("もしかして 'today' ではありませんか?", text)
        self.assertIn("参照:", text)
        self.assertNotIn("Did you mean", text)
        self.assertNotIn("See:", text)

    def test_unknown_workspace_guidance_is_localized_to_japanese(self):
        from lifetxt import i18n

        exc = ValueError("Unknown workspace 'reseach'. Available: personal, research")
        with i18n.locale_context("ja"):
            with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
                text = cli_error_guidance.render_value_error_text(exc)
        # The leading ERROR line is untouched (it happens to also contain
        # the English word "Available:" as part of the raw exception
        # text, which must stay locale-independent).
        self.assertTrue(
            text.startswith(
                "ERROR: Unknown workspace 'reseach'. Available: personal, research\n"
            )
        )
        self.assertIn("もしかして 'research' ではありませんか?", text)
        self.assertIn("利用可能:\n  personal", text)
        self.assertNotIn("Available:\n  personal", text)

    def test_default_locale_guidance_is_unchanged_english(self):
        # No locale context active: default English wording is unaffected
        # by the localization wiring (this is what every other test in
        # this file already asserts; this test only makes the "unaffected
        # by default" invariant explicit).
        with mock.patch.object(cli_error_guidance.sys, "stderr", _FakeTty()):
            text = cli_error_guidance.unknown_command_text("todya")
        self.assertIn("Did you mean 'today'?", text)
        self.assertIn("See:", text)


if __name__ == "__main__":
    unittest.main()
