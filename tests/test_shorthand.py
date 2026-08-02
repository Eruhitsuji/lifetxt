"""Tests for the shorthand notations shared by the CLI, TUI, and Web UI."""

import argparse
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

from lifetxt import presence, shorthand, tui_app
from lifetxt.parser import parse_text


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUNDAY = datetime.date(2026, 7, 19)


class DateTokenTests(unittest.TestCase):
    def test_named_days(self):
        self.assertEqual(
            "2026-07-19", shorthand.resolve_date_token("today", today=SUNDAY)
        )
        self.assertEqual(
            "2026-07-20", shorthand.resolve_date_token("tomorrow", today=SUNDAY)
        )
        self.assertEqual(
            "2026-07-18", shorthand.resolve_date_token("yesterday", today=SUNDAY)
        )

    def test_weekday_resolves_to_the_next_occurrence(self):
        # SUNDAY is a Sunday, so "sunday" must mean a week out, not today.
        self.assertEqual(
            "2026-07-20", shorthand.resolve_date_token("monday", today=SUNDAY)
        )
        self.assertEqual(
            "2026-07-26", shorthand.resolve_date_token("sunday", today=SUNDAY)
        )
        self.assertEqual(
            "2026-07-27", shorthand.resolve_date_token("next_monday", today=SUNDAY)
        )

    def test_signed_offsets(self):
        cases = {
            "+3d": "2026-07-22",
            "-1w": "2026-07-12",
            "+2m": "2026-09-19",
            "+1y": "2027-07-19",
            "+0d": "2026-07-19",
        }
        for token, expected in cases.items():
            self.assertEqual(
                expected, shorthand.resolve_date_token(token, today=SUNDAY), token
            )

    def test_month_offset_clamps_to_a_valid_day(self):
        # 31 January + 1 month has no 31st to land on.
        self.assertEqual(
            "2026-02-28",
            shorthand.resolve_date_token("+1m", today=datetime.date(2026, 1, 31)),
        )

    def test_iso_dates_pass_through(self):
        self.assertEqual(
            "2026-01-05", shorthand.resolve_date_token("2026-01-05", today=SUNDAY)
        )

    def test_unknown_token_passes_through_unless_strict(self):
        self.assertEqual(
            "garbage", shorthand.resolve_date_token("garbage", today=SUNDAY)
        )
        with self.assertRaises(shorthand.ShorthandError):
            shorthand.resolve_date_token("garbage", today=SUNDAY, strict=True)

    def test_strict_rejects_an_impossible_calendar_date(self):
        with self.assertRaises(shorthand.ShorthandError):
            shorthand.resolve_date_token("2026-13-99", today=SUNDAY, strict=True)

    def test_cli_resolver_delegates_to_the_shared_one(self):
        from lifetxt.cli import _resolve_relative_date

        # +3d is new; it only works if the CLI really delegates.
        self.assertEqual(
            shorthand.resolve_date_token("+3d", today=SUNDAY),
            _resolve_relative_date("+3d", today=SUNDAY),
        )

    def test_tui_resolver_delegates_to_the_shared_one(self):
        self.assertEqual(
            shorthand.resolve_date_token("+3d"),
            tui_app._resolve_date_token("+3d"),
        )


class CaptureSigilTests(unittest.TestCase):
    def test_all_four_sigils(self):
        title, details = shorthand.parse_capture(
            "Buy milk @home #errand !high ^tomorrow", today=SUNDAY
        )

        self.assertEqual("Buy milk", title)
        self.assertEqual(["home"], details["project"])
        self.assertEqual(["errand"], details["tag"])
        self.assertEqual(["high"], details["priority"])
        self.assertEqual(["2026-07-20"], details["due"])

    def test_repeated_tags_accumulate(self):
        _title, details = shorthand.parse_capture("Multi #a #b @proj", today=SUNDAY)

        self.assertEqual(["a", "b"], details["tag"])
        self.assertEqual(["proj"], details["project"])

    def test_sigil_inside_a_word_is_not_a_sigil(self):
        # An email address must survive capture untouched.
        title, details = shorthand.parse_capture("Mail a@b.com about it", today=SUNDAY)

        self.assertEqual("Mail a@b.com about it", title)
        self.assertEqual({}, details)

    def test_bare_sigil_character_is_left_alone(self):
        title, details = shorthand.parse_capture(
            "Compute 10 ^ 2 carefully", today=SUNDAY
        )

        self.assertEqual("Compute 10 ^ 2 carefully", title)
        self.assertEqual({}, details)

    def test_backslash_escapes_a_sigil(self):
        title, details = shorthand.parse_capture(
            r"Escaped \@notaproject stays", today=SUNDAY
        )

        self.assertEqual("Escaped @notaproject stays", title)
        self.assertEqual({}, details)

    def test_extra_whitespace_is_collapsed(self):
        title, details = shorthand.parse_capture("  spaced   out  @p  ", today=SUNDAY)

        self.assertEqual("spaced out", title)
        self.assertEqual(["p"], details["project"])

    def test_invalid_due_token_fails_loudly(self):
        with self.assertRaises(shorthand.ShorthandError):
            shorthand.parse_capture("Thing ^notadate", today=SUNDAY, strict_dates=True)

    def test_text_without_sigils_is_unchanged(self):
        title, details = shorthand.parse_capture("Plain title here", today=SUNDAY)

        self.assertEqual("Plain title here", title)
        self.assertEqual({}, details)


