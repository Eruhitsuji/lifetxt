import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.model import Item
from lifetxt.parser import parse_text
from lifetxt.ticket_planning import (
    build_sprint,
    build_version,
    planning_report,
    validate_planning,
)
from lifetxt.ticket_planning_mutation import (
    assign_planning,
    create_sprint,
    create_version,
    update_planning_state,
)
from lifetxt.ticket_revision_writes import ticket_file_revision


class TicketPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        self.config = {
            "paths": [self.life],
            "write_file": self.life,
            "user": {"name": "alice"},
            "ticketing": {},
        }
        self.write_life(
            "[ ] T Bug record:ticket id:BUG-1 tracker:bug "
            "ticket_status:new priority:high project:web story_points:5\n"
            "[ ] T Feature record:ticket id:FEAT-1 tracker:feature "
            "ticket_status:new priority:normal project:web story_points:8\n"
        )
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self.config, handle)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_life(self, text):
        with open(self.life, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def read_items(self):
        with open(self.life, encoding="utf-8") as handle:
            items, diagnostics = parse_text(
                handle.read(), id_key="id", check_ids=False, check_references=False
            )
        self.assertFalse([d.to_dict() for d in diagnostics if d.severity == "error"])
        return items

    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", self.config_path] + list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_build_and_validate_version_sprint_records(self):
        version = build_version(
            "v1.0", "web", "VER-1", due="2026-08-10", description="First release"
        )
        sprint = build_sprint(
            "Sprint 1",
            "web",
            "SPR-1",
            "2026-07-20",
            "2026-08-02",
            capacity=10,
            version="VER-1",
        )
        rows = validate_planning(self.read_items() + [version, sprint])
        self.assertEqual([], rows)

    def test_create_version_sprint_and_assign_membership_with_event(self):
        revision = ticket_file_revision(self.life)
        version = create_version(
            self.life,
            "v1.0",
            "web",
            revision,
            due="2026-08-10",
            key="id",
        )
        self.assertEqual("VER-1", version["record"]["details"]["id"][0])

        sprint = create_sprint(
            self.life,
            "Sprint 1",
            "web",
            "2026-07-20",
            "2026-08-02",
            version["revision_after"],
            capacity=10,
            version="VER-1",
            key="id",
        )
        self.assertEqual("SPR-1", sprint["record"]["details"]["id"][0])

        planned = assign_planning(
            self.life,
            "BUG-1",
            sprint["revision_after"],
            "alice",
            sprint="SPR-1",
            config=self.config,
            at="2026-07-25T00:00:00Z",
            key="id",
        )
        self.assertEqual("sprint_assigned", planned["event"]["event"])
        report = planning_report(self.read_items(), project="web", config=self.config)
        self.assertEqual(["BUG-1"], report["versions"][0]["ticket_ids"])
        self.assertEqual(["BUG-1"], report["sprints"][0]["ticket_ids"])
        self.assertEqual(["FEAT-1"], [row["id"] for row in report["backlog"]])
        self.assertEqual([], report["sprints"][0]["warnings"])

    def test_capacity_warning_and_close_guard(self):
        revision = ticket_file_revision(self.life)
        version = create_version(self.life, "v1", "web", revision)
        sprint = create_sprint(
            self.life,
            "Sprint",
            "web",
            "2026-07-20",
            "2026-08-02",
            version["revision_after"],
            capacity=4,
        )
        planned = assign_planning(
            self.life,
            "BUG-1",
            sprint["revision_after"],
            "alice",
            sprint="SPR-1",
            config=self.config,
            at="2026-07-25T00:00:00Z",
        )
        report = planning_report(self.read_items(), project="web", config=self.config)
        self.assertIn("story_points_exceed_capacity", report["sprints"][0]["warnings"])

        before = ticket_file_revision(self.life)
        with self.assertRaises(ValueError):
            update_planning_state(
                self.life,
                "SPR-1",
                "sprint",
                "closed",
                before,
            )
        self.assertEqual(before, ticket_file_revision(self.life))
        closed = update_planning_state(
            self.life,
            "SPR-1",
            "sprint",
            "closed",
            before,
            force=True,
        )
        self.assertEqual("closed", closed["record"]["details"]["state"][0])
        report = planning_report(self.read_items(), project="web", config=self.config)
        self.assertIn("closed_with_open_tickets", report["sprints"][0]["warnings"])

    def test_invalid_references_and_conflicting_membership_are_diagnostic(self):
        items = self.read_items()
        version = build_version("v1", "web", "VER-1")
        sprint = build_sprint(
            "Sprint", "web", "SPR-1", "2026-07-20", "2026-08-02", version="VER-2"
        )
        items[0].details["version"] = ["VER-1"]
        items[0].details["sprint"] = ["SPR-1"]
        codes = {row["code"] for row in validate_planning(items + [version, sprint])}
        self.assertTrue({"TK050", "TK053"}.issubset(codes))

    def test_clear_membership_keeps_append_only_event(self):
        revision = ticket_file_revision(self.life)
        version = create_version(self.life, "v1", "web", revision)
        first = assign_planning(
            self.life,
            "BUG-1",
            version["revision_after"],
            "alice",
            version="VER-1",
            config=self.config,
            at="2026-07-25T00:00:00Z",
        )
        second = assign_planning(
            self.life,
            "BUG-1",
            first["revision_after"],
            "alice",
            clear_version=True,
            config=self.config,
            at="2026-07-25T00:01:00Z",
        )
        self.assertEqual("field_change", second["event"]["event"])
        with open(self.life, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(2, text.count("record:ticket_event"))
        ticket = next(
            item
            for item in self.read_items()
            if "ticket" in item.details.get("record", [])
        )
        self.assertNotIn("version", ticket.details)

    def test_version_release_guard_and_project_membership_scope(self):
        revision = ticket_file_revision(self.life)
        version = create_version(self.life, "v1", "web", revision)
        assigned = assign_planning(
            self.life,
            "BUG-1",
            version["revision_after"],
            "alice",
            version="VER-1",
            config=self.config,
            at="2026-07-25T00:00:00Z",
        )
        with self.assertRaises(ValueError):
            update_planning_state(
                self.life,
                "VER-1",
                "version",
                "released",
                assigned["revision_after"],
            )
        released = update_planning_state(
            self.life,
            "VER-1",
            "version",
            "released",
            assigned["revision_after"],
            force=True,
        )
        self.assertEqual("released", released["record"]["details"]["state"][0])
        report = planning_report(self.read_items(), project="web", config=self.config)
        self.assertIn("released_with_open_tickets", report["versions"][0]["warnings"])

        current = ticket_file_revision(self.life)
        other = create_version(
            self.life,
            "other",
            "mobile",
            current,
            identifier="VER-MOBILE",
        )
        with self.assertRaises(ValueError):
            assign_planning(
                self.life,
                "BUG-1",
                other["revision_after"],
                "alice",
                version="VER-MOBILE",
                config=self.config,
                at="2026-07-25T00:01:00Z",
            )
        self.assertEqual(other["revision_after"], ticket_file_revision(self.life))

    def test_cli_version_sprint_plan_backlog_and_roadmap(self):
        revision = ticket_file_revision(self.life)
        code, stdout, stderr = self.run_cli(
            [
                "version",
                "new",
                "v1.0",
                "--project",
                "web",
                "--due",
                "2026-08-10",
                "--revision",
                revision,
                "--json",
            ]
        )
        self.assertEqual(0, code, stderr)
        version = json.loads(stdout)
        self.assertEqual("VER-1", version["record"]["details"]["id"][0])

        code, stdout, stderr = self.run_cli(
            [
                "sprint",
                "new",
                "Sprint 1",
                "--project",
                "web",
                "--start",
                "2026-07-20",
                "--end",
                "2026-08-02",
                "--version",
                "VER-1",
                "--capacity",
                "10",
                "--revision",
                version["revision_after"],
                "--json",
            ]
        )
        self.assertEqual(0, code, stderr)
        sprint = json.loads(stdout)

        code, stdout, stderr = self.run_cli(
            [
                "ticket",
                "plan",
                "BUG-1",
                "--sprint",
                "SPR-1",
                "--revision",
                sprint["revision_after"],
                "--at",
                "2026-07-25T00:00:00Z",
                "--json",
            ]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("sprint_assigned", json.loads(stdout)["event"]["event"])

        code, stdout, stderr = self.run_cli(
            ["ticket", "roadmap", "--project", "web", "--format", "json"]
        )
        self.assertEqual(0, code, stderr)
        roadmap = json.loads(stdout)
        self.assertEqual(1, len(roadmap["versions"]))
        self.assertEqual(1, len(roadmap["sprints"]))

        code, stdout, stderr = self.run_cli(
            ["ticket", "backlog", "--project", "web", "--format", "json"]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(
            ["FEAT-1"], [row["id"] for row in json.loads(stdout)["backlog"]]
        )


if __name__ == "__main__":
    unittest.main()
