import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_people_keys_are_known_and_recommended_for_matching_types(self):
        _items, diagnostics = parse_text(
            "[ ] T Write_Report due:2026-06-12 assignee:alice owner:bob\n"
            "[ ] E Seminar from:2026-06-08T13:00 "
            "to:2026-06-08T14:00 attendee:alice owner:bob\n"
            "[ ] D Form due:2026-06-20 owner:alice assignee:bob\n"
        )

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertFalse(any(d.code == "W106" for d in diagnostics))

    def test_tab_only_blank_line_reports_blank_warning(self):
        items, diagnostics = parse_text("\t\n")

        self.assertEqual([], items)
        self.assertTrue(any(d.code == "W001" for d in diagnostics))
        self.assertFalse(any(d.severity == "error" for d in diagnostics))


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

    def test_status_cli_active_only_ignores_finished_latest_log(self):
        text = (
            "[/] S Working from:2026-06-07T09:00 state:working person:self\n"
            "[x] S Meeting from:2026-06-07T10:00 "
            "to:2026-06-07T11:00 state:meeting person:self\n"
        )

        stdout, stderr, code = run_cli("status", "--active", input_text=text)

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("working", normalized)
        self.assertNotIn("meeting", normalized)


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

    def test_agenda_life_output_preserves_original_line(self):
        text = '[ ] R "Break" at:2026-06-06T14:15\n'

        stdout, stderr, code = run_cli(
            "agenda",
            "--around",
            "2026-06-06T14:00",
            "--window",
            "30m",
            "--format",
            "life",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(text, normalize_newlines(stdout))

    def test_agenda_cli_open_filter(self):
        text = (
            "[ ] T Open_Task due:2026-06-06 project:work\n"
            "[/] T Doing_Task due:2026-06-06 project:work\n"
            "[x] T Done_Task due:2026-06-06 done:2026-06-06 project:work\n"
            "[-] E Canceled_Event from:2026-06-06T13:00 "
            "to:2026-06-06T14:00 reason:canceled\n"
            "[N] N Dated_Note due:2026-06-06 project:work\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--open",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Open_Task", normalized)
        self.assertIn("Doing_Task", normalized)
        self.assertNotIn("Done_Task", normalized)
        self.assertNotIn("Canceled_Event", normalized)
        self.assertNotIn("Dated_Note", normalized)

    def test_agenda_cli_status_type_and_project_filters(self):
        text = (
            "[ ] T Research_Task due:2026-06-06 project:research\n"
            "[ ] T Life_Task due:2026-06-06 project:life\n"
            "[ ] E Research_Event from:2026-06-06T13:00 "
            "to:2026-06-06T14:00 project:research\n"
            "[x] T Done_Research due:2026-06-06 done:2026-06-06 project:research\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--status",
            "todo",
            "--type",
            "task",
            "--project",
            "research",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Research_Task", normalized)
        self.assertNotIn("Life_Task", normalized)
        self.assertNotIn("Research_Event", normalized)
        self.assertNotIn("Done_Research", normalized)

    def test_agenda_cli_detail_person_and_text_filters(self):
        text = (
            "[ ] T Create_Slides due:2026-06-06 tag:urgent project:research\n"
            "[ ] T Buy_Milk due:2026-06-06 tag:urgent project:life\n"
            "[/] S Alice_Focus from:2026-06-06T13:00 state:focus person:alice\n"
            "[/] S Bob_Focus from:2026-06-06T13:00 state:focus person:bob\n"
            "[/] S Self_Away from:2026-06-06T14:00 state:away\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--detail",
            "tag=urgent",
            "--text",
            "slides",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Create_Slides", normalized)
        self.assertNotIn("Buy_Milk", normalized)

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--person",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Alice_Focus", normalized)
        self.assertNotIn("Bob_Focus", normalized)
        self.assertNotIn("Self_Away", normalized)

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--person",
            "self",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Self_Away", normalized)
        self.assertNotIn("Alice_Focus", normalized)

    def test_agenda_cli_people_filters(self):
        text = (
            "[ ] T Alice_Task due:2026-06-06 assignee:alice\n"
            "[ ] T Bob_Task due:2026-06-06 assignee:bob\n"
            "[ ] E Alice_Event from:2026-06-06T13:00 "
            "to:2026-06-06T14:00 attendee:alice\n"
            "[ ] D Owned_Deadline due:2026-06-06 owner:alice\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--assignee",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Alice_Task", normalized)
        self.assertNotIn("Bob_Task", normalized)
        self.assertNotIn("Alice_Event", normalized)

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--attendee",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Alice_Event", normalized)
        self.assertNotIn("Alice_Task", normalized)

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            "--owner",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Owned_Deadline", normalized)
        self.assertNotIn("Alice_Task", normalized)

    def test_agenda_cli_output_file(self):
        text = (
            "[ ] E Seminar from:2026-06-06T13:00 to:2026-06-06T14:30\n"
            "[ ] D Form due:2026-06-07\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "life.txt")
            output_path = os.path.join(temp_dir, "agenda.life.txt")
            with open(input_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

            stdout, stderr, code = run_cli(
                "agenda",
                input_path,
                "--from",
                "2026-06-06",
                "--to",
                "2026-06-06",
                "--format",
                "life",
                "-o",
                output_path,
            )

            self.assertEqual("", stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(output_path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    "[ ] E Seminar from:2026-06-06T13:00 to:2026-06-06T14:30\n",
                    handle.read(),
                )

    def test_agenda_cli_week_window(self):
        text = (
            "[ ] D Soon due:2026-06-12\n"
            "[ ] D Later due:2026-06-15\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--around",
            "2026-06-07T00:00",
            "--window",
            "1w",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Soon", normalized)
        self.assertNotIn("Later", normalized)


class LifeTxtFilterCliTests(unittest.TestCase):
    def test_filter_cli_writes_open_tasks_to_life_file(self):
        text = (
            "[ ] T Open_Task due:2026-06-08 project:work\n"
            "[x] T Done_Task due:2026-06-08 done:2026-06-08 project:work\n"
            "[ ] E Meeting from:2026-06-08T10:00 to:2026-06-08T11:00\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "life.txt")
            output_path = os.path.join(temp_dir, "open_tasks.life.txt")
            with open(input_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

            stdout, stderr, code = run_cli(
                "filter",
                input_path,
                "--open",
                "--type",
                "task",
                "-o",
                output_path,
            )

            self.assertEqual("", stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(output_path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    "[ ] T Open_Task due:2026-06-08 project:work\n",
                    handle.read(),
                )

    def test_filter_cli_future_and_person_filters(self):
        text = (
            "[ ] E Past from:2026-06-05T10:00 to:2026-06-05T11:00\n"
            "[ ] E Future from:2026-06-08T10:00 to:2026-06-08T11:00\n"
            "[/] S Self_Away from:2026-06-06T15:30 state:away\n"
            "[/] S Alice_Focus from:2026-06-06T16:00 state:focus person:alice\n"
        )

        stdout, stderr, code = run_cli(
            "filter",
            "--type",
            "event",
            "--after",
            "2026-06-07",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Future", normalized)
        self.assertNotIn("Past", normalized)
        self.assertNotIn("Self_Away", normalized)

        stdout, stderr, code = run_cli(
            "filter",
            "--type",
            "status",
            "--person",
            "self",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Self_Away", normalized)
        self.assertNotIn("Alice_Focus", normalized)

    def test_filter_life_output_preserves_original_line_unless_canonical(self):
        text = (
            '[ ] T "Open_Task" due:2026-06-08 project:research\n'
            '[x] T "Done_Task" due:2026-06-08 done:2026-06-08\n'
        )

        stdout, stderr, code = run_cli(
            "filter",
            "--open",
            "--type",
            "task",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            '[ ] T "Open_Task" due:2026-06-08 project:research\n',
            normalize_newlines(stdout),
        )

        stdout, stderr, code = run_cli(
            "filter",
            "--open",
            "--type",
            "task",
            "--canonical",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[ ] T Open_Task due:2026-06-08 project:research\n",
            normalize_newlines(stdout),
        )

    def test_filter_one_sided_time_filter_ignores_floating_at(self):
        text = (
            "[ ] H Daily repeat:daily at:18:00\n"
            "[ ] D Past due:2026-06-06\n"
            "[ ] D Future due:2026-06-08\n"
        )

        stdout, stderr, code = run_cli(
            "filter",
            "--before",
            "2026-06-07",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Past", normalized)
        self.assertNotIn("Daily", normalized)
        self.assertNotIn("Future", normalized)

    def test_filter_cli_people_filters(self):
        text = (
            "[ ] T Alice_Task due:2026-06-08 assignee:alice owner:team_a\n"
            "[ ] T Bob_Task due:2026-06-08 assignee:bob owner:team_b\n"
            "[ ] E Review from:2026-06-08T10:00 to:2026-06-08T11:00 attendee:alice\n"
        )

        stdout, stderr, code = run_cli(
            "filter",
            "--assignee",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Alice_Task", normalized)
        self.assertNotIn("Bob_Task", normalized)
        self.assertNotIn("Review", normalized)

        stdout, stderr, code = run_cli(
            "to-json",
            "--owner",
            "team_b",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["Bob_Task"], [entry["title"] for entry in data])

        stdout, stderr, code = run_cli(
            "filter",
            "--attendee",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Review", normalized)
        self.assertNotIn("Alice_Task", normalized)

    def test_to_json_and_to_jsonl_filters(self):
        text = (
            "[ ] T Open_Task due:2026-06-08 project:research\n"
            "[x] T Done_Task due:2026-06-08 done:2026-06-08 project:research\n"
            "[ ] T Other_Task due:2026-06-08 project:life\n"
        )

        stdout, stderr, code = run_cli(
            "to-json",
            "--open",
            "--type",
            "task",
            "--project",
            "research",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["Open_Task"], [entry["title"] for entry in data])

        stdout, stderr, code = run_cli(
            "to-jsonl",
            "--project",
            "life",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        rows = [json.loads(line) for line in stdout.splitlines()]
        self.assertEqual(["Other_Task"], [entry["title"] for entry in rows])

    def test_multiple_life_input_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First due:2026-06-08")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Second due:2026-06-09\n")

            stdout, stderr, code = run_cli(
                "filter",
                first_path,
                second_path,
                "--open",
                "--format",
                "json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual(["First", "Second"], [entry["title"] for entry in data])

    def test_multiple_life_input_diagnostics_include_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First due:2026-06-08\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Broken Title due:2026-06-09\n")

            stdout, stderr, code = run_cli("check", first_path, second_path)

            normalized = normalize_newlines(stdout)
            self.assertEqual("", stderr)
            self.assertEqual(1, code)
            self.assertIn(os.path.basename(second_path), normalized)
            self.assertIn(":1:", normalized)
            self.assertIn("E010", normalized)

    def test_utf8_bom_life_file_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "bom.life.txt")
            with open(path, "w", encoding="utf-8-sig", newline="\n") as handle:
                handle.write("[ ] T First due:2026-06-08\n")

            stdout, stderr, code = run_cli("check", path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("OK: 1 item(s)", normalize_newlines(stdout))

    def test_multiple_json_input_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.json")
            second_path = os.path.join(temp_dir, "second.json")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {"status": "[ ]", "type": "T", "title": "First", "details": {}},
                    handle,
                )
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {"status": "[N]", "type": "N", "title": "Second", "details": {}},
                    handle,
                )

            stdout, stderr, code = run_cli("from-json", first_path, second_path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertEqual("[ ] T First\n[N] N Second\n", normalize_newlines(stdout))


class LifeTxtIcsImportCliTests(unittest.TestCase):
    def test_import_ics_cli_converts_google_event(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:event-1@example.com\n"
            "SUMMARY:Research Meeting\n"
            "DTSTART;TZID=Asia/Tokyo:20260608T130000\n"
            "DTEND;TZID=Asia/Tokyo:20260608T143000\n"
            "LOCATION:Meeting Room A\n"
            "DESCRIPTION:Bring outline\n"
            "ORGANIZER;CN=Prof. Smith:mailto:prof@example.com\n"
            "ATTENDEE;CN=Alice:mailto:alice@example.com\n"
            "ATTENDEE:mailto:bob@example.com\n"
            "URL:https://example.com/meet\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

        stdout, stderr, code = run_cli(
            "import-ics",
            "--project",
            "research",
            "--tag",
            "imported",
            input_text=ics,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            '[ ] E "Research Meeting" id:event-1@example.com '
            "from:2026-06-08T13:00 to:2026-06-08T14:30 "
            'loc:"Meeting Room A" note:"Bring outline" '
            "url:https://example.com/meet "
            'owner:"Prof. Smith" attendee:Alice attendee:bob@example.com '
            "project:research tag:imported\n",
            normalize_newlines(stdout),
        )

    def test_import_ics_cli_converts_multi_day_all_day_event(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:all-day@example.com\n"
            "SUMMARY:Conference\n"
            "DTSTART;VALUE=DATE:20260608\n"
            "DTEND;VALUE=DATE:20260610\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

        stdout, stderr, code = run_cli("import-ics", input_text=ics)

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[ ] E Conference id:all-day@example.com "
            "on:2026-06-08 on:2026-06-09\n",
            normalize_newlines(stdout),
        )

    def test_import_ics_cli_preserves_cancelled_recurring_categories(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:cancel@example.com\n"
            "SUMMARY:Canceled\n"
            "STATUS:CANCELLED\n"
            "DTSTART:20260608T130000\n"
            "RRULE:FREQ=WEEKLY;INTERVAL=1\n"
            "CATEGORIES:work,important\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

        stdout, stderr, code = run_cli("import-ics", input_text=ics)

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[-] E Canceled id:cancel@example.com from:2026-06-08T13:00 "
            "repeat:RRULE:FREQ=WEEKLY;INTERVAL=1 "
            "tag:work tag:important reason:canceled\n",
            normalize_newlines(stdout),
        )

    def test_import_ics_cli_maps_tentative_status(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:tentative@example.com\n"
            "SUMMARY:Tentative\n"
            "STATUS:TENTATIVE\n"
            "DTSTART:20260608T130000\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

        stdout, stderr, code = run_cli("import-ics", input_text=ics)

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[?] E Tentative id:tentative@example.com from:2026-06-08T13:00\n",
            normalize_newlines(stdout),
        )

    def test_import_ics_cli_appends_to_output_file(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:event@example.com\n"
            "SUMMARY:Review\n"
            "DTSTART:20260608T100000\n"
            "DTEND:20260608T103000\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "calendar.ics")
            output_path = os.path.join(temp_dir, "life.txt")
            with open(input_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(ics)
            with open(output_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# existing")

            stdout, stderr, code = run_cli(
                "import-ics",
                input_path,
                "-o",
                output_path,
                "--append",
            )

            self.assertEqual("", stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(output_path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    "# existing\n"
                    "[ ] E Review id:event@example.com "
                    "from:2026-06-08T10:00 to:2026-06-08T10:30\n",
                    handle.read(),
                )


class LifeTxtIcsSyncCliTests(unittest.TestCase):
    def test_sync_ics_cli_reads_url_env_and_writes_generated_file(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:sync-event@example.com\n"
            "SUMMARY:Synced Event\n"
            "DTSTART:20260608T100000\n"
            "DTEND:20260608T103000\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "calendar.ics")
            output_path = os.path.join(temp_dir, "generated", "generated.life.txt")
            cache_dir = os.path.join(temp_dir, "cache")
            with open(input_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(ics)

            stdout, stderr, code = run_cli(
                "sync-ics",
                "--url-env",
                "LIFETXT_TEST_ICS",
                "-o",
                output_path,
                "--cache-dir",
                cache_dir,
                "--tag",
                "google",
                env_update={"LIFETXT_TEST_ICS": Path(input_path).as_uri()},
            )

            self.assertEqual("", stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            with open(output_path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    '[ ] E "Synced Event" id:sync-event@example.com '
                    "from:2026-06-08T10:00 to:2026-06-08T10:30 tag:google\n",
                    handle.read(),
                )
            self.assertEqual(1, len(os.listdir(cache_dir)))

    def test_sync_ics_cli_dry_run_does_not_write_output_or_cache(self):
        ics = (
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:dry-run@example.com\n"
            "SUMMARY:Dry Run\n"
            "DTSTART:20260608T100000\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "calendar.ics")
            output_path = os.path.join(temp_dir, "generated.life.txt")
            cache_dir = os.path.join(temp_dir, "cache")
            with open(input_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(ics)

            stdout, stderr, code = run_cli(
                "sync-ics",
                "--url",
                Path(input_path).as_uri(),
                "-o",
                output_path,
                "--cache-dir",
                cache_dir,
                "--dry-run",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertEqual(
                '[ ] E "Dry Run" id:dry-run@example.com from:2026-06-08T10:00\n',
                normalize_newlines(stdout),
            )
            self.assertFalse(os.path.exists(output_path))
            self.assertFalse(os.path.exists(cache_dir))

    def test_sync_ics_cli_requires_source(self):
        stdout, stderr, code = run_cli("sync-ics")

        self.assertEqual("", stdout)
        self.assertEqual(1, code)
        self.assertIn("Specify at least one --url or --url-env.", stderr)


class LifeTxtWebAppTests(unittest.TestCase):
    def test_webapp_file_helpers_append_update_and_delete_item(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# life\n[ ] T First\n")

            item = webapp.item_from_payload(
                {
                    "status": "[ ]",
                    "type": "T",
                    "title": "Second",
                    "details": {"due": ["2026-06-12"]},
                }
            )
            line = webapp.append_item_to_file(path, item)
            self.assertEqual(3, line)

            updated = webapp.update_item_in_file(
                path,
                2,
                {
                    "title": "First Updated",
                    "details": {"project": ["life"]},
                },
            )
            self.assertEqual("First Updated", updated.title)

            deleted = webapp.delete_item_from_file(path, 3)
            self.assertEqual("[ ] T Second due:2026-06-12", deleted)

            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    "# life\n"
                    '[ ] T "First Updated" project:life\n',
                    handle.read(),
                )

    def test_webapp_items_response_marks_writable_source_editable(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First\n")

            items, diagnostics = webapp.read_life_inputs([path])
            response = webapp.items_response(items, diagnostics, path)

            self.assertEqual(1, response["count"])
            self.assertTrue(response["items"][0]["editable"])
            self.assertEqual("[ ] T First", response["items"][0]["text"])

    def test_webapp_sort_items_by_title_and_time(self):
        from lifetxt import webapp

        text = (
            "[ ] T Zebra due:2026-06-12\n"
            "[ ] T Alpha due:2026-06-10\n"
            "[ ] T Middle\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        by_title = webapp.sort_items(items, "title", "asc")
        self.assertEqual(["Alpha", "Middle", "Zebra"], [item.title for item in by_title])

        by_time = webapp.sort_items(items, "time", "asc")
        self.assertEqual(["Alpha", "Zebra", "Middle"], [item.title for item in by_time])

        by_time_desc = webapp.sort_items(items, "time", "desc")
        self.assertEqual(
            ["Zebra", "Alpha", "Middle"],
            [item.title for item in by_time_desc],
        )

    def test_webapp_limit_items(self):
        from lifetxt import webapp

        items, diagnostics = parse_text("[ ] T One\n[ ] T Two\n[ ] T Three\n")
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        self.assertEqual(["One", "Two"], [item.title for item in webapp.limit_items(items, 2)])
        self.assertEqual(["One", "Two", "Three"], [item.title for item in webapp.limit_items(items, "")])
        self.assertEqual(["One", "Two", "Three"], [item.title for item in webapp.limit_items(items, "bad")])

    def test_serve_help_does_not_require_web_dependencies(self):
        stdout, stderr, code = run_cli("serve", "--help")

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Run the optional FastAPI REST API", stdout)


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

    def test_assist_people_detail_flags(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--type",
            "task",
            "--title",
            "Review PR",
            "--assignee",
            "alice",
            "--owner",
            "team_a",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            '[ ] T "Review PR" owner:team_a assignee:alice\n',
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

    def test_assist_interactive_all_key_help_and_status_key_suggestions(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--interactive",
            "--no-completion",
            input_text=(
                "T\n"
                "?\n"
                "[ ]\n"
                "Write_Report\n"
                "?all\n"
                "\n"
            ),
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Suggested detail keys by status:", normalized)
        self.assertIn("[ ] do, due, priority, project, tag, note", normalized)
        self.assertIn("Known detail keys by category:", normalized)
        self.assertIn("Common keys:", normalized)
        self.assertIn("Type-specific keys:", normalized)
        self.assertIn("| state | Status / presence state", normalized)
        self.assertTrue(normalized.rstrip().endswith("[ ] T Write_Report"))

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
    env_update = kwargs.get("env_update")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if env_update:
        env.update(env_update)
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
