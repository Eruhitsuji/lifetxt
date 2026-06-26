import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from lifetxt.parser import parse_text
from lifetxt.csvio import items_from_csv_text, items_to_csv
from lifetxt.links import link_records
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

    def test_parse_message_item(self):
        text = (
            '[ ] M "Review slides" sender:self recipient:alice '
            "notify_at:2026-06-06T09:00 channel:teams\n"
        )
        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(1, len(items))
        self.assertEqual("M", items[0].kind)
        self.assertEqual(["self"], items[0].details["sender"])
        self.assertEqual(["alice"], items[0].details["recipient"])

    def test_message_item_requires_sender_and_recipient(self):
        _items, diagnostics = parse_text("[ ] M Ping notify_at:2026-06-06T09:00\n")

        self.assertTrue(any(d.code == "E205" for d in diagnostics))
        self.assertTrue(any(d.code == "E206" for d in diagnostics))

    def test_message_notification_period_warns_when_reversed(self):
        _items, diagnostics = parse_text(
            "[ ] M Ping sender:self recipient:alice "
            "notify_from:2026-06-06T17:00 notify_to:2026-06-06T09:00\n"
        )

        self.assertTrue(any(d.code == "W211" for d in diagnostics))

    def test_parse_journal_item_with_multiline_body(self):
        text = (
            '[N] J "Research day" on:2026-06-23 mood:good tag:lab\n'
            "| Read papers in the morning.\n"
            "|\n"
            "| Wrote parser tests in the afternoon.\n"
        )

        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(1, len(items))
        self.assertEqual("J", items[0].kind)
        self.assertEqual("[N]", items[0].status)
        self.assertEqual(["good"], items[0].details["mood"])
        self.assertEqual(
            ["Read papers in the morning.\n\nWrote parser tests in the afternoon."],
            items[0].details["body"],
        )
        self.assertEqual(4, items[0].end_line)
        self.assertEqual(text.strip(), item_to_line(items[0]))

    def test_continuation_without_item_reports_error(self):
        _items, diagnostics = parse_text("| orphan body\n")

        self.assertTrue(any(d.code == "E019" for d in diagnostics))

    def test_csv_round_trip_preserves_details_and_body(self):
        text = (
            '[N] J "Research day" on:2026-06-23 tag:lab tag:parser\n'
            "| First line.\n"
            "| Second line.\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        csv_text = items_to_csv(items)
        decoded = items_from_csv_text(csv_text)

        self.assertEqual(["lab", "parser"], decoded[0].details["tag"])
        self.assertEqual(["First line.\nSecond line."], decoded[0].details["body"])
        self.assertEqual(item_to_line(items[0]), item_to_line(decoded[0]))

    def test_safe_markdown_subset_renders_html_and_plain_text(self):
        from lifetxt.markdown import markdown_to_html, markdown_to_plain

        html = markdown_to_html(
            "# Heading\n\n"
            "See **bold**, *italic*, `code`, and [site](https://example.com).\n\n"
            "- one\n"
            "- two\n\n"
            "```html\n"
            "<script>alert(1)</script>\n"
            "```"
        )

        self.assertIn("<h1>Heading</h1>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn('href="https://example.com"', html)
        self.assertIn("<ul>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertEqual("Heading\nbold and site", markdown_to_plain("# Heading\n**bold** and [site](https://example.com)"))

    def test_markdown_table_renders_html(self):
        from lifetxt.markdown import markdown_to_html, markdown_to_plain

        md = (
            "| Name | Score |\n"
            "|------|-------|\n"
            "| Alice | 10 |\n"
            "| Bob | 20 |\n"
        )
        result = markdown_to_html(md)

        self.assertIn("<table>", result)
        self.assertIn("<thead>", result)
        self.assertIn("<th>Name</th>", result)
        self.assertIn("<th>Score</th>", result)
        self.assertIn("<tbody>", result)
        self.assertIn("<td>Alice</td>", result)
        self.assertIn("<td>Bob</td>", result)
        self.assertNotIn("|---", result)

    def test_markdown_table_alignment(self):
        from lifetxt.markdown import markdown_to_html

        md = (
            "| Left | Center | Right |\n"
            "|:-----|:------:|------:|\n"
            "| a | b | c |\n"
        )
        result = markdown_to_html(md)

        self.assertIn('style="text-align:left"', result)
        self.assertIn('style="text-align:center"', result)
        self.assertIn('style="text-align:right"', result)

    def test_markdown_table_inline_formatting(self):
        from lifetxt.markdown import markdown_to_html

        md = (
            "| Task | Status |\n"
            "|------|--------|\n"
            "| **Done** | `ok` |\n"
        )
        result = markdown_to_html(md)

        self.assertIn("<strong>Done</strong>", result)
        self.assertIn("<code>ok</code>", result)

    def test_markdown_table_plain_text(self):
        from lifetxt.markdown import markdown_to_plain

        md = (
            "| Name | Score |\n"
            "|------|-------|\n"
            "| Alice | 10 |\n"
        )
        result = markdown_to_plain(md)

        self.assertIn("Name", result)
        self.assertIn("Alice", result)
        self.assertNotIn("---", result)
        self.assertNotIn("|", result)

    def test_markdown_table_header_only_no_sep_renders_as_paragraphs(self):
        from lifetxt.markdown import markdown_to_html

        md = "| col1 | col2 |\n"
        result = markdown_to_html(md)

        self.assertNotIn("<table>", result)
        self.assertIn("<p>", result)

    def test_safe_markdown_rejects_unsafe_link_scheme(self):
        from lifetxt.markdown import markdown_to_html

        html = markdown_to_html("[bad](javascript:alert(1))")

        self.assertIn("bad", html)
        self.assertNotIn("href=", html)
        self.assertNotIn("javascript:", html)

    def test_markdown_cli_json_renders_body(self):
        stdout, stderr, code = run_cli(
            "markdown",
            "--format",
            "json",
            "--field",
            "body",
            input_text=(
                '[N] J "Research day" on:2026-06-23\n'
                "| **Done**\n"
                "| - Parser\n"
            ),
        )

        data = json.loads(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(1, len(data))
        self.assertEqual("body", data[0]["field"])
        self.assertIn("<strong>Done</strong>", data[0]["html"])
        self.assertIn("<li>Parser</li>", data[0]["html"])

    def test_datetime_seconds_and_timezone_are_valid(self):
        text = (
            "[ ] E Call from:2026-06-06T09:00:30.25+09:00 "
            "to:2026-06-06T09:30:00.5+09:00\n"
            "[ ] R Alarm at:18:00:30.125+09:00\n"
        )

        _items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertFalse(any(d.code in ("W202", "W204") for d in diagnostics))

    def test_repeat_helpers_are_validated(self):
        _items, diagnostics = parse_text(
            "[ ] H Review repeat:weekdays interval:2 until:2026-06-30 count:5 at:09:00\n"
        )

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertFalse(any(d.code in ("W203", "W205", "W219") for d in diagnostics))

    def test_id_style_warning(self):
        _items, diagnostics = parse_text('[ ] T Bad_ID id:"bad id"\n')

        self.assertTrue(any(d.code == "W214" for d in diagnostics))

    def test_normalize_duration_returns_compact_form(self):
        from lifetxt.timeutil import normalize_duration

        self.assertEqual("1h30m", normalize_duration("90m"))
        self.assertEqual("1h", normalize_duration("60m"))
        self.assertEqual("2h", normalize_duration("120m"))
        self.assertEqual("25m", normalize_duration("25m"))
        self.assertEqual("1h30m", normalize_duration("1h30m"))
        self.assertEqual("1h", normalize_duration("1h00m"))
        self.assertEqual("1h30m", normalize_duration("90"))
        self.assertEqual("1.5h", normalize_duration("1.5h"))

    def test_duration_canonical_form_no_warning(self):
        _items, diagnostics = parse_text("[ ] T Review est:1h30m elapsed:25m\n")

        self.assertFalse(any(d.code == "W222" for d in diagnostics))

    def test_duration_non_canonical_warns_w222(self):
        _items, diagnostics = parse_text("[ ] T Review est:90m elapsed:120m\n")

        w222 = [d for d in diagnostics if d.code == "W222"]
        codes_keys = [d.message.split(":")[0] for d in w222]
        self.assertIn("est", codes_keys)
        self.assertIn("elapsed", codes_keys)

    def test_duration_unrecognized_format_no_warning(self):
        _items, diagnostics = parse_text("[ ] T Review est:1.5h\n")

        self.assertFalse(any(d.code == "W222" for d in diagnostics))

    def test_reference_diagnostics_and_link_records(self):
        text = (
            "[ ] T Root id:task_root\n"
            "[ ] T Child id:task_child parent:task_root ref:task_root related:missing_note\n"
            "[ ] T Self id:task_self ref:task_self\n"
        )

        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertTrue(any(d.code == "W215" and d.line == 2 for d in diagnostics))
        self.assertTrue(any(d.code == "W216" and d.line == 3 for d in diagnostics))

        records = link_records(items)
        compact = [
            (record["relation"], record["source_id"], record["target_id"], record["status"])
            for record in records
        ]
        self.assertIn(("parent", "task_child", "task_root", "ok"), compact)
        self.assertIn(("ref", "task_child", "task_root", "ok"), compact)
        self.assertIn(("related", "task_child", "missing_note", "missing"), compact)
        self.assertIn(("ref", "task_self", "task_self", "self"), compact)

    def test_indented_items_infer_parent_from_nearest_id(self):
        text = (
            "[ ] T Project id:task_project\n"
            "  [ ] T Outline id:task_outline\n"
            "    [N] N Outline_Note\n"
            "[ ] T Other id:task_other\n"
            "  [ ] T Explicit parent:task_project\n"
        )

        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(["task_project"], items[1].details["parent"])
        self.assertEqual(["task_outline"], items[2].details["parent"])
        self.assertEqual(["task_project"], items[4].details["parent"])
        self.assertEqual(2, items[1].indent)
        self.assertEqual(4, items[2].indent)
        self.assertEqual(4, items[2].to_dict()["indent"])

    def test_indented_item_warns_when_parent_has_no_id(self):
        _items, diagnostics = parse_text(
            "[ ] T Parent_Without_ID\n"
            "  [ ] T Child\n"
        )

        self.assertTrue(any(d.code == "W221" for d in diagnostics))

    def test_indented_body_continuation_round_trip(self):
        text = (
            "[ ] T Project id:task_project\n"
            "  [N] N Child_Note\n"
            "  | First line.\n"
            "  | Second line.\n"
        )

        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(["task_project"], items[1].details["parent"])
        self.assertEqual(["First line.\nSecond line."], items[1].details["body"])
        self.assertIn("  | First line.", item_to_line(items[1]))

    def test_parent_cycle_reports_warning(self):
        _items, diagnostics = parse_text(
            "[ ] T First id:a parent:b\n"
            "[ ] T Second id:b parent:a\n"
        )

        self.assertTrue(any(d.code == "W217" for d in diagnostics))

    def test_auto_id_generation_avoids_existing_ids(self):
        from lifetxt.ids import ensure_item_id

        items, diagnostics = parse_text("[ ] M Ping sender:self recipient:alice\n")
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        existing = {"msg_20260621120000", "msg_20260621120000_2"}
        assigned = ensure_item_id(
            items[0],
            existing_ids=existing,
            prefix="msg",
            now=datetime(2026, 6, 21, 12, 0),
        )

        self.assertEqual("msg_20260621120000_3", assigned)
        self.assertEqual(["msg_20260621120000_3"], items[0].details["id"])
        self.assertIn("msg_20260621120000_3", existing)

    def test_duplicate_id_reports_warning(self):
        _items, diagnostics = parse_text(
            "[ ] T First id:task_001\n"
            "[ ] T Second id:task_001\n"
        )

        duplicate_warnings = [d for d in diagnostics if d.code == "W213"]
        self.assertEqual(1, len(duplicate_warnings))
        self.assertEqual(2, duplicate_warnings[0].line)
        self.assertIn("Duplicate id:task_001", duplicate_warnings[0].message)

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

    def test_agenda_cli_message_notification_time(self):
        text = (
            "[ ] M Ping sender:self recipient:alice notify_at:2026-06-06T14:15\n"
            "[ ] M Later sender:self recipient:bob notify_at:2026-06-07T14:15\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--around",
            "2026-06-06T14:00",
            "--window",
            "30m",
            "--recipient",
            "alice",
            input_text=text,
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("Ping", normalized)
        self.assertNotIn("Later", normalized)

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

    def test_agenda_cli_repeats_weekly_with_interval_and_until(self):
        text = (
            "[ ] H Review repeat:weekly interval:2 on:2026-06-01 "
            "until:2026-06-30 count:3\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-15",
            "--to",
            "2026-06-15",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["Review"], [entry["title"] for entry in data])
        self.assertEqual("repeat:on", data[0]["key"])
        self.assertEqual("2026-06-15T00:00..2026-06-15T23:59:59", data[0]["when"])

    def test_agenda_cli_repeats_weekdays_with_count(self):
        text = "[ ] H Standup repeat:weekdays on:2026-06-05 count:2 at:09:00\n"

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-08T08:30",
            "--to",
            "2026-06-08T09:30",
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

    def test_filter_user_team_and_tag_modes_with_config(self):
        text = (
            "[ ] T Alice_Task due:2026-06-08 assignee:alice tag:urgent tag:review\n"
            "[ ] T Bob_Task due:2026-06-08 assignee:bob tag:urgent\n"
            "[ ] T Team_Direct due:2026-06-08 team:research tag:deep\n"
            "[ ] T Hidden due:2026-06-08 assignee:carol tag:archive\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "lifetxt.json")
            with open(config_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {
                        "users": {"alice": {"aliases": ["a"]}},
                        "teams": {"research": {"members": ["alice"]}},
                        "tags": {
                            "aliases": {"review": ["code-review"]},
                            "groups": {"review_pack": ["urgent", "review"]},
                        },
                    },
                    handle,
                )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "filter",
                "--user",
                "a",
                input_text=text,
            )

            normalized = normalize_newlines(stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Alice_Task", normalized)
            self.assertNotIn("Bob_Task", normalized)

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "filter",
                "--team",
                "research",
                input_text=text,
            )

            normalized = normalize_newlines(stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Alice_Task", normalized)
            self.assertIn("Team_Direct", normalized)
            self.assertNotIn("Bob_Task", normalized)

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "filter",
                "--tag",
                "code-review",
                input_text=text,
            )

            normalized = normalize_newlines(stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Alice_Task", normalized)
            self.assertNotIn("Bob_Task", normalized)

            stdout, stderr, code = run_cli(
                "filter",
                "--tag-all",
                "urgent,review",
                "--exclude-tag",
                "archive",
                input_text=text,
            )

            normalized = normalize_newlines(stdout)
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Alice_Task", normalized)
            self.assertNotIn("Bob_Task", normalized)
            self.assertNotIn("Hidden", normalized)

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

    def test_to_csv_and_from_csv_round_trip_with_filters(self):
        text = (
            "[ ] T Open_Task due:2026-06-08 project:research tag:a tag:b\n"
            "[x] T Done_Task due:2026-06-08 done:2026-06-08 project:research\n"
            '[N] J "Research day" on:2026-06-08 project:research mood:good\n'
            "| First line.\n"
            "| Second line.\n"
        )

        stdout, stderr, code = run_cli(
            "to-csv",
            "--type",
            "journal",
            "--project",
            "research",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("status,type,title", stdout.splitlines()[0])
        self.assertIn("Research day", stdout)
        self.assertNotIn("Open_Task", stdout)

        life_stdout, stderr, code = run_cli("from-csv", input_text=stdout)

        normalized = normalize_newlines(life_stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn('[N] J "Research day"', normalized)
        self.assertIn("| First line.", normalized)
        self.assertIn("| Second line.", normalized)

    def test_links_cli_outputs_reference_records(self):
        text = (
            "[ ] T Root id:task_root\n"
            "[ ] T Child id:task_child parent:task_root depends_on:task_root\n"
            "[N] N Note id:note_001 related:task_child\n"
        )

        stdout, stderr, code = run_cli(
            "links",
            "--id",
            "task_root",
            "--direction",
            "incoming",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        compact = [
            (record["relation"], record["source_id"], record["target_id"], record["status"])
            for record in data
        ]
        self.assertEqual(
            [
                ("parent", "task_child", "task_root", "ok"),
                ("depends_on", "task_child", "task_root", "ok"),
            ],
            compact,
        )

    def test_links_cli_filters_by_relation(self):
        text = (
            "[ ] T Root id:task_root\n"
            "[ ] T Other id:task_other\n"
            "[ ] T Child id:task_child parent:task_root depends_on:task_root blocks:task_other\n"
        )

        stdout, stderr, code = run_cli(
            "links",
            "--relation",
            "depends_on,blocks",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["blocks", "depends_on"], sorted(record["relation"] for record in data))

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

    def test_sources_cli_reports_source_ownership(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First id:first\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Parent id:parent\n")
                handle.write("  [ ] T Child id:child parent:parent\n")

            stdout, stderr, code = run_cli(
                "sources",
                first_path,
                second_path,
                "--format",
                "json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual(["First", "Parent", "Child"], [entry["title"] for entry in data])
            self.assertEqual(["first.life.txt", "second.life.txt", "second.life.txt"], [os.path.basename(entry["source"]) for entry in data])
            self.assertEqual([1, 1, 2], [entry["line"] for entry in data])
            self.assertEqual("parent", data[2]["parent"])
            self.assertEqual(2, data[2]["indent"])

    def test_sources_cli_filters_missing_ids_and_preserves_warnings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Missing\n")
                handle.write("[ ] T Duplicate id:task_001\n")
                handle.write("[ ] T Duplicate_2 id:task_001\n")

            stdout, stderr, code = run_cli("sources", path, "--missing-id")

            self.assertEqual(0, code)
            self.assertIn("Source ownership (id): 1 item(s)", stdout)
            self.assertIn("Missing", stdout)
            self.assertNotIn("Duplicate_2", stdout)
            self.assertIn("WARNING W213", stderr)

    def test_glob_and_directory_life_input_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first_life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            ignored_path = os.path.join(temp_dir, "ignored.md")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First due:2026-06-08\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Second due:2026-06-09\n")
            with open(ignored_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Ignored due:2026-06-10\n")

            stdout, stderr, code = run_cli(
                "filter",
                os.path.join(temp_dir, "*life.txt"),
                "--format",
                "json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual(["First", "Second"], sorted(entry["title"] for entry in data))

            stdout, stderr, code = run_cli("check", temp_dir)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("OK: 2 item(s)", normalize_newlines(stdout))

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


class LifeTxtConfigCliTests(unittest.TestCase):
    def test_config_init_and_show(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".lifetxt.json")

            stdout, stderr, code = run_cli("config", "init", "-o", config_path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Wrote", stdout)
            self.assertTrue(os.path.exists(config_path))

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "config",
                "show",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual("life.txt", data["write_file"])
            self.assertEqual("self", data["user"]["name"])


class LifeTxtIdDiagnosticsTests(unittest.TestCase):
    def test_ids_cli_text_reports_duplicates_and_missing_ids(self):
        text = (
            "[ ] T First id:task_001\n"
            "[ ] T Second id:task_001\n"
            "[ ] N Missing\n"
        )

        stdout, stderr, code = run_cli("ids", input_text=text)

        self.assertEqual(0, code)
        self.assertIn(
            "ID audit (id): 3 item(s), 1 id(s), 1 duplicate id(s), 1 missing id item(s)",
            stdout,
        )
        self.assertIn("Duplicate IDs:", stdout)
        self.assertIn("task_001", stdout)
        self.assertIn("Missing IDs:", stdout)
        self.assertIn("Missing", stdout)
        self.assertIn("WARNING W213", stderr)

    def test_ids_cli_json_missing_only(self):
        text = (
            "[ ] T First id:task_001\n"
            "[ ] T Missing\n"
        )

        stdout, stderr, code = run_cli(
            "ids",
            "--only",
            "missing",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual("id", data["key"])
        self.assertEqual(1, data["missing_count"])
        self.assertEqual("Missing", data["missing"][0]["title"])

    def test_ids_cli_cross_file_duplicate_shows_marker_and_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "a.life.txt")
            second_path = os.path.join(temp_dir, "b.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Alpha id:dup_001\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Beta id:dup_001\n")

            stdout, stderr, code = run_cli("ids", first_path, second_path)

            self.assertEqual(0, code)
            self.assertIn("1 cross-file", stdout)
            self.assertIn("dup_001*", stdout)
            self.assertIn("* = duplicate spans multiple files", stdout)

    def test_ids_cli_cross_file_duplicate_json_includes_count_and_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "a.life.txt")
            second_path = os.path.join(temp_dir, "b.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Alpha id:dup_001\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Beta id:dup_001\n")

            stdout, stderr, code = run_cli(
                "ids", first_path, second_path, "--format", "json"
            )

            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual(1, data["cross_file_duplicate_count"])
            self.assertEqual(1, len(data["cross_file_duplicates"]))
            self.assertEqual("dup_001", data["cross_file_duplicates"][0]["id"])
            self.assertTrue(data["cross_file_duplicates"][0]["cross_file"])

    def test_ids_cli_same_file_duplicate_no_cross_file_marker(self):
        text = (
            "[ ] T First id:task_001\n"
            "[ ] T Second id:task_001\n"
        )

        stdout, stderr, code = run_cli("ids", input_text=text)

        self.assertEqual(0, code)
        self.assertNotIn("cross-file", stdout)
        self.assertNotIn("*", stdout)

    def test_ids_assign_dry_run_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            text = "[ ] T Missing\n"
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

            stdout, stderr, code = run_cli("ids", path, "--assign", "--dry-run")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Planned ID assignments: 1 item(s)", stdout)
            self.assertRegex(stdout, r"task_\d{14}")
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(text, handle.read())

    def test_ids_assign_writes_ids_and_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Missing\n")

            stdout, stderr, code = run_cli("ids", path, "--assign", "--backup")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("ID assignments: 1 item(s)", stdout)
            with open(path, "r", encoding="utf-8") as handle:
                self.assertRegex(handle.read(), r"^\[ \] T Missing id:task_\d{14}\n$")
            with open(path + ".bak", "r", encoding="utf-8") as handle:
                self.assertEqual("[ ] T Missing\n", handle.read())

    def test_ids_assign_custom_key_and_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Missing\n")
                handle.write("[ ] M Ping sender:self recipient:alice\n")

            stdout, stderr, code = run_cli(
                "ids",
                path,
                "--assign",
                "--key",
                "uid",
                "--prefix",
                "item",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("ID assignments: 2 item(s)", stdout)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertRegex(text, r"^\[ \] T Missing uid:item_\d{14}\n")
            self.assertRegex(
                text,
                r"\[ \] M Ping sender:self recipient:alice uid:item_\d{14}_2\n$",
            )

    def test_check_cli_warns_for_cross_file_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First id:task_001\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Second id:task_001\n")

            stdout, stderr, code = run_cli("check", first_path, second_path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("WARNING W213", stdout)
            self.assertIn("Duplicate id:task_001", stdout)
            self.assertIn("first.life.txt:1", stdout)

    def test_check_cli_filters_diagnostics_by_code_severity_and_category(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First id:task_001 parent:missing from:not-a-date\n")
                handle.write("[ ] T Second id:task_001\n")

            stdout, stderr, code = run_cli("check", path, "--code", "W213")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("WARNING W213", stdout)
            self.assertNotIn("WARNING W202", stdout)
            self.assertNotIn("WARNING W215", stdout)

            stdout, stderr, code = run_cli(
                "check",
                path,
                "--severity",
                "warning",
                "--category",
                "reference",
                "--format",
                "json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual(["W215"], [entry["code"] for entry in data])
            self.assertEqual(["reference"], [entry["category"] for entry in data])

    def test_check_cli_filter_exit_code_uses_matching_diagnostics_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Broken Title due:2026-06-12\n")

            stdout, stderr, code = run_cli("check", path, "--severity", "warning")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("0 matching diagnostic", stdout)

    def test_webapp_read_life_inputs_warns_for_cross_file_duplicate_ids(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First id:task_001\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Second id:task_001\n")

            _items, diagnostics = webapp.read_life_inputs([first_path, second_path])

            duplicate_warnings = [d for d in diagnostics if d.code == "W213"]
            self.assertEqual(1, len(duplicate_warnings))
            self.assertEqual(second_path, duplicate_warnings[0].source)
            self.assertIn("Duplicate id:task_001", duplicate_warnings[0].message)


class LifeTxtNotifyTests(unittest.TestCase):
    def test_notification_records_for_recipient(self):
        from lifetxt.notifier import notification_records

        text = (
            "[ ] M Ping id:msg_001 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00 note:hello\n"
            "[ ] M Other id:msg_002 sender:bob recipient:alice "
            "notify_at:2026-06-06T09:00\n"
            "[x] M Done id:msg_003 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00 done:2026-06-06T09:01\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        records = notification_records(
            items,
            recipient="self",
            now=datetime(2026, 6, 6, 9, 0),
        )

        self.assertEqual(1, len(records))
        self.assertEqual("msg_001", records[0]["id"])
        self.assertEqual("Ping", records[0]["title"])
        self.assertEqual("hello", records[0]["body"])

    def test_notification_records_skip_ack_and_future_snooze(self):
        from lifetxt.notifier import notification_records

        text = (
            "[ ] M Acked id:msg_001 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00 ack:2026-06-06T09:01\n"
            "[ ] M Snoozed id:msg_002 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00 snooze_until:2026-06-06T09:30\n"
            "[ ] M Ready id:msg_003 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00 snooze_until:2026-06-06T08:30\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        records = notification_records(
            items,
            recipient="self",
            now=datetime(2026, 6, 6, 9, 0),
        )

        self.assertEqual(["msg_003"], [record["id"] for record in records])

    def test_notification_records_accept_seconds(self):
        from lifetxt.notifier import notification_records

        text = (
            "[ ] M Ping id:msg_001 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00:30\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))

        records = notification_records(
            items,
            recipient="self",
            now=datetime(2026, 6, 6, 9, 0, 30),
        )

        self.assertEqual(1, len(records))
        self.assertEqual("2026-06-06T09:00:30", records[0]["when"])

    def test_watch_notifications_persists_seen_state(self):
        from lifetxt.notifier import notification_records, watch_notifications

        text = (
            "[ ] M Ping id:msg_001 sender:bob recipient:self "
            "notify_at:2026-06-06T09:00\n"
        )
        items, diagnostics = parse_text(text)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        records = notification_records(
            items,
            recipient="self",
            now=datetime(2026, 6, 6, 9, 0),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, "notifications.json")
            first_output = io.StringIO()
            second_output = io.StringIO()

            watch_notifications(
                lambda: records,
                once=True,
                output=first_output,
                state_file=state_path,
            )
            watch_notifications(
                lambda: records,
                once=True,
                output=second_output,
                state_file=state_path,
            )

            self.assertIn("Ping", first_output.getvalue())
            self.assertEqual("", second_output.getvalue())
            with open(state_path, "r", encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertIn(records[0]["notification_id"], state["seen"])

    def test_notify_cli_json_output(self):
        text = (
            "[ ] M Ping id:msg_001 sender:bob recipient:self "
            "notify_from:2000-01-01T00:00 notify_to:2999-01-01T00:00 "
            "note:short body:long_message\n"
        )

        stdout, stderr, code = run_cli(
            "notify",
            "--recipient",
            "self",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual("msg_001", data[0]["id"])
        self.assertEqual("long_message", data[0]["body"])


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

    def test_webapp_file_helpers_update_and_delete_multiline_item(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    '# life\n[N] J "Day one" on:2026-06-23\n'
                    "| Old body\n"
                    "[ ] T Next\n"
                )

            updated = webapp.update_item_in_file(
                path,
                2,
                {
                    "title": "Day one updated",
                    "details": {"on": ["2026-06-23"], "body": ["New body\nMore"]},
                },
            )

            self.assertEqual("Day one updated", updated.title)
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    '# life\n[N] J "Day one updated" on:2026-06-23\n'
                    "| New body\n"
                    "| More\n"
                    "[ ] T Next\n",
                    handle.read(),
                )

            deleted = webapp.delete_item_from_file(path, 2)

            self.assertIn("| New body", deleted)
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual("# life\n[ ] T Next\n", handle.read())

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

    def test_webapp_generated_path_is_read_only(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "generated.life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] E Synced id:event_001 from:2026-06-08T10:00\n")

            items, diagnostics = webapp.read_life_inputs(
                [path],
                {"sync_ics": {"generated_paths": [path]}},
            )
            response = webapp.items_response(items, diagnostics, path)

            self.assertEqual(1, response["count"])
            self.assertTrue(response["items"][0]["generated"])
            self.assertFalse(response["items"][0]["editable"])

    def test_webapp_read_life_inputs_expands_globs(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second_life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Second\n")

            items, diagnostics = webapp.read_life_inputs([os.path.join(temp_dir, "*life.txt")])

            self.assertFalse(any(d.severity == "error" for d in diagnostics))
            self.assertEqual(["First", "Second"], sorted(item.title for item in items))

    def test_webapp_links_response_uses_all_loaded_files(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Root id:task_root\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Child id:task_child parent:task_root\n")

            items, diagnostics = webapp.read_life_inputs([first_path, second_path])
            records = link_records(items, focus_id="task_root", direction="incoming")
            response = webapp.links_response(records, diagnostics)

            self.assertFalse(any(d["code"] == "W215" for d in response["diagnostics"]))
            self.assertEqual(1, response["count"])
            self.assertEqual("task_child", response["records"][0]["source_id"])
            self.assertEqual("task_root", response["records"][0]["target_id"])

    def test_webapp_message_payload_helper(self):
        from lifetxt import webapp

        item = webapp.message_item_from_payload(
            {
                "body": "Review slides",
                "sender": "self",
                "recipients": ["alice", "bob"],
                "notify_at": "2026-06-06T09:00",
                "channel": "teams",
            }
        )

        self.assertEqual("M", item.kind)
        self.assertEqual("Review slides", item.title)
        self.assertEqual(["self"], item.details["sender"])
        self.assertEqual(["alice", "bob"], item.details["recipient"])
        self.assertEqual(["Review slides"], item.details["body"])

    def test_webapp_message_payload_uses_config_user_name(self):
        from lifetxt import webapp

        item = webapp.message_item_from_payload(
            {
                "title": "Ping",
                "recipient": "alice",
            },
            config={"user": {"name": "me"}},
        )

        self.assertEqual(["me"], item.details["sender"])

    def test_webapp_auto_id_uses_all_loaded_items(self):
        from lifetxt import webapp

        file_a_items, diagnostics_a = parse_text(
            "[ ] M First id:msg_20260621120000 sender:alice recipient:self\n"
        )
        file_b_items, diagnostics_b = parse_text(
            "[ ] T Other id:msg_20260621120000_2\n"
        )
        self.assertFalse(any(d.severity == "error" for d in diagnostics_a + diagnostics_b))

        item = webapp.message_item_from_payload(
            {
                "title": "Reply",
                "sender": "self",
                "recipient": "alice",
            }
        )
        assigned = webapp.assign_auto_id(
            item,
            config={"ids": {"auto": True, "key": "id"}},
            existing_items=file_a_items + file_b_items,
            now=datetime(2026, 6, 21, 12, 0),
        )

        self.assertEqual("msg_20260621120000_3", assigned)
        self.assertEqual(["msg_20260621120000_3"], item.details["id"])

    def test_webapp_auto_id_paths_include_writable_file(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            read_path = os.path.join(temp_dir, "read.life.txt")
            write_path = os.path.join(temp_dir, "write.life.txt")
            with open(read_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "[ ] M First id:msg_20260621120000 sender:alice recipient:self\n"
                )
            with open(write_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Existing id:msg_20260621120000_2\n")

            item = webapp.message_item_from_payload(
                {"title": "New", "sender": "self", "recipient": "alice"}
            )
            assigned = webapp.assign_auto_id_from_paths(
                item,
                config={"ids": {"auto": True, "key": "id"}},
                paths=webapp.auto_id_paths([read_path], write_path),
                now=datetime(2026, 6, 21, 12, 0),
            )

            self.assertEqual("msg_20260621120000_3", assigned)

    def test_webapp_update_and_delete_by_id(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First id:task_001\n")
                handle.write("[ ] T Second id:task_002\n")

            updated = webapp.update_item_by_id_in_file(
                path,
                "task_001",
                {"status": "[x]", "details": {"done": ["2026-06-06"]}},
            )
            self.assertEqual("[x]", updated.status)

            deleted = webapp.delete_item_by_id_from_file(path, "task_002")
            self.assertEqual("[ ] T Second id:task_002", deleted)

            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual("[x] T First done:2026-06-06\n", handle.read())

    def test_webapp_custom_id_key_helpers(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First uid:task_001\n")

            items, diagnostics = webapp.read_life_inputs([path], {"ids": {"key": "uid"}})
            self.assertFalse(any(d.severity == "error" for d in diagnostics))
            found = webapp.find_item_by_id(items, "task_001", key="uid")
            self.assertEqual("First", found.title)
            self.assertEqual("task_001", webapp.api_item(found, path, id_key="uid")["id"])

            updated = webapp.update_item_by_id_in_file(
                path,
                "task_001",
                {"title": "Updated", "details": {"uid": ["task_001"], "tag": ["done"]}},
                key="uid",
            )

            self.assertEqual("Updated", updated.title)
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual("[ ] T Updated uid:task_001 tag:done\n", handle.read())

    def test_webapp_api_item_includes_safe_markdown_payload(self):
        from lifetxt import webapp

        items, diagnostics = parse_text(
            '[N] J "Research **day**"\n'
            "| **Done**\n"
            "| [bad](javascript:alert(1))\n"
        )

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        data = webapp.api_item(items[0])

        self.assertIn("<strong>day</strong>", data["markdown"]["title"])
        self.assertIn("<strong>Done</strong>", data["markdown"]["details"]["body"][0])
        self.assertNotIn("javascript:", data["markdown"]["details"]["body"][0])

    def test_webapp_ack_and_snooze_message_helpers(self):
        from lifetxt import webapp

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "[ ] M Ping id:msg_001 sender:bob recipient:self "
                    "notify_at:2026-06-06T09:00\n"
                )

            acked = webapp.ack_message_in_file(
                path,
                "msg_001",
                {"ack": "2026-06-06T09:01"},
            )
            self.assertEqual(["2026-06-06T09:01"], acked.details["ack"])
            self.assertNotIn("snooze_until", acked.details)

            snoozed = webapp.snooze_message_in_file(
                path,
                "msg_001",
                {"duration": "15m"},
                now=datetime(2026, 6, 6, 9, 5),
            )
            self.assertNotIn("ack", snoozed.details)
            self.assertEqual(["2026-06-06T09:20"], snoozed.details["snooze_until"])

            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    "[ ] M Ping id:msg_001 sender:bob recipient:self "
                    "notify_at:2026-06-06T09:00 updated:2026-06-06T09:05 "
                    "snooze_until:2026-06-06T09:20\n",
                    handle.read(),
                )

    def test_webapp_message_reply_payload(self):
        from lifetxt import webapp

        original = webapp.message_item_from_payload(
            {
                "title": "Original",
                "id": "msg_001",
                "sender": "alice",
                "recipient": "self",
            }
        )
        reply = webapp.message_reply_from_payload(
            original,
            "msg_001",
            {"title": "Reply"},
            {"user": {"name": "self"}},
        )

        self.assertEqual(["msg_001"], reply.details["parent"])
        self.assertEqual(["self"], reply.details["sender"])
        self.assertEqual(["alice"], reply.details["recipient"])

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

    def test_assist_message_item_non_interactive(self):
        stdout, stderr, code = run_cli(
            "assist",
            "--type",
            "message",
            "--title",
            "Review Slides",
            "--sender",
            "self",
            "--recipient",
            "alice",
            "--notify_at",
            "2026-06-06T09:00",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            '[ ] M "Review Slides" sender:self recipient:alice '
            "notify_at:2026-06-06T09:00\n",
            normalize_newlines(stdout),
        )

    def test_assist_message_uses_config_default_sender(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "lifetxt.json")
            with open(config_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write('{"message":{"default_sender":"bot"}}')

            stdout, stderr, code = run_cli(
                "assist",
                "--config",
                config_path,
                "--type",
                "message",
                "--title",
                "Ping",
                "--recipient",
                "alice",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertEqual(
                "[ ] M Ping recipient:alice sender:bot\n",
                normalize_newlines(stdout),
            )

    def test_assist_auto_id_with_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            extra_path = os.path.join(temp_dir, "archive.life.txt")
            config_path = os.path.join(temp_dir, "lifetxt.json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# life\n")
            with open(extra_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Existing id:task_existing\n")
            with open(config_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {
                        "paths": [path, extra_path],
                        "write_file": path,
                        "ids": {"auto": True, "key": "id"},
                    },
                    handle,
                )

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "assist",
                "--type",
                "task",
                "--title",
                "New Task",
                "--output",
                path,
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            normalized = normalize_newlines(stdout)
            self.assertRegex(normalized, r'^\[ \] T "New Task" id:task_\d{14}\n$')
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual("# life\n" + normalized, handle.read())

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
