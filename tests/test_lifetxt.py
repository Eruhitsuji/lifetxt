import json
import os
import subprocess
import sys
import tempfile
import unittest

from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line, items_from_jsonl_text, items_to_jsonl


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LifeTxtParserTests(unittest.TestCase):
    def test_parse_repeated_details(self):
        text = (
            "[ ] T Create_Slides project:research "
            "tag:important tag:thesis tag:presentation\n"
        )
        items, diagnostics = parse_text(text)

        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(1, len(items))
        self.assertEqual("Create_Slides", items[0].title)
        self.assertEqual(["important", "thesis", "presentation"], items[0].details["tag"])

    def test_quoted_values_round_trip(self):
        text = '[ ] E "Research Meeting" loc:"Meeting Room A" note:"Use \\"life.txt\\""\n'
        items, diagnostics = parse_text(text)

        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(text.strip(), item_to_line(items[0]))

    def test_invalid_detail_reports_error(self):
        items, diagnostics = parse_text("[ ] T Write Report due:2026-06-12\n")

        self.assertEqual(1, len(items))
        self.assertTrue(any(d.code == "E010" for d in diagnostics))

    def test_jsonl_round_trip(self):
        text = (
            "[ ] T Write_Report due:2026-06-12 tag:report tag:important\n"
            "[N] N Presentation_Memo note:\"Use figures\"\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        jsonl = items_to_jsonl(items)
        decoded = items_from_jsonl_text(jsonl)

        self.assertEqual(
            [json.loads(line) for line in jsonl.splitlines()],
            [item.to_dict() for item in decoded],
        )

    def test_parse_status_item(self):
        text = (
            "[/] S Working from:2026-06-06T14:00 state:busy person:self\n"
            '[x] S "Sleeping" from:2026-06-05T01:00 '
            "to:2026-06-05T08:30 state:sleeping person:self\n"
        )
        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(2, len(items))
        self.assertEqual("S", items[0].kind)
        self.assertEqual(["busy"], items[0].details["state"])
        self.assertEqual(["self"], items[0].details["person"])

    def test_status_item_requires_from_and_state(self):
        _items, diagnostics = parse_text("[/] S Working from:13:00\n")

        self.assertTrue(any(d.code == "E202" for d in diagnostics))
        self.assertTrue(any(d.code == "E203" for d in diagnostics))

    def test_status_item_recommends_status_by_to_presence(self):
        _items, diagnostics = parse_text(
            "[/] S Working from:2026-06-06T14:00 "
            "to:2026-06-06T16:00 state:busy\n"
            "[x] S Working from:2026-06-06T16:00 state:busy\n"
        )

        self.assertTrue(any(d.code == "W208" for d in diagnostics))
        self.assertTrue(any(d.code == "W209" for d in diagnostics))


class LifeTxtStatusCliTests(unittest.TestCase):
    def test_status_cli_outputs_latest_status_for_each_person(self):
        text = (
            "[/] S Working from:2026-06-06T14:00 state:busy person:alice\n"
            "[/] S Focus from:2026-06-06T16:00 state:focus person:alice service:teams\n"
            "[x] S Sleeping from:2026-06-05T01:00 "
            "to:2026-06-05T08:30 state:sleeping person:bob\n"
            "[/] S Away from:2026-06-06T15:30 state:away\n"
        )

        stdout, stderr, code = run_cli("status", input_text=text)

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("| person | state", normalized)
        self.assertIn("| alice  | focus", normalized)
        self.assertIn("2026-06-06T16:00", normalized)
        self.assertNotIn("2026-06-06T14:00", normalized)
        self.assertIn("| bob    | sleeping", normalized)
        self.assertIn("| self   | away", normalized)

    def test_status_cli_json_output(self):
        text = (
            "[/] S Working from:2026-06-06T14:00 state:busy person:alice\n"
            "[/] S Focus from:2026-06-06T16:00 state:focus person:alice service:teams\n"
            "[/] S Away from:2026-06-06T15:30 state:away\n"
        )

        stdout, stderr, code = run_cli("status", "--format", "json", input_text=text)

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["alice", "self"], [entry["person"] for entry in data])
        self.assertEqual("focus", data[0]["state"])
        self.assertEqual("teams", data[0]["service"])
        self.assertTrue(data[0]["active"])
        self.assertEqual("self", data[1]["person"])
        self.assertEqual("away", data[1]["state"])

    def test_status_cli_filters_by_person(self):
        text = (
            "[/] S Working from:2026-06-06T14:00 state:busy person:alice\n"
            "[/] S Away from:2026-06-06T15:30 state:away\n"
        )

        stdout, stderr, code = run_cli("status", "--person", "self", input_text=text)

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertNotIn("alice", normalized)
        self.assertIn("self", normalized)
        self.assertIn("away", normalized)


