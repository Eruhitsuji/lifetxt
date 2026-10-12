import json
import tempfile
import unittest
from pathlib import Path
from lifetxt.parser import parse_text
from lifetxt.project_validation import validate_risks
from tests.test_lifetxt import run_cli


class ProjectRiskValidationTests(unittest.TestCase):
    def test_defaults_implicit_projects_and_custom_fields_are_valid(self):
        items, _ = parse_text(
            "[N] N Risk record:risk project:implicit custom:kept\n[N] N Other record:decision state:WHAT\n"
        )
        result = validate_risks(items)
        self.assertEqual(1, result["risk_count"])
        self.assertEqual([], result["diagnostics"])

    def test_warnings_preserve_values_and_match_first_marker_semantics(self):
        items, _ = parse_text(
            "[N] N Risk record:risk record:decision severity:banana severity:HIGH state:CLOSED state:weird\n[N] N Ticket record:ticket record:risk severity:banana\n"
        )
        before = repr(items[0].details)
        result = validate_risks(items)
        self.assertEqual(1, result["risk_count"])
        self.assertEqual(
            ["PRV001", "PRV001", "PRV001", "PRV002", "PRV003", "PRV004", "PRV005"],
            [d["code"] for d in result["diagnostics"]],
        )
        self.assertTrue(
            all(
                d["severity"] == "warning" and d["category"] == "semantic"
                for d in result["diagnostics"]
            )
        )
        self.assertEqual(before, repr(items[0].details))

    def test_cli_is_opt_in_read_only_text_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "life.txt"
            data = b"[N] N Risk record:risk severity:banana state:CLOSED\r\n"
            path.write_bytes(data)
            regular = run_cli("check", str(path))
            for fmt in ("json", "text"):
                result = run_cli(
                    "project",
                    "validate",
                    str(path),
                    "--records",
                    "risk",
                    "--format",
                    fmt,
                )
                self.assertEqual(0, result[2], result[1])
                if fmt == "json":
                    self.assertTrue(json.loads(result[0])["read_only"])
                else:
                    self.assertIn("PRV003", result[0])
                self.assertEqual(data, path.read_bytes())
            after = run_cli("check", str(path))
            self.assertEqual(regular[0], after[0])
            self.assertEqual(regular[2], after[2])