class PresenceTransitionTests(unittest.TestCase):
    MOMENT = datetime.datetime(2026, 7, 19, 14, 30)
    OPEN = "[/] S Available from:2026-07-19T09:00 state:available person:self service:teams\n"

    def test_opening_a_status_closes_the_previous_one(self):
        result = presence.status_transition(
            self.OPEN, state="focus", person="self", moment=self.MOMENT
        )
        new_text, closed, opened = result.text, result.closed, result.opened

        self.assertEqual(1, len(closed))
        self.assertIn("to:2026-07-19T14:30", closed[0])
        self.assertTrue(closed[0].startswith("[x] S"))
        self.assertTrue(opened.startswith("[/] S"))
        self.assertIn("state:focus", opened)
        self.assertIn("from:2026-07-19T14:30", opened)
        items, diagnostics = parse_text(new_text)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(2, len(items))

    def test_to_is_written_next_to_from(self):
        closed = presence.status_transition(
            self.OPEN, state="focus", person="self", moment=self.MOMENT
        ).closed

        self.assertIn(
            "from:2026-07-19T09:00 to:2026-07-19T14:30 state:available", closed[0]
        )

    def test_other_people_are_untouched(self):
        text = (
            self.OPEN + "[/] S Working from:2026-07-19T10:00 state:busy person:alice\n"
        )

        result = presence.status_transition(
            text, state="away", person="self", moment=self.MOMENT
        )
        new_text, closed = result.text, result.closed

        self.assertEqual(1, len(closed))
        self.assertIn(
            "[/] S Working from:2026-07-19T10:00 state:busy person:alice", new_text
        )

    def test_already_closed_records_are_left_alone(self):
        text = "[x] S Sleeping from:2026-07-19T01:00 to:2026-07-19T08:30 state:sleeping person:self\n"

        result = presence.status_transition(
            text, state="busy", person="self", moment=self.MOMENT
        )
        new_text, closed = result.text, result.closed

        self.assertEqual([], closed)
        self.assertIn("to:2026-07-19T08:30", new_text)

    def test_multiple_open_records_are_all_closed(self):
        text = (
            "[/] S A from:2026-07-19T09:00 state:available person:self\n"
            "[/] S B from:2026-07-19T10:00 state:busy person:self\n"
        )

        closed = presence.status_transition(
            text, state="away", person="self", moment=self.MOMENT
        ).closed

        self.assertEqual(2, len(closed))

    def test_repeating_the_same_state_is_a_no_op(self):
        text = "[/] S Busy from:2026-07-19T09:00 state:busy person:self\n"

        result = presence.status_transition(
            text, state="busy", person="self", moment=self.MOMENT
        )

        # Fragmenting a long busy block into a stub plus a new record would
        # quietly lose the real start time.
        self.assertEqual("busy", result.unchanged)
        self.assertEqual(text, result.text)
        self.assertEqual([], result.closed)
        self.assertEqual("", result.opened)

    def test_force_records_a_new_block_for_the_same_state(self):
        text = "[/] S Busy from:2026-07-19T09:00 state:busy person:self\n"

        result = presence.status_transition(
            text, state="busy", person="self", moment=self.MOMENT, force=True
        )

        self.assertEqual("", result.unchanged)
        self.assertEqual(1, len(result.closed))
        self.assertTrue(result.opened)

    def test_a_different_state_always_transitions(self):
        text = "[/] S Busy from:2026-07-19T09:00 state:busy person:self\n"

        result = presence.status_transition(
            text, state="focus", person="self", moment=self.MOMENT
        )

        self.assertEqual("", result.unchanged)
        self.assertEqual(1, len(result.closed))

    def test_result_exposes_named_fields(self):
        result = presence.status_transition(
            self.OPEN, state="focus", person="self", moment=self.MOMENT
        )

        self.assertEqual(
            ("text", "closed", "opened", "unchanged"), presence.StatusTransition._fields
        )
        self.assertTrue(result.text)
        self.assertEqual(1, len(result.closed))
        self.assertTrue(result.opened)
        self.assertEqual("", result.unchanged)

    def test_crlf_line_endings_are_preserved(self):
        text = "[/] S A from:2026-07-19T09:00 state:busy person:self\r\n"

        result = presence.status_transition(
            text, state="away", person="self", moment=self.MOMENT
        )

        # Every newline must still be part of a CRLF pair, and the appended
        # record must use the file's existing ending rather than a bare LF.
        self.assertEqual(result.text.count("\n"), result.text.count("\r\n"))
        self.assertEqual(2, result.text.count("\r\n"))

    def test_file_without_a_trailing_newline_stays_valid(self):
        result = presence.status_transition(
            "[ ] T A id:t1", state="busy", person="self", moment=self.MOMENT
        )

        items, diagnostics = parse_text(result.text)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(2, len(items))

    def test_close_only_opens_nothing(self):
        result = presence.status_transition(
            self.OPEN, person="self", moment=self.MOMENT, close_only=True
        )
        new_text, closed, opened = result.text, result.closed, result.opened

        self.assertEqual(1, len(closed))
        self.assertEqual("", opened)
        items, _diagnostics = parse_text(new_text)
        self.assertEqual(1, len(items))

    def test_transition_without_a_state_is_rejected(self):
        with self.assertRaises(ValueError):
            presence.status_transition(self.OPEN, person="self", moment=self.MOMENT)

    def test_a_future_open_record_is_reported_instead_of_corrupted(self):
        text = "[/] S Future from:2026-12-31T09:00 state:busy person:self\n"

        with self.assertRaises(ValueError) as caught:
            presence.status_transition(
                text, state="away", person="self", moment=self.MOMENT
            )

        self.assertIn("after", str(caught.exception))

    def test_empty_file_just_opens_a_status(self):
        result = presence.status_transition(
            "", state="busy", person="self", moment=self.MOMENT
        )
        new_text, closed, opened = result.text, result.closed, result.opened

        self.assertEqual([], closed)
        self.assertIn("state:busy", opened)
        items, diagnostics = parse_text(new_text)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(1, len(items))

    def test_title_defaults_to_the_state_name(self):
        opened = presence.status_transition(
            "", state="focus", person="self", moment=self.MOMENT
        ).opened

        self.assertIn("[/] S Focus ", opened)

    def test_extra_details_are_preserved(self):
        opened = presence.status_transition(
            "",
            state="focus",
            person="self",
            moment=self.MOMENT,
            details={"note": ["slow replies"], "project": ["research"]},
        ).opened

        self.assertIn('note:"slow replies"', opened)
        self.assertIn("project:research", opened)

    def test_active_status_items_ignores_records_without_from(self):
        items, _diagnostics = parse_text("[/] S Broken state:busy person:self\n")

        self.assertEqual([], presence.active_status_items(items, person="self"))


