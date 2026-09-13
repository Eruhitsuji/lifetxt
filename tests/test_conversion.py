import contextlib
import datetime
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt.conversion import (
    CANONICAL_FORMATS,
    ConversionLossError,
    InvalidConversionInputError,
    UnsupportedConversionError,
    conversion_capabilities,
    convert_text,
)
from lifetxt.entrypoint import main


def run_cli(*argv, input_text=""):
    stdout = io.StringIO()
    stderr = io.StringIO()
    stdin = io.StringIO(input_text)
    with (
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
        mock.patch("sys.stdin", stdin),
    ):
        code = main(list(argv))
    return stdout.getvalue(), stderr.getvalue(), code


class ConversionCoreTests(unittest.TestCase):
    def test_capabilities_are_machine_readable_and_stable(self):
        capabilities = conversion_capabilities()

        self.assertEqual("lifetxt-conversion-capabilities-v1", capabilities["schema"])
        self.assertEqual(list(CANONICAL_FORMATS), capabilities["formats"])
        self.assertIn({"from": "csv", "to": "jsonl"}, capabilities["pairs"])
        self.assertNotIn({"from": "json", "to": "ics"}, capabilities["pairs"])
        json.dumps(capabilities)

    def test_life_to_json_uses_shared_item_model(self):
        result = convert_text(
            "life", "json", "[ ] T Example due:2026-09-14\n", pretty=True
        )

        self.assertEqual(1, result.item_count)
        self.assertEqual("Example", json.loads(result.content)[0]["title"])

    def test_csv_to_jsonl_cross_conversion(self):
        result = convert_text("csv", "jsonl", "status,type,title\n[ ],T,CSV_task\n")

        self.assertEqual("CSV_task", json.loads(result.content)["title"])

    def test_markdown_and_todo_decode_to_life(self):
        markdown = convert_text("markdown-task-list", "life", "- [ ] Review docs\n")
        todo = convert_text("todo", "life", "(A) Ship release +lifetxt @desk\n")

        self.assertEqual("[ ] T Review_docs\n", markdown.content)
        self.assertIn("priority:A", todo.content)
        self.assertIn("project:lifetxt", todo.content)

    def test_invalid_json_fails_explicitly(self):
        with self.assertRaisesRegex(InvalidConversionInputError, "Invalid json"):
            convert_text("json", "life", "{")

    def test_unsupported_pair_fails_explicitly(self):
        with self.assertRaisesRegex(UnsupportedConversionError, "json -> ics"):
            convert_text("json", "ics", "[]")

    def test_ics_output_refuses_silent_item_loss(self):
        with self.assertRaisesRegex(ConversionLossError, "dropping item"):
            convert_text("life", "ics", "[ ] T Not_an_event\n")

    def test_ics_output_is_callable_without_cli(self):
        generated_at = datetime.datetime(2026, 9, 13, 12, 0, 0)
        result = convert_text(
            "life",
            "ics",
            "[ ] E Meeting on:2026-09-14 id:event_1\n",
            generated_at=generated_at,
        )

        self.assertIn("DTSTAMP:20260913T120000Z", result.content)
        self.assertIn("DTSTART;VALUE=DATE:20260914", result.content)


class ConvertCliTests(unittest.TestCase):
    def test_stdin_stdout_conversion(self):
        stdout, stderr, code = run_cli(
            "convert",
            "--from",
            "life",
            "--to",
            "json",
            input_text="[ ] T Example\n",
        )

        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("Example", json.loads(stdout)[0]["title"])

    def test_to_json_compatibility_entry_point_matches_convert(self):
        source = "[ ] T Example due:2026-09-14\n"
        converted, convert_stderr, convert_code = run_cli(
            "convert", "--from", "life", "--to", "json", input_text=source
        )
        legacy, legacy_stderr, legacy_code = run_cli("to-json", input_text=source)

        self.assertEqual((0, ""), (convert_code, convert_stderr))
        self.assertEqual((0, ""), (legacy_code, legacy_stderr))
        self.assertEqual(legacy, converted)

    def test_from_json_compatibility_entry_point_matches_convert(self):
        source = json.dumps(
            {"status": "[ ]", "type": "T", "title": "Example", "details": {}}
        )
        converted, convert_stderr, convert_code = run_cli(
            "convert", "--from", "json", "--to", "life", input_text=source
        )
        legacy, legacy_stderr, legacy_code = run_cli("from-json", input_text=source)

        self.assertEqual((0, ""), (convert_code, convert_stderr))
        self.assertEqual((0, ""), (legacy_code, legacy_stderr))
        self.assertEqual(legacy, converted)

    def test_multiple_paths_and_output_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = os.path.join(temp_dir, "first.csv")
            second = os.path.join(temp_dir, "second.csv")
            output = os.path.join(temp_dir, "items.jsonl")
            for path, title in ((first, "First"), (second, "Second")):
                with open(path, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write("status,type,title\n[ ],T,%s\n" % title)

            stdout, stderr, code = run_cli(
                "convert",
                "--from",
                "csv",
                "--to",
                "jsonl",
                first,
                second,
                "-o",
                output,
            )

            self.assertEqual(0, code)
            self.assertEqual("", stdout)
            self.assertEqual("", stderr)
            with open(output, encoding="utf-8") as handle:
                titles = [json.loads(line)["title"] for line in handle]
            self.assertEqual(["First", "Second"], titles)

    def test_capabilities_do_not_require_formats(self):
        stdout, stderr, code = run_cli("convert", "--capabilities")

        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual(
            "lifetxt-conversion-capabilities-v1", json.loads(stdout)["schema"]
        )

    def test_formats_are_required_for_conversion(self):
        stdout, stderr, code = run_cli("convert", input_text="")

        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("requires --from FORMAT and --to FORMAT", stderr)

    def test_unsupported_pair_fails_before_reading_input(self):
        stdout, stderr, code = run_cli(
            "convert", "--from", "json", "--to", "ics", input_text="not json"
        )

        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("Unsupported conversion: json -> ics", stderr)
        self.assertNotIn("Invalid json", stderr)


if __name__ == "__main__":
    unittest.main()
