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
        self.assertEqual(
            "locks", _build_parser("safety").parse_args(["locks"]).safety_action
        )
        self.assertEqual(
            "info",
            _build_parser("format").parse_args(["info", "life.txt"]).format_action,
        )
        self.assertEqual(
            "token", _build_parser("capabilities").parse_args([]).authentication
        )
        self.assertEqual(
            "json",
            _build_parser("doctor").parse_args(["--workspace-safety"]).format,
        )

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

    def test_format_check_preserves_parser_end_span(self):
        path = self.path("life.txt")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write('[ ] T "Unclosed title\n')
        code, stdout, stderr = self.run_command(["format", "check", path, "--pretty"])
        self.assertEqual(1, code)
        diagnostic = next(
            item for item in json.loads(stdout)["diagnostics"] if item["code"] == "E018"
        )
        self.assertEqual("E018", diagnostic["code"])
        self.assertEqual(22, diagnostic["span"]["end"]["column"])

    def test_format_canon_writes_with_revision_precondition(self):
        path = self.path("life.txt")
        with open(path, "wb") as handle:
            handle.write(b"#! format_version: 1\r\n[ ] T Task  \r\n")
        code, stdout, stderr = self.run_command(
            ["format", "canon", path, "--write", "--pretty"]
        )
        self.assertEqual(0, code, stderr)
        self.assertTrue(json.loads(stdout)["written"])
        with open(path, "rb") as handle:
            self.assertEqual(b"#! format_version: 1\n[ ] T Task\n", handle.read())

    def test_format_migrate_previews_and_writes_unversioned_files(self):
        path = self.path("life.txt")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("#! timezone: UTC\n[ ] T Task\n")
        code, stdout, stderr = self.run_command(["format", "migrate", path, "--pretty"])
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual("add-format-version", report["action"])
        self.assertFalse(report["written"])
        with open(path, encoding="utf-8") as handle:
            self.assertFalse(handle.read().startswith("#! format_version"))
        code, stdout, stderr = self.run_command(
            ["format", "migrate", path, "--write", "--pretty"]
        )
        self.assertEqual(0, code, stderr)
        self.assertTrue(json.loads(stdout)["written"])
        code, stdout, stderr = self.run_command(
            ["format", "migrate", path, "--write", "--pretty"]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("noop", json.loads(stdout)["action"])

    def test_format_migrate_refuses_unsupported_and_downgrade_is_inspection_only(self):
        path = self.path("future.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#! format_version: 2\n[ ] T Future\n")
        code, stdout, stderr = self.run_command(
            ["format", "migrate", path, "--write", "--pretty"]
        )
        self.assertEqual(1, code)
        self.assertFalse(json.loads(stdout)["written"])
        with open(path, encoding="utf-8") as handle:
            self.assertIn("format_version: 2", handle.read())
        code, stdout, stderr = self.run_command(
            ["format", "downgrade", path, "--to", "0", "--pretty"]
        )
        self.assertEqual(1, code)
        self.assertFalse(json.loads(stdout)["writable"])

    def test_safety_timezone_and_serve_target_commands(self):
        path = self.path("life.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#! timezone: Asia/Tokyo\n")
        code, stdout, stderr = self.run_command(
            ["safety", "timezone", path, "--pretty"]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("file", json.loads(stdout)["source"])
        other = self.path("other.txt")
        code, stdout, stderr = self.run_command(
            ["safety", "serve-target", path, "--write-file", other, "--pretty"]
        )
        self.assertEqual(0, code, stderr)
        self.assertTrue(json.loads(stdout)["mismatch"])

    def test_format_schemas_command_writes_expanded_contract_bundle(self):
        directory = self.path("schemas")
        code, stdout, stderr = self.run_command(
            ["format", "schemas", directory, "--pretty"]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual(78, len(report["files"]))
        self.assertEqual(78, len(os.listdir(directory)))
        for name in (
            "release-manifest-v1.schema.json",
            "revision-metrics-v1.schema.json",
            "timezone-policy-v1.schema.json",
            "doctor-v1.schema.json",
            "proposal-v1.schema.json",
            "delivery-state-v1.schema.json",
            "transaction-journal-v1.schema.json",
            "transaction-recovery-v1.schema.json",
            "timer-operation-v1.schema.json",
            "support-bundle-v1.schema.json",
            "revision-migration-evidence-v1.schema.json",
            "ticket-field-registry-v1.schema.json",
            "ticket-custom-field-registry-v1.schema.json",
            "ticket-workflow-v1.schema.json",
            "ticket-event-v1.schema.json",
            "ticket-time-entry-v1.schema.json",
            "ticket-activity-v1.schema.json",
            "ticket-version-v1.schema.json",
            "ticket-sprint-v1.schema.json",
            "ticket-planning-v1.schema.json",
            "ticket-v1.schema.json",
            "ticket-project-report-v1.schema.json",
        ):
            self.assertIn(name, report["files"])
        with open(
            os.path.join(directory, "release-manifest-v1.schema.json"),
            "r",
            encoding="utf-8",
        ) as handle:
            schema = json.load(handle)
        self.assertEqual("lifetxt release manifest v1", schema["title"])


class _NarrowConsoleStream:
    """Simulates a real Windows cp932-console stdout: raises UnicodeEncodeError
    on write, like the host that surfaced #429."""

    def __init__(self, encoding="cp932"):
        self.encoding = encoding
        self.written = []

    def write(self, text):
        text.encode(self.encoding)
        self.written.append(text)
        return len(text)


class ConsoleEncodingSafetyTests(unittest.TestCase):
    """Every stdout write boundary must survive a narrow console codec
    rather than crashing with UnicodeEncodeError (#429). Covers both write
    boundaries directly with representative non-ASCII content: extended
    commands via extra_common._write_output and legacy commands via
    cli.write_text -- the two call sites wired to atomic.write_console_text.
    """

    NON_ASCII_TEXT = '{"note": "record ↵ arrow"}\n'

    def test_extra_common_write_output_survives_narrow_console_codec(self):
        from lifetxt.extra_common import _write_output

        stream = _NarrowConsoleStream()
        with contextlib.redirect_stdout(stream):
            _write_output(self.NON_ASCII_TEXT)

        self.assertEqual(1, len(stream.written))
        self.assertNotIn("↵", stream.written[0])
        self.assertIn("record ", stream.written[0])

    def test_cli_write_text_survives_narrow_console_codec(self):
        from lifetxt import cli

        stream = _NarrowConsoleStream()
        with contextlib.redirect_stdout(stream):
            cli.write_text(None, self.NON_ASCII_TEXT)

        self.assertEqual(1, len(stream.written))
        self.assertNotIn("↵", stream.written[0])
        self.assertIn("record ", stream.written[0])


if __name__ == "__main__":
    unittest.main()
