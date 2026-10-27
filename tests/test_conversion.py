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
    decode_text,
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

    def test_todo_decoder_handles_priority_date_unicode_and_extensions(self):
        source = (
            "(A) 2026-10-26 Prepare proposal +Work +日本語 @office @職場 "
            "project:legacy context:personal due:2026-10-30 "
            "owner:alice owner:bob\n"
        )
        result = convert_text("todo", "life", source, source_name="fixture.todo")
        item, diagnostics = decode_text("todo", source, source_name="fixture.todo")

        self.assertEqual(1, result.item_count)
        self.assertEqual("Prepare proposal", item[0].title)
        self.assertEqual(["A"], item[0].details["priority"])
        self.assertEqual(["2026-10-26"], item[0].details["created"])
        self.assertEqual(["Work", "日本語", "legacy"], item[0].details["project"])
        self.assertEqual(["office", "職場", "personal"], item[0].details["context"])
        self.assertEqual(["2026-10-30"], item[0].details["due"])
        self.assertEqual(["alice", "bob"], item[0].details["owner"])
        self.assertEqual((), diagnostics)
        self.assertIn("created:2026-10-26", result.content)

    def test_todo_decoder_preserves_identity_and_date_less_completion(self):
        source = "x Send report +Work @email pri:A id:stable_1 source:archive.txt\n"
        result = convert_text("todo", "life", source, source_name="fixture.todo")
        item, _ = decode_text("todo", source, source_name="fixture.todo")

        self.assertEqual("[x]", item[0].status)
        self.assertEqual("Send report", item[0].title)
        self.assertEqual(["A"], item[0].details["priority"])
        self.assertEqual(["stable_1"], item[0].details["id"])
        self.assertEqual(["archive.txt"], item[0].details["source"])
        self.assertNotIn("done:", result.content)

    def test_malformed_todo_tokens_remain_visible_and_invalid_dates_warn(self):
        result = convert_text(
            "todo",
            "life",
            "2026-02-30 Bad date due:bad:token + @\n",
        )

        self.assertIn("Bad date due:bad:token + @", result.content)
        self.assertEqual("warning", result.diagnostics[0].severity)
        self.assertEqual("W203", result.diagnostics[0].code)

    def test_life_to_todo_strict_encoder_preserves_supported_fields(self):
        source = (
            '[ ] T "Prepare proposal" priority:A created:2026-10-26 '
            "project:Work context:office due:2026-10-30 id:task_1 source:todo.txt\n"
            '[x] T "Send report" done:2026-10-26 created:2026-10-20 '
            "priority:B project:Work context:email id:task_2 source:todo.txt\n"
        )
        result = convert_text("life", "todo", source)

        self.assertEqual(
            "(A) 2026-10-26 Prepare proposal +Work @office "
            "due:2026-10-30 id:task_1 source:todo.txt\n"
            "x 2026-10-26 2026-10-20 Send report +Work @email "
            "pri:B id:task_2 source:todo.txt\n",
            result.content,
        )
        round_trip = convert_text("todo", "life", result.content)
        self.assertIn("id:task_1", round_trip.content)
        self.assertIn("id:task_2", round_trip.content)
        self.assertIn("priority:B", round_trip.content)

    def test_life_to_todo_strict_encoder_rejects_unrepresentable_semantics(self):
        with self.assertRaisesRegex(ConversionLossError, "item 1 field type=E"):
            convert_text("life", "todo", "[ ] E Meeting on:2026-10-26\n")
        with self.assertRaisesRegex(ConversionLossError, r"item 1 field status=\[/\]"):
            convert_text("life", "todo", "[/] T In_progress\n")
        with self.assertRaisesRegex(ConversionLossError, "completed task needs done:"):
            convert_text("life", "todo", "[x] T Completed created:2026-10-26\n")
        with self.assertRaisesRegex(ConversionLossError, "item 1 field due"):
            convert_text("life", "todo", "[ ] T Deadline due:2026-10-26T12:00\n")

    def test_todo_encoder_is_advertised_only_for_life_source(self):
        capabilities = conversion_capabilities()

        self.assertIn("todo", capabilities["target_formats"])
        self.assertIn({"from": "life", "to": "todo"}, capabilities["pairs"])
        self.assertNotIn({"from": "json", "to": "todo"}, capabilities["pairs"])

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

    def test_life_to_todo_cli_and_failed_export_leave_destination_unchanged(self):
        stdout, stderr, code = run_cli(
            "convert",
            "--from",
            "life",
            "--to",
            "todo",
            input_text="[ ] T Example priority:A\n",
        )
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("(A) Example\n", stdout)

        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.life.txt")
            output = os.path.join(temp_dir, "todo.txt")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Safe\n[ ] E Meeting on:2026-10-26\n")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("preserve this file\n")

            stdout, stderr, code = run_cli(
                "convert", "--from", "life", "--to", "todo", source, "-o", output
            )
            self.assertEqual(1, code)
            self.assertEqual("", stdout)
            self.assertIn("item 2 field type=E", stderr)
            with open(output, encoding="utf-8") as handle:
                self.assertEqual("preserve this file\n", handle.read())

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
