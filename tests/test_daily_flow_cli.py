"""Read-only Daily Flow CLI acceptance and compatibility tests (#1145)."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from lifetxt import daily_flow_cli
from lifetxt.config import load_config
from lifetxt.daily_flow import build_daily_flow
from lifetxt.entrypoint import main
from lifetxt.mutation import read_text_snapshot, hash_bytes
from lifetxt.parser import parse_text
from lifetxt.timezone_policy import clock_context
from tests.test_lifetxt import run_cli


CLOCK = datetime(2026, 10, 8, tzinfo=timezone.utc)
FLAGS = ["--date", "2026-10-09", "--day-start", "09:00", "--day-end", "12:00"]
SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] E Meeting id:e from:2026-10-09T10:00 to:2026-10-09T11:00\n"
    "[ ] R Ping id:r at:2026-10-09T09:30\n"
    "[ ] T Work id:t est:30m\n"
    "[ ] T Missing id:missing\n"
    "[ ] T Large id:large est:4h\n"
)


class DailyFlowCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.json"
        self.config.write_text("{}", encoding="utf-8")
        self.source = self.write("life.txt", SAMPLE)

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def cli(self, *paths, flags=None, output="json", config=None):
        argv = [
            "flow",
            *map(str, paths),
            *(FLAGS if flags is None else flags),
            "--format",
            output,
            "--config",
            str(config or self.config),
        ]
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            clock_context(CLOCK),
        ):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code
        return stdout.getvalue(), stderr.getvalue(), code

    def result(self, *paths, **kwargs):
        stdout, stderr, code = self.cli(*paths, **kwargs)
        result = json.loads(stdout)
        self.assertNotEqual("blocked", result["completeness"]["state"], stderr)
        self.assertEqual(
            0 if result["completeness"]["state"] == "complete" else 1, code, stderr
        )
        return result

    def test_json_is_exact_shared_model_not_an_envelope(self):
        actual = self.result(self.source)
        snapshots = {str(self.source.resolve()): read_text_snapshot(self.source)}
        items, notes = daily_flow_cli._parse(snapshots, None, {})
        expected = build_daily_flow(
            items,
            date="2026-10-09",
            day_start="09:00",
            day_end="12:00",
            timezone="UTC",
            evaluated_at=CLOCK,
            occupancy_complete=True,
            source_revisions={
                str(self.source.resolve()): snapshots[
                    str(self.source.resolve())
                ].content_hash
            },
            input_diagnostics=notes,
            config=load_config(str(self.config)),
        )
        self.assertEqual(expected, actual)
        self.assertEqual("daily-flow-lite-v1", actual["schema"])
        self.assertEqual(
            "source_snapshot", actual["source_revision"]["sources"][0]["basis"]
        )

    def test_text_has_fixed_candidate_instants_unplaced_and_why(self):
        stdout, stderr, code = self.cli(self.source, output="text")
        self.assertEqual(1, code, stderr)
        for text in (
            "[fixed]",
            "[candidate]",
            "Meeting",
            "Work",
            "Instants (1)",
            "Unplaced (2)",
            "missing_estimate",
            "insufficient_capacity",
            "why:",
            "source=",
            "line=",
            "Diagnostics (1)",
            "read-only suggestions, not saved",
        ):
            self.assertIn(text, stdout)

    def test_json_deterministic_with_same_reference_clock(self):
        self.assertEqual(self.cli(self.source), self.cli(self.source))

    def test_read_only_byte_hashes_and_directory_inventory(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.result(self.source)
        self.cli(self.source, output="text")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_bom_and_crlf_revision_is_exact_bytes(self):
        self.source.write_bytes(b"\xef\xbb\xbf" + SAMPLE.replace("\n", "\r\n").encode())
        result = self.result(self.source)
        self.assertEqual(
            hash_bytes(self.source.read_bytes()),
            result["source_revision"]["sources"][0]["revision"],
        )

    def test_multiple_sources_keep_occupancy_and_dependencies(self):
        self.source.write_text(
            "#! timezone: UTC\n[ ] T Dependent id:d est:30m depends_on:base\n[ ] T Ready id:t est:1h\n",
            encoding="utf-8",
        )
        other = self.write(
            "other.txt", "[ ] T Base id:base est:30m\n[ ] E Busy id:e on:2026-10-09\n"
        )
        result = self.result(self.source, other)
        reasons = {r["item"]["id"]: r["reason"] for r in result["unplaced"]}
        self.assertEqual("unresolved_dependency", reasons["d"])
        self.assertEqual("insufficient_capacity", reasons["t"])
        self.assertEqual([], result["free"])

    def test_source_enumeration_permutation_preserves_json(self):
        other = self.write("other.txt", "#! timezone: UTC\n[ ] T Other id:o est:30m\n")
        self.assertEqual(
            self.result(self.source, other), self.result(other, self.source)
        )

    def test_alias_paths_do_not_create_duplicate_identity(self):
        self.assertEqual(
            self.result(self.source),
            self.result(self.source, self.source.parent / "." / self.source.name),
        )

    def test_symlink_alias_is_admitted_once(self):
        alias = self.root / "alias.txt"
        try:
            alias.symlink_to(self.source)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.result(self.source), self.result(self.source, alias))

    def test_directory_and_glob_follow_existing_path_expansion(self):
        directory = self.root / "active"
        directory.mkdir()
        (directory / "life.txt").write_text(SAMPLE, encoding="utf-8")
        (directory / "other.txt").write_text(
            "[ ] T Other id:o est:30m\n", encoding="utf-8"
        )
        self.assertEqual(self.result(directory), self.result(str(directory / "*.txt")))

    def test_configured_paths_and_timezone(self):
        self.source.write_text("[ ] T Work id:t est:30m\n", encoding="utf-8")
        self.config.write_text(
            json.dumps(
                {"paths": [str(self.source)], "defaults": {"timezone": "Asia/Tokyo"}}
            ),
            encoding="utf-8",
        )
        result = self.result()
        self.assertEqual("Asia/Tokyo", result["timezone"])
        self.assertTrue(result["timeline"][0]["start"].endswith("+09:00"))

    def test_file_timezone_wins_over_config(self):
        self.config.write_text(
            json.dumps({"defaults": {"timezone": "Asia/Tokyo"}}), encoding="utf-8"
        )
        self.assertEqual("UTC", self.result(self.source)["timezone"])

    def test_workspace_excludes_archives(self):
        archive = self.write("archive.txt", "[ ] E Archive id:arch on:2026-10-09\n")
        self.config.write_text(
            json.dumps(
                {
                    "default_workspace": "daily",
                    "workspaces": {
                        "daily": {
                            "sources": [
                                {"path": str(self.source), "role": "primary"},
                                {"path": str(archive), "role": "archive"},
                            ]
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        result = self.result()
        self.assertEqual(1, len(result["scope"]["active_sources"]))
        self.assertNotIn("arch", json.dumps(result))

    def test_stdin_is_explicit_read_once_and_parsed_revision(self):
        with patch("sys.stdin", io.StringIO(SAMPLE)):
            result = self.result("-")
        self.assertEqual(
            "parsed_snapshot", result["source_revision"]["sources"][0]["basis"]
        )

    def test_default_workspace_timezone_does_not_prescan_excluded_archive(self):
        archive = self.write(
            "archive.txt",
            "#! timezone: Not/A_Timezone\n[ ] E Hidden id:arch on:2026-10-09\n",
        )
        self.config.write_text(
            json.dumps(
                {
                    "default_workspace": "daily",
                    "workspaces": {
                        "daily": {
                            "sources": [
                                {
                                    "path": str(self.source),
                                    "role": "primary",
                                    "priority": 100,
                                },
                                {
                                    "path": str(archive),
                                    "role": "archive",
                                    "priority": 1,
                                },
                            ]
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        flags = list(FLAGS)
        flags[1] = "2099-10-09"
        stdout, stderr, code = run_cli(
            "flow",
            *flags,
            "--format",
            "json",
            env_update={"LIFETXT_CONFIG": str(self.config)},
        )
        self.assertEqual(1, code, stderr)  # complete admitted scope, partial estimate
        result = json.loads(stdout)
        self.assertEqual("UTC", result["timezone"])
        self.assertEqual(1, len(result["scope"]["active_sources"]))

    def test_flow_never_uses_legacy_timezone_prescan(self):
        with patch(
            "lifetxt.safety_foundation.read_text_exact",
            side_effect=AssertionError("no speculative reads"),
        ):
            result = self.result(self.source)
        self.assertEqual("UTC", result["timezone"])

    def test_each_window_flag_is_required(self):
        for offset in (0, 2, 4):
            with self.subTest(flag=FLAGS[offset]):
                stdout, stderr, code = self.cli(
                    self.source, flags=FLAGS[:offset] + FLAGS[offset + 2 :]
                )
                self.assertEqual(2, code)
                self.assertEqual("", stdout)
                self.assertIn(FLAGS[offset], stderr)

    def test_invalid_explicit_values_fail_before_snapshot_read(self):
        for index, value in (
            (1, "today"),
            (1, "2026-02-30"),
            (1, "9999-12-31"),
            (3, "9:00"),
            (3, "24:00"),
            (5, "08:00"),
            (5, "12:00Z"),
            (5, ""),
        ):
            flags = list(FLAGS)
            flags[index] = value
            with (
                self.subTest(value=value),
                patch.object(
                    daily_flow_cli,
                    "_read",
                    side_effect=AssertionError("must validate first"),
                ),
            ):
                stdout, stderr, code = self.cli(self.source, flags=flags)
                self.assertEqual(1, code)
                self.assertEqual("", stdout)
                self.assertIn("flow", stderr)

    def test_exclusive_next_midnight(self):
        flags = list(FLAGS)
        flags[-1] = "00:00"
        self.assertEqual(
            "2026-10-10T00:00:00+00:00",
            self.result(self.source, flags=flags)["window"]["end"],
        )

    def test_missing_input_fails_without_fabricated_plan(self):
        stdout, stderr, code = self.cli(self.root / "missing.txt")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("complete active scope", stderr)

    def test_unreadable_member_never_uses_partial_inventory(self):
        stdout, stderr, code = self.cli(self.source, self.root / "missing.txt")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)

    def test_invalid_encoding_fails_loudly(self):
        self.source.write_bytes(b"\xff\xfe")
        stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("cannot read", stderr)

    def test_recurring_unknown_occupancy_is_blocked_with_nonzero_exit(self):
        self.source.write_text(
            SAMPLE + "[ ] E Recurring id:repeat on:2026-10-09 repeat:daily\n",
            encoding="utf-8",
        )
        stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        result = json.loads(stdout)
        self.assertEqual("blocked", result["completeness"]["state"])
        self.assertEqual(
            [], [r for r in result["timeline"] if r["kind"] == "candidate"]
        )
        self.assertIn("skipped_recurring", stdout)
        self.assertIn("fix diagnostics", stderr)

    def test_incomplete_and_untimed_events_are_not_apparent_gaps(self):
        for record in (
            "[ ] E Bad id:e from:2026-10-09T10:00\n",
            "[ ] E Bad id:e\n",
            "[ ] E Point id:e at:2026-10-09T10:00\n",
        ):
            with self.subTest(record=record):
                self.source.write_text(
                    "#! timezone: UTC\n[ ] T Work id:t est:30m\n" + record,
                    encoding="utf-8",
                )
                stdout, stderr, code = self.cli(self.source)
                self.assertEqual(1, code, stderr)
                result = json.loads(stdout)
                self.assertEqual("unknown", result["completeness"]["occupancy"])
                self.assertEqual([], result["free"])

    def test_parser_error_blocks_but_json_stays_canonical(self):
        self.source.write_text(SAMPLE + "not a record\n", encoding="utf-8")
        stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        self.assertIn("input_parse_error", stdout)
        self.assertIn("ERROR:", stderr)
        self.assertEqual([], json.loads(stdout)["free"])

    def test_invalid_estimate_is_visible_unplaced(self):
        self.source.write_text(
            "#! timezone: UTC\n[ ] T Bad id:bad est:bogus\n", encoding="utf-8"
        )
        result = self.result(self.source)
        self.assertEqual("invalid_estimate", result["unplaced"][0]["reason"])
        self.assertEqual([], result["timeline"])

    def test_duplicate_ids_block_and_do_not_place(self):
        other = self.write("other.txt", "[ ] T Collision id:t est:30m\n")
        stdout, stderr, code = self.cli(self.source, other)
        self.assertEqual(1, code)
        self.assertIn("ambiguous_identity", stdout)

    def test_dst_transition_day_blocks_placement(self):
        self.source.write_text(
            "#! timezone: America/New_York\n[ ] T Work id:t est:30m\n", encoding="utf-8"
        )
        flags = list(FLAGS)
        flags[1] = "2026-11-01"
        stdout, stderr, code = self.cli(self.source, flags=flags)
        self.assertEqual(1, code, stderr)
        self.assertIn("unsupported_timezone_window", stdout)
        self.assertEqual([], json.loads(stdout)["timeline"])

    def test_past_date_and_elapsed_window_block(self):
        for reference in (
            datetime(2026, 10, 10, tzinfo=timezone.utc),
            datetime(2026, 10, 9, 13, tzinfo=timezone.utc),
        ):
            with (
                self.subTest(reference=reference),
                patch.object(daily_flow_cli, "now", return_value=reference),
            ):
                stdout, stderr, code = self.cli(self.source)
                self.assertEqual(1, code)
                self.assertEqual("blocked", json.loads(stdout)["completeness"]["state"])

    def test_offset_event_normalizes_to_workspace_zone(self):
        self.source.write_text(
            "#! timezone: Asia/Tokyo\n[ ] E Busy id:e from:2026-10-09T00:00Z to:2026-10-09T01:00Z\n[ ] T Work id:t est:30m\n",
            encoding="utf-8",
        )
        result = self.result(self.source)
        self.assertEqual("2026-10-09T09:00:00+09:00", result["timeline"][0]["start"])
        self.assertEqual("fixed", result["timeline"][0]["kind"])

    def test_one_snapshot_race_retries_then_succeeds(self):
        with patch.object(
            daily_flow_cli, "_unchanged", side_effect=[False, True]
        ) as unchanged:
            self.result(self.source)
        self.assertEqual(2, unchanged.call_count)

    def test_repeated_snapshot_race_is_generic_blocked_model(self):
        with patch.object(
            daily_flow_cli, "_unchanged", return_value=False
        ) as unchanged:
            stdout, stderr, code = self.cli(self.source)
        self.assertEqual(2, unchanged.call_count)
        self.assertEqual(1, code)
        result = json.loads(stdout)
        self.assertEqual(["source_changed"], result["completeness"]["reasons"])
        self.assertEqual([], result["timeline"])
        self.assertIsNone(result["source_revision"])

    def test_actual_hash_change_during_model_build_is_detected(self):
        original = daily_flow_cli.build_daily_flow
        count = 0

        def changing(items, **options):
            nonlocal count
            result = original(items, **options)
            count += 1
            if count == 1:
                self.source.write_text(
                    "#! timezone: UTC\n[ ] E NowBusy id:new on:2026-10-09\n",
                    encoding="utf-8",
                )
            return result

        with patch.object(daily_flow_cli, "build_daily_flow", side_effect=changing):
            result = self.result(self.source)
        self.assertEqual(2, count)
        self.assertEqual("new", result["timeline"][0]["item"]["id"])

    def test_input_set_change_is_detected(self):
        args = type("Args", (), {"paths": [str(self.root / "*.life.txt")]})()
        self.write("a.life.txt", SAMPLE)
        paths = daily_flow_cli._paths(args, {})
        snapshots = {p: read_text_snapshot(p) for p in paths}
        self.write("b.life.txt", "[ ] T New id:new est:30m\n")
        self.assertFalse(daily_flow_cli._unchanged(args, {}, paths, snapshots))

    def test_host_local_fallback_has_actionable_error(self):
        with patch.object(
            daily_flow_cli, "resolve_timezone_name", return_value="local"
        ):
            stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("defaults.timezone", stderr)

    def test_text_renders_break_buffer_secondary_and_controls(self):
        items, _ = parse_text("[ ] T Work id:t est:30m\n[ ] T Missing id:m\n")
        result = build_daily_flow(
            items,
            date="2026-10-09",
            day_start="09:00",
            day_end="12:00",
            timezone="UTC",
            evaluated_at=CLOCK,
            occupancy_complete=True,
            policy={"break_minutes": 5, "buffer_minutes": 10},
        )
        result["timeline"][0]["item"]["title"] = "bad\x1b[31m\nline"
        result["unplaced"][0]["secondary"] = ["future_intent"]
        text = daily_flow_cli.format_flow_text(result)
        self.assertIn("[policy_break]", text)
        self.assertIn("[buffer]", text)
        self.assertIn("also: future_intent", text)
        self.assertNotIn("\x1b", text)
        self.assertIn("\\u000a", text)

    def test_resource_bound_never_silently_truncates(self):
        with patch.object(daily_flow_cli.os.path, "getsize", return_value=16000001):
            stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("input bound", stderr)

    def test_aggregate_bound_stops_before_reading_remaining_members(self):
        second = self.write("other.txt", "#" + "x" * 450)
        third = self.write("last.txt", "#! timezone: UTC\n")
        original = daily_flow_cli._read
        with (
            patch.dict(daily_flow_cli.HARD_LIMITS, {"text_chars": 500}),
            patch.object(daily_flow_cli, "_read", wraps=original) as reader,
        ):
            stdout, stderr, code = self.cli(self.source, second, third)
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertEqual(2, reader.call_count)
        self.assertIn("selected text exceeds", stderr)

    def test_special_file_is_rejected_without_blocking_read(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "regular files"):
            daily_flow_cli._read(str(fifo))

    def test_candidate_cap_is_visible_and_preserves_inventory(self):
        self.source.write_text(
            "#! timezone: UTC\n"
            + "".join("[ ] T Work id:t%d est:30m\n" % n for n in range(1001)),
            encoding="utf-8",
        )
        stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        result = json.loads(stdout)
        self.assertEqual("bounded", result["completeness"]["inventory"])
        placed = sum(r["kind"] == "candidate" for r in result["timeline"])
        self.assertEqual(1001, placed + len(result["unplaced"]))
        self.assertIn("limit_exceeded", stdout)

    def test_long_relevant_utc_span_retains_core_blocking(self):
        self.source.write_text(
            "#! timezone: UTC\n[ ] E Long id:e from:2026-10-08T00:00 to:2026-10-11T00:00\n[ ] T Work id:t est:30m\n",
            encoding="utf-8",
        )
        stdout, stderr, code = self.cli(self.source)
        self.assertEqual(1, code)
        self.assertIn("unsupported_timezone_window", stdout)
        self.assertEqual([], json.loads(stdout)["free"])

    def test_default_life_file_and_default_text_public_entry(self):
        flags = list(FLAGS)
        flags[1] = "2099-10-09"
        stdout, stderr, code = run_cli(
            "flow", *flags, "--config", str(self.config), cwd=str(self.root)
        )
        self.assertEqual(1, code, stderr)  # missing estimate is partial
        self.assertIn("Daily Flow Lite", stdout)
        self.assertIn("missing_estimate", stdout)

    def test_cli_help_and_subprocess_public_entry(self):
        stdout, stderr, code = run_cli("flow", "--help")
        self.assertEqual(0, code, stderr)
        for flag in (
            "--date",
            "--day-start",
            "--day-end",
            "--format",
            "workspace/config",
        ):
            self.assertIn(flag, stdout)
        stdout, stderr, code = run_cli(
            "flow",
            str(self.source),
            "--date",
            "2099-10-09",
            "--day-start",
            "09:00",
            "--day-end",
            "12:00",
            "--format",
            "json",
            "--config",
            str(self.config),
        )
        self.assertEqual(1, code, stderr)
        self.assertEqual("daily-flow-lite-v1", json.loads(stdout)["schema"])


if __name__ == "__main__":
    unittest.main()
