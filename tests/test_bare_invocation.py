"""Tests for the bare `lifetxt` smart entry (#636): interactive-terminal-only
guidance that never changes non-TTY/redirected/scripted behavior.
"""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import entrypoint
from tests.test_lifetxt import run_cli


class BareInvocationNonTtyRegressionTests(unittest.TestCase):
    """Real subprocess: stdout/stderr are pipes here, never a TTY, so bare
    invocation must be completely unaffected -- the existing argparse
    usage/exit-2 behavior."""

    def test_bare_invocation_over_a_pipe_is_unchanged(self):
        out, err, rc = run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("usage:", out)


class BareInvocationTtySimulationTests(unittest.TestCase):
    """In-process: mock isatty() to simulate an interactive terminal."""

    def _run_bare_main(self, cwd, argv=None):
        original_cwd = os.getcwd()
        os.chdir(cwd)
        try:
            buf = io.StringIO()
            buf.isatty = lambda: True
            with (
                mock.patch("sys.stdin.isatty", return_value=True),
                contextlib.redirect_stdout(buf),
            ):
                rc = entrypoint.main(argv if argv is not None else [])
            return rc, buf.getvalue()
        finally:
            os.chdir(original_cwd)

    def test_uninitialized_directory_shows_welcome_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc, out = self._run_bare_main(tmpdir)
            self.assertEqual(rc, 0)
            self.assertIn("Welcome to lifetxt", out)
            self.assertIn("lifetxt tour", out)
            self.assertIn("lifetxt init", out)
            self.assertIn("lifetxt help beginner", out)

    def test_uninitialized_directory_makes_no_persistent_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            before = sorted(os.listdir(tmpdir))
            self._run_bare_main(tmpdir)
            after = sorted(os.listdir(tmpdir))
            self.assertEqual(before, after)

    def test_initialized_directory_delegates_to_today(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            with open(life_file, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Buy_milk\n")
            rc, out = self._run_bare_main(tmpdir)
            self.assertEqual(rc, 0)
            self.assertNotIn("Welcome to lifetxt", out)
            # today's own text renderer always prints a "... brief" header.
            self.assertIn("brief", out)

    def test_lang_ja_translates_the_welcome_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc, out = self._run_bare_main(tmpdir, argv=["--lang", "ja"])
            self.assertEqual(rc, 0)
            self.assertIn("lifetxt へようこそ", out)


class BareInvocationParityTests(unittest.TestCase):
    def test_module_and_console_script_share_the_same_entry_point(self):
        # Both `python -m lifetxt` and the installed console script resolve
        # to lifetxt.entrypoint:main (see pyproject.toml), so no separate
        # bare-invocation logic needs to exist for either surface.
        import lifetxt.__main__ as main_module

        self.assertIs(main_module.main, entrypoint.main)


if __name__ == "__main__":
    unittest.main()
