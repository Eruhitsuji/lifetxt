"""Covers #146: the `project archive` workflow.

Moves a project's records to the active workspace's configured archive
source, reusing `command_archive`'s candidate filtering, external-reference
warnings, and transactional multi-file write. Ticket history
(record:ticket_event / record:time_entry Notes) follows its archived parent
ticket unconditionally via `parent:`, even though history has no
done/canceled status of its own.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt import cli


class ProjectArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def read(self, name):
        path = os.path.join(self.root, name)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def config_path(self, data):
        path = os.path.join(self.root, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def run_project_archive(self, argv, config_path):
        return cli.main(["--config", config_path] + argv)

    WORK_TEXT = (
        "[x] T Ticket_one id:t1 project:alpha priority:medium done:2026-01-01\n"
        "[N] N Ticket_event record:ticket_event id:t1_e1 parent:t1 project:alpha "
        "event:created author:local at:2026-01-01T00:00:00Z sequence:1 "
        "transaction:tx1 ticket_revision:1\n"
        "[N] N Ticket_time record:time_entry id:t1_time1 parent:t1 project:alpha "
        "user:local activity:development on:2026-01-01 elapsed:1h sequence:1 "
        "event_id:evt1 created_at:2026-01-01T00:00:00Z\n"
        "[ ] T Ticket_two id:t2 project:alpha priority:high\n"
        "[ ] T Other_project_task id:t3 project:beta priority:low\n"
    )

    def _workspace_config(self):
        self.write("work.life.txt", self.WORK_TEXT)
        return self.config_path(
            OrderedDict(
                (
                    (
                        "workspaces",
                        OrderedDict(
                            (
                                (
                                    "work",
                                    OrderedDict(
                                        (
                                            (
                                                "sources",
                                                [
                                                    {
                                                        "path": "work.life.txt",
                                                        "role": "primary",
                                                    },
                                                    {
                                                        "path": "archive.life.txt",
                                                        "role": "archive",
                                                    },
                                                ],
                                            ),
                                        )
                                    ),
                                ),
                            )
                        ),
                    ),
                    ("default_workspace", "work"),
                )
            )
        )

    def test_archives_matching_project_and_leaves_others(self):
        config = self._workspace_config()
        code = self.run_project_archive(
            ["project", "archive", "alpha", "--yes"], config
        )
        self.assertEqual(0, code)
        remaining = self.read("work.life.txt")
        self.assertNotIn("Ticket_one", remaining)
        self.assertIn("Ticket_two", remaining)
        self.assertIn("Other_project_task", remaining)
        archived = self.read("archive.life.txt")
        self.assertIn("Ticket_one", archived)

    def test_ticket_event_and_time_entry_history_follows_its_archived_ticket(self):
        config = self._workspace_config()
        self.run_project_archive(["project", "archive", "alpha", "--yes"], config)
        remaining = self.read("work.life.txt")
        archived = self.read("archive.life.txt")
        self.assertNotIn("record:ticket_event", remaining)
        self.assertNotIn("record:time_entry", remaining)
        self.assertIn("record:ticket_event", archived)
        self.assertIn("record:time_entry", archived)

    def test_open_project_items_are_not_archived_by_default(self):
        config = self._workspace_config()
        self.run_project_archive(["project", "archive", "alpha", "--yes"], config)
        remaining = self.read("work.life.txt")
        self.assertIn("Ticket_two", remaining)
        archived = self.read("archive.life.txt") or ""
        self.assertNotIn("Ticket_two", archived)

    def test_archive_destination_is_never_scanned_as_a_source(self):
        """Regression: the archive-role file must not appear in the source scan."""
        config = self._workspace_config()
        code = self.run_project_archive(
            ["project", "archive", "alpha", "--yes"], config
        )
        self.assertEqual(0, code)
        code = self.run_project_archive(["project", "archive", "beta", "--yes"], config)
        self.assertEqual(0, code)

    def test_missing_archive_role_source_reports_a_clear_error(self):
        work = self.write(
            "work.life.txt", "[x] T Solo id:s1 project:alpha done:2026-01-01\n"
        )
        config = self.config_path({"paths": [work]})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cli.main(
                ["--config", config, "project", "archive", "alpha", "--yes"]
            )
        self.assertEqual(1, code)
        self.assertIn("archive-role", stderr.getvalue())

    def test_explicit_dest_overrides_workspace_archive_resolution(self):
        work = self.write(
            "work.life.txt", "[x] T Solo id:s1 project:alpha done:2026-01-01\n"
        )
        config = self.config_path({"paths": [work]})
        dest = os.path.join(self.root, "custom-archive.life.txt")
        code = cli.main(
            [
                "--config",
                config,
                "project",
                "archive",
                "alpha",
                "--dest",
                dest,
                "--yes",
            ]
        )
        self.assertEqual(0, code)
        self.assertIn("Solo", self.read("custom-archive.life.txt"))

    def test_dry_run_makes_no_changes(self):
        config = self._workspace_config()
        before = self.read("work.life.txt")
        code = self.run_project_archive(
            ["project", "archive", "alpha", "--dry-run", "--yes"], config
        )
        self.assertEqual(0, code)
        self.assertEqual(before, self.read("work.life.txt"))
        self.assertIsNone(self.read("archive.life.txt"))


if __name__ == "__main__":
    unittest.main()