class LifeTxtAgendaCliTests(unittest.TestCase):
    def test_agenda_cli_outputs_items_in_datetime_range(self):
        text = (
            "[ ] E Seminar from:2026-06-06T13:00 to:2026-06-06T14:30\n"
            "[ ] D Form due:2026-06-06T17:00\n"
            "[ ] T Future due:2026-06-07\n"
            "[/] S Working from:2026-06-06T12:00 state:busy person:self\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06T13:30",
            "--to",
            "2026-06-06T18:00",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("| when", normalized)
        self.assertIn("Seminar", normalized)
        self.assertIn("Form", normalized)
        self.assertIn("Working", normalized)
        self.assertNotIn("Future", normalized)

    def test_agenda_cli_around_window(self):
        text = (
            "[ ] R Break at:2026-06-06T14:15\n"
            "[ ] T Morning due:2026-06-06T10:00\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--around",
            "2026-06-06T14:00",
            "--window",
            "30m",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Break", normalized)
        self.assertNotIn("Morning", normalized)

    def test_agenda_cli_json_output(self):
        text = (
            "[ ] E Seminar from:2026-06-06T13:00 to:2026-06-06T14:30\n"
            "[ ] D Form due:2026-06-06T17:00\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["Seminar", "Form"], [entry["title"] for entry in data])
        self.assertEqual("from/to", data[0]["key"])
        self.assertEqual("due", data[1]["key"])

    def test_agenda_cli_time_only_at_matches_range_day(self):
        text = "[ ] H Practice repeat:daily at:18:00\n"

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06T17:30",
            "--to",
            "2026-06-06T18:30",
            "--format",
            "life",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(text, normalize_newlines(stdout))


class LifeTxtAssistCliTests(unittest.TestCase):
    def test_assist_output_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# existing\n")

            stdout, stderr, code = run_cli(
                "assist",
                "--type",
                "task",
                "--title",
                "Write Report",
                "--id",
                "task_001",
                "--due",
                "2026-06-12",
                "--output",
                path,
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            expected = '[ ] T "Write Report" id:task_001 due:2026-06-12\n'
            self.assertEqual(
                '[ ] T "Write Report" id:task_001 due:2026-06-12\n',
                normalize_newlines(stdout),
            )
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual("# existing\n" + expected, handle.read())

    def test_assist_status_item_non_interactive(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--type",
            "status",
            "--title",
            "Working",
            "--from",
            "2026-06-06T14:00",
            "--state",
            "busy",
            "--person",
            "self",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[/] S Working from:2026-06-06T14:00 state:busy person:self\n",
            normalize_newlines(stdout),
        )

    def test_assist_status_item_with_to_defaults_done(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--type",
            "S",
            "--title",
            "Sleeping",
            "--from",
            "2026-06-05T01:00",
            "--to",
            "2026-06-05T08:30",
            "--state",
            "sleeping",
            "--person",
            "self",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[x] S Sleeping from:2026-06-05T01:00 "
            "to:2026-06-05T08:30 state:sleeping person:self\n",
            normalize_newlines(stdout),
        )

    def test_assist_update_by_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# life\n")
                handle.write("[ ] T Old_Title id:task_001 tag:old\n")
                handle.write("[ ] T Other id:task_002\n")

            stdout, stderr, code = run_cli(
                "assist",
                "--update",
                path,
                "--match-id",
                "task_001",
                "--status",
                "done",
                "--title",
                "New Title",
                "--done",
                "2026-06-06",
                "--tag",
                "new",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertEqual(
                '[x] T "New Title" id:task_001 tag:new done:2026-06-06\n',
                normalize_newlines(stdout),
            )
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    "# life\n"
                    '[x] T "New Title" id:task_001 tag:new done:2026-06-06\n'
                    "[ ] T Other id:task_002\n",
                    handle.read(),
                )

    def test_assist_interactive_help_commands(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--interactive",
            "--no-completion",
            input_text=(
                "?\n"
                "T\n"
                "?status\n"
                "[ ]\n"
                "Write_Report\n"
                "?detail\n"
                "project:research\n"
                "\n"
            ),
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Type values:", normalized)
        self.assertIn("Status values:", normalized)
        self.assertIn("Recommended detail keys for type T:", normalized)
        self.assertIn("| Key | Meaning | Example |", normalized)
        self.assertIn("| due | Deadline date or datetime. | `due:2026-06-12` |", normalized)
        self.assertIn("-" * 56, normalized)
        self.assertIn("-" * 32, normalized)
        self.assertTrue(normalized.rstrip().endswith("[ ] T Write_Report project:research"))

    def test_assist_interactive_title_help_is_title_specific(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--interactive",
            "--no-completion",
            input_text=(
                "T\n"
                "[ ]\n"
                "?\n"
                "Write_Report\n"
                "\n"
            ),
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        title_help_index = normalized.index("Title: main item text.")
        details_index = normalized.index("Details:")
        self.assertLess(title_help_index, details_index)
        self.assertTrue(normalized.rstrip().endswith("[ ] T Write_Report"))

    def test_assist_interactive_note_status_accepts_n(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--interactive",
            "--no-completion",
            input_text=(
                "N\n"
                "N\n"
                "Memo\n"
                "\n"
            ),
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertTrue(normalize_newlines(stdout).rstrip().endswith("[N] N Memo"))

    def test_assist_interactive_detail_key_help(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--interactive",
            "--no-completion",
            input_text=(
                "T\n"
                "[ ]\n"
                "Write_Report\n"
                "?due\n"
                "due:2026-06-12\n"
                "\n"
            ),
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("due: Deadline date or datetime.", normalized)
        self.assertIn("Example: due:2026-06-12", normalized)
        self.assertIn("-" * 32, normalized)
        self.assertTrue(normalized.rstrip().endswith("[ ] T Write_Report due:2026-06-12"))

    def test_field_completer_common_prefix(self):
        from lifetxt.interactive import FieldCompleter

        completer = FieldCompleter(["project:", "priority:", "tag:"])

        completed, matches = completer.complete_value("pr")

        self.assertEqual("pr", completed)
        self.assertEqual(["project:", "priority:"], matches)

        completed, matches = completer.complete_value("proj")

        self.assertEqual("project:", completed)
        self.assertEqual(["project:"], matches)


def run_cli(*args, **kwargs):
    input_text = kwargs.get("input_text")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [sys.executable, "-m", "lifetxt"] + list(args),
        cwd=ROOT_DIR,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    input_bytes = None
    if input_text is not None:
        input_bytes = input_text.encode("utf-8")
    stdout, stderr = process.communicate(input_bytes)
    return (
        stdout.decode("utf-8"),
        stderr.decode("utf-8"),
        process.returncode,
    )


def normalize_newlines(text):
    return text.replace("\r\n", "\n")


if __name__ == "__main__":
    unittest.main()
