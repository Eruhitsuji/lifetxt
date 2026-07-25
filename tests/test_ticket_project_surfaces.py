import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone

from lifetxt import entrypoint, mcp
from lifetxt.mcp import McpContext
from lifetxt.parser import parse_text
from lifetxt.projects import portfolio, project_hub
from lifetxt.safety_foundation import capability_document
from lifetxt.ticket_project_surfaces import (
    build_configured_ticket_project_report,
    effective_high_severities,
    effective_stale_after_days,
    effective_terminal_statuses,
)


CONFIG = {
    "projects": {
        "web": {
            "display_name": "Website",
            "aliases": ["website"],
        }
    },
    "ticketing": {
        "statuses": {
            "shipped": {"life_status": "[x]"},
        },
        "high_severities": ["major"],
        "report": {"stale_after_days": 7},
    },
}

SAMPLE = """#! timezone: UTC
[N] N Website record:project project:web state:active
[ ] T Login_race record:ticket id:BUG-1 tracker:bug ticket_status:new priority:high severity:major assignee:alice project:web due:2026-07-20 updated:2026-07-01T00:00:00Z est:8h elapsed:10h
[x] T Released_theme record:ticket id:BUG-2 tracker:feature ticket_status:shipped priority:normal severity:minor assignee:bob project:website updated:2026-07-24T00:00:00Z est:4h elapsed:4h
[ ] T Plain_task id:T-1 project:web
"""


class TicketProjectSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.items, diagnostics = parse_text(SAMPLE)
        self.assertFalse([row for row in diagnostics if row.severity == "error"])
        self.reference = datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)

    def test_effective_configuration_uses_ticket_registry(self):
        self.assertIn("shipped", effective_terminal_statuses(CONFIG))
        self.assertEqual(("major",), effective_high_severities(CONFIG))
        self.assertEqual(7, effective_stale_after_days(CONFIG))

    def test_configured_report_canonicalizes_project_aliases(self):
        report = build_configured_ticket_project_report(
            self.items,
            config=CONFIG,
            project="website",
            reference_time=self.reference,
        )
        self.assertEqual("web", report["scope"]["project"])
        self.assertEqual(2, report["summary"]["total"])
        self.assertEqual(1, report["summary"]["terminal"])
        self.assertEqual(1, report["summary"]["high_severity"])
        self.assertEqual(1, report["summary"]["overdue"])
        self.assertEqual(7, report["stale_after_days"])
        self.assertEqual({"web"}, {row["project"] for row in report["tickets"]})

    def test_project_hub_embeds_scoped_report(self):
        hub = project_hub(
            self.items,
            CONFIG,
            "website",
            date(2026, 7, 25),
            reference_time=self.reference,
        )
        report = hub["ticket_report"]
        self.assertEqual("ticket-project-report-v1", report["schema"])
        self.assertEqual("web", report["scope"]["project"])
        self.assertEqual(2, report["summary"]["total"])

    def test_portfolio_embeds_global_and_per_project_ticket_results(self):
        result = portfolio(
            self.items,
            CONFIG,
            date(2026, 7, 25),
            reference_time=self.reference,
        )
        self.assertEqual(2, result["ticket_report"]["summary"]["total"])
        web = next(row for row in result["projects"] if row["name"] == "web")
        self.assertEqual(2, web["ticket_summary"]["total"])

    def test_mcp_tools_are_read_only_and_return_shared_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(SAMPLE)
            context = McpContext(
                paths=[path], writable_path=path, config=CONFIG, read_only=True
            )
            names = [row["name"] for row in mcp.tool_schemas()]
            for name in (
                "get_ticket_project_report",
                "get_ticket_board",
                "get_ticket_attention",
            ):
                self.assertIn(name, names)
                schema = next(row for row in mcp.tool_schemas() if row["name"] == name)
                self.assertTrue(schema["annotations"]["readOnlyHint"])

            report = mcp.call_tool(
                "get_ticket_project_report",
                {"project": "website", "at": self.reference.isoformat()},
                context,
            )
            self.assertEqual("ticket-project-report-v1", report["schema"])
            self.assertEqual(2, report["summary"]["total"])
            self.assertIn(
                "ticket_report",
                mcp.call_tool("get_project", {"name": "web"}, context),
            )
            self.assertIn(
                "ticket_report",
                mcp.call_tool("get_portfolio", {}, context),
            )

    def test_capability_discovery_publishes_report_contract(self):
        value = capability_document(config=CONFIG)
        contract = value["ticket_project_report"]
        self.assertEqual("1", contract["contract_version"])
        self.assertEqual("ticket-project-report-v1.schema.json", contract["schema"])
        self.assertTrue(contract["read_only"])
        self.assertEqual(7, contract["configuration"]["stale_after_days"])


class TicketProjectSurfaceCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        self.config_path = os.path.join(self.temp.name, "config.json")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(SAMPLE)
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(CONFIG, handle)

    def tearDown(self):
        self.temp.cleanup()

    def run_command(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_ticket_summary_is_available_in_main_cli(self):
        code, stdout, stderr = self.run_command(
            [
                "--config",
                self.config_path,
                "ticket",
                "summary",
                self.path,
                "--project",
                "website",
                "--at",
                "2026-07-25T00:00:00Z",
                "--format",
                "json",
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual("web", report["scope"]["project"])
        self.assertEqual(2, report["summary"]["total"])

    def test_project_tickets_supports_attention_view_and_json_contract(self):
        code, stdout, stderr = self.run_command(
            [
                "--config",
                self.config_path,
                "project",
                "tickets",
                "website",
                self.path,
                "--view",
                "attention",
                "--at",
                "2026-07-25T00:00:00Z",
                "--format",
                "json",
            ]
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual("ticket-project-report-v1", report["schema"])
        self.assertEqual(1, len(report["attention"]["overdue"]))


if __name__ == "__main__":
    unittest.main()
