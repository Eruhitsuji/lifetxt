import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-integrity-cwd-") as cwd:
        process = subprocess.Popen(
            [sys.executable, "-m", "lifetxt"] + list(args),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
    return stdout.decode("utf-8"), stderr.decode("utf-8"), process.returncode


class LifeTxtIntegrityCliTests(unittest.TestCase):
    def _fixture(self, temp_dir, name="life.txt", text="[ ] T Task id:t1\n"):
        path = os.path.join(temp_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_clean_file_reports_ok_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir)
            before_files = sorted(os.listdir(temp_dir))
            before_text = self._read(path)

            stdout, stderr, code = run_cli("integrity", path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("integrity: OK", stdout)
            self.assertIn("syntax", stdout)
            self.assertEqual(before_files, sorted(os.listdir(temp_dir)))
            self.assertEqual(before_text, self._read(path))

    def test_json_report_normalizes_parser_and_reference_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text=("[ ] T First id:dup depends_on:missing\n[ ] T Second id:dup\n"),
            )

            stdout, stderr, code = run_cli("integrity", path, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("integrity-v1", payload["schema"])
            self.assertEqual(False, payload["ok"])
            diagnostics = payload["diagnostics"]
            self.assertTrue(any(row["code"] == "W213" for row in diagnostics))
            self.assertTrue(any(row["category"] == "reference" for row in diagnostics))
            for row in diagnostics:
                self.assertIn("severity", row)
                self.assertIn("effective_severity", row)
                self.assertIn("category", row)
                self.assertIn("message", row)
                self.assertIn("check_state", row)

    def test_missing_file_is_reported_as_blocked_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = os.path.join(temp_dir, "missing.life.txt")

            stdout, stderr, code = run_cli("integrity", missing, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual(False, payload["ok"])
            self.assertTrue(
                any(
                    row["check_state"] == "blocked"
                    and row["category"] == "source"
                    and row["source_file"] == missing
                    for row in payload["diagnostics"]
                )
            )

    def test_verify_files_surfaces_attachment_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text='[ ] T Review id:t1 file:"./missing.md#sha256=0123456789abcdef"\n',
            )

            stdout, stderr, code = run_cli(
                "integrity", path, "--json", "--verify-files"
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertTrue(
                any(row["category"] == "files" for row in payload["diagnostics"])
            )

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()


if __name__ == "__main__":
    unittest.main()