def _run_cli(cwd, *args):
    env = dict(os.environ, PYTHONPATH=ROOT_DIR, PYTHONIOENCODING="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "lifetxt"] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
    )
    out, _err = process.communicate()
    return out.decode("utf-8", "replace").strip(), process.returncode


class CliShorthandTests(unittest.TestCase):
    def _workspace(
        self, content="[ ] T Write_Report id:t1 project:work\n", config=None
    ):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        settings = {
            "write_file": "life.txt",
            "timer": {"state_file": os.path.join(tmp.name, "timer.json")},
        }
        settings.update(config or {})
        with open(
            os.path.join(tmp.name, ".lifetxt.json"), "w", encoding="utf-8"
        ) as handle:
            json.dump(settings, handle)
        return tmp.name, path

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_quick_expands_capture_sigils(self):
        cwd, path = self._workspace("")

        out, code = _run_cli(cwd, "q", "Buy milk @home #errand !high ^tomorrow")

        self.assertEqual(0, code, out)
        content = self._read(path)
        self.assertIn("project:home", content)
        self.assertIn("tag:errand", content)
        self.assertIn("priority:high", content)
        self.assertIn("due:", content)
        items, diagnostics = parse_text(content)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual("Buy milk", items[0].title)

    def test_quick_keeps_an_email_address_in_the_title(self):
        cwd, path = self._workspace("")

        _out, code = _run_cli(cwd, "q", "Mail a@b.com about #budget")

        self.assertEqual(0, code)
        items, _diagnostics = parse_text(self._read(path))
        self.assertEqual("Mail a@b.com about", items[0].title)
        self.assertEqual(["budget"], items[0].details["tag"])

    def test_quick_no_shorthand_keeps_the_tokens(self):
        cwd, path = self._workspace("")

        _out, code = _run_cli(cwd, "q", "Keep @literal", "--no-shorthand")

        self.assertEqual(0, code)
        items, _diagnostics = parse_text(self._read(path))
        self.assertEqual("Keep @literal", items[0].title)

    def test_quick_flags_win_over_sigils_for_single_valued_keys(self):
        cwd, path = self._workspace("")

        _out, code = _run_cli(
            cwd, "q", "Report @work #x", "--project", "override", "--tag", "y"
        )

        self.assertEqual(0, code)
        items, _diagnostics = parse_text(self._read(path))
        self.assertEqual(["override"], items[0].details["project"])
        self.assertEqual(["y", "x"], items[0].details["tag"])

    def test_quick_rejects_a_title_made_only_of_sigils(self):
        cwd, _path = self._workspace("")

        out, code = _run_cli(cwd, "q", "@home")

        self.assertNotEqual(0, code)
        self.assertIn("consumed the whole title", out)

    def test_done_writes_a_date_by_default(self):
        cwd, path = self._workspace()

        out, code = _run_cli(cwd, "done", "life.txt", "t1")

        self.assertEqual(0, code, out)
        self.assertRegex(self._read(path), r"done:\d{4}-\d{2}-\d{2}\b")
        self.assertNotIn("T", self._read(path).split("done:")[1][:6])

    def test_done_now_writes_a_timestamp(self):
        cwd, path = self._workspace()

        out, code = _run_cli(cwd, "done", "life.txt", "t1", "--now")

        self.assertEqual(0, code, out)
        self.assertRegex(self._read(path), r"done:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_config_precision_datetime_makes_time_the_default(self):
        cwd, path = self._workspace(config={"done": {"precision": "datetime"}})

        _out, code = _run_cli(cwd, "done", "life.txt", "t1")

        self.assertEqual(0, code)
        self.assertRegex(self._read(path), r"done:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_date_only_overrides_config_precision(self):
        cwd, path = self._workspace(config={"done": {"precision": "datetime"}})

        _out, code = _run_cli(cwd, "done", "life.txt", "t1", "--date-only")

        self.assertEqual(0, code)
        content = self._read(path)
        self.assertRegex(content, r"done:\d{4}-\d{2}-\d{2}\b")
        self.assertNotIn("T", content.split("done:")[1][:6])

    def test_invalid_config_precision_fails_loudly(self):
        cwd, _path = self._workspace(config={"done": {"precision": "nanoseconds"}})

        out, code = _run_cli(cwd, "done", "life.txt", "t1")

        self.assertNotEqual(0, code)
        self.assertIn("done.precision", out)

    def test_habit_completion_stays_date_only(self):
        cwd, path = self._workspace(
            "[ ] H Exercise id:h1 repeat:daily\n",
            config={"done": {"precision": "datetime"}},
        )

        _out, code = _run_cli(cwd, "done", "life.txt", "h1")

        self.assertEqual(0, code)
        content = self._read(path)
        self.assertRegex(content, r"done:\d{4}-\d{2}-\d{2}\b")
        self.assertNotIn("T", content.split("done:")[1][:6])

    def test_done_alias_d(self):
        cwd, path = self._workspace()

        _out, code = _run_cli(cwd, "d", "life.txt", "t1")

        self.assertEqual(0, code)
        self.assertIn("[x] T Write_Report", self._read(path))

    def test_state_opens_and_then_switches_a_status(self):
        cwd, path = self._workspace()

        out, code = _run_cli(cwd, "s", "busy")
        self.assertEqual(0, code, out)
        self.assertIn("Opened:", out)

        out, code = _run_cli(cwd, "state", "focus", "--title", "Deep Work")
        self.assertEqual(0, code, out)
        self.assertIn("Closed:", out)
        self.assertIn("Opened:", out)

        content = self._read(path)
        self.assertEqual(1, content.count("[/] S"))
        self.assertEqual(1, content.count("[x] S"))

    def test_repeating_a_state_writes_nothing(self):
        cwd, path = self._workspace()
        _run_cli(cwd, "s", "busy")
        before = self._read(path)

        out, code = _run_cli(cwd, "s", "busy")

        self.assertEqual(0, code)
        self.assertIn("Already busy", out)
        self.assertEqual(before, self._read(path))

    def test_force_records_a_repeated_state(self):
        cwd, path = self._workspace()
        _run_cli(cwd, "s", "busy")

        out, code = _run_cli(cwd, "s", "busy", "--force")

        self.assertEqual(0, code)
        self.assertIn("Opened:", out)
        self.assertEqual(2, self._read(path).count(" S "))

    def test_state_end_closes_without_opening(self):
        cwd, path = self._workspace()
        _run_cli(cwd, "state", "busy")

        out, code = _run_cli(cwd, "state", "--end")

        self.assertEqual(0, code, out)
        self.assertIn("Closed:", out)
        self.assertEqual(0, self._read(path).count("[/] S"))

    def test_state_end_with_nothing_open_says_so(self):
        cwd, _path = self._workspace()

        out, code = _run_cli(cwd, "state", "--end")

        self.assertEqual(0, code)
        self.assertIn("No open status", out)

    def test_state_without_a_value_explains_itself(self):
        cwd, _path = self._workspace()

        out, code = _run_cli(cwd, "state")

        self.assertNotEqual(0, code)
        self.assertIn("--end", out)

    def test_state_dry_run_writes_nothing(self):
        cwd, path = self._workspace()
        before = self._read(path)

        out, code = _run_cli(cwd, "state", "busy", "--dry-run")

        self.assertEqual(0, code)
        self.assertIn("[dry-run]", out)
        self.assertEqual(before, self._read(path))

    def test_start_then_stop_records_the_whole_cycle(self):
        cwd, path = self._workspace()

        out, code = _run_cli(cwd, "start", "life.txt", "t1")
        self.assertEqual(0, code, out)
        content = self._read(path)
        self.assertIn("[/] T Write_Report", content)
        self.assertIn("state:busy", content)

        out, code = _run_cli(cwd, "stop", "--done")
        self.assertEqual(0, code, out)
        content = self._read(path)
        self.assertIn("[x] T Write_Report", content)
        self.assertIn("elapsed:", content)
        self.assertIn("done:", content)
        self.assertEqual(0, content.count("[/] S"))

    def test_start_refuses_a_second_concurrent_timer(self):
        cwd, _path = self._workspace()
        _run_cli(cwd, "start", "life.txt", "t1")

        out, code = _run_cli(cwd, "start", "life.txt", "t1")

        self.assertNotEqual(0, code)
        self.assertIn("already running", out)

    def test_stop_without_a_timer_explains_how_to_start(self):
        cwd, _path = self._workspace()

        out, code = _run_cli(cwd, "stop")

        self.assertNotEqual(0, code)
        self.assertIn("lifetxt start", out)

    def test_start_dry_run_writes_nothing(self):
        cwd, path = self._workspace()
        before = self._read(path)

        out, code = _run_cli(cwd, "start", "life.txt", "t1", "--dry-run")

        self.assertEqual(0, code)
        self.assertIn("[dry-run]", out)
        self.assertEqual(before, self._read(path))

    def test_start_no_presence_leaves_status_alone(self):
        cwd, path = self._workspace()

        _out, code = _run_cli(cwd, "start", "life.txt", "t1", "--no-presence")

        self.assertEqual(0, code)
        self.assertNotIn(" S ", self._read(path))

    def test_start_requires_an_id(self):
        cwd, _path = self._workspace("[ ] T NoId project:work\n")

        out, code = _run_cli(cwd, "start", "life.txt", "--text", "NoId")

        self.assertNotEqual(0, code)
        self.assertIn("ids --assign", out)


class TuiShorthandTests(unittest.TestCase):
    def _state(self, content="[ ] T Write_Report id:t1 project:work\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        args = argparse.Namespace(
            paths=[path],
            config_data={"tui": {"session": "off"}, "write_file": path},
        )
        state = tui_app.WorkspaceState(args, glyphs=tui_app.ASCII_GLYPHS)
        state.reload()
        return state, path

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_state_command_switches_presence(self):
        state, path = self._state()

        tui_app.run_command(state, "/state busy")
        level, message = tui_app.run_command(state, "/state focus Deep Work")

        self.assertEqual("success", level)
        self.assertIn("closed 1 previous", message)
        content = self._read(path)
        self.assertEqual(1, content.count("[/] S"))
        self.assertIn("state:focus", content)

    def test_state_end_closes_the_open_status(self):
        state, path = self._state()
        tui_app.run_command(state, "/state busy")

        level, _message = tui_app.run_command(state, "/state end")

        self.assertEqual("success", level)
        self.assertEqual(0, self._read(path).count("[/] S"))

    def test_state_end_label_keeps_a_quoted_title_intact(self):
        state, _path = self._state()
        tui_app.run_command(state, "/state focus Deep Work")

        _level, message = tui_app.run_command(state, "/state end")

        self.assertIn("Deep Work", message)

    def test_repeating_a_state_reports_no_change(self):
        state, path = self._state()
        tui_app.run_command(state, "/state busy")
        before = self._read(path)

        level, message = tui_app.run_command(state, "/state busy")

        self.assertEqual("info", level)
        self.assertIn("Already busy", message)
        self.assertEqual(before, self._read(path))

    def test_now_reports_the_open_status(self):
        state, _path = self._state()

        _level, message = tui_app.run_command(state, "/now")
        self.assertIn("No open status", message)

        tui_app.run_command(state, "/state busy")
        _level, message = tui_app.run_command(state, "/now")
        self.assertIn("busy", message)

    def test_add_expands_capture_sigils(self):
        state, path = self._state()

        tui_app.run_command(state, "/add Buy milk @home #errand !high ^tomorrow")

        content = self._read(path)
        self.assertIn("project:home", content)
        self.assertIn("priority:high", content)
        items, diagnostics = parse_text(content)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])

    def test_add_rejects_an_invalid_due_token(self):
        state, _path = self._state()

        with self.assertRaises(ValueError):
            tui_app.run_command(state, "/add Thing ^notadate")

    def test_done_records_a_date_by_default(self):
        state, path = self._state()

        _level, message = tui_app.run_command(state, "/done")

        self.assertIn("done:", self._read(path))
        self.assertNotIn("T", message.split("(")[1][:6])

    def test_done_now_records_a_timestamp(self):
        state, path = self._state()

        tui_app.run_command(state, "/done now")

        self.assertRegex(self._read(path), r"done:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_done_honours_config_precision(self):
        state, path = self._state()
        state.args.config_data["done"] = {"precision": "datetime"}

        tui_app.run_command(state, "/done")

        self.assertRegex(self._read(path), r"done:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_done_rejects_an_unknown_argument(self):
        state, _path = self._state()

        with self.assertRaises(ValueError):
            tui_app.run_command(state, "/done zzz")

    def test_aliases_resolve_to_their_command(self):
        expected = {
            "d": "done",
            "s": "state",
            "a": "add",
            "f": "search",
            "t": "timer",
            "e": "edit",
            "u": "undo",
            "n": "next",
            "q": "quit",
        }
        actual = dict((c.alias, c.name) for c in tui_app.COMMANDS if c.alias)

        self.assertEqual(expected, actual)

    def test_alias_beats_fuzzy_ranking_in_the_palette(self):
        # /d must be /done, not /detail or /delete, which also fuzzy-match "d".
        self.assertEqual("done", tui_app.command_suggestions("/d")[0][0].name)
        self.assertEqual("state", tui_app.command_suggestions("/s")[0][0].name)
        self.assertEqual("timer", tui_app.command_suggestions("/t")[0][0].name)

    def test_alias_runs_the_command(self):
        state, path = self._state()

        tui_app.run_command(state, "/d")

        self.assertIn("[x] T Write_Report", self._read(path))

    def test_every_alias_is_unique(self):
        aliases = [c.alias for c in tui_app.COMMANDS if c.alias]
        self.assertEqual(len(aliases), len(set(aliases)))

    def test_no_alias_shadows_a_real_command_name(self):
        names = set(c.name for c in tui_app.COMMANDS)
        for command in tui_app.COMMANDS:
            if command.alias:
                self.assertNotIn(command.alias, names, command.alias)


class WebShorthandApiTests(unittest.TestCase):
    def _client(self, content="[ ] T A id:t1\n"):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            self.skipTest("FastAPI test client is unavailable: %s" % exc)
        from lifetxt.webapp import create_app

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        try:
            return TestClient(create_app([path], writable_path=path)), path
        except Exception as exc:
            self.skipTest("FastAPI test client could not start: %s" % exc)

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_post_status_opens_and_closes(self):
        client, path = self._client()

        first = client.post("/api/status", json={"state": "busy"})
        self.assertEqual(201, first.status_code)
        self.assertEqual([], first.json()["closed"])

        second = client.post(
            "/api/status", json={"state": "focus", "title": "Deep Work"}
        )
        self.assertEqual(201, second.status_code)
        self.assertEqual(1, len(second.json()["closed"]))

        content = self._read(path)
        self.assertEqual(1, content.count("[/] S"))
        self.assertIn("state:focus", content)

    def test_post_status_end_closes_without_opening(self):
        client, path = self._client()
        client.post("/api/status", json={"state": "busy"})

        response = client.post("/api/status", json={"end": True})

        self.assertEqual(201, response.status_code)
        self.assertEqual("", response.json()["opened"])
        self.assertEqual(0, self._read(path).count("[/] S"))

    def test_repeating_a_state_writes_nothing(self):
        client, path = self._client()
        client.post("/api/status", json={"state": "busy"})
        before = self._read(path)

        response = client.post("/api/status", json={"state": "busy"})

        self.assertEqual(201, response.status_code)
        self.assertEqual("busy", response.json()["unchanged"])
        self.assertEqual(before, self._read(path))

    def test_force_records_a_repeated_state(self):
        client, path = self._client()
        client.post("/api/status", json={"state": "busy"})

        response = client.post("/api/status", json={"state": "busy", "force": True})

        self.assertEqual("", response.json()["unchanged"])
        self.assertEqual(1, len(response.json()["closed"]))
        self.assertEqual(2, self._read(path).count(" S "))

    def test_post_status_without_state_is_rejected(self):
        client, _path = self._client()

        response = client.post("/api/status", json={})

        self.assertEqual(400, response.status_code)
        self.assertIn("state is required", json.dumps(response.json()))

    def test_get_status_reflects_the_new_record(self):
        client, _path = self._client()
        client.post("/api/status", json={"state": "focus"})

        records = client.get("/api/status?active=true").json()["records"]

        self.assertEqual(1, len(records))
        self.assertEqual("focus", records[0]["state"])

    def test_capture_endpoint_expands_sigils(self):
        client, path = self._client()

        response = client.post(
            "/api/items/capture",
            json={"text": "Buy milk @home #errand !high ^tomorrow"},
        )

        self.assertEqual(201, response.status_code)
        line = response.json()["line"]
        self.assertIn("project:home", line)
        self.assertIn("priority:high", line)
        items, diagnostics = parse_text(self._read(path))
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(2, len(items))

    def test_capture_rejects_a_title_made_only_of_sigils(self):
        client, _path = self._client()

        response = client.post("/api/items/capture", json={"text": "@home"})

        self.assertEqual(400, response.status_code)

    def test_capture_rejects_an_invalid_due_token(self):
        client, _path = self._client()

        response = client.post("/api/items/capture", json={"text": "Thing ^notadate"})

        self.assertEqual(400, response.status_code)
        self.assertIn("is not a date", json.dumps(response.json()))

    def test_shorthand_parse_previews_without_writing(self):
        client, path = self._client()
        before = self._read(path)

        response = client.post(
            "/api/shorthand/parse", json={"text": "Buy milk @home ^tomorrow"}
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("Buy milk", payload["title"])
        self.assertEqual(["home"], payload["details"]["project"])
        self.assertTrue(payload["sigils"])
        self.assertEqual(before, self._read(path))

    def test_browser_page_exposes_the_new_controls(self):
        client, _path = self._client()

        html = client.get("/").text

        for probe in (
            "presence-bar",
            "previewShorthand",
            "setPresence",
            "endPresence",
            "/api/items/capture",
        ):
            self.assertIn(probe, html, probe)


if __name__ == "__main__":
    unittest.main()
