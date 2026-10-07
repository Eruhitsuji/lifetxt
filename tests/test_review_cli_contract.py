"""Review adapter contracts for #1137, using the real temporal builder."""

import datetime
import json
from pathlib import Path
import tempfile
from unittest import mock

from lifetxt import cli, entrypoint
from lifetxt.native_history import build_item_event
from lifetxt.runtime_safety_v2 import install_cli_timezone_context
from lifetxt.serializer import item_to_line
from lifetxt.temporal_review import build_temporal_review
from lifetxt.timezone_policy import clock_context
from tests.test_core_cli_entrypoint import CliContractTestCase


class ReviewCliContractTests(CliContractTestCase):
    def setUp(self):
        super().setUp()
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "life.txt"
        self.config_path = Path(directory) / "config.json"
        self.config_path.write_text(
            '{"defaults": {"timezone": "UTC"}}', encoding="utf-8"
        )
        install_cli_timezone_context(cli)
        self.stack.enter_context(
            mock.patch(
                "lifetxt.config.find_config_path", return_value=str(self.config_path)
            )
        )
        self.stack.enter_context(
            clock_context(datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc))
        )
        events = [
            build_item_event(
                "done",
                event,
                "2026-06-10T%s:00:00Z" % hour,
                sequence,
                "TX-%d" % sequence,
                "a" * 64,
                **fields,
            )
            for sequence, event, hour, fields in (
                (
                    1,
                    "created",
                    "10",
                    {"item_kind": "T", "item_title": "Done", "after_status": "[ ]"},
                ),
                (2, "completed", "12", {"before_status": "[ ]", "after_status": "[x]"}),
            )
        ]
        self.history = "\n".join(item_to_line(event) for event in events) + "\n"
        self.path.write_text(
            "[x] T Done id:done project:p\n"
            "[ ] T Open id:open project:p\n"
            "[ ] T Other id:other project:q\n" + self.history,
            encoding="utf-8",
        )

    def run_review(self, *options, temporal=True):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        original = self.path.read_bytes(), self.config_path.read_bytes()
        argv = ["review", str(self.path)]
        if temporal:
            argv += [
                "--temporal",
                "--since",
                "2026-06-01",
                "--until",
                "2026-06-30",
                "--project",
                "p",
            ]
        result = entrypoint.main(argv + list(options))
        self.assertEqual(
            (self.path.read_bytes(), self.config_path.read_bytes()), original
        )
        return result

    def assert_period_and_counts(self, result):
        self.assertEqual(result["schema"], "temporal-life-review-v1")
        self.assertEqual(
            result["period"],
            {
                "since": "2026-06-01T00:00:00+00:00",
                "until": "2026-06-30T23:59:59.999999+00:00",
            },
        )
        self.assertEqual(
            result["counts"],
            {
                "events": 2,
                "changed": 0,
                "completed": 1,
                "reopened_or_rescheduled": 0,
                "carry_forward": 1,
            },
        )
        self.assertEqual([row["target_id"] for row in result["completed"]], ["done"])
        self.assertEqual(result["carry_forward"], [{"id": "open", "title": "Open"}])
        self.assertEqual(self.stderr.getvalue(), "")

    def test_json_and_jsonl_keep_real_builder_data_and_compact_output(self):
        for fmt, pretty in (("json", False), ("jsonl", False), ("jsonl", True)):
            with self.subTest(format=fmt, pretty=pretty):
                self.assertEqual(
                    self.run_review("--format", fmt, *(["--pretty"] if pretty else [])),
                    0,
                )
                output = self.stdout.getvalue()
                self.assertEqual(len(output.splitlines()), 1)
                self.assert_period_and_counts(json.loads(output))

    def test_pretty_json_retains_same_data(self):
        self.assertEqual(self.run_review("--format", "json", "--pretty"), 0)
        output = self.stdout.getvalue()
        self.assertGreater(len(output.splitlines()), 1)
        self.assertIn('\n  "schema":', output)
        self.assert_period_and_counts(json.loads(output))

    def test_text_displays_period_counts_and_limitations(self):
        self.assertEqual(self.run_review(), 0)
        output = self.stdout.getvalue()
        self.assertIn(
            "Temporal Life Review: 2026-06-01T00:00:00+00:00 .. 2026-06-30T23:59:59.999999+00:00",
            output,
        )
        self.assertIn("  events: 2\n", output)
        self.assertIn("  completed: 1\n", output)
        self.assertIn("  carry forward: 1\n", output)
        self.assertIn("  Limitations:", output)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_complete_history_text_has_no_limitations_line(self):
        self.path.write_text(
            "[x] T Done id:done project:p\n" + self.history, encoding="utf-8"
        )
        self.assertEqual(self.run_review(), 0)
        self.assertIn("  completed: 1\n", self.stdout.getvalue())
        self.assertNotIn("Limitations:", self.stdout.getvalue())
        self.assertEqual(self.stderr.getvalue(), "")

    def test_adapter_forwards_bounds_project_limit_and_configured_id_key(self):
        self.config_path.write_text(
            '{"defaults": {"timezone": "UTC"}, "ids": {"key": "uid"}}', encoding="utf-8"
        )
        with mock.patch(
            "lifetxt.temporal_review.build_temporal_review", wraps=build_temporal_review
        ) as builder:
            self.assertEqual(self.run_review("--format", "json", "--limit", "1"), 0)
        builder.assert_called_once()
        self.assertEqual(
            builder.call_args.kwargs,
            {
                "since": "2026-06-01",
                "until": "2026-06-30",
                "week": False,
                "limit": 1,
                "project": "p",
                "id_key": "uid",
            },
        )
        self.assertEqual(
            [item.title for item in builder.call_args.args[0]][:3],
            ["Done", "Open", "Other"],
        )
        self.assertEqual(self.stderr.getvalue(), "")

    def test_week_adapter_forwards_week_and_uses_frozen_date(self):
        with mock.patch(
            "lifetxt.temporal_review.build_temporal_review", wraps=build_temporal_review
        ) as builder:
            self.assertEqual(
                self.run_review(
                    "--temporal", "--week", "--format", "json", temporal=False
                ),
                0,
            )
        self.assertEqual(
            builder.call_args.kwargs,
            {
                "since": None,
                "until": None,
                "week": True,
                "limit": 100,
                "project": None,
                "id_key": "id",
            },
        )
        result = json.loads(self.stdout.getvalue())
        self.assertEqual(result["period"]["since"], "2026-06-29T00:00:00+00:00")
        self.assertEqual(result["period"]["until"], "2026-07-05T23:59:59.999999+00:00")
        self.assertEqual(self.stderr.getvalue(), "")

    def test_real_limit_bounds_events_and_reports_truncation(self):
        self.assertEqual(self.run_review("--format", "json", "--limit", "1"), 0)
        result = json.loads(self.stdout.getvalue())
        self.assertEqual(result["counts"]["events"], 1)
        self.assertEqual(result["counts"]["completed"], 0)
        self.assertEqual(result["event_counts"], {"created": 1})
        self.assertIn("event_limit_truncated", result["limitations"])
        self.assertEqual(self.stderr.getvalue(), "")

    def test_week_conflict_uses_public_error_contract(self):
        self.assert_error(
            self.run_review("--week"), "--week cannot be combined with --since/--until."
        )

    def test_legacy_invalid_month_and_dates_use_public_error_contract(self):
        for option, value, label, guidance in (
            ("--month", "2026/06", "month", "YYYY-MM"),
            ("--from", "2026-02-30", "from date", "YYYY-MM-DD"),
            ("--to", "bad", "to date", "YYYY-MM-DD"),
        ):
            with self.subTest(option=option):
                self.assert_error(
                    self.run_review(option, value, temporal=False),
                    "Invalid %s %r. Use %s." % (label, value, guidance),
                )
