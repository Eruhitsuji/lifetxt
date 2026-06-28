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

    def test_line_continuation_joins_next_line(self):
        text = (
            "[ ] T Write_Report \\\n"
            "  due:2026-06-12 project:research\n"
        )

        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(1, len(items))
        self.assertEqual(1, items[0].line)
        self.assertEqual(2, items[0].end_line)
        self.assertEqual(["2026-06-12"], items[0].details["due"])
        self.assertEqual(
            "[ ] T Write_Report due:2026-06-12 project:research",
            item_to_line(items[0]),
        )

    def test_line_continuation_strips_trailing_and_leading_whitespace(self):
        text = (
            "[ ] T Review \\   \n"
            "    due:2026-06-12\n"
        )

        items, diagnostics = parse_text(text)

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(["2026-06-12"], items[0].details["due"])

    def test_line_continuation_at_eof_reports_error(self):
        _items, diagnostics = parse_text("[ ] T Broken \\")

        self.assertTrue(any(d.code == "E020" for d in diagnostics))

    def test_line_continuation_into_body_reports_error(self):
        _items, diagnostics = parse_text(
            "[ ] T Broken \\\n"
            "| body\n"
        )

        self.assertTrue(any(d.code == "E021" for d in diagnostics))

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
            "| Bob | 200 |\n"
        )
        result = markdown_to_plain(md)

        self.assertEqual(
            "| Name  | Score |\n"
            "| ----- | ----- |\n"
            "| Alice | 10    |\n"
            "| Bob   | 200   |",
            result,
        )

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

    def test_markdown_cli_text_preserves_table_shape(self):
        stdout, stderr, code = run_cli(
            "markdown",
            "--format",
            "text",
            "--field",
            "body",
            input_text=(
                '[N] J "Table day"\n'
                "| | Name | Score |\n"
                "| |------|-------|\n"
                "| | Alice | 10 |\n"
                "| | Bob | 200 |\n"
            ),
        )

        normalized = normalize_newlines(stdout)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("| Name  | Score |", normalized)
        self.assertIn("| ----- | ----- |", normalized)
        self.assertIn("| Alice | 10    |", normalized)
        self.assertIn("| Bob   | 200   |", normalized)

    def test_webapp_markdown_css_includes_table_rules(self):
        from lifetxt import webapp

        self.assertIn(".markdown table", webapp.HTML_PAGE)
        self.assertIn("border-collapse: collapse", webapp.HTML_PAGE)

    def test_webapp_item_render_functions_are_not_self_overridden(self):
        from lifetxt import webapp

        self.assertEqual(1, webapp.HTML_PAGE.count("function renderItems("))
        self.assertEqual(1, webapp.HTML_PAGE.count("function selectItem("))
        self.assertNotIn("_origRenderItems", webapp.HTML_PAGE)
        self.assertNotIn("_origSelectItem", webapp.HTML_PAGE)

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

    def test_supported_rrule_subset_has_no_warning(self):
        _items, diagnostics = parse_text(
            "[ ] E Training repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3 "
            "from:2026-06-01T09:00 to:2026-06-01T10:00\n"
        )

        self.assertFalse(any(d.code == "W223" for d in diagnostics))

    def test_unsupported_rrule_features_warn_w223(self):
        _items, diagnostics = parse_text(
            "[ ] H Hourly repeat:RRULE:FREQ=HOURLY at:09:00\n"
            "[ ] H Positional repeat:RRULE:FREQ=MONTHLY;BYDAY=1MO at:09:00\n"
            "[ ] H MonthFilter repeat:RRULE:FREQ=WEEKLY;BYMONTH=6 at:09:00\n"
            "[ ] H BadCount repeat:RRULE:FREQ=DAILY;COUNT=zero at:09:00\n"
        )

        warnings = [d for d in diagnostics if d.code == "W223"]
        self.assertGreaterEqual(len(warnings), 4)
        messages = "\n".join(d.message for d in warnings)
        self.assertIn("FREQ=HOURLY", messages)
        self.assertIn("BYDAY", messages)
        self.assertIn("BYMONTH", messages)
        self.assertIn("COUNT", messages)

    def test_check_cli_rrule_warning_is_recurrence_category(self):
        stdout, stderr, code = run_cli(
            "check",
            "--category",
            "recurrence",
            input_text="[ ] H Hourly repeat:RRULE:FREQ=HOURLY at:09:00\n",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("W223", stdout)
        self.assertIn("FREQ=HOURLY", stdout)

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

    def test_completed_item_warns_when_dependency_is_still_open(self):
        text = (
            "[ ] T Prerequisite id:task_setup\n"
            "[x] T Finished_Work id:task_finish depends_on:task_setup\n"
        )

        _items, diagnostics = parse_text(text)

        warnings = [d for d in diagnostics if d.code == "W224"]
        self.assertEqual(1, len(warnings))
        self.assertEqual(2, warnings[0].line)

    def test_completed_item_has_no_dependency_warning_when_dependency_is_done(self):
        text = (
            "[x] T Prerequisite id:task_setup\n"
            "[x] T Finished_Work id:task_finish depends_on:task_setup\n"
        )

        _items, diagnostics = parse_text(text)

        self.assertFalse(any(d.code == "W224" for d in diagnostics))

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

    def test_people_keys_are_known_for_matching_types(self):
        _items, diagnostics = parse_text(
            "[ ] T Write_Report due:2026-06-12 assignee:alice owner:bob\n"
            "[ ] E Seminar from:2026-06-08T13:00 "
            "to:2026-06-08T14:00 attendee:alice owner:bob\n"
            "[ ] D Form due:2026-06-20 owner:alice assignee:bob\n"
        )

        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertFalse(any(d.code == "W106" for d in diagnostics))

    def test_type_recommended_keys_are_short_first_choice_lists(self):
        from lifetxt.model import KNOWN_KEYS, RECOMMENDED_KEYS_BY_TYPE

        self.assertEqual(
            ("do", "due", "priority", "assignee", "owner", "project", "tag", "id"),
            RECOMMENDED_KEYS_BY_TYPE["T"],
        )
        self.assertLessEqual(max(len(keys) for keys in RECOMMENDED_KEYS_BY_TYPE.values()), 10)
        self.assertIn("depends_on", KNOWN_KEYS)
        self.assertNotIn("depends_on", RECOMMENDED_KEYS_BY_TYPE["T"])

        _items, diagnostics = parse_text("[ ] T Write_Report depends_on:t0 body:details\n")

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

    def test_agenda_cli_marks_blocked_items_in_json_and_text(self):
        text = (
            "[ ] T Setup id:task_setup\n"
            "[ ] T Report id:task_report due:2026-06-06 depends_on:task_setup\n"
            "[ ] T Review id:task_review due:2026-06-06\n"
            "[ ] T Gate id:task_gate blocks:task_review\n"
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
        by_title = {entry["title"]: entry for entry in data}
        self.assertTrue(by_title["Report"]["blocked"])
        self.assertEqual("task_setup", by_title["Report"]["blocked_by"][0]["id"])
        self.assertEqual("depends_on", by_title["Report"]["blocked_by"][0]["relation"])
        self.assertTrue(by_title["Review"]["blocked"])
        self.assertEqual("task_gate", by_title["Review"]["blocked_by"][0]["id"])
        self.assertEqual("blocks", by_title["Review"]["blocked_by"][0]["relation"])

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-06",
            "--to",
            "2026-06-06",
            input_text=text,
        )
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        normalized = normalize_newlines(stdout)
        self.assertIn("blocked", normalized.splitlines()[0])
        self.assertIn("yes", normalized)

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

    def test_agenda_cli_expands_rrule_weekly_byday(self):
        text = (
            "[ ] E Training repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3 "
            "from:2026-06-01T09:00 to:2026-06-01T10:00\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-03",
            "--to",
            "2026-06-03",
            "--format",
            "json",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        data = json.loads(stdout)
        self.assertEqual(["Training"], [entry["title"] for entry in data])
        self.assertEqual("2026-06-03T09:00..2026-06-03T10:00", data[0]["when"])
        self.assertEqual("repeat:from/to", data[0]["key"])
        self.assertEqual("RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3", data[0]["matches"][0]["repeat"])
        self.assertEqual(2, data[0]["matches"][0]["occurrence_index"])

    def test_agenda_cli_rrule_count_limits_later_occurrences(self):
        text = (
            "[ ] E Training repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3 "
            "from:2026-06-01T09:00 to:2026-06-01T10:00\n"
        )

        stdout, stderr, code = run_cli(
            "agenda",
            "--from",
            "2026-06-10",
            "--to",
            "2026-06-10",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertIn("No agenda items found.", normalize_newlines(stdout))

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

    def test_filter_canonical_outputs_explicit_parent_without_indent(self):
        text = (
            "[ ] T Project id:proj_research\n"
            "  [ ] T Literature_Review id:task_lit\n"
        )

        stdout, stderr, code = run_cli("filter", input_text=text)

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(text, normalize_newlines(stdout))

        stdout, stderr, code = run_cli("filter", "--canonical", input_text=text)

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[ ] T Project id:proj_research\n"
            "[ ] T Literature_Review id:task_lit parent:proj_research\n",
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

    def test_filter_time_range_expands_rrule_daily_byday_until(self):
        text = (
            "[ ] H Workday_Checkin repeat:RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20260610 "
            "at:09:00\n"
        )

        stdout, stderr, code = run_cli(
            "filter",
            "--after",
            "2026-06-08",
            "--before",
            "2026-06-08",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(text, normalize_newlines(stdout))

        stdout, stderr, code = run_cli(
            "filter",
            "--after",
            "2026-06-13",
            "--before",
            "2026-06-13",
            input_text=text,
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual("", normalize_newlines(stdout))

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

    def test_to_json_records_source_metadata_for_file_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Root id:task_root\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Child id:task_child parent:task_root\n")

            stdout, stderr, code = run_cli(
                "to-json",
                first_path,
                second_path,
                "--pretty",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            by_title = {entry["title"]: entry for entry in data}
            self.assertEqual(
                "first.life.txt",
                os.path.basename(by_title["Root"]["_source_file"]),
            )
            self.assertEqual(1, by_title["Root"]["_source_line"])
            self.assertEqual(
                "second.life.txt",
                os.path.basename(by_title["Child"]["_source_file"]),
            )
            self.assertEqual(1, by_title["Child"]["_source_line"])

    def test_to_jsonl_records_source_metadata_for_single_file_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T First id:task_001\n")

            stdout, stderr, code = run_cli("to-jsonl", path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            rows = [json.loads(line) for line in stdout.splitlines()]
            self.assertEqual(1, len(rows))
            self.assertEqual("life.txt", os.path.basename(rows[0]["_source_file"]))
            self.assertEqual(1, rows[0]["_source_line"])

    def test_check_cli_resolves_references_across_input_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Root id:task_root\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Child id:task_child parent:task_root depends_on:task_root\n")

            stdout, stderr, code = run_cli("check", first_path, second_path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertNotIn("W215", stdout)

            stdout, stderr, code = run_cli("check", second_path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("WARNING W215", stdout)
            self.assertIn(os.path.basename(second_path), stdout)

    def test_links_cli_reports_cross_file_source_locations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Root id:task_root\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Child id:task_child parent:task_root\n")

            stdout, stderr, code = run_cli(
                "links",
                first_path,
                second_path,
                "--id",
                "task_root",
                "--direction",
                "incoming",
                "--format",
                "json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            data = json.loads(stdout)
            self.assertEqual(1, len(data))
            self.assertIn(os.path.basename(second_path), data[0]["source_location"])
            self.assertIn(os.path.basename(first_path), data[0]["target_location"])

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
            items = data["items"]
            self.assertEqual(["First", "Parent", "Child"], [entry["title"] for entry in items])
            self.assertEqual(["first.life.txt", "second.life.txt", "second.life.txt"], [os.path.basename(entry["source"]) for entry in items])
            self.assertEqual([1, 1, 2], [entry["line"] for entry in items])
            self.assertEqual("parent", items[2]["parent"])
            self.assertEqual(2, items[2]["indent"])
            self.assertIn("directives", data)

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

    def test_from_json_canonical_outputs_explicit_parent_without_indent(self):
        payload = [
            {
                "status": "[ ]",
                "type": "T",
                "title": "Project",
                "details": {"id": ["proj_research"]},
            },
            {
                "status": "[ ]",
                "type": "T",
                "title": "Literature Review",
                "indent": 2,
                "details": {"id": ["task_lit"]},
            },
        ]

        stdout, stderr, code = run_cli("from-json", input_text=json.dumps(payload))

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[ ] T Project id:proj_research\n"
            '  [ ] T "Literature Review" id:task_lit\n',
            normalize_newlines(stdout),
        )

        stdout, stderr, code = run_cli(
            "from-json",
            "--canonical",
            input_text=json.dumps(payload),
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        self.assertEqual(
            "[ ] T Project id:proj_research\n"
            '[ ] T "Literature Review" id:task_lit parent:proj_research\n',
            normalize_newlines(stdout),
        )


class LifeTxtArchiveCliTests(unittest.TestCase):
    SOURCE_TEXT = (
        "[x] T Done_Task id:T001 done:2026-01-15\n"
        "[-] T Canceled_Task id:T002 done:2026-03-10\n"
        "[ ] T Open_Task id:T003\n"
        "[x] T Recent_Done id:T004 done:2026-06-20\n"
    )

    def test_archive_dry_run_shows_preview_and_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)

            stdout, stderr, code = run_cli("archive", src, "--dest", dest, "--dry-run", "--yes")

            self.assertEqual(0, code, stderr)
            self.assertIn("(dry run", stdout)
            self.assertIn("Done_Task", stdout)
            self.assertIn("Canceled_Task", stdout)
            self.assertFalse(os.path.exists(dest))
            with open(src, "r", encoding="utf-8") as f:
                self.assertEqual(self.SOURCE_TEXT, f.read())

    def test_archive_move_removes_items_from_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)

            stdout, stderr, code = run_cli("archive", src, "--dest", dest, "--yes")

            self.assertEqual(0, code, stderr)
            with open(src, "r", encoding="utf-8") as f:
                src_content = f.read()
            with open(dest, "r", encoding="utf-8") as f:
                dest_content = f.read()

            self.assertNotIn("Done_Task", src_content)
            self.assertNotIn("Canceled_Task", src_content)
            self.assertIn("Open_Task", src_content)
            self.assertIn("Done_Task", dest_content)
            self.assertIn("Canceled_Task", dest_content)

    def test_archive_copy_keeps_items_in_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)

            stdout, stderr, code = run_cli("archive", src, "--dest", dest, "--copy", "--yes")

            self.assertEqual(0, code, stderr)
            with open(src, "r", encoding="utf-8") as f:
                src_content = f.read()
            self.assertEqual(self.SOURCE_TEXT, src_content)
            with open(dest, "r", encoding="utf-8") as f:
                dest_content = f.read()
            self.assertIn("Done_Task", dest_content)

    def test_archive_before_filter_excludes_recent_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)

            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--before", "2026-04-01", "--dry-run", "--yes"
            )

            self.assertEqual(0, code, stderr)
            self.assertIn("Done_Task", stdout)
            self.assertIn("Canceled_Task", stdout)
            self.assertNotIn("Recent_Done", stdout)

    def test_archive_max_items_limits_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)

            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--max-items", "1", "--yes"
            )

            self.assertEqual(0, code, stderr)
            with open(dest, "r", encoding="utf-8") as f:
                dest_content = f.read()
            items_in_dest = [l for l in dest_content.splitlines() if l.strip()]
            self.assertEqual(1, len(items_in_dest))

    def test_archive_no_match_exits_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write("[ ] T Open_Task\n")

            stdout, stderr, code = run_cli("archive", src, "--dest", dest, "--yes")

            self.assertEqual(0, code, stderr)
            self.assertIn("No items", stdout)
            self.assertFalse(os.path.exists(dest))

    def test_archive_aborted_on_no_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = os.path.join(temp_dir, "life.txt")
            dest = os.path.join(temp_dir, "archive.life.txt")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)

            stdout, stderr, code = run_cli("archive", src, "--dest", dest, input_text="n\n")

            self.assertEqual(0, code, stderr)
            self.assertIn("Aborted", stdout)
            self.assertFalse(os.path.exists(dest))


class LifeTxtDirectiveTests(unittest.TestCase):
    def test_parse_directives_extracts_block(self):
        from lifetxt.parser import parse_directives
        text = "#! self: alice\n#! timezone: UTC\n#! project: work\n[ ] T Task\n"
        directives = parse_directives(text)
        self.assertEqual("alice", directives["self"])
        self.assertEqual("UTC", directives["timezone"])
        self.assertEqual("work", directives["project"])

    def test_parse_directives_stops_at_blank_line(self):
        from lifetxt.parser import parse_directives
        text = "#! self: alice\n\n#! timezone: UTC\n"
        directives = parse_directives(text)
        self.assertEqual({"self": "alice"}, dict(directives))

    def test_parse_directives_stops_at_non_directive(self):
        from lifetxt.parser import parse_directives
        text = "#! self: alice\n# regular comment\n#! timezone: UTC\n"
        directives = parse_directives(text)
        self.assertEqual({"self": "alice"}, dict(directives))

    def test_parse_directives_empty_file(self):
        from lifetxt.parser import parse_directives
        self.assertEqual({}, dict(parse_directives("")))

    def test_parse_directives_no_directives(self):
        from lifetxt.parser import parse_directives
        text = "[ ] T Task\n"
        self.assertEqual({}, dict(parse_directives(text)))

    def test_parse_directives_ignored_by_item_parser(self):
        text = "#! self: alice\n#! project: work\n[ ] T Task\n"
        items, diagnostics = parse_text(text)
        self.assertEqual(1, len(items))
        self.assertEqual("Task", items[0].title)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])

    def test_sources_json_includes_directives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("#! self: alice\n#! timezone: UTC\n[ ] T Task\n")
            stdout, stderr, code = run_cli("sources", path, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIn("items", data)
            self.assertIn("directives", data)
            source_key = list(data["directives"].keys())[0]
            self.assertEqual("alice", data["directives"][source_key]["self"])
            self.assertEqual("UTC", data["directives"][source_key]["timezone"])

    def test_sources_json_empty_directives_when_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("[ ] T Task\n")
            stdout, stderr, code = run_cli("sources", path, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            source_key = list(data["directives"].keys())[0]
            self.assertEqual({}, data["directives"][source_key])

    def test_sources_text_shows_directives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("#! self: alice\n[ ] T Task\n")
            stdout, stderr, code = run_cli("sources", path)
            self.assertEqual(0, code, stderr)
            self.assertIn("#! self: alice", stdout)


class LifeTxtQuickCliTests(unittest.TestCase):
    def test_quick_appends_task_to_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            stdout, stderr, code = run_cli(
                "quick", "Buy_milk", "--append", path,
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Buy_milk", stdout)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[ ] T Buy_milk", content)

    def test_quick_applies_detail_flags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            run_cli(
                "quick", "Buy_milk",
                "--due", "2026-12-31",
                "--project", "home",
                "--append", path,
            )
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("due:2026-12-31", content)
            self.assertIn("project:home", content)

    def test_quick_resolves_today(self):
        import datetime as dt
        today_iso = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            run_cli("quick", "Task", "--due", "today", "--append", path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("due:%s" % today_iso, content)

    def test_quick_resolves_tomorrow(self):
        import datetime as dt
        tomorrow_iso = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            run_cli("quick", "Task", "--due", "tomorrow", "--append", path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("due:%s" % tomorrow_iso, content)

    def test_quick_alias_q_works(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            stdout, stderr, code = run_cli("q", "Quick_task", "--append", path)
            self.assertEqual(0, code, stderr)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Quick_task", content)

    def test_quick_fails_without_output_file(self):
        stdout, stderr, code = run_cli("quick", "Task")
        self.assertEqual(1, code)
        self.assertIn("No output file", stderr)

    def test_quick_appends_to_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("[ ] T Existing\n")
            run_cli("quick", "New_task", "--append", path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Existing", content)
            self.assertIn("New_task", content)


class LifeTxtDoneCliTests(unittest.TestCase):
    SOURCE_TEXT = "[ ] T Buy_milk id:t001\n[ ] T Clean_house id:t002\n[ ] T Walk_dog\n"

    def test_done_by_id_marks_complete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("done", path, "t001")
            self.assertEqual(0, code, stderr)
            self.assertIn("Done:", stdout)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[x] T Buy_milk", content)
            self.assertIn("[ ] T Clean_house", content)

    def test_done_by_id_appends_done_date(self):
        import datetime as dt
        today_iso = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            run_cli("done", path, "t001")
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("done:%s" % today_iso, content)

    def test_done_by_line_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("done", path, "--line", "2")
            self.assertEqual(0, code, stderr)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[x] T Clean_house", content)

    def test_done_by_text_unique_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("done", path, "--text", "Walk")
            self.assertEqual(0, code, stderr)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[x] T Walk_dog", content)

    def test_done_by_text_multiple_matches_prompt(self):
        source = "[ ] T Buy_milk\n[ ] T Buy_bread\n[ ] T Sleep\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(source)
            stdout, stderr, code = run_cli("done", path, "--text", "Buy", input_text="1\n")
            self.assertEqual(0, code, stderr)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[x] T Buy_milk", content)
            self.assertIn("[ ] T Buy_bread", content)

    def test_done_already_done_no_rewrite(self):
        import datetime as dt
        date = dt.date.today().isoformat()
        source = "[x] T Done_task id:t001 done:%s\n" % date
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(source)
            stdout, stderr, code = run_cli("done", path, "t001")
            self.assertEqual(0, code, stderr)
            self.assertIn("Already done", stdout)

    def test_done_missing_id_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("done", path, "nonexistent")
            self.assertEqual(1, code)


class LifeTxtSummaryCliTests(unittest.TestCase):
    SOURCE_TEXT = (
        "[ ] T Buy_milk id:t001 due:2026-06-01\n"
        "[x] T Clean_house id:t002 done:2026-06-02\n"
        "[N] N A_note\n"
    )

    def test_summary_text_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("summary", path)
            self.assertEqual(0, code, stderr)
            self.assertIn("Items:", stdout)
            self.assertIn("3", stdout)
            self.assertIn("Lines:", stdout)

    def test_summary_json_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("summary", path, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(3, data["item_count"])
            self.assertEqual(3, data["line_count"])
            self.assertIn("type_counts", data)
            self.assertIn("status_counts", data)

    def test_summary_counts_by_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("summary", path, "--format", "json")
            data = json.loads(stdout)
            self.assertEqual(2, data["type_counts"].get("T", 0))
            self.assertEqual(1, data["type_counts"].get("N", 0))

    def test_summary_counts_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("summary", path, "--format", "json")
            data = json.loads(stdout)
            self.assertEqual(2, data["ids_present"])
            self.assertEqual(1, data["ids_missing"])

    def test_summary_date_range(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.SOURCE_TEXT)
            stdout, stderr, code = run_cli("summary", path, "--format", "json")
            data = json.loads(stdout)
            self.assertEqual("2026-06-01", data["date_min"])
            self.assertEqual("2026-06-02", data["date_max"])

    def test_summary_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("")
            stdout, stderr, code = run_cli("summary", path, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(0, data["item_count"])
            self.assertEqual(0, data["line_count"])


class LifeTxtDoneEdgeCaseTests(unittest.TestCase):
    SOURCE = "[ ] T Buy_milk id:t001\n[ ] T Clean_house id:t002\n"

    def test_done_text_no_match_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli("done", path, "--text", "xyz_nonexistent_999")
            self.assertEqual(1, code)
            self.assertIn("xyz_nonexistent_999", stderr)

    def test_done_line_on_blank_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T First_item\n\n[ ] T Third_item\n")
            stdout, stderr, code = run_cli("done", path, "--line", "2")
            self.assertEqual(1, code)

    def test_done_no_args_exits_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli("done", path)
            self.assertEqual(1, code)


class LifeTxtSummaryEdgeCaseTests(unittest.TestCase):
    def test_summary_multi_file_returns_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path1 = os.path.join(tmp, "a.txt")
            path2 = os.path.join(tmp, "b.txt")
            with open(path1, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_A id:A001\n")
            with open(path2, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_B id:B001\n")
            stdout, stderr, code = run_cli("summary", path1, path2, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIsInstance(data, list)
            self.assertEqual(2, len(data))
            sources = [d["source"] for d in data]
            self.assertIn(path1, sources)
            self.assertIn(path2, sources)

    def test_summary_pretty_indents_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one\n")
            stdout, stderr, code = run_cli("summary", path, "--format", "json", "--pretty")
            self.assertEqual(0, code, stderr)
            self.assertIn("  ", stdout)
            data = json.loads(stdout)
            self.assertIn("item_count", data)

    def test_summary_single_file_returns_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one\n")
            stdout, stderr, code = run_cli("summary", path, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIsInstance(data, dict)
            self.assertIn("item_count", data)


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


class LifeTxtCheckLineTests(unittest.TestCase):
    def test_check_line_valid_item_returns_ok(self):
        from lifetxt.parser import parse_text as pt
        text = "[ ] T Valid_task due:2026-06-30\n"
        items, diags = pt(text)
        self.assertEqual(1, len(items))
        self.assertFalse(any(d.severity == "error" for d in diags))

    def test_check_line_invalid_item_has_error_diagnostic(self):
        from lifetxt.parser import parse_text as pt
        text = "NOTAVALIDLINE\n"
        items, diags = pt(text)
        self.assertEqual(0, len(items))

    def test_webapp_check_line_function_ok(self):
        from lifetxt.webapp import create_app
        items, diags = parse_text("[ ] T Good_task project:work\n")
        has_error = any(d.severity == "error" for d in diags)
        self.assertFalse(has_error)

    def test_public_git_config_defaults(self):
        from lifetxt.webapp import public_git_config
        result = public_git_config({})
        self.assertFalse(result["enable_api"])
        self.assertTrue(result["ui_poll"])
        self.assertEqual(60, result["ui_poll_seconds"])

    def test_public_web_config_due_soon_days(self):
        from lifetxt.webapp import public_web_config
        result = public_web_config({"web": {"due_soon_days": "7"}})
        self.assertEqual(7, result["due_soon_days"])

    def test_public_web_config_due_soon_days_default(self):
        from lifetxt.webapp import public_web_config
        result = public_web_config({})
        self.assertEqual(3, result["due_soon_days"])


class LifeTxtItemsRawTests(unittest.TestCase):
    def test_items_raw_parse_valid_line(self):
        from lifetxt.parser import parse_text
        text = "[ ] T Buy_milk due:2026-06-30 project:home\n"
        items, diags = parse_text(text)
        self.assertEqual(1, len(items))
        self.assertFalse(any(d.severity == "error" for d in diags))

    def test_items_raw_empty_line_parses_nothing(self):
        from lifetxt.parser import parse_text
        text = "\n"
        items, diags = parse_text(text)
        self.assertEqual(0, len(items))

    def test_items_raw_invalid_line_has_no_items(self):
        from lifetxt.parser import parse_text
        text = "NOT A VALID LINE\n"
        items, diags = parse_text(text)
        self.assertEqual(0, len(items))

    def test_items_raw_write_appends_newline(self):
        import tempfile, os
        from lifetxt.webapp import write_text, read_text, ensure_parent_dir
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("[ ] T Existing_task\n")
            path = f.name
        try:
            existing = read_text(path)
            raw = "[ ] T New_task"
            prefix = "\n" if existing and not existing.endswith(("\n", "\r")) else ""
            write_text(path, existing + prefix + raw + "\n")
            content = read_text(path)
            lines = content.splitlines()
            self.assertIn("[ ] T New_task", lines)
            self.assertEqual(2, len(lines))
        finally:
            os.unlink(path)


class LifeTxtHeatmapTests(unittest.TestCase):
    def test_habit_completion_dates_returns_date_set(self):
        from lifetxt.stats import item_completion_dates
        from lifetxt.parser import parse_text
        items, _ = parse_text("[x] H Exercise done:2026-06-20 done:2026-06-21\n")
        if items:
            dates = item_completion_dates(items[0])
            self.assertIsInstance(dates, set)

    def test_streak_days_zero_for_empty(self):
        from lifetxt.stats import streak_days
        import datetime
        result = streak_days(set(), datetime.date.today())
        self.assertEqual(0, result)


class LifeTxtStatsSummaryTests(unittest.TestCase):
    def _make_items(self, text):
        from lifetxt.parser import parse_text
        items, _ = parse_text(text)
        return items

    def test_project_stats_returns_by_project(self):
        from lifetxt.stats import project_stats
        items = self._make_items(
            "[ ] T Task1 project:alpha\n"
            "[x] T Task2 project:alpha\n"
            "[ ] T Task3 project:beta\n"
        )
        result = project_stats(items)
        self.assertIn("alpha", result)
        self.assertEqual(2, result["alpha"]["total"])
        self.assertEqual(1, result["alpha"]["done"])

    def test_project_stats_rate_calculation(self):
        from lifetxt.stats import project_stats
        items = self._make_items(
            "[x] T Done project:work\n"
            "[x] T Done2 project:work\n"
            "[ ] T Open project:work\n"
        )
        result = project_stats(items)
        self.assertGreater(result["work"]["rate"], 50)  # rate is percentage (0-100)

    def test_habit_chart_data_is_numeric(self):
        from lifetxt.stats import make_buckets, item_completion_dates, streak_days
        import datetime
        items = self._make_items("[ ] H Exercise done:2026-06-01 done:2026-06-02\n")
        if not items:
            return
        s = datetime.date(2026, 5, 1)
        e = datetime.date(2026, 6, 30)
        buckets = make_buckets(s, e, "weekly")
        habit = items[0]
        dates = item_completion_dates(habit)
        counts = []
        for bucket_start, bucket_end in buckets:
            count = 0
            d = bucket_start
            while d <= bucket_end:
                if d in dates:
                    count += 1
                d += datetime.timedelta(days=1)
            counts.append(count)
        for val in counts:
            self.assertIsInstance(val, int)

    def test_make_buckets_weekly_produces_7day_buckets(self):
        from lifetxt.stats import make_buckets
        import datetime
        s = datetime.date(2026, 6, 1)
        e = datetime.date(2026, 6, 21)
        buckets = make_buckets(s, e, "weekly")
        self.assertTrue(len(buckets) >= 3)
        span = (buckets[0][1] - buckets[0][0]).days + 1
        self.assertEqual(7, span)

    def test_make_buckets_monthly_covers_full_month(self):
        from lifetxt.stats import make_buckets
        import datetime
        s = datetime.date(2026, 1, 1)
        e = datetime.date(2026, 3, 31)
        buckets = make_buckets(s, e, "monthly")
        self.assertEqual(3, len(buckets))

    def test_mood_chart_data_is_numeric_or_none(self):
        from lifetxt.stats import make_buckets, mood_stats
        import datetime
        items = self._make_items("[ ] J Journal mood:good\n")
        s = datetime.date(2026, 6, 1)
        e = datetime.date(2026, 6, 30)
        buckets = make_buckets(s, e, "daily")
        result = mood_stats(items, buckets)
        self.assertIn("counts", result)


class LifeTxtWebappHelperTests(unittest.TestCase):
    def test_subgraph_returns_reachable_nodes_only(self):
        from lifetxt.webapp import _subgraph
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]
        edges = [
            {"source": "a", "target": "b", "relation": "depends_on"},
            {"source": "b", "target": "c", "relation": "depends_on"},
        ]
        fn, fe = _subgraph(nodes, edges, "a", depth=None)
        ids = {n["id"] for n in fn}
        self.assertIn("a", ids)
        self.assertIn("b", ids)
        self.assertIn("c", ids)
        self.assertNotIn("d", ids)

    def test_subgraph_depth_limit(self):
        from lifetxt.webapp import _subgraph
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [
            {"source": "a", "target": "b", "relation": "depends_on"},
            {"source": "b", "target": "c", "relation": "depends_on"},
        ]
        fn, fe = _subgraph(nodes, edges, "a", depth=1)
        ids = {n["id"] for n in fn}
        self.assertIn("a", ids)
        self.assertIn("b", ids)
        self.assertNotIn("c", ids)

    def test_subgraph_unknown_root_returns_empty(self):
        from lifetxt.webapp import _subgraph
        nodes = [{"id": "a"}]
        edges = []
        fn, fe = _subgraph(nodes, edges, "zzz", depth=None)
        self.assertEqual([], fn)
        self.assertEqual([], fe)

    def test_elapsed_to_minutes_compact_form(self):
        from lifetxt.webapp import _elapsed_to_minutes
        self.assertEqual(90, _elapsed_to_minutes("1h30m"))
        self.assertEqual(30, _elapsed_to_minutes("30m"))
        self.assertEqual(60, _elapsed_to_minutes("1h"))

    def test_elapsed_to_minutes_bare_integer(self):
        from lifetxt.webapp import _elapsed_to_minutes
        self.assertEqual(90, _elapsed_to_minutes("90"))

    def test_elapsed_to_minutes_invalid_returns_none(self):
        from lifetxt.webapp import _elapsed_to_minutes
        self.assertIsNone(_elapsed_to_minutes("abc"))

    def test_chart_tasks_stats_via_library(self):
        from lifetxt.stats import stats_range, make_buckets, task_bucket_stats
        items_text = "[x] T Done done:2026-06-01\n[ ] T Open due:2026-06-01\n"
        items, _ = parse_text(items_text)
        s, e = stats_range("2026-06-01", "2026-06-30")
        buckets = make_buckets(s, e, "daily")
        stats = task_bucket_stats(items, buckets)
        self.assertIsInstance(stats, list)
        self.assertIn("done", stats[0])
        self.assertIn("total", stats[0])

    def test_chart_mood_via_library(self):
        from lifetxt.stats import stats_range, make_buckets, mood_stats
        items_text = "[x] J Morning mood:happy done:2026-06-01\n[x] J Evening mood:sad done:2026-06-02\n"
        items, _ = parse_text(items_text)
        s, e = stats_range("2026-06-01", "2026-06-30")
        buckets = make_buckets(s, e, "daily")
        result = mood_stats(items, buckets)
        self.assertIn("counts", result)
        self.assertIn("happy", result["counts"])


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


class LifeTxtDirectiveWiringTests(unittest.TestCase):
    def test_quick_applies_project_directive_to_new_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("#! project: myproj\n\n")
            stdout, stderr, code = run_cli("quick", "Buy_milk", "--append", life_file)
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("project:myproj", content)
            self.assertIn("Buy_milk", content)

    def test_quick_applies_self_directive_as_person_for_S_item(self):
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("#! self: alice\n\n")
            stdout, stderr, code = run_cli(
                "quick", "At_office", "--type", "S",
                "--from", now, "--state", "working",
                "--append", life_file,
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("person:alice", content)

    def test_quick_explicit_project_overrides_directive(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("#! project: defaultproj\n\n")
            stdout, stderr, code = run_cli(
                "quick", "Task_A", "--project", "explicit", "--append", life_file
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("project:explicit", content)
            self.assertNotIn("project:defaultproj", content)


class LifeTxtInitCliTests(unittest.TestCase):
    def test_init_creates_life_txt_with_directives(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            cfg_file = os.path.join(tmp, ".lifetxt.json")
            stdout, stderr, code = run_cli(
                "init",
                "--file", life_file,
                "--config-output", cfg_file,
                "--name", "alice",
                "--timezone", "Asia/Tokyo",
                "--project", "work",
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("#! self: alice", content)
            self.assertIn("#! timezone: Asia/Tokyo", content)
            self.assertIn("#! project: work", content)
            self.assertIn("First_Task", content)
            self.assertIn("project:work", content)

    def test_init_creates_config_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            cfg_file = os.path.join(tmp, ".lifetxt.json")
            run_cli(
                "init",
                "--file", life_file,
                "--config-output", cfg_file,
                "--name", "bob",
                "--timezone", "UTC",
            )
            data = json.loads(open(cfg_file, encoding="utf-8").read())
            self.assertEqual("bob", data["defaults"]["person"])
            self.assertEqual("UTC", data["defaults"]["timezone"])

    def test_init_interactive_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            cfg_file = os.path.join(tmp, ".lifetxt.json")
            stdin = "carol\nEurope/London\nresearch\n"
            stdout, stderr, code = run_cli(
                "init", "--file", life_file, "--config-output", cfg_file,
                input_text=stdin,
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("#! self: carol", content)
            self.assertIn("#! timezone: Europe/London", content)
            self.assertIn("#! project: research", content)

    def test_init_prompts_before_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            cfg_file = os.path.join(tmp, ".lifetxt.json")
            open(life_file, "w").close()
            stdout, stderr, code = run_cli(
                "init", "--file", life_file, "--config-output", cfg_file,
                "--name", "alice", "--timezone", "UTC",
                input_text="n\n",
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Aborted", stdout)


class LifeTxtDoctorCliTests(unittest.TestCase):
    def test_doctor_ok_with_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_bug\n")
            stdout, stderr, code = run_cli("doctor", life_file)
            normalized = normalize_newlines(stdout)
            self.assertIn("[OK]", normalized)
            self.assertIn("life.txt", normalized)

    def test_doctor_fail_on_missing_file(self):
        stdout, stderr, code = run_cli("doctor", "/nonexistent/no_such_file.life.txt")
        normalized = normalize_newlines(stdout)
        self.assertEqual(1, code)
        self.assertIn("[XX]", normalized)

    def test_doctor_json_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one\n")
            stdout, stderr, code = run_cli("doctor", life_file, "--format", "json")
            records = json.loads(stdout)
            self.assertIsInstance(records, list)
            self.assertTrue(len(records) > 0)
            self.assertIn("status", records[0])
            self.assertIn("check", records[0])
            self.assertIn("message", records[0])

    def test_doctor_fail_on_syntax_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("not a valid life.txt line\n")
            stdout, stderr, code = run_cli("doctor", life_file)
            normalized = normalize_newlines(stdout)
            self.assertEqual(1, code)
            self.assertIn("[XX]", normalized)


class LifeTxtAssignCliTests(unittest.TestCase):
    def test_assign_updates_assignee_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:T001 assignee:alice\n")
            stdout, stderr, code = run_cli("assign", life_file, "T001", "--to", "bob")
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("assignee:bob", content)
            self.assertNotIn("assignee:alice", content)

    def test_assign_adds_assignee_when_none_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:T001\n")
            stdout, stderr, code = run_cli("assign", life_file, "T001", "--to", "carol")
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("assignee:carol", content)

    def test_assign_fails_on_missing_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:T001\n")
            stdout, stderr, code = run_cli("assign", life_file, "T999", "--to", "bob")
            self.assertEqual(1, code)
            self.assertIn("T999", stderr)

    def test_assign_notify_appends_M_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:T001\n")
            stdout, stderr, code = run_cli("assign", life_file, "T001", "--to", "dave", "--notify")
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("[ ] M", content)
            self.assertIn("recipient:dave", content)


class LifeTxtHealthCliTests(unittest.TestCase):
    def test_health_clean_file_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_bug\n")
            stdout, stderr, code = run_cli("health", life_file)
            self.assertEqual(0, code, stderr)
            self.assertIn("OK", normalize_newlines(stdout))

    def test_health_w303_overdue_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Old_task due:2020-01-01\n")
            stdout, stderr, code = run_cli("health", life_file)
            self.assertEqual(1, code)
            self.assertIn("W303", normalize_newlines(stdout))

    def test_health_w303_upcoming_task(self):
        import datetime
        soon = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Upcoming_task due:%s\n" % soon)
            stdout, stderr, code = run_cli("health", life_file)
            self.assertEqual(1, code)
            self.assertIn("W303", normalize_newlines(stdout))

    def test_health_json_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Old_task due:2020-01-01\n")
            stdout, stderr, code = run_cli("health", life_file, "--format", "json")
            issues = json.loads(stdout)
            self.assertIsInstance(issues, list)
            self.assertTrue(len(issues) > 0)
            self.assertIn("code", issues[0])
            codes = [issue["code"] for issue in issues]
            self.assertIn("W303", codes)

    def test_health_reports_blocked_items_w305(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[ ] T Setup id:task_setup\n"
                    "[ ] T Report id:task_report depends_on:task_setup\n"
                )
            stdout, stderr, code = run_cli("health", life_file, "--format", "json")
            issues = json.loads(stdout)
            codes = [issue["code"] for issue in issues]
            self.assertEqual(1, code)
            self.assertEqual("", stderr)
            self.assertIn("W305", codes)
            issue = [entry for entry in issues if entry["code"] == "W305"][0]
            self.assertEqual("Report", issue["title"])
            self.assertEqual("task_setup", issue["blocked_by"])

    def test_health_w302_open_habit_no_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] H Daily_exercise repeat:daily\n")
            stdout, stderr, code = run_cli("health", life_file)
            self.assertEqual(1, code)
            self.assertIn("W302", normalize_newlines(stdout))


class LifeTxtInboxCliTests(unittest.TestCase):
    def test_inbox_empty_when_all_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_bug project:work due:2026-12-01\n")
            stdout, stderr, code = run_cli("inbox", life_file)
            self.assertEqual(0, code, stderr)
            self.assertIn("empty", normalize_newlines(stdout).lower())

    def test_inbox_shows_unclassified_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Buy_milk\n")
            stdout, stderr, code = run_cli("inbox", life_file)
            self.assertEqual(0, code, stderr)
            self.assertIn("Buy_milk", normalize_newlines(stdout))

    def test_inbox_excludes_task_with_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Buy_milk project:shopping\n[ ] T Fix_bug\n")
            stdout, stderr, code = run_cli("inbox", life_file)
            self.assertEqual(0, code, stderr)
            self.assertNotIn("Buy_milk", normalize_newlines(stdout))
            self.assertIn("Fix_bug", normalize_newlines(stdout))

    def test_inbox_json_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Unclassified_task\n")
            stdout, stderr, code = run_cli("inbox", life_file, "--format", "json")
            self.assertEqual(0, code, stderr)
            items = json.loads(stdout)
            self.assertEqual(1, len(items))
            self.assertEqual("Unclassified_task", items[0]["title"])


class LifeTxtCleanupCliTests(unittest.TestCase):
    def test_cleanup_ok_with_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_bug id:T001 project:work\n")
            stdout, stderr, code = run_cli("cleanup", life_file)
            self.assertEqual(0, code, stderr)
            self.assertIn("OK", normalize_newlines(stdout))

    def test_cleanup_reports_missing_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T No_id_here project:work\n")
            stdout, stderr, code = run_cli("cleanup", life_file)
            self.assertEqual(0, code, stderr)
            normalized = normalize_newlines(stdout)
            self.assertIn("ids", normalized)
            self.assertIn("missing", normalized)

    def test_cleanup_json_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T No_id_here\n")
            stdout, stderr, code = run_cli("cleanup", life_file, "--format", "json")
            self.assertEqual(0, code, stderr)
            suggestions = json.loads(stdout)
            self.assertIsInstance(suggestions, list)
            checks = [s["check"] for s in suggestions]
            self.assertIn("ids", checks)


class LifeTxtUndoCliTests(unittest.TestCase):
    def _cfg(self, tmp):
        """Return a --config path that isolates undo/backup dirs inside tmp."""
        cfg_path = os.path.join(tmp, ".lifetxt.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(
                {"undo": {"dir": os.path.join(tmp, "undo")},
                 "backup": {"dir": os.path.join(tmp, "backup")}},
                f,
            )
        return cfg_path

    def test_undo_restores_previous_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one id:T001\n")
            run_cli("--config", cfg, "done", life_file, "T001")
            with open(life_file, encoding="utf-8") as fh:
                content_after_done = fh.read()
            self.assertIn("[x]", content_after_done)
            stdout, stderr, code = run_cli("--config", cfg, "undo", life_file)
            self.assertEqual(0, code, stderr)
            self.assertIn("Restored", normalize_newlines(stdout))
            with open(life_file, encoding="utf-8") as fh:
                restored = fh.read()
            self.assertIn("[ ]", restored)

    def test_undo_list_shows_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one id:T001\n")
            run_cli("--config", cfg, "done", life_file, "T001")
            stdout, stderr, code = run_cli("--config", cfg, "undo", life_file, "--list")
            self.assertEqual(0, code, stderr)
            self.assertIn("op=done", normalize_newlines(stdout))

    def test_undo_no_history_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one\n")
            stdout, stderr, code = run_cli("--config", cfg, "undo", life_file)
            self.assertEqual(0, code, stderr)
            self.assertIn("No undo history", normalize_newlines(stdout))

    def test_undo_quick_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Existing\n")
            run_cli("--config", cfg, "quick", "--append", life_file, "New_task")
            stdout, stderr, code = run_cli("--config", cfg, "undo", life_file, "--list")
            self.assertEqual(0, code, stderr)
            self.assertIn("op=quick", normalize_newlines(stdout))


class LifeTxtReviewCliTests(unittest.TestCase):
    def _make_file(self, tmp, content):
        life_file = os.path.join(tmp, "life.txt")
        with open(life_file, "w", encoding="utf-8") as f:
            f.write(content)
        return life_file

    def test_review_text_shows_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            today = __import__("datetime").date.today().isoformat()
            content = (
                "[x] T Finished_task done:%s id:T001\n"
                "[ ] T Open_task id:T002\n"
            ) % today
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week")
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("Completed:", out)
            self.assertIn("Open:", out)

    def test_review_json_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            today = __import__("datetime").date.today().isoformat()
            content = "[x] T Done_task done:%s id:T001\n[ ] T Open_task id:T002\n" % today
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week", "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIn("completed_tasks", data)
            self.assertIn("open_tasks", data)
            self.assertIn("range", data)
            self.assertEqual(1, data["completed_tasks"])
            self.assertEqual(1, data["open_tasks"])

    def test_review_month_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "[x] T January_task done:2026-01-15 id:T001\n"
                "[x] T February_task done:2026-02-10 id:T002\n"
            )
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli(
                "review", life_file, "--month", "2026-01", "--format", "json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(1, data["completed_tasks"])

    def test_review_habit_completion_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "[x] H Exercise\n"
                "[x] H Exercise\n"
                "[ ] H Exercise\n"
            )
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week", "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIn("Exercise", data["habits"])
            h = data["habits"]["Exercise"]
            self.assertEqual(2, h["done"])
            self.assertEqual(1, h["open"])
            self.assertEqual(67, h["completion_rate"])

    def test_review_elapsed_by_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "[x] T Work_task project:projectA elapsed:1h30m done:2026-01-15 id:T001\n"
                "[x] T Other_task project:projectB elapsed:45m done:2026-01-15 id:T002\n"
            )
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli(
                "review", life_file, "--month", "2026-01", "--format", "json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIn("projectA", data["elapsed_by_project"])
            self.assertIn("projectB", data["elapsed_by_project"])


class LifeTxtW225Tests(unittest.TestCase):
    def test_w225_fires_for_completed_parent_with_open_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent_task id:P001\n"
                    "[ ] T Child_task parent:P001 id:C001\n"
                )
            stdout, stderr, code = run_cli("check", life_file)
            out = normalize_newlines(stdout + stderr)
            self.assertIn("W225", out)

    def test_w225_no_fire_when_all_children_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent_task id:P001\n"
                    "[x] T Child_task parent:P001 id:C001\n"
                )
            stdout, stderr, code = run_cli("check", life_file)
            out = normalize_newlines(stdout + stderr)
            self.assertNotIn("W225", out)

    def test_w225_no_fire_for_open_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[ ] T Parent_task id:P001\n"
                    "[ ] T Child_task parent:P001 id:C001\n"
                )
            stdout, stderr, code = run_cli("check", life_file)
            out = normalize_newlines(stdout + stderr)
            self.assertNotIn("W225", out)

    def test_w225_fires_for_canceled_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[-] T Canceled_parent id:P001\n"
                    "[ ] T Orphan_child parent:P001 id:C001\n"
                )
            stdout, stderr, code = run_cli("check", life_file)
            out = normalize_newlines(stdout + stderr)
            self.assertIn("W225", out)


class LifeTxtInitYesTests(unittest.TestCase):
    def test_init_yes_creates_files_without_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            config_file = os.path.join(tmp, ".lifetxt.json")
            stdout, stderr, code = run_cli(
                "init",
                "--file", life_file,
                "--config-output", config_file,
                "--yes",
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue(os.path.exists(life_file))
            self.assertTrue(os.path.exists(config_file))
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("#! self: self", content)
            self.assertIn("#! timezone: UTC", content)

    def test_init_yes_with_name_uses_provided_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            config_file = os.path.join(tmp, ".lifetxt.json")
            run_cli(
                "init",
                "--file", life_file,
                "--config-output", config_file,
                "--yes",
                "--name", "alice",
            )
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("#! self: alice", content)

    def test_init_yes_overwrite_without_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            config_file = os.path.join(tmp, ".lifetxt.json")
            # Create existing file
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("# existing\n")
            stdout, stderr, code = run_cli(
                "init",
                "--file", life_file,
                "--config-output", config_file,
                "--yes",
            )
            self.assertEqual(0, code, stderr)
            # Should have overwritten without prompting
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("#! self:", content)


class LifeTxtCheckIgnoreTests(unittest.TestCase):
    def test_check_ignore_suppresses_w225(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent_task id:P001\n"
                    "[ ] T Child_task id:C001 parent:P001\n"
                )
            stdout, stderr, code = run_cli("check", life_file, "--ignore", "W225")
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W225", normalize_newlines(stdout))

    def test_check_ignore_multiple_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task est:90m\n")
            stdout, stderr, code = run_cli("check", life_file, "--ignore", "W222")
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W222", normalize_newlines(stdout))

    def test_check_w225_shows_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent_task id:P001\n"
                    "[ ] T Child_task id:C001 parent:P001\n"
                )
            stdout, stderr, code = run_cli("check", life_file)
            self.assertIn("W225", normalize_newlines(stdout))
            self.assertIn("Hint", normalize_newlines(stdout))
            self.assertIn("adopt", normalize_newlines(stdout))

    def test_check_ignore_comma_separated(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent id:P001\n"
                    "[ ] T Child parent:P001 est:90m\n"
                )
            stdout, stderr, code = run_cli("check", life_file, "--ignore", "W225,W222")
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W225", normalize_newlines(stdout))
            self.assertNotIn("W222", normalize_newlines(stdout))


class LifeTxtAssignTextTests(unittest.TestCase):
    def test_assign_text_selects_by_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login_bug id:T001 assignee:alice\n")
            stdout, stderr, code = run_cli("assign", life_file, "--text", "Fix_login", "--to", "bob")
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("assignee:bob", content)
            self.assertNotIn("assignee:alice", content)

    def test_assign_text_no_match_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:T001\n")
            stdout, stderr, code = run_cli("assign", life_file, "--text", "nonexistent", "--to", "bob")
            self.assertEqual(1, code)
            self.assertIn("nonexistent", stderr)

    def test_assign_requires_id_or_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:T001\n")
            stdout, stderr, code = run_cli("assign", life_file, "--to", "bob")
            self.assertEqual(1, code)


class LifeTxtHealthExtTests(unittest.TestCase):
    def test_health_jsonl_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Old_task due:2020-01-01\n")
            stdout, stderr, code = run_cli("health", life_file, "--format", "jsonl")
            self.assertEqual(1, code)
            lines = [l for l in normalize_newlines(stdout).splitlines() if l.strip()]
            self.assertGreater(len(lines), 0)
            records = [json.loads(l) for l in lines]
            codes = [r["code"] for r in records]
            self.assertIn("W303", codes)

    def test_health_type_filter_restricts_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(
                    "[ ] T Old_task due:2020-01-01\n"
                    "[ ] H Daily_habit repeat:daily\n"
                )
            stdout, stderr, code = run_cli("health", life_file, "--type", "H")
            self.assertEqual(1, code)
            normalized = normalize_newlines(stdout)
            self.assertIn("W302", normalized)
            self.assertNotIn("W303", normalized)

    def test_health_w301_suppressed_for_deferred_items(self):
        import datetime as _dt
        old_date = (_dt.date.today() - _dt.timedelta(days=60)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[>] T Deferred_task updated:%s\n" % old_date)
            stdout, stderr, code = run_cli("health", life_file, "--since", "30")
            self.assertEqual(0, code)
            self.assertNotIn("W301", normalize_newlines(stdout))


class LifeTxtReviewJsonlTests(unittest.TestCase):
    def test_review_jsonl_returns_single_line_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[x] T Done_task done:2026-06-01\n")
            stdout, stderr, code = run_cli("review", life_file, "--format", "jsonl")
            self.assertEqual(0, code, stderr)
            lines = [l for l in normalize_newlines(stdout).splitlines() if l.strip()]
            self.assertEqual(1, len(lines))
            record = json.loads(lines[0])
            self.assertIn("range", record)
            self.assertIn("completed_tasks", record)

    def test_review_jsonl_no_pretty_indentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Open_task\n")
            stdout, stderr, code = run_cli("review", life_file, "--format", "jsonl")
            self.assertEqual(0, code, stderr)
            output = normalize_newlines(stdout).strip()
            self.assertNotIn("\n  ", output)


class LifeTxtArchiveOrphanTests(unittest.TestCase):
    SOURCE_WITH_CHILDREN = (
        "[x] T Parent_done id:P001 done:2026-01-01\n"
        "[ ] T Child_open id:C001 parent:P001\n"
        "[ ] T Unrelated id:U001\n"
    )

    def test_archive_orphan_block_refuses_when_open_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE_WITH_CHILDREN)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--orphan-children", "block"
            )
            self.assertEqual(1, code)
            normalized = normalize_newlines(stdout)
            self.assertIn("P001", normalized)
            self.assertFalse(os.path.exists(dest))

    def test_archive_orphan_adopt_moves_children_as_canceled(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE_WITH_CHILDREN)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--orphan-children", "adopt"
            )
            self.assertEqual(0, code, stderr)
            archive_content = open(dest, encoding="utf-8").read()
            self.assertIn("Parent_done", archive_content)
            self.assertIn("Child_open", archive_content)
            self.assertIn("[-]", archive_content)
            src_content = open(src, encoding="utf-8").read()
            self.assertNotIn("Child_open", src_content)

    def test_archive_orphan_promote_archives_parent_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE_WITH_CHILDREN)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--orphan-children", "promote"
            )
            self.assertEqual(0, code, stderr)
            archive_content = open(dest, encoding="utf-8").read()
            self.assertIn("Parent_done", archive_content)
            self.assertNotIn("Child_open", archive_content)
            src_content = open(src, encoding="utf-8").read()
            self.assertIn("Child_open", src_content)
            self.assertNotIn("parent:P001", src_content)

    def test_archive_orphan_dry_run_block_shows_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE_WITH_CHILDREN)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--dry-run"
            )
            self.assertEqual(1, code)
            self.assertIn("P001", normalize_newlines(stdout))
            self.assertFalse(os.path.exists(dest))

    def test_archive_no_orphan_when_children_done(self):
        content = (
            "[x] T Parent_done id:P001 done:2026-01-01\n"
            "[x] T Child_done id:C001 parent:P001 done:2026-01-02\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes"
            )
            self.assertEqual(0, code, stderr)
            archive_content = open(dest, encoding="utf-8").read()
            self.assertIn("Parent_done", archive_content)
            self.assertIn("Child_done", archive_content)


class LifeTxtArchiveExternalRefsTests(unittest.TestCase):
    def test_archive_warns_on_external_ref_by_default(self):
        content = (
            "[x] T Done_task id:T001 done:2026-01-01\n"
            "[ ] T Open_blocker depends_on:T001\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes"
            )
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("Warning", out)
            self.assertIn("T001", out)
            archive_content = open(dest, encoding="utf-8").read()
            self.assertIn("Done_task", archive_content)

    def test_archive_block_on_external_refs_exits_nonzero(self):
        content = (
            "[x] T Done_task id:T001 done:2026-01-01\n"
            "[ ] T Open_blocker depends_on:T001\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--block-on-external-refs"
            )
            self.assertEqual(1, code)
            out = normalize_newlines(stdout)
            self.assertIn("Blocked", out)
            self.assertFalse(os.path.exists(dest))

    def test_archive_no_external_refs_no_warning(self):
        content = (
            "[x] T Done_task id:T001 done:2026-01-01\n"
            "[ ] T Unrelated_task id:T002\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes"
            )
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertNotIn("Warning", out)

    def test_archive_dry_run_shows_external_ref_warning(self):
        content = (
            "[x] T Done_task id:T001 done:2026-01-01\n"
            "[ ] T Ref_task depends_on:T001\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--dry-run"
            )
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("Warning", out)
            self.assertIn("T001", out)
            self.assertIn("dry run", out)
            self.assertFalse(os.path.exists(dest))


class LifeTxtCleanupArchiveHintTests(unittest.TestCase):
    def test_cleanup_suggests_archive_for_many_old_done_items(self):
        import datetime as _dt
        old_date = (_dt.date.today() - _dt.timedelta(days=100)).isoformat()
        lines = ""
        for i in range(12):
            lines += "[x] T Old_task_%d id:T%03d done:%s\n" % (i, i, old_date)
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(lines)
            stdout, stderr, code = run_cli("cleanup", life_file)
            self.assertEqual(0, code, stderr)
            normalized = normalize_newlines(stdout)
            self.assertIn("archive", normalized.lower())

    def test_cleanup_no_archive_hint_for_few_old_items(self):
        import datetime as _dt
        old_date = (_dt.date.today() - _dt.timedelta(days=100)).isoformat()
        lines = "[x] T Old_task id:T001 done:%s\n" % old_date
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write(lines)
            stdout, stderr, code = run_cli("cleanup", life_file)
            self.assertEqual(0, code, stderr)
            normalized = normalize_newlines(stdout)
            self.assertNotIn("archive", normalized.lower())


class LifeTxtAssignFromUserEdgeCaseTests(unittest.TestCase):
    def test_assign_from_user_empty_string_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task id:T001\n")
            stdout, stderr, code = run_cli(
                "assign", life_file, "T001", "--to", "bob", "--notify", "--from-user", ""
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("sender:self", content)

    def test_assign_from_user_without_notify_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Task id:T001\n")
            stdout, stderr, code = run_cli(
                "assign", life_file, "T001", "--to", "bob", "--from-user", "alice"
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertNotIn("sender:", content)
            self.assertIn("assignee:bob", content)


class LifeTxtReviewJournalBodyTests(unittest.TestCase):
    def _make_file(self, tmp, content):
        life_file = os.path.join(tmp, "life.txt")
        with open(life_file, "w", encoding="utf-8") as f:
            f.write(content)
        return life_file

    def test_review_journal_body_shown_in_text_output(self):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        content = '[ ] J Morning_notes on:%s body:"Had_a_great_day"\n' % today
        with tempfile.TemporaryDirectory() as tmp:
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week")
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("Morning_notes", out)
            self.assertIn("Had_a_great_day", out)

    def test_review_journal_no_body_still_shows_title(self):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        content = "[ ] J Evening_notes on:%s\n" % today
        with tempfile.TemporaryDirectory() as tmp:
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week")
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("Evening_notes", out)

    def test_review_journal_body_truncated_at_200_chars(self):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        long_body = "x" * 300
        content = '[ ] J Long_entry on:%s body:"%s"\n' % (today, long_body)
        with tempfile.TemporaryDirectory() as tmp:
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week")
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("x" * 200, out)
            self.assertNotIn("x" * 201, out)

    def test_review_journal_body_in_json_output(self):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        content = '[ ] J Morning_notes on:%s body:"Had_a_great_day"\n' % today
        with tempfile.TemporaryDirectory() as tmp:
            life_file = self._make_file(tmp, content)
            stdout, stderr, code = run_cli("review", life_file, "--week", "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(1, data["journals"])
            self.assertIn("journal_entries", data)
            entries = data["journal_entries"]
            self.assertEqual(1, len(entries))
            self.assertEqual("Morning_notes", entries[0]["title"])
            self.assertIn("Had_a_great_day", entries[0]["excerpt"])


class LifeTxtArchivePreserveStructureTests(unittest.TestCase):
    SOURCE = (
        "# Tasks section\n"
        "[x] T Done_task id:T001 done:2026-01-01\n"
        "\n"
        "# Notes section\n"
        "[ ] T Open_task id:T002\n"
    )

    def test_preserve_structure_keeps_comments_in_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--preserve-structure"
            )
            self.assertEqual(0, code, stderr)
            content = open(src, encoding="utf-8").read()
            self.assertIn("# Tasks section", content)
            self.assertIn("# Notes section", content)
            self.assertNotIn("Done_task", content)
            self.assertIn("Open_task", content)

    def test_preserve_structure_keeps_comments_in_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--preserve-structure"
            )
            self.assertEqual(0, code, stderr)
            archive_content = open(dest, encoding="utf-8").read()
            self.assertIn("# Tasks section", archive_content)
            self.assertIn("Done_task", archive_content)

    def test_preserve_structure_keeps_blank_lines_in_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes", "--preserve-structure"
            )
            self.assertEqual(0, code, stderr)
            content = open(src, encoding="utf-8").read()
            self.assertIn("\n\n", content)

    def test_no_preserve_structure_omits_comments_from_archive_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "life.txt")
            dest = os.path.join(tmp, "archive.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli(
                "archive", src, "--dest", dest, "--yes"
            )
            self.assertEqual(0, code, stderr)
            archive_content = open(dest, encoding="utf-8").read()
            self.assertNotIn("# Tasks section", archive_content)
            self.assertIn("Done_task", archive_content)


class LifeTxtAssignFromUserTests(unittest.TestCase):
    def test_assign_from_user_overrides_sender_in_notify(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Review_PR id:T001\n")
            stdout, stderr, code = run_cli(
                "assign", life_file, "T001", "--to", "bob",
                "--notify", "--from-user", "alice",
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("sender:alice", content)
            self.assertIn("recipient:bob", content)

    def test_assign_without_from_user_uses_default_sender(self):
        with tempfile.TemporaryDirectory() as tmp:
            life_file = os.path.join(tmp, "life.txt")
            with open(life_file, "w", encoding="utf-8") as f:
                f.write("[ ] T Review_PR id:T001\n")
            stdout, stderr, code = run_cli(
                "assign", life_file, "T001", "--to", "bob", "--notify"
            )
            self.assertEqual(0, code, stderr)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("sender:self", content)
            self.assertIn("recipient:bob", content)


class LifeTxtLinksMermaidTests(unittest.TestCase):
    TEXT = (
        "[ ] T Root id:root_001\n"
        "[x] T Done id:done_001\n"
        "[ ] T Child id:child_001 depends_on:root_001 parent:done_001\n"
    )

    def test_mermaid_starts_with_graph_lr(self):
        stdout, stderr, code = run_cli("links", "--format", "mermaid", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        self.assertTrue(normalize_newlines(stdout).startswith("graph LR"))

    def test_mermaid_contains_node_ids(self):
        stdout, stderr, code = run_cli("links", "--format", "mermaid", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("root_001", out)
        self.assertIn("child_001", out)

    def test_mermaid_contains_relation_edges(self):
        stdout, stderr, code = run_cli("links", "--format", "mermaid", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("depends_on", out)
        self.assertIn("-->", out)

    def test_mermaid_done_node_has_class(self):
        stdout, stderr, code = run_cli("links", "--format", "mermaid", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn(":::done", out)
        self.assertIn("classDef done", out)

    def test_mermaid_no_links_still_outputs_graph(self):
        stdout, stderr, code = run_cli("links", "--format", "mermaid", input_text="[ ] T Solo\n")
        self.assertEqual(0, code, stderr)
        self.assertIn("graph LR", normalize_newlines(stdout))


class LifeTxtLinksDotTests(unittest.TestCase):
    TEXT = (
        "[ ] T Task_A id:ta depends_on:tb\n"
        "[x] T Task_B id:tb\n"
    )

    def test_dot_starts_with_digraph(self):
        stdout, stderr, code = run_cli("links", "--format", "dot", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        self.assertIn("digraph links", normalize_newlines(stdout))

    def test_dot_contains_arrow_edges(self):
        stdout, stderr, code = run_cli("links", "--format", "dot", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("->", out)
        self.assertIn("depends_on", out)

    def test_dot_done_node_has_dashed_style(self):
        stdout, stderr, code = run_cli("links", "--format", "dot", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        self.assertIn("style=dashed", normalize_newlines(stdout))

    def test_dot_no_links_outputs_empty_digraph(self):
        stdout, stderr, code = run_cli("links", "--format", "dot", input_text="[ ] T Solo\n")
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("digraph links", out)
        self.assertNotIn("->", out)


class LifeTxtW219Tests(unittest.TestCase):
    def test_w219_no_warning_for_valid_interval(self):
        _items, diags = parse_text("[ ] H Meditate repeat:daily interval:2\n")
        self.assertFalse(any(d.code == "W219" for d in diags))

    def test_w219_fires_for_non_integer_interval(self):
        _items, diags = parse_text("[ ] H Meditate repeat:daily interval:every_other\n")
        self.assertTrue(any(d.code == "W219" for d in diags))

    def test_w219_no_warning_for_valid_count(self):
        _items, diags = parse_text("[ ] H Meditate repeat:weekly count:5\n")
        self.assertFalse(any(d.code == "W219" for d in diags))

    def test_w219_fires_for_non_integer_count(self):
        _items, diags = parse_text("[ ] H Meditate repeat:weekly count:five\n")
        self.assertTrue(any(d.code == "W219" for d in diags))


class LifeTxtReviewEdgeCaseTests(unittest.TestCase):
    def _make_file(self, tmp, content):
        path = os.path.join(tmp, "life.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_review_custom_from_to_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "[x] T Task_in_range done:2026-03-15 id:T001\n"
                "[x] T Task_out_of_range done:2026-01-10 id:T002\n"
            )
            path = self._make_file(tmp, content)
            stdout, stderr, code = run_cli(
                "review", path,
                "--from", "2026-03-01", "--to", "2026-03-31",
                "--format", "json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(1, data["completed_tasks"])

    def test_review_empty_period_returns_zero_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "[x] T Old_task done:2025-01-01 id:T001\n"
            path = self._make_file(tmp, content)
            stdout, stderr, code = run_cli(
                "review", path,
                "--from", "2026-05-01", "--to", "2026-05-31",
                "--format", "json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(0, data["completed_tasks"])

    def test_review_range_in_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._make_file(tmp, "[x] T Task done:2026-03-15 id:T001\n")
            stdout, stderr, code = run_cli(
                "review", path,
                "--from", "2026-03-01", "--to", "2026-03-31",
                "--format", "json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIn("range", data)
            self.assertIn("2026-03-01", str(data["range"]))
            self.assertIn("2026-03-31", str(data["range"]))

    def test_review_multi_file_aggregates_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "a.txt")
            p2 = os.path.join(tmp, "b.txt")
            with open(p1, "w", encoding="utf-8") as f:
                f.write("[x] T Task_A done:2026-03-10 id:A001\n")
            with open(p2, "w", encoding="utf-8") as f:
                f.write("[x] T Task_B done:2026-03-12 id:B001\n")
            stdout, stderr, code = run_cli(
                "review", p1, p2,
                "--from", "2026-03-01", "--to", "2026-03-31",
                "--format", "json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(2, data["completed_tasks"])


class LifeTxtCheckIgnoreEdgeCaseTests(unittest.TestCase):
    def test_check_ignore_unknown_code_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Normal_task\n")
            stdout, stderr, code = run_cli("check", path, "--ignore", "W999")
            self.assertEqual(0, code, stderr)

    def test_check_ignore_takes_precedence_over_code_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task est:90m\n")
            stdout, stderr, code = run_cli(
                "check", path, "--code", "W222", "--ignore", "W222"
            )
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W222", normalize_newlines(stdout))

    def test_check_ignore_suppresses_in_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task est:90m\n")
            stdout, stderr, code = run_cli(
                "check", path, "--ignore", "W222", "--format", "json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIsInstance(data, list)
            codes = [d["code"] for d in data]
            self.assertNotIn("W222", codes)


class LifeTxtWhoCommandTests(unittest.TestCase):
    SOURCE = (
        "[ ] S Alice person:alice state:focus from:2026-06-27T09:00\n"
        "[ ] S Bob person:bob state:away from:2026-06-26T08:00\n"
        "[ ] S Alice person:alice state:lunch from:2026-06-27T12:00\n"
    )

    def test_who_shows_latest_active_per_person(self):
        stdout, stderr, code = run_cli("who", input_text=self.SOURCE)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("alice", out)
        self.assertIn("bob", out)
        self.assertIn("lunch", out)
        self.assertNotIn("focus", out)

    def test_who_json_returns_list(self):
        stdout, stderr, code = run_cli("who", "--format", "json", input_text=self.SOURCE)
        self.assertEqual(0, code, stderr)
        data = json.loads(stdout)
        self.assertIsInstance(data, list)
        persons = [r["person"] for r in data]
        self.assertIn("alice", persons)
        self.assertIn("bob", persons)

    def test_who_empty_when_no_s_items(self):
        stdout, stderr, code = run_cli("who", input_text="[ ] T Task\n")
        self.assertEqual(0, code, stderr)
        self.assertIn("No active", normalize_newlines(stdout))

    def test_who_excludes_finished_s_records(self):
        source = (
            "[ ] S Alice person:alice state:focus from:2026-06-27T09:00 to:2026-06-27T10:00\n"
        )
        stdout, stderr, code = run_cli("who", input_text=source)
        self.assertEqual(0, code, stderr)
        self.assertIn("No active", normalize_newlines(stdout))


class LifeTxtSearchCommandTests(unittest.TestCase):
    SOURCE = (
        "[ ] T Fix_login_bug project:auth\n"
        "[x] T Write_unit_tests project:testing\n"
        "[N] N Important_note body:login_details_here\n"
        "[ ] T Deploy_service note:urgent\n"
    )

    def test_search_substring_match_in_title(self):
        stdout, stderr, code = run_cli("search", "Fix", input_text=self.SOURCE)
        self.assertEqual(0, code, stderr)
        self.assertIn("Fix_login_bug", normalize_newlines(stdout))
        self.assertNotIn("Write_unit_tests", normalize_newlines(stdout))

    def test_search_no_match_exits_nonzero(self):
        stdout, stderr, code = run_cli("search", "zzz_nonexistent", input_text=self.SOURCE)
        self.assertEqual(1, code)

    def test_search_regex_flag(self):
        stdout, stderr, code = run_cli(
            "search", "^fix.*bug$", "--regex", input_text=self.SOURCE
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("Fix_login_bug", normalize_newlines(stdout))

    def test_search_in_title_field(self):
        stdout, stderr, code = run_cli(
            "search", "login", "--in", "title", input_text=self.SOURCE
        )
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("Fix_login_bug", out)
        self.assertNotIn("Important_note", out)

    def test_search_json_output_schema(self):
        stdout, stderr, code = run_cli(
            "search", "Fix", "--format", "json", input_text=self.SOURCE
        )
        self.assertEqual(0, code, stderr)
        data = json.loads(stdout)
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 1)
        rec = data[0]
        self.assertIn("title", rec)
        self.assertIn("match_field", rec)
        self.assertIn("status", rec)

    def test_search_life_format_outputs_source_line(self):
        stdout, stderr, code = run_cli(
            "search", "login", "--format", "life", input_text=self.SOURCE
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("Fix_login_bug", normalize_newlines(stdout))


class LifeTxtHealthEdgeCaseTests(unittest.TestCase):
    def test_health_ignore_suppresses_w303(self):
        import datetime as dt
        today = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Overdue due:2020-01-01 updated:%s\n" % today)
            stdout, stderr, code = run_cli("health", path, "--ignore", "W303")
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W303", normalize_newlines(stdout))

    def test_health_w301_not_fired_for_recently_updated_task(self):
        import datetime as dt
        today = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Ongoing updated:%s\n" % today)
            stdout, stderr, code = run_cli("health", path)
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W301", normalize_newlines(stdout))

    def test_health_w302_not_fired_for_recently_completed_habit(self):
        import datetime as dt
        today = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] H Morning_run\n[x] H Morning_run done:%s\n" % today)
            stdout, stderr, code = run_cli("health", path)
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W302", normalize_newlines(stdout))


class LifeTxtQuickTests(unittest.TestCase):
    def test_quick_creates_task_with_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            stdout, stderr, code = run_cli("quick", "Buy_groceries", "--append", path)
            self.assertEqual(0, code, stderr)
            content = open(path, encoding="utf-8").read()
            self.assertIn("Buy_groceries", content)
            self.assertIn("[ ] T", content)

    def test_quick_default_type_is_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            run_cli("quick", "Task_title", "--append", path)
            content = open(path, encoding="utf-8").read()
            self.assertIn("[ ] T Task_title", content)

    def test_quick_explicit_type_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            run_cli("quick", "Team_meeting", "--type", "E", "--append", path)
            content = open(path, encoding="utf-8").read()
            self.assertIn("[ ] E Team_meeting", content)

    def test_quick_appends_to_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Existing_task\n")
            run_cli("quick", "New_task", "--append", path)
            content = open(path, encoding="utf-8").read()
            self.assertIn("Existing_task", content)
            self.assertIn("New_task", content)

    def test_quick_generated_line_passes_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            run_cli("quick", "Valid_title", "--append", path)
            stdout, stderr, code = run_cli("check", path)
            self.assertEqual(0, code, stderr)


class LifeTxtCleanupIgnoreTests(unittest.TestCase):
    def test_cleanup_ignore_suppresses_specific_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent_task id:P001\n"
                    "[ ] T Child_task parent:P001\n"
                )
            stdout, stderr, code = run_cli("cleanup", path, "--ignore", "W225")
            self.assertEqual(0, code, stderr)

    def test_cleanup_json_schema_has_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_without_project\n")
            stdout, stderr, code = run_cli("cleanup", path, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertIsInstance(data, list)
            if data:
                rec = data[0]
                self.assertIn("priority", rec)
                self.assertIn("check", rec)
                self.assertIn("count", rec)
                self.assertIn("action", rec)

    def test_cleanup_ignore_comma_separated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "[x] T Parent id:P001\n"
                    "[ ] T Child parent:P001 est:90m\n"
                )
            stdout, stderr, code = run_cli("cleanup", path, "--ignore", "W225,W222")
            self.assertEqual(0, code, stderr)


class LifeTxtUndoEdgeCaseTests(unittest.TestCase):
    def test_undo_creates_snapshot_on_quick_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            cfg_path = os.path.join(tmp, "config.toml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write('{"undo": {"dir": "%s"}}' % os.path.join(tmp, "undo").replace("\\", "/"))
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Old_task\n")
            run_cli("quick", "New_task", "--append", path, "--config", cfg_path)
            stdout, stderr, code = run_cli("undo", path, "--list", "--config", cfg_path)
            self.assertEqual(0, code, stderr)
            self.assertIn("quick", normalize_newlines(stdout))

    def test_undo_restores_previous_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            cfg_path = os.path.join(tmp, "config.toml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write('{"undo": {"dir": "%s"}}' % os.path.join(tmp, "undo").replace("\\", "/"))
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Original_task\n")
            run_cli("quick", "Added_task", "--append", path, "--config", cfg_path)
            run_cli("undo", path, "--config", cfg_path)
            content = open(path, encoding="utf-8").read()
            self.assertIn("Original_task", content)
            self.assertNotIn("Added_task", content)

    def test_undo_creates_snapshot_on_done_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            cfg_path = os.path.join(tmp, "config.toml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write('{"undo": {"dir": "%s"}}' % os.path.join(tmp, "undo").replace("\\", "/"))
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Buy_milk id:t001\n")
            run_cli("done", path, "t001", "--config", cfg_path)
            stdout, stderr, code = run_cli("undo", path, "--list", "--config", cfg_path)
            self.assertEqual(0, code, stderr)
            self.assertIn("done", normalize_newlines(stdout))


class LifeTxtHealthW304Tests(unittest.TestCase):
    def test_w304_fires_when_assignee_has_no_s_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_bug assignee:alice\n")
            stdout, stderr, code = run_cli("health", path)
            self.assertIn("W304", normalize_newlines(stdout))

    def test_w304_not_fired_when_assignee_has_recent_s_record(self):
        import datetime as dt
        today = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "[ ] T Fix_bug assignee:alice updated:%s\n"
                    "[ ] S Alice person:alice state:active from:%sT09:00\n" % (today, today)
                )
            stdout, stderr, code = run_cli("health", path)
            self.assertNotIn("W304", normalize_newlines(stdout))


class LifeTxtLinksScopeTests(unittest.TestCase):
    TEXT = (
        "[ ] T Root id:root\n"
        "[ ] T Child id:child parent:root\n"
        "[ ] T Unrelated id:other\n"
    )

    def test_links_id_scope_mermaid_limits_nodes(self):
        stdout, stderr, code = run_cli(
            "links", "--id", "root", "--direction", "incoming",
            "--format", "mermaid", input_text=self.TEXT
        )
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("child", out)
        self.assertIn("root", out)
        self.assertNotIn("other", out)

    def test_links_id_scope_dot_limits_nodes(self):
        stdout, stderr, code = run_cli(
            "links", "--id", "root", "--direction", "incoming",
            "--format", "dot", input_text=self.TEXT
        )
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("child", out)
        self.assertIn("root", out)
        self.assertNotIn("other", out)


class LifeTxtDependencyEdgeCaseTests(unittest.TestCase):
    def test_missing_depends_on_id_fires_w215(self):
        text = "[ ] T Task depends_on:nonexistent_id\n"
        _items, diags = parse_text(text)
        self.assertTrue(any(d.code == "W215" for d in diags))

    def test_duplicate_depends_on_blocks_pair_allowed(self):
        text = (
            "[ ] T Task_A id:A depends_on:B\n"
            "[ ] T Task_B id:B blocks:A\n"
        )
        _items, diags = parse_text(text)
        errors = [d for d in diags if d.severity == "error"]
        self.assertEqual([], errors)

    def test_self_reference_fires_w216(self):
        text = "[ ] T Task id:t001 depends_on:t001\n"
        _items, diags = parse_text(text)
        self.assertTrue(any(d.code == "W216" for d in diags))

    def test_ambiguous_id_fires_w218(self):
        text = (
            "[ ] T Task_A id:dup\n"
            "[ ] T Task_B id:dup\n"
            "[ ] T Task_C depends_on:dup\n"
        )
        _items, diags = parse_text(text)
        self.assertTrue(any(d.code == "W218" for d in diags))


class LifeTxtDoneTests(unittest.TestCase):
    def test_done_marks_item_done_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_login id:fix001\n")
            stdout, stderr, code = run_cli("done", path, "fix001")
            self.assertEqual(0, code, stderr)
            content = open(path, encoding="utf-8").read()
            self.assertIn("[x]", content)
            self.assertIn("done:", content)

    def test_done_marks_item_by_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T First_task\n[ ] T Second_task\n")
            stdout, stderr, code = run_cli("done", path, "--line", "2")
            self.assertEqual(0, code, stderr)
            content = open(path, encoding="utf-8").read()
            lines = content.splitlines()
            self.assertIn("[x]", lines[1])
            self.assertIn("[ ]", lines[0])

    def test_done_marks_item_by_title_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Login_bug_fix\n[ ] T Deploy_service\n")
            stdout, stderr, code = run_cli("done", path, "--text", "Login_bug")
            self.assertEqual(0, code, stderr)
            content = open(path, encoding="utf-8").read()
            self.assertIn("[x] T Login_bug_fix", content)
            self.assertIn("[ ] T Deploy_service", content)

    def test_done_appends_done_date_today(self):
        import datetime
        today = datetime.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Buy_milk id:m001\n")
            run_cli("done", path, "m001")
            content = open(path, encoding="utf-8").read()
            self.assertIn("done:%s" % today, content)


class LifeTxtW222Tests(unittest.TestCase):
    def test_w222_fires_for_90m_not_compact(self):
        items, diags = parse_text("[ ] T Task est:90m\n")
        codes = [d.code for d in diags]
        self.assertIn("W222", codes)

    def test_w222_fires_for_bare_integer(self):
        items, diags = parse_text("[ ] T Task est:90\n")
        codes = [d.code for d in diags]
        self.assertIn("W222", codes)

    def test_w222_not_fired_for_compact_form_1h30m(self):
        items, diags = parse_text("[ ] T Task est:1h30m\n")
        codes = [d.code for d in diags]
        self.assertNotIn("W222", codes)

    def test_w222_message_suggests_compact_form(self):
        items, diags = parse_text("[ ] T Task est:90m\n")
        w222 = next(d for d in diags if d.code == "W222")
        self.assertIn("1h30m", w222.message)


class LifeTxtDirectiveParserTests(unittest.TestCase):
    def test_directives_at_top_are_parsed(self):
        from lifetxt.parser import parse_directives
        text = "#! self: alice\n#! project: myproject\n[ ] T Task\n"
        d = parse_directives(text)
        self.assertEqual("alice", d.get("self"))
        self.assertEqual("myproject", d.get("project"))

    def test_unknown_directive_key_returned_without_error(self):
        from lifetxt.parser import parse_directives
        text = "#! unknown_key: value\n#! self: alice\n"
        d = parse_directives(text)
        self.assertEqual("value", d.get("unknown_key"))
        self.assertEqual("alice", d.get("self"))

    def test_directive_after_item_line_is_not_parsed(self):
        from lifetxt.parser import parse_directives
        text = "[ ] T Task\n#! self: alice\n"
        d = parse_directives(text)
        self.assertEqual(0, len(d))

    def test_directive_block_ends_at_blank_line(self):
        from lifetxt.parser import parse_directives
        text = "#! self: alice\n\n#! project: late\n"
        d = parse_directives(text)
        self.assertIn("self", d)
        self.assertNotIn("project", d)


class LifeTxtReviewMoodTests(unittest.TestCase):
    SOURCE = (
        "[x] J Morning_entry mood:happy done:2026-06-01\n"
        "[x] J Afternoon_entry mood:sad done:2026-06-02\n"
        "[x] J Evening_entry mood:happy done:2026-06-03\n"
    )

    def test_review_mood_trend_sorted_chronologically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.SOURCE)
            stdout, stderr, code = run_cli(
                "review", path, "--format", "json",
                "--from", "2026-06-01", "--to", "2026-06-30"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            trend = data.get("mood_trend", [])
            self.assertEqual(3, len(trend))
            dates = [e["date"] for e in trend]
            self.assertEqual(sorted(dates), dates)

    def test_review_elapsed_by_project_returns_formatted_string(self):
        text = "[x] T Work_task project:backend elapsed:90m done:2026-06-01\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            stdout, stderr, code = run_cli(
                "review", path, "--format", "json",
                "--from", "2026-06-01", "--to", "2026-06-30"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            elapsed = data.get("elapsed_by_project", {})
            self.assertIn("backend", elapsed)
            val = elapsed["backend"]
            self.assertIsInstance(val, str)
            self.assertIn("h", val)


class LifeTxtArchiveMultiFileRefsTests(unittest.TestCase):
    def test_archive_cross_file_warning_shows_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_path = os.path.join(tmp, "main.life.txt")
            ref_path = os.path.join(tmp, "refs.life.txt")
            archive_path = os.path.join(tmp, "archive.life.txt")
            with open(main_path, "w", encoding="utf-8") as f:
                f.write("[x] T Done_item id:d001\n")
            with open(ref_path, "w", encoding="utf-8") as f:
                f.write("[ ] T Depends_on_done depends_on:d001\n")
            stdout, stderr, code = run_cli(
                "archive", main_path, ref_path,
                "--dest", archive_path,
                "--dry-run", "--yes"
            )
            out = normalize_newlines(stdout)
            self.assertIn("d001", out)
            self.assertIn("depends_on", out)

    def test_archive_block_cross_file_ref_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_path = os.path.join(tmp, "main.life.txt")
            ref_path = os.path.join(tmp, "refs.life.txt")
            archive_path = os.path.join(tmp, "archive.life.txt")
            with open(main_path, "w", encoding="utf-8") as f:
                f.write("[x] T Done_item id:d001\n")
            with open(ref_path, "w", encoding="utf-8") as f:
                f.write("[ ] T Depends_on_done depends_on:d001\n")
            stdout, stderr, code = run_cli(
                "archive", main_path, ref_path,
                "--dest", archive_path,
                "--dry-run", "--yes", "--block-on-external-refs"
            )
            self.assertEqual(1, code)
            self.assertIn("Blocked", normalize_newlines(stdout))


class LifeTxtW219ExtraTests(unittest.TestCase):
    def test_w219_ignore_suppresses_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] R Habit repeat:daily interval:abc\n")
            stdout, stderr, code = run_cli("check", path, "--ignore", "W219")
            self.assertEqual(0, code, stderr)
            self.assertNotIn("W219", normalize_newlines(stdout))

    def test_w219_no_false_positive_for_leading_zero_interval(self):
        items, diags = parse_text("[ ] R Habit repeat:daily interval:02\n")
        codes = [d.code for d in diags]
        self.assertNotIn("W219", codes)

    def test_w219_no_false_positive_for_leading_zero_count(self):
        items, diags = parse_text("[ ] R Habit repeat:daily count:05\n")
        codes = [d.code for d in diags]
        self.assertNotIn("W219", codes)


class LifeTxtQuickExtraTests(unittest.TestCase):
    def test_quick_relative_due_date_resolved(self):
        import datetime
        today = datetime.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            run_cli("quick", "Urgent_task", "--due", "today", "--append", path)
            content = open(path, encoding="utf-8").read()
            self.assertIn("due:%s" % today, content)

    def test_quick_validation_error_exits_nonzero_for_bad_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            stdout, stderr, code = run_cli(
                "quick", "Bad_item", "--type", "INVALID_TYPE", "--append", path
            )
            self.assertNotEqual(0, code)


class LifeTxtSummaryStdinTest(unittest.TestCase):
    def test_summary_reads_from_stdin(self):
        text = (
            "[ ] T Open_task\n"
            "[x] T Done_task\n"
        )
        stdout, stderr, code = run_cli("summary", "--format", "json", input_text=text)
        self.assertEqual(0, code, stderr)
        data = json.loads(stdout)
        self.assertIsInstance(data, dict)
        self.assertIn("item_count", data)
        self.assertEqual(2, data["item_count"])
        self.assertIn("status_counts", data)


class LifeTxtCheckIgnoreExtraTests(unittest.TestCase):
    def test_check_ignore_comma_separated_suppresses_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[x] T Old_task\n[ ] T Task_without_id est:90m\n")
            stdout, stderr, code = run_cli("check", path, "--ignore", "W103,W222")
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertNotIn("W103", out)
            self.assertNotIn("W222", out)

    def test_check_ignore_repeated_flag_suppresses_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[x] T Old_task\n[ ] T Task est:90m\n")
            stdout, stderr, code = run_cli("check", path, "--ignore", "W103", "--ignore", "W222")
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertNotIn("W103", out)
            self.assertNotIn("W222", out)

    def test_check_ignore_unknown_code_does_not_crash(self):
        text = "[ ] T Normal_task\n"
        stdout, stderr, code = run_cli("check", "--ignore", "W9999", input_text=text)
        self.assertEqual(0, code, stderr)


class LifeTxtUndoEvictionTests(unittest.TestCase):
    def test_undo_keep_evicts_oldest_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            cfg_path = os.path.join(tmp, "config.json")
            undo_dir = os.path.join(tmp, "undo")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write('{"undo": {"dir": "%s", "keep": 2}}' % undo_dir.replace("\\", "/"))
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_v1\n")
            for i in range(3):
                run_cli("quick", "Task_v%d" % (i + 2), "--append", path, "--config", cfg_path)
            entries = sorted(os.listdir(os.path.join(undo_dir, "life.txt")))
            self.assertLessEqual(len(entries), 2)

    def test_backup_auto_creates_file_in_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            cfg_path = os.path.join(tmp, "config.json")
            backup_dir = os.path.join(tmp, "backup")
            undo_dir = os.path.join(tmp, "undo")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(
                    '{"undo": {"dir": "%s"}, "backup": {"auto": true, "dir": "%s"}}'
                    % (undo_dir.replace("\\", "/"), backup_dir.replace("\\", "/"))
                )
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Initial_task\n")
            run_cli("quick", "New_task", "--append", path, "--config", cfg_path)
            backup_subdir = os.path.join(backup_dir, "life.txt")
            self.assertTrue(os.path.isdir(backup_subdir), "backup dir should exist")
            entries = os.listdir(backup_subdir)
            self.assertGreater(len(entries), 0, "backup should contain at least one file")


class LifeTxtLinksSpecialCharsTests(unittest.TestCase):
    TEXT = (
        "[ ] T Item-with-dash id:dash-001\n"
        "[ ] T Another_item id:other depends_on:dash-001\n"
    )

    def test_links_mermaid_sanitizes_dash_in_node_id(self):
        stdout, stderr, code = run_cli("links", "--format", "mermaid", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn("dash_001", out)
        self.assertIn("graph LR", out)

    def test_links_dot_quotes_dash_id(self):
        stdout, stderr, code = run_cli("links", "--format", "dot", input_text=self.TEXT)
        self.assertEqual(0, code, stderr)
        out = normalize_newlines(stdout)
        self.assertIn('"dash-001"', out)


class LifeTxtWhoMultiFileTests(unittest.TestCase):
    def test_who_aggregates_across_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            file1 = os.path.join(tmp, "alice.life.txt")
            file2 = os.path.join(tmp, "bob.life.txt")
            with open(file1, "w", encoding="utf-8") as f:
                f.write("[ ] S Alice person:alice state:coding from:2026-06-27T09:00\n")
            with open(file2, "w", encoding="utf-8") as f:
                f.write("[ ] S Bob person:bob state:meeting from:2026-06-27T10:00\n")
            stdout, stderr, code = run_cli("who", file1, file2)
            self.assertEqual(0, code, stderr)
            out = normalize_newlines(stdout)
            self.assertIn("alice", out)
            self.assertIn("bob", out)

    def test_who_multi_file_json_includes_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            file1 = os.path.join(tmp, "file1.life.txt")
            file2 = os.path.join(tmp, "file2.life.txt")
            with open(file1, "w", encoding="utf-8") as f:
                f.write("[ ] S Alice person:alice state:active from:2026-06-27T09:00\n")
            with open(file2, "w", encoding="utf-8") as f:
                f.write("[ ] S Bob person:bob state:active from:2026-06-27T09:00\n")
            stdout, stderr, code = run_cli("who", file1, file2, "--format", "json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            persons = [r["person"] for r in data]
            self.assertIn("alice", persons)
            self.assertIn("bob", persons)


class LifeTxtAssignEdgeCaseTests(unittest.TestCase):
    def test_assign_by_id_sets_assignee(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one id:t001\n")
            stdout, stderr, code = run_cli("assign", path, "t001", "--to", "alice")
            self.assertEqual(0, code, stderr)
            content = open(path, encoding="utf-8").read()
            self.assertIn("assignee:alice", content)

    def test_assign_missing_id_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Task_one id:t001\n")
            stdout, stderr, code = run_cli("assign", path, "noexist", "--to", "alice")
            self.assertNotEqual(0, code)

    def test_assign_notify_appends_m_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[ ] T Fix_bug id:bug001\n")
            stdout, stderr, code = run_cli("assign", path, "bug001", "--to", "bob", "--notify")
            self.assertEqual(0, code, stderr)
            content = open(path, encoding="utf-8").read()
            self.assertIn("[ ] M", content)
            self.assertIn("recipient:bob", content)
            self.assertIn("ref:bug001", content)


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


class LifeTxtCheckLineTests(unittest.TestCase):
    """Tests for the /api/check-line logic via parse_text (pure function)."""

    def _check_line(self, line):
        """Mirror the /api/check-line endpoint logic."""
        if not str(line).strip():
            return {"ok": True, "item_count": 0, "diagnostics": []}
        text = str(line).rstrip("\n") + "\n"
        items, diagnostics = parse_text(text)
        has_error = any(d.severity == "error" for d in diagnostics)
        return {
            "ok": not has_error,
            "item_count": len(items),
            "diagnostics": [d.to_dict() for d in diagnostics],
        }

    def test_valid_line_returns_ok_true(self):
        result = self._check_line("[ ] T My_task due:2026-01-01")
        self.assertTrue(result["ok"])
        self.assertEqual(result["item_count"], 1)
        errors = [d for d in result["diagnostics"] if d["severity"] == "error"]
        self.assertEqual(errors, [])

    def test_invalid_status_returns_ok_false(self):
        result = self._check_line("[X] T Bad_status")
        self.assertFalse(result["ok"])
        self.assertGreater(len(result["diagnostics"]), 0)

    def test_empty_line_returns_ok_true_zero_items(self):
        result = self._check_line("")
        self.assertTrue(result["ok"])
        self.assertEqual(result["item_count"], 0)

    def test_whitespace_only_returns_ok_true(self):
        result = self._check_line("   \t  ")
        self.assertTrue(result["ok"])
        self.assertEqual(result["item_count"], 0)

    def test_comment_line_is_valid(self):
        result = self._check_line("# This is a comment")
        self.assertTrue(result["ok"])

    def test_valid_event_line(self):
        result = self._check_line("[ ] E Team_standup  from:2026-01-01T09:00  to:2026-01-01T09:30")
        self.assertTrue(result["ok"])
        self.assertEqual(result["item_count"], 1)

    def test_done_status_is_valid(self):
        result = self._check_line("[x] T Completed_task  done:2026-01-01")
        self.assertTrue(result["ok"])
        self.assertEqual(result["item_count"], 1)


class LifeTxtSummaryCommandTests(unittest.TestCase):
    """Tests for the summary command output."""

    def _run_summary(self, text, fmt="text"):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            f.flush()
            fname = f.name
        try:
            out, err, rc = run_cli("summary", fname, "--format", fmt)
        finally:
            os.unlink(fname)
        return out, err, rc

    def test_summary_counts_match_file_content(self):
        text = (
            "[ ] T Task_one  project:work\n"
            "[x] T Task_two  done:2026-01-01\n"
            "[ ] H Daily_habit\n"
        )
        out, err, rc = self._run_summary(text)
        self.assertEqual(rc, 0)
        self.assertIn("Items:", out)
        self.assertIn("3", out)

    def test_summary_type_counts_shown(self):
        text = (
            "[ ] T Task_one\n"
            "[ ] T Task_two\n"
            "[ ] N Note_one\n"
        )
        out, err, rc = self._run_summary(text)
        self.assertEqual(rc, 0)
        self.assertIn("T:", out)
        self.assertIn("N:", out)

    def test_summary_json_schema_has_required_keys(self):
        text = "[ ] T Task_one  project:work\n"
        out, err, rc = self._run_summary(text, fmt="json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        for key in ("source", "line_count", "item_count", "type_counts", "status_counts"):
            self.assertIn(key, data)

    def test_summary_status_counts_accurate(self):
        text = (
            "[ ] T Open_task\n"
            "[x] T Done_task  done:2026-01-01\n"
            "[-] T Cancelled_task\n"
        )
        out, err, rc = self._run_summary(text, fmt="json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["status_counts"].get("[ ]"), 1)
        self.assertEqual(data["status_counts"].get("[x]"), 1)
        self.assertEqual(data["status_counts"].get("[-]"), 1)


class LifeTxtDoneCommandTests(unittest.TestCase):
    """Tests for the done command."""

    def _run_done(self, text, *extra_args):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            f.flush()
            fname = f.name
        try:
            out, err, rc = run_cli("done", fname, *extra_args)
            with open(fname, encoding="utf-8") as fh:
                new_text = fh.read()
        finally:
            os.unlink(fname)
        return out, err, rc, new_text

    def test_done_by_line_marks_item(self):
        text = "[ ] T Task_to_complete\n"
        out, err, rc, new_text = self._run_done(text, "--line", "1")
        self.assertEqual(rc, 0)
        self.assertIn("[x]", new_text)

    def test_done_by_text_marks_item(self):
        text = "[ ] T My_unique_task\n"
        out, err, rc, new_text = self._run_done(text, "--text", "unique_task")
        self.assertEqual(rc, 0)
        self.assertIn("[x]", new_text)
        self.assertIn("done:", new_text)

    def test_done_already_done_prints_message(self):
        text = "[x] T Already_done  done:2026-01-01\n"
        out, err, rc, new_text = self._run_done(text, "--line", "1")
        self.assertEqual(rc, 0)
        self.assertIn("Already done", out)

    def test_done_missing_line_exits_nonzero(self):
        text = "[ ] T Task\n"
        out, err, rc, new_text = self._run_done(text, "--line", "99")
        self.assertNotEqual(rc, 0)

    def test_done_writes_today_date(self):
        import datetime as _dt
        today = _dt.date.today().isoformat()
        text = "[ ] T Dateable_task\n"
        out, err, rc, new_text = self._run_done(text, "--line", "1")
        self.assertEqual(rc, 0)
        self.assertIn("done:" + today, new_text)


class LifeTxtParserEdgeCaseTests(unittest.TestCase):
    """Edge-case tests for the parser."""

    def test_unicode_title_is_preserved(self):
        text = "[ ] T 日本語タイトル  project:work\n"
        items, diags = parse_text(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "日本語タイトル")

    def test_emoji_in_title(self):
        text = "[ ] T 🎯_Goal_item\n"
        items, diags = parse_text(text)
        self.assertEqual(len(items), 1)
        self.assertIn("🎯", items[0].title)

    def test_body_continuation_multiline(self):
        text = "[ ] J Journal_entry  body:First_line\n| Second line\n| Third line\n"
        items, diags = parse_text(text)
        self.assertEqual(len(items), 1)
        body = items[0].details.get("body", [])
        self.assertTrue(body)
        self.assertIn("Second line", body[0])
        self.assertIn("Third line", body[0])

    def test_empty_file_parses_cleanly(self):
        items, diags = parse_text("")
        self.assertEqual(items, [])
        errors = [d for d in diags if d.severity == "error"]
        self.assertEqual(errors, [])

    def test_comment_lines_ignored(self):
        text = "# Comment line\n[ ] T Real_item\n"
        items, diags = parse_text(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Real_item")

    def test_windows_line_endings(self):
        text = "[ ] T Task_one\r\n[x] T Task_two\r\n"
        items, diags = parse_text(text)
        self.assertEqual(len(items), 2)

    def test_multiple_values_for_same_key(self):
        text = "[ ] T Multi_tag  tag:a  tag:b  tag:c\n"
        items, diags = parse_text(text)
        self.assertEqual(len(items), 1)
        tags = items[0].details.get("tag", [])
        self.assertEqual(len(tags), 3)
        self.assertIn("a", tags)

    def test_directive_line_not_parsed_as_item(self):
        text = "#! self:alice\n[ ] T Normal_item\n"
        items, diags = parse_text(text)
        item_titles = [i.title for i in items]
        self.assertNotIn("self:alice", item_titles)
        self.assertIn("Normal_item", item_titles)


class LifeTxtSearchCommandTests(unittest.TestCase):
    """Tests for the search command."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_search_finds_substring_in_title(self):
        path = self._make_file("[ ] T My_special_task  project:work\n[x] T Other_task\n")
        try:
            out, err, rc = run_cli("search", path, "special")
            self.assertEqual(rc, 0)
            self.assertIn("special", out.lower())
        finally:
            os.unlink(path)

    def test_search_no_match_returns_nonzero(self):
        path = self._make_file("[ ] T Ordinary_task\n")
        try:
            out, err, rc = run_cli("search", path, "xyzzy_no_match")
            self.assertNotEqual(rc, 0)
        finally:
            os.unlink(path)

    def test_search_regex_mode(self):
        path = self._make_file("[ ] T Task_2026\n[ ] T Another_2025\n")
        try:
            out, err, rc = run_cli("search", path, "Task_[0-9]+", "--regex")
            self.assertEqual(rc, 0)
            self.assertIn("Task_2026", out)
        finally:
            os.unlink(path)

    def test_search_json_format(self):
        path = self._make_file("[ ] T Find_me  project:work\n")
        try:
            out, err, rc = run_cli("search", path, "Find_me", "--format", "json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 1)
            self.assertIn("title", data[0])
        finally:
            os.unlink(path)

    def test_search_in_field_scope(self):
        path = self._make_file("[ ] T Task  project:targeted_project\n[ ] T Other  project:different\n")
        try:
            out, err, rc = run_cli("search", path, "targeted", "--in", "project", "--format", "json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            # Only the item with project:targeted_project should match
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["title"], "Task")
        finally:
            os.unlink(path)


class LifeTxtSnapshotCommandTests(unittest.TestCase):
    """Tests for the snapshot command."""

    def test_snapshot_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "life.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T My_task\n")
            snap_dir = os.path.join(tmpdir, "snaps")
            out, err, rc = run_cli("snapshot", src, "--dir", snap_dir)
            self.assertEqual(rc, 0)
            snaps = os.listdir(snap_dir)
            self.assertEqual(len(snaps), 1)
            self.assertIn("life.txt", snaps[0])

    def test_snapshot_content_matches_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "data.txt")
            content = "[ ] T Snapshot_test\n"
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            out, err, rc = run_cli("snapshot", src)
            self.assertEqual(rc, 0)
            snap_dir = os.path.join(tmpdir, "snapshots")
            snaps = os.listdir(snap_dir)
            dest = os.path.join(snap_dir, snaps[0])
            with open(dest, encoding="utf-8") as f:
                self.assertEqual(f.read(), content)

    def test_snapshot_custom_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "life.txt")
            dest = os.path.join(tmpdir, "my_snap.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("[ ] T Task\n")
            out, err, rc = run_cli("snapshot", src, "-o", dest)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(dest))

    def test_snapshot_missing_source_exits_nonzero(self):
        out, err, rc = run_cli("snapshot", "/nonexistent/path/life.txt")
        self.assertNotEqual(rc, 0)


class LifeTxtLintCommandTests(unittest.TestCase):
    """Tests for the lint command."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_lint_detects_key_typo(self):
        path = self._make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("lint", path)
            self.assertNotEqual(rc, 0)
            self.assertIn("proj", out)
        finally:
            os.unlink(path)

    def test_lint_clean_file_exits_zero(self):
        path = self._make_file("[ ] T Task  project:work  due:2026-01-01\n")
        try:
            out, err, rc = run_cli("lint", path)
            self.assertEqual(rc, 0)
            self.assertIn("No lint issues", out)
        finally:
            os.unlink(path)

    def test_lint_json_format(self):
        path = self._make_file("[ ] T Task  proj:myproject\n")
        try:
            out, err, rc = run_cli("lint", path, "--format", "json")
            self.assertNotEqual(rc, 0)
            data = json.loads(out)
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 0)
            self.assertIn("code", data[0])
            self.assertIn("message", data[0])
        finally:
            os.unlink(path)

    def test_lint_stdin_input(self):
        out, err, rc = run_cli("lint", "-", input_text="[ ] T Task  proj:work\n")
        self.assertNotEqual(rc, 0)
        self.assertIn("proj", out)


class LifeTxtDiffCommandTests(unittest.TestCase):
    """Tests for the diff command."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_diff_detects_added_item(self):
        a = self._make_file("[ ] T Task_one\n")
        b = self._make_file("[ ] T Task_one\n[x] T New_task  done:2026-01-01\n")
        try:
            out, err, rc = run_cli("diff", a, b)
            self.assertEqual(rc, 0)
            self.assertIn("added", out)
            self.assertIn("New_task", out)
        finally:
            os.unlink(a); os.unlink(b)

    def test_diff_detects_removed_item(self):
        a = self._make_file("[ ] T Task_one\n[ ] T Task_two\n")
        b = self._make_file("[ ] T Task_one\n")
        try:
            out, err, rc = run_cli("diff", a, b)
            self.assertEqual(rc, 0)
            self.assertIn("removed", out)
            self.assertIn("Task_two", out)
        finally:
            os.unlink(a); os.unlink(b)

    def test_diff_detects_completed_item(self):
        a = self._make_file("[ ] T Task_one\n")
        b = self._make_file("[x] T Task_one  done:2026-01-01\n")
        try:
            out, err, rc = run_cli("diff", a, b)
            self.assertEqual(rc, 0)
            self.assertIn("Task_one", out)
        finally:
            os.unlink(a); os.unlink(b)

    def test_diff_detects_detail_change(self):
        a = self._make_file("[ ] T Task_one  project:work\n")
        b = self._make_file("[ ] T Task_one  project:work  due:2026-12-31\n")
        try:
            out, err, rc = run_cli("diff", a, b)
            self.assertEqual(rc, 0)
            self.assertIn("detail-changed", out)
        finally:
            os.unlink(a); os.unlink(b)

    def test_diff_no_changes_empty_output(self):
        a = self._make_file("[ ] T Task_one\n")
        b = self._make_file("[ ] T Task_one\n")
        try:
            out, err, rc = run_cli("diff", a, b)
            self.assertEqual(rc, 0)
            self.assertIn("No differences", out)
        finally:
            os.unlink(a); os.unlink(b)

    def test_diff_json_format(self):
        a = self._make_file("[ ] T Task_one\n")
        b = self._make_file("[ ] T Task_one\n[x] T New_item  done:2026-01-01\n")
        try:
            out, err, rc = run_cli("diff", a, b, "--format", "json")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["change"], "added")
        finally:
            os.unlink(a); os.unlink(b)

    def test_diff_type_filter(self):
        a = self._make_file("[ ] T Task_add\n")
        b = self._make_file("[ ] T Task_add\n[x] H Habit_add  done:2026-01-01\n")
        try:
            out, err, rc = run_cli("diff", a, b, "--format", "json", "--type", "T")
            self.assertEqual(rc, 0)
            data = json.loads(out)
            # Only T items should appear
            for item in data:
                self.assertEqual(item["type"], "T")
        finally:
            os.unlink(a); os.unlink(b)


class LifeTxtMigrateCommandTests(unittest.TestCase):
    """Tests for the migrate command."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_rename_key_dry_run(self):
        path = self._make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("migrate", path, "--migration", "rename-key=proj=project", "--dry-run")
            self.assertEqual(rc, 0)
            self.assertIn("dry-run", out.lower())
            self.assertIn("project", out)
            # File unchanged
            with open(path, encoding="utf-8") as f:
                self.assertIn("proj:work", f.read())
        finally:
            os.unlink(path)

    def test_rename_key_applies_change(self):
        path = self._make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("migrate", path, "--migration", "rename-key=proj=project")
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("project:work", content)
            self.assertNotIn("proj:work", content)
        finally:
            os.unlink(path)

    def test_normalize_elapsed_converts_minutes(self):
        path = self._make_file("[ ] T Task  elapsed:90m\n")
        try:
            out, err, rc = run_cli("migrate", path, "--migration", "normalize-elapsed")
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("elapsed:1h30m", content)
        finally:
            os.unlink(path)

    def test_backup_flag_creates_bak(self):
        path = self._make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("migrate", path, "--migration", "rename-key=proj=project", "--backup")
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(path + ".bak"))
        finally:
            os.unlink(path)
            if os.path.exists(path + ".bak"):
                os.unlink(path + ".bak")

    def test_no_changes_exits_zero(self):
        path = self._make_file("[ ] T Task  project:work\n")
        try:
            out, err, rc = run_cli("migrate", path, "--migration", "rename-key=proj=project")
            self.assertEqual(rc, 0)
            self.assertIn("No changes", out)
        finally:
            os.unlink(path)

    def test_missing_file_exits_nonzero(self):
        out, err, rc = run_cli("migrate", "/nonexistent/path.txt", "--migration", "normalize-elapsed")
        self.assertNotEqual(rc, 0)


class LifeTxtLintFixTests(unittest.TestCase):
    """Tests for lint --fix auto-correction."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_fix_renames_typo_key_in_place(self):
        path = self._make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("lint", path, "--fix")
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("project:work", content)
            self.assertNotIn("proj:work", content)
        finally:
            os.unlink(path)

    def test_fix_reports_count(self):
        path = self._make_file("[ ] T Task  proj:work\n[ ] T Another  date:2026-01-01\n")
        try:
            out, err, rc = run_cli("lint", path, "--fix")
            self.assertIn("Fixed", out)
        finally:
            os.unlink(path)

    def test_fix_does_not_affect_clean_file(self):
        path = self._make_file("[ ] T Task  project:work  due:2026-01-01\n")
        try:
            out, err, rc = run_cli("lint", path, "--fix")
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("project:work", content)
        finally:
            os.unlink(path)


class LifeTxtReviewMarkdownTests(unittest.TestCase):
    """Tests for review --format markdown."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_markdown_output_has_heading(self):
        import datetime as _dt
        today = _dt.date.today()
        path = self._make_file(
            "[x] T Completed_task  done:%s\n[ ] T Open_task\n" % today.isoformat()
        )
        try:
            out, err, rc = run_cli("review", path, "--format", "markdown", "--week")
            self.assertEqual(rc, 0)
            self.assertTrue(out.startswith("#"))
            self.assertIn("Tasks", out)
        finally:
            os.unlink(path)

    def test_markdown_completed_section(self):
        import datetime as _dt
        today = _dt.date.today()
        path = self._make_file("[x] T My_done_task  done:%s\n" % today.isoformat())
        try:
            out, err, rc = run_cli("review", path, "--format", "markdown", "--week")
            self.assertEqual(rc, 0)
            self.assertIn("Completed", out)
            self.assertIn("My_done_task", out)
        finally:
            os.unlink(path)

    def test_markdown_habit_bar(self):
        path = self._make_file(
            "[x] H Daily_habit\n[x] H Daily_habit\n[ ] H Daily_habit\n"
        )
        try:
            out, err, rc = run_cli("review", path, "--format", "markdown")
            self.assertEqual(rc, 0)
            self.assertIn("Habits", out)
        finally:
            os.unlink(path)


class LifeTxtFilterLimitTests(unittest.TestCase):
    """Tests for filter --limit N."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_limit_restricts_output(self):
        text = "".join("[ ] T Task_%d\n" % i for i in range(10))
        path = self._make_file(text)
        try:
            out, err, rc = run_cli("filter", path, "--limit", "3")
            self.assertEqual(rc, 0)
            lines = [l for l in out.strip().splitlines() if l.startswith("[")]
            self.assertLessEqual(len(lines), 3)
        finally:
            os.unlink(path)

    def test_limit_zero_returns_all(self):
        text = "".join("[ ] T Task_%d\n" % i for i in range(5))
        path = self._make_file(text)
        try:
            out, err, rc = run_cli("filter", path, "--limit", "0")
            self.assertEqual(rc, 0)
            lines = [l for l in out.strip().splitlines() if l.startswith("[")]
            self.assertEqual(len(lines), 5)
        finally:
            os.unlink(path)


class LifeTxtSearchHighlightCountTests(unittest.TestCase):
    """Tests for search --highlight and --count."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_count_returns_number(self):
        path = self._make_file("[ ] T Apple_task\n[ ] T Banana_task\n[ ] T Another_apple\n")
        try:
            out, err, rc = run_cli("search", path, "apple", "--count")
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "2")
        finally:
            os.unlink(path)

    def test_highlight_includes_ansi_codes(self):
        path = self._make_file("[ ] T Find_this_item\n")
        try:
            out, err, rc = run_cli("search", path, "Find_this", "--highlight")
            self.assertEqual(rc, 0)
            self.assertIn("\033[", out)  # ANSI escape present
        finally:
            os.unlink(path)


class LifeTxtDoneDryRunTests(unittest.TestCase):
    """Tests for done --dry-run."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_dry_run_does_not_write(self):
        path = self._make_file("[ ] T Preview_task\n")
        original = open(path, encoding="utf-8").read()
        try:
            out, err, rc = run_cli("done", path, "--line", "1", "--dry-run")
            self.assertEqual(rc, 0)
            self.assertIn("dry-run", out.lower())
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), original)  # File unchanged
        finally:
            os.unlink(path)

    def test_dry_run_shows_would_mark(self):
        path = self._make_file("[ ] T My_pending_task\n")
        try:
            out, err, rc = run_cli("done", path, "--line", "1", "--dry-run")
            self.assertEqual(rc, 0)
            self.assertIn("My_pending_task", out)
        finally:
            os.unlink(path)


class LifeTxtFromMarkdownTests(unittest.TestCase):
    """Tests for the from-markdown command."""

    def test_converts_unchecked_task(self):
        out, err, rc = run_cli("from-markdown", "-", input_text="- [ ] My open task\n")
        self.assertEqual(rc, 0)
        self.assertIn("[ ]", out)
        self.assertIn("My_open_task", out)

    def test_converts_checked_task(self):
        out, err, rc = run_cli("from-markdown", "-", input_text="- [x] Done task\n")
        self.assertEqual(rc, 0)
        self.assertIn("[x]", out)

    def test_converts_multiple_tasks(self):
        text = "- [ ] Task one\n- [x] Task two\n- [ ] Task three\n"
        out, err, rc = run_cli("from-markdown", "-", input_text=text)
        self.assertEqual(rc, 0)
        self.assertIn("Task_one", out)
        self.assertIn("Task_two", out)
        self.assertIn("Task_three", out)

    def test_project_flag_applied(self):
        out, err, rc = run_cli("from-markdown", "-", "--project", "myproject", input_text="- [ ] A task\n")
        self.assertEqual(rc, 0)
        self.assertIn("project:myproject", out)

    def test_non_task_lines_ignored(self):
        text = "# Heading\nSome paragraph.\n- [ ] Real task\n- Note without checkbox\n"
        out, err, rc = run_cli("from-markdown", "-", input_text=text)
        self.assertEqual(rc, 0)
        items = [l for l in out.strip().splitlines() if l.startswith("[")]
        self.assertEqual(len(items), 1)

    def test_asterisk_bullet_supported(self):
        out, err, rc = run_cli("from-markdown", "-", input_text="* [ ] Star task\n")
        self.assertEqual(rc, 0)
        self.assertIn("Star_task", out)


class LifeTxtSummaryCompareTests(unittest.TestCase):
    """Tests for summary --compare."""

    def _make_file(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.flush()
        f.close()
        return f.name

    def test_compare_shows_both_files(self):
        a = self._make_file("[ ] T Task_one\n[ ] T Task_two\n")
        b = self._make_file("[ ] T Task_one\n[x] T Task_two  done:2026-01-01\n[ ] T Task_three\n")
        try:
            out, err, rc = run_cli("summary", a, "--compare", b)
            self.assertEqual(rc, 0)
            self.assertIn("Items", out)
        finally:
            os.unlink(a); os.unlink(b)

    def test_compare_shows_delta(self):
        a = self._make_file("[ ] T Task_one\n")
        b = self._make_file("[ ] T Task_one\n[ ] T Task_two\n[ ] T Task_three\n")
        try:
            out, err, rc = run_cli("summary", a, "--compare", b)
            self.assertEqual(rc, 0)
            self.assertIn("+2", out)
        finally:
            os.unlink(a); os.unlink(b)


if __name__ == "__main__":
    unittest.main()
