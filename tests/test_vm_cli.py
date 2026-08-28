"""CLI wiring tests for `lifetxt vm run` (#560)."""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


MOVE_X_TO_Y = """[N] N Counter_X id:x value:3
[N] N Counter_Y id:y value:0

[N] N Check_X id:s1 op:dec_jz var:x nonzero:s2 zero:halt
[N] N Increment_Y id:s2 op:inc var:y next:s1

[N] N Halt id:halt op:halt
"""


class VmRunCliTests(unittest.TestCase):
    def _write_source(self, temp_dir, text=MOVE_X_TO_Y, name="program.life.txt"):
        path = os.path.join(temp_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_text_output_reports_step_count_and_final_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("vm", "run", src, "--entry", "s1")
            self.assertEqual(0, code, stderr)
            self.assertEqual(
                "HALT after 7 steps\nx=0\ny=3\n", stdout.replace("\r\n", "\n")
            )

    def test_json_output_matches_the_expected_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("vm", "run", src, "--entry", "s1", "--json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(7, data["steps"])
            self.assertEqual("s1", data["entry"])
            self.assertTrue(data["halted"])
            self.assertEqual({"x": 0, "y": 3}, data["state"])

    def test_unknown_entry_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("vm", "run", src, "--entry", "nope")
            self.assertNotEqual(0, code)
            self.assertIn("does not exist", stderr)

    def test_max_steps_below_completion_fails_loudly_without_halting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "vm", "run", src, "--entry", "s1", "--max-steps", "6"
            )
            self.assertNotEqual(0, code)
            self.assertIn("Step limit", stderr)
            self.assertEqual("", stdout)

    def test_max_steps_matching_completion_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "vm", "run", src, "--entry", "s1", "--max-steps", "7"
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("HALT after 7 steps", stdout)

    def test_max_steps_zero_means_unlimited(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "vm", "run", src, "--entry", "s1", "--max-steps", "0"
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("HALT after 7 steps", stdout)

    def test_negative_max_steps_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "vm", "run", src, "--entry", "s1", "--max-steps", "-1"
            )
            self.assertNotEqual(0, code)
            self.assertIn("max_steps must be >= 0", stderr)

    def test_invalid_program_fails_loudly_before_execution(self):
        text = "[N] N S1 id:s1 op:dec_jz var:missing nonzero:s1 zero:s1\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, text=text)
            stdout, stderr, code = run_cli("vm", "run", src, "--entry", "s1")
            self.assertNotEqual(0, code)
            self.assertIn("unknown counter", stderr)
            self.assertEqual("", stdout)

    def test_vm_records_do_not_execute_under_plain_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("check", src)
            self.assertEqual(0, code, stderr)
            # Custom-key warnings only; no VM execution, no HALT/state output.
            self.assertNotIn("HALT", stdout)

    def test_mixed_vm_and_ordinary_records_only_executes_the_vm_records(self):
        text = (
            "[ ] T Buy_Milk due:2026-09-01\n"
            "[N] N Counter_X id:x value:2\n"
            "[N] N S1 id:s1 op:dec_jz var:x nonzero:s1 zero:halt\n"
            "[N] N Halt id:halt op:halt\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, text=text)
            stdout, stderr, code = run_cli("vm", "run", src, "--entry", "s1")
            self.assertEqual(0, code, stderr)
            self.assertIn("HALT after 3 steps", stdout)
            self.assertIn("x=0", stdout)

    def test_vm_top_level_help_and_run_help_succeed(self):
        stdout, stderr, code = run_cli("vm", "--help")
        self.assertEqual(0, code, stderr)
        stdout, stderr, code = run_cli("vm", "run", "--help")
        self.assertEqual(0, code, stderr)
        self.assertIn("--entry", stdout)
        self.assertIn("--max-steps", stdout)


if __name__ == "__main__":
    unittest.main()
