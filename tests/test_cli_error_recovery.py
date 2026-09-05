"""Integration tests for CLI general-error actionable diagnostics (#643):
unknown command, missing global option value, unknown workspace,
invalid/missing config, and missing/unreadable input path -- through the
real entrypoint, covering both non-TTY (real subprocess, unaffected) and
TTY-simulated (in-process, enhanced) behavior, plus exit-code parity.
"""

import io
import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


def _run_with_tty_stderr(argv):
    """Invoke the real package entry point with `sys.stderr` replaced by a
    StringIO whose `isatty()` reports True, simulating an interactive
    terminal without needing a real one."""
    from lifetxt import entrypoint

    class _FakeTty(io.StringIO):
        def isatty(self):
            return True

    buf = _FakeTty()
    import sys

    original_stderr = sys.stderr
    sys.stderr = buf
    try:
        code = entrypoint.main(argv)
    finally:
        sys.stderr = original_stderr
    return code, buf.getvalue()


class UnknownCommandRecoveryTests(unittest.TestCase):
    def test_non_tty_real_subprocess_is_a_plain_one_line_error(self):
        out, err, code = run_cli("todya")
        self.assertEqual(2, code)
        self.assertIn("Unknown command: 'todya'", err)
        self.assertNotIn("Did you mean", err)

    def test_tty_shows_did_you_mean_and_exits_with_the_same_code(self):
        code, err = _run_with_tty_stderr(["todya"])
        self.assertEqual(2, code)
        self.assertIn("Did you mean 'today'?", err)

    def test_a_real_alias_is_never_treated_as_unknown(self):
        # "d" is a real alias for "done"; confirm the unknown-command path
        # is never reached for it (its own usage error, not "Unknown
        # command", or a normal run against a real file).
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as handle:
            handle.write("[ ] T Buy_milk\n")
            path = handle.name
        try:
            out, err, code = run_cli("d", path, "--line", "1")
            self.assertNotIn("Unknown command", err)
        finally:
            os.unlink(path)


class MissingOptionValueRecoveryTests(unittest.TestCase):
    def test_non_tty_real_subprocess_is_unchanged(self):
        out, err, code = run_cli("--config")
        self.assertEqual(1, code)
        self.assertIn("--config requires a path.", err)
        self.assertNotIn("Usage:", err)

    def test_tty_shows_usage(self):
        code, err = _run_with_tty_stderr(["--config"])
        self.assertEqual(1, code)
        self.assertIn("Usage: --config PATH", err)


class UnknownWorkspaceRecoveryTests(unittest.TestCase):
    def _fixture_config(self):
        tmpdir = tempfile.mkdtemp()
        config_path = os.path.join(tmpdir, ".lifetxt.json")
        life_path = os.path.join(tmpdir, "life.txt")
        with open(life_path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Buy_milk\n")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "workspaces": {
                        "personal": {"sources": [life_path]},
                        "research": {"sources": [life_path]},
                    }
                },
                handle,
            )
        return config_path

    def test_non_tty_real_subprocess_is_unchanged(self):
        config_path = self._fixture_config()
        out, err, code = run_cli(
            "--config", config_path, "--workspace", "reseach", "check", "-"
        )
        self.assertEqual(1, code)
        self.assertIn("Unknown workspace 'reseach'", err)
        self.assertNotIn("Did you mean", err)

    def test_tty_shows_suggestion_and_available_list(self):
        config_path = self._fixture_config()
        code, err = _run_with_tty_stderr(
            ["--config", config_path, "--workspace", "reseach", "check", "-"]
        )
        self.assertEqual(1, code)
        self.assertIn("Did you mean 'research'?", err)
        self.assertIn("personal", err)
        self.assertIn("research", err)


class InvalidConfigRecoveryTests(unittest.TestCase):
    def _broken_config(self):
        tmpdir = tempfile.mkdtemp()
        config_path = os.path.join(tmpdir, ".lifetxt.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write("{ this is not valid json")
        return config_path

    def test_non_tty_real_subprocess_is_unchanged(self):
        config_path = self._broken_config()
        out, err, code = run_cli("--config", config_path, "check", "-")
        self.assertEqual(1, code)
        self.assertIn("Could not read config:", err)
        self.assertNotIn("lifetxt doctor", err)

    def test_tty_suggests_doctor(self):
        config_path = self._broken_config()
        code, err = _run_with_tty_stderr(["--config", config_path, "check", "-"])
        self.assertEqual(1, code)
        self.assertIn("lifetxt doctor", err)


class MissingInputPathRecoveryTests(unittest.TestCase):
    def test_non_tty_real_subprocess_is_unchanged(self):
        out, err, code = run_cli(
            "check", os.path.join(tempfile.gettempdir(), "no_such_life_file_xyz.txt")
        )
        self.assertEqual(1, code)
        self.assertIn("ERROR:", err)
        self.assertNotIn("lifetxt path", err)

    def test_tty_shows_guidance(self):
        missing_path = os.path.join(tempfile.gettempdir(), "no_such_life_file_xyz.txt")
        code, err = _run_with_tty_stderr(["check", missing_path])
        self.assertEqual(1, code)
        self.assertIn("Could not read:", err)
        self.assertIn("lifetxt path", err)


class StructuredOutputInvarianceTests(unittest.TestCase):
    def test_json_format_output_never_contains_guidance_text(self):
        # A normal, valid check --format json run must never be polluted by
        # any of this feature's presentation text.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as handle:
            handle.write("[ ] T Buy_milk\n")
            path = handle.name
        try:
            out, err, code = run_cli("check", path, "--format", "json")
            self.assertEqual(0, code)
            json.loads(out)  # must still be valid JSON
            self.assertNotIn("Did you mean", out)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
