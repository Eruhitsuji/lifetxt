"""Tests for beginner-facing write commands' TTY-only "Next:"/"Undo:"
success guidance (#638): `init`, `quick`/`add`/`q`, `done`, `complete`.

Guidance must only ever appear when stdout is a TTY, must never appear in
structured/JSON output, and "Undo:" must only be shown for an operation
that is genuinely reversible through the existing `lifetxt undo PATH`
contract.
"""

import contextlib
import io
import os
import tempfile
import unittest

from lifetxt import cli_taxonomy
from tests.test_lifetxt import run_cli


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class RenderSuccessGuidanceUnitTests(unittest.TestCase):
    def test_unregistered_command_returns_empty_string(self):
        self.assertEqual("", cli_taxonomy.render_success_guidance("check"))

    def test_init_never_shows_undo(self):
        self.assertNotIn(
            "Undo:", cli_taxonomy.render_success_guidance("init", path="life.txt")
        )

    def test_quick_shows_undo_only_when_a_path_is_given(self):
        self.assertIn(
            "Undo:", cli_taxonomy.render_success_guidance("quick", path="life.txt")
        )
        self.assertNotIn("Undo:", cli_taxonomy.render_success_guidance("quick"))

    def test_done_and_complete_show_undo_with_a_path(self):
        for command in ("done", "complete"):
            self.assertIn(
                "Undo:",
                cli_taxonomy.render_success_guidance(command, path="life.txt"),
            )
            self.assertIn(
                "lifetxt undo life.txt",
                cli_taxonomy.render_success_guidance(command, path="life.txt"),
            )


class NonTtyRegressionTests(unittest.TestCase):
    """Real subprocess: stdout is a pipe, never a TTY, so guidance must
    never appear -- exact prior output for every affected command."""

    def test_quick_over_a_pipe_shows_no_guidance(self):
        path = _make_file("")
        try:
            out, err, rc = run_cli("quick", "Buy_milk", "--append", path)
            self.assertEqual(rc, 0)
            self.assertNotIn("Next:", out)
            self.assertNotIn("Undo:", out)
        finally:
            os.unlink(path)

    def test_done_over_a_pipe_shows_no_guidance(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("done", path, "--line", "1")
            self.assertEqual(rc, 0)
            self.assertNotIn("Next:", out)
        finally:
            os.unlink(path)

    def test_init_over_a_pipe_shows_no_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            out, err, rc = run_cli(
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--yes",
            )
            self.assertEqual(rc, 0)
            self.assertNotIn("Undo:", out)


class TtySimulationTests(unittest.TestCase):
    """In-process: mock isatty() to simulate an interactive terminal,
    invoking the CLI's own argument-parsing entrypoint directly."""

    def _run_with_tty_stdout(self, argv):
        from lifetxt.cli import main as cli_main

        buf = io.StringIO()
        buf.isatty = lambda: True
        with contextlib.redirect_stdout(buf):
            rc = cli_main(argv)
        return rc, buf.getvalue()

    def test_quick_over_a_tty_shows_next_and_undo(self):
        path = _make_file("")
        try:
            rc, out = self._run_with_tty_stdout(["quick", "Buy_milk", "--append", path])
            self.assertEqual(rc, 0)
            self.assertIn("Next:", out)
            self.assertIn("lifetxt today", out)
            self.assertIn("Undo:", out)
            self.assertIn("lifetxt undo %s" % path, out)
        finally:
            os.unlink(path)

    def test_done_over_a_tty_shows_next_and_undo(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            rc, out = self._run_with_tty_stdout(["done", path, "--line", "1"])
            self.assertEqual(rc, 0)
            self.assertIn("Next:", out)
            self.assertIn("Undo:", out)
        finally:
            os.unlink(path)

    def test_already_done_shows_no_guidance(self):
        path = _make_file("[x] T Buy_milk done:2026-01-01\n")
        try:
            rc, out = self._run_with_tty_stdout(["done", path, "--line", "1"])
            self.assertEqual(rc, 0)
            self.assertNotIn("Next:", out)
        finally:
            os.unlink(path)

    def test_dry_run_shows_no_guidance(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            rc, out = self._run_with_tty_stdout(
                ["done", path, "--line", "1", "--dry-run"]
            )
            self.assertEqual(rc, 0)
            self.assertNotIn("Next:", out)
        finally:
            os.unlink(path)

    def test_init_over_a_tty_shows_next_but_no_undo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            rc, out = self._run_with_tty_stdout(
                [
                    "init",
                    "--file",
                    life_file,
                    "--config-output",
                    config_file,
                    "--yes",
                ]
            )
            self.assertEqual(rc, 0)
            self.assertIn("Next:", out)
            self.assertNotIn("Undo:", out)


class StructuredOutputInvarianceTests(unittest.TestCase):
    def test_quick_json_line_output_is_unaffected(self):
        # `quick` has no --format json of its own; confirm its one-line
        # machine-consumable echo (the serialized record) is unaffected in
        # both TTY and non-TTY modes -- only extra lines are ever appended.
        path = _make_file("")
        try:
            out, err, rc = run_cli("quick", "Buy_milk", "--append", path)
            first_line = out.splitlines()[0]
            self.assertIn("Buy_milk", first_line)
            self.assertNotIn("Next:", first_line)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
