import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.extra_cli import _build_parser


class SafetyCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name):
        return os.path.join(self.temp_dir.name, name)

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_extended_parser_registers_new_command_families(self):
        self.assertEqual("locks", _build_parser("safety").parse_args(["locks"]).safety_action)
        self.assertEqual("info", _build_parser("format").parse_args(["info", "life.txt"]).format_action)
        self.assertEqual("token", _build_parser("capabilities").parse_args([]).authentication)

    def test_capabilities_command_returns_versioned_json(self):
        code, stdout, stderr = self.run_command(["capabilities", "--pretty"])
        self.assertEqual(0, code, stderr)
        value = json.loads(stdout)
        self.assertEqual("1", value["capability_version"])
        self.assertTrue(value["revision_preconditions"]["supported"])

    def test_format_info_and_check_return_stable_json(self):
        path = self.path("life.txt")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("#! format_version: 1\n[ ] T Task id:T-1\n")
        code, stdout, stderr = self.run_command(["format", "info", path, "--pretty"])
        self.assertEqual(0, code, stderr)
        self.assertEqual("current", json.loads(stdout)["format"]["state"])
        code, stdout, stderr = self.run_command(["format", "check", path, "--pretty"])
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(1, report["item_count"])

    def test_format_canon_writes_with_revision_precondition(self):
        path = self.path("life.txt")
        with open(path, "wb") as handle:
            handle.write(b"#! format_version: 1\r\n[ ] T Task  \r\n")
        code, stdout, stderr = self.run_command(["format", "canon", path, "--write", "--pretty"])
        self.assertEqual(0, code, stderr)
        self.assertTrue(json.loads(stdout)["written"])
        with open(path, "rb") as handle:
            self.assertEqual(b"#! format_version: 1\n[ ] T Task\n", handle.read())

    def test_safety_timezone_and_serve_target_commands(self):
        path = self.path("life.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#! timezone: Asia/Tokyo\n")
        code, stdout, stderr = self.run_command(["safety", "timezone", path, "--pretty"])
        self.assertEqual(0, code, stderr)
        self.assertEqual("file", json.loads(stdout)["source"])
        other = self.path("other.txt")
        code, stdout, stderr = self.run_command([
            "safety", "serve-target", path, "--write-file", other, "--pretty"
        ])
        self.assertEqual(0, code, stderr)
        self.assertTrue(json.loads(stdout)["mismatch"])

    def test_format_schemas_command_writes_release_manifest_document(self):
        directory = self.path("schemas")
        code, stdout, stderr = self.run_command(["format", "schemas", directory, "--pretty"])
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual(5, len(report["files"]))
        self.assertEqual(5, len(os.listdir(directory)))
        self.assertIn("release-manifest-v1.schema.json", report["files"])
        with open(
            os.path.join(directory, "release-manifest-v1.schema.json"),
            "r",
            encoding="utf-8",
        ) as handle:
            schema = json.load(handle)
        self.assertEqual("lifetxt release manifest v1", schema["title"])


if __name__ == "__main__":
    unittest.main()
