"""CLI wiring tests for `lifetxt item-uri format|parse` (#840).

Pure identity translation: no life.txt file is read or written by either
subcommand, mirroring the design constraint that URI parsing/resolution
stays separate from record authorization/existence checks.
"""

import json
import unittest

from tests.test_lifetxt import run_cli


class ItemUriCliTests(unittest.TestCase):
    def test_format_prints_the_uri(self):
        stdout, stderr, code = run_cli("item-uri", "format", "task-001")
        self.assertEqual(0, code, stderr)
        self.assertEqual("lifetxt://item/task-001\n", stdout.replace("\r\n", "\n"))

    def test_format_with_base_url_also_prints_the_web_deep_link(self):
        stdout, stderr, code = run_cli(
            "item-uri",
            "format",
            "task-001",
            "--base-url",
            "https://lifetxt.example.invalid",
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(
            "lifetxt://item/task-001\n"
            "https://lifetxt.example.invalid/?id=task-001\n",
            stdout.replace("\r\n", "\n"),
        )

    def test_format_json_output(self):
        stdout, stderr, code = run_cli(
            "item-uri", "format", "task-001", "--json"
        )
        self.assertEqual(0, code, stderr)
        payload = json.loads(stdout)
        self.assertEqual(
            {"id": "task-001", "uri": "lifetxt://item/task-001"}, payload
        )

    def test_format_rejects_an_empty_id(self):
        stdout, stderr, code = run_cli("item-uri", "format", "")
        self.assertNotEqual(0, code)
        self.assertIn("ERROR", stderr)

    def test_parse_recovers_the_canonical_id(self):
        stdout, stderr, code = run_cli(
            "item-uri", "parse", "lifetxt://item/task-001"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("task-001\n", stdout.replace("\r\n", "\n"))

    def test_parse_json_output(self):
        stdout, stderr, code = run_cli(
            "item-uri", "parse", "lifetxt://item/task-001", "--json"
        )
        self.assertEqual(0, code, stderr)
        payload = json.loads(stdout)
        self.assertEqual(
            {"uri": "lifetxt://item/task-001", "id": "task-001"}, payload
        )

    def test_parse_round_trips_an_id_needing_encoding(self):
        format_out, format_err, format_code = run_cli(
            "item-uri", "format", "a b/c"
        )
        self.assertEqual(0, format_code, format_err)
        uri = format_out.strip()
        parse_out, parse_err, parse_code = run_cli("item-uri", "parse", uri)
        self.assertEqual(0, parse_code, parse_err)
        self.assertEqual("a b/c\n", parse_out.replace("\r\n", "\n"))

    def test_parse_rejects_a_malformed_uri(self):
        stdout, stderr, code = run_cli(
            "item-uri", "parse", "https://example.invalid/item/task-001"
        )
        self.assertNotEqual(0, code)
        self.assertIn("ERROR", stderr)

    def test_help_lists_both_subcommands(self):
        stdout, stderr, code = run_cli("item-uri", "--help")
        self.assertEqual(0, code, stderr)
        self.assertIn("format", stdout)
        self.assertIn("parse", stdout)


if __name__ == "__main__":
    unittest.main()
