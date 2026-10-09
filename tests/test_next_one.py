"""Public CLI regression coverage for the opt-in single next action."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import datetime
import io

from lifetxt import extra_cli
from lifetxt.command_center import command_center
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line
from tests.test_lifetxt import run_cli


class NextOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.write("life.txt", '[ ] T "日本語 task" id:t1 custom:"a b"\n')

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_one(self, *flags, path=None):
        return run_cli("next", path or self.path, "--one", *flags)

    def assert_success(self, result):
        out, err, code = result
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        return out

    def test_one_record_is_canonical_round_trippable_and_json_locates_it(self):
        text = self.assert_success(self.run_one())
        items, diagnostics = parse_text(text)
        self.assertEqual(len(items), 1)
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        self.assertEqual(items[0].details["custom"], ["a b"])
        self.assertEqual(text, item_to_line(items[0]) + "\n")
        for flags in (("--json",), ("--format", "json"), ("--json", "--pretty")):
            with self.subTest(flags=flags):
                result = json.loads(self.assert_success(self.run_one(*flags)))
                self.assertEqual(
                    result,
                    {
                        "item": text.rstrip("\n"),
                        "source": os.path.abspath(self.path),
                        "line": 1,
                    },
                )

    def test_empty_and_non_actionable_are_successful_empty_results(self):
        for fixture in (
            "",
            "# comment only\n",
            "[x] T Done\n[-] T Cancelled\n[?] T Parked\n[>] T Moved\n[ ] E Meeting on:2026-10-09\n[ ] T Waiting tag:waiting\n[ ] T Maybe tag:maybe\n[ ] T Someday tag:someday\n[ ] T Blocked tag:blocked\n[ ] T Dangling depends_on:missing\n",
        ):
            with self.subTest(fixture=fixture):
                Path(self.path).write_text(fixture, encoding="utf-8")
                self.assertEqual(self.assert_success(self.run_one()), "")
                self.assertEqual(self.assert_success(self.run_one("--json")), "null\n")

    def test_multiple_candidates_match_legacy_first_without_changing_list(self):
        Path(self.path).write_text(
            "[ ] T Low id:low priority:C due:2000-01-01\n[ ] T High id:high priority:A due:2099-01-01\n[ ] T Middle id:mid priority:B\n",
            encoding="utf-8",
        )
        for rank in ((), ("--rank",)):
            with self.subTest(rank=rank):
                legacy = json.loads(
                    self.assert_success(
                        run_cli("next", self.path, "--format", "json", *rank)
                    )
                )
                self.assertEqual(len(legacy), 3)
                selected = json.loads(
                    self.assert_success(self.run_one("--json", *rank))
                )
                item = parse_text(selected["item"])[0][0]
                self.assertEqual(item.details["id"][0], legacy[0]["id"])
                self.assertEqual(item.details["id"][0], "low" if rank else "high")
        table = self.assert_success(run_cli("next", self.path))
        self.assertIn("TITLE", table)
        self.assertIn("Middle", table)

    def test_ties_use_created_then_line_then_input_order(self):
        Path(self.path).write_text(
            "[ ] T Later priority:A created:2026-10-08\n[ ] T First priority:A created:2026-10-01\n[ ] T Second priority:A created:2026-10-01\n",
            encoding="utf-8",
        )
        self.assertIn("First", self.assert_success(self.run_one()))
        other = self.write("other.txt", "[ ] T Other priority:A created:2026-10-01\n")
        first = self.write(
            "first.txt", "[ ] T InputFirst priority:A created:2026-10-01\n"
        )
        for paths, title in (((first, other), "InputFirst"), ((other, first), "Other")):
            self.assertIn(title, self.assert_success(run_cli("next", *paths, "--one")))

    def test_dependencies_resolve_across_files_without_adding_other_sources(self):
        Path(self.path).write_text(
            "[ ] T Child id:child depends_on:parent\n", encoding="utf-8"
        )
        parent = self.write("parent.txt", "[?] T Parent id:parent\n")
        self.assertEqual(self.assert_success(self.run_one()), "")
        self.assertEqual(
            self.assert_success(run_cli("next", self.path, parent, "--one")), ""
        )
        Path(parent).write_text("[x] T Parent id:parent\n", encoding="utf-8")
        self.assertIn(
            "Child", self.assert_success(run_cli("next", self.path, parent, "--one"))
        )

    def test_existing_filters_and_actionable_kinds_are_preserved(self):
        for kind in ("T", "D", "R", "H"):
            with self.subTest(kind=kind):
                Path(self.path).write_text(
                    f"[ ] T Other priority:A project:other\n[/] {kind} Chosen project:work assignee:me context:desk\n",
                    encoding="utf-8",
                )
                self.assertIn(
                    "Chosen",
                    self.assert_success(
                        self.run_one(
                            "--project", "work", "--user", "me", "--context", "desk"
                        )
                    ),
                )
                self.assertEqual(
                    self.assert_success(self.run_one("--user", "someone_else")), ""
                )

    def test_stdin_and_record_without_id(self):
        row = json.loads(
            self.assert_success(
                run_cli("next", "-", "--one", "--json", input_text="[ ] T NoID\n")
            )
        )
        self.assertEqual(row, {"item": "[ ] T NoID", "source": "-", "line": 1})

    def test_malformed_missing_and_unreadable_input_do_not_return_empty_success(self):
        broken = self.write("broken.txt", "not a life.txt record\n")
        for source in (broken, str(self.root / "missing.txt"), str(self.root)):
            for flags in ((), ("--json",)):
                with self.subTest(source=source, flags=flags):
                    out, err, code = run_cli("next", source, "--one", *flags)
                    self.assertEqual(code, 1)
                    self.assertEqual(out, "")
                    self.assertIn("ERROR", err)
        out, err, code = run_cli("next", self.path, broken, "--one", "--json")
        self.assertEqual((out, code), ("", 1))
        self.assertIn("parse errors", err)

    def test_invalid_rank_date_keeps_existing_error_behavior(self):
        Path(self.path).write_text("[ ] T Bad due:not-a-date\n", encoding="utf-8")
        self.assertIn("Bad", self.assert_success(self.run_one()))
        out, err, code = self.run_one("--rank", "--json")
        self.assertEqual((out, code), ("", 1))
        self.assertIn("invalid due date", err)

    def test_incompatible_flags_are_usage_errors_and_cannot_overwrite_input(self):
        for flags in (
            ("--why",),
            ("--limit", "1"),
            ("-o", self.path),
            ("--output", self.path),
            ("--json", "--format", "life"),
        ):
            with self.subTest(flags=flags):
                before = Path(self.path).read_bytes()
                out, err, code = self.run_one(*flags)
                self.assertEqual((out, code), ("", 2))
                self.assertIn("error:", err)
                self.assertEqual(Path(self.path).read_bytes(), before)
        out, err, code = run_cli("next", self.path, "--json")
        self.assertEqual((out, code), ("", 2))
        self.assertIn("requires --one", err)

    def test_workspace_default_explicit_override_and_archives_are_scoped_read_only(
        self,
    ):
        archive = self.write("archive.txt", "[ ] T Archive priority:A\n")
        work = self.write("work.txt", "[ ] T Work priority:A\n")
        config = self.write(
            "config.json",
            json.dumps(
                {
                    "config_version": 1,
                    "default_workspace": "personal",
                    "workspaces": {
                        "personal": {
                            "sources": [
                                {"path": "life.txt", "role": "primary"},
                                {"path": "archive.txt", "role": "archive"},
                            ]
                        },
                        "work": {"sources": [{"path": "work.txt", "role": "primary"}]},
                    },
                }
            ),
        )
        files = [Path(self.path), Path(archive), Path(work), Path(config)]
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
        names = set(self.root.iterdir())
        for flags, title in (
            ((), "日本語 task"),
            (("--workspace", "work"), "Work"),
            (("--workspace", "work", self.path), "日本語 task"),
        ):
            row = json.loads(
                self.assert_success(
                    run_cli(
                        "--config",
                        config,
                        "next",
                        "--one",
                        "--json",
                        *flags,
                        cwd=str(self.root),
                    )
                )
            )
            self.assertIn(title, row["item"])
            self.assertNotIn("Archive", row["item"])
        self.assertEqual(set(self.root.iterdir()), names)
        self.assertEqual(
            {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}, before
        )

    def test_default_life_txt_and_legacy_config_paths(self):
        self.assertIn(
            "日本語 task",
            self.assert_success(run_cli("next", "--one", cwd=str(self.root))),
        )
        config = self.write("legacy.json", json.dumps({"paths": [self.path]}))
        self.assertIn(
            "日本語 task",
            self.assert_success(run_cli("--config", config, "next", "--one")),
        )
        broken = self.write("invalid.json", "{")
        out, err, code = run_cli("--config", broken, "next", "--one", "--json")
        self.assertEqual((out, code), ("", 1))
        self.assertIn("ERROR", err)

    def test_rank_resolves_workspace_timezone(self):
        Path(self.path).write_text(
            "[ ] T High priority:A due:2026-10-10\n[ ] T Low priority:C due:2026-10-09\n",
            encoding="utf-8",
        )
        config = self.write(
            "timezone.json", json.dumps({"defaults": {"timezone": "Asia/Tokyo"}})
        )
        from lifetxt.timezone_policy import current_timezone_name

        def today_in_context():
            self.assertEqual(current_timezone_name(), "Asia/Tokyo")
            return datetime.date(2026, 10, 10)

        output = io.StringIO()
        with (
            patch("lifetxt.extra_core.timezone_today", side_effect=today_in_context),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(
                extra_cli.main(
                    ["next", self.path, "--one", "--rank"], config_path=config
                ),
                0,
            )
        self.assertIn("Low", output.getvalue())

    def test_cli_order_intentionally_differs_from_today_order(self):
        text = "[ ] T CliFirst priority:B\n[ ] T TodayFirst priority:high\n"
        Path(self.path).write_text(text, encoding="utf-8")
        self.assertIn("CliFirst", self.assert_success(self.run_one()))
        items, _ = parse_text(text)
        self.assertEqual(
            command_center(items)["next_actions"][0]["title"], "TodayFirst"
        )


if __name__ == "__main__":
    unittest.main()
