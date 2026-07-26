import json
import os
import tempfile
import unittest

from lifetxt import mcp
from lifetxt.mcp import McpContext
from lifetxt.safety_foundation import capability_document, schema_bundle
from lifetxt.ticket_revision_writes import ticket_file_revision
from lifetxt.ticket_workflow import apply_comment
from lifetxt.ticket_planning_mutation import create_sprint, create_version


SCHEMAS = {
    "ticket-workflow-v1.schema.json",
    "ticket-event-v1.schema.json",
    "ticket-time-entry-v1.schema.json",
    "ticket-activity-v1.schema.json",
    "ticket-version-v1.schema.json",
    "ticket-sprint-v1.schema.json",
    "ticket-planning-v1.schema.json",
}


class TicketWorkflowSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.config = {
            "paths": [self.life],
            "write_file": self.life,
            "user": {"name": "alice"},
            "ticketing": {"activities": ["development", "review"]},
        }
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Bug record:ticket id:BUG-1 tracker:bug "
                "ticket_status:new priority:normal project:web\n"
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def call(self, name, arguments=None):
        context = McpContext(
            paths=[self.life],
            writable_path=self.life,
            config=self.config,
            read_only=True,
        )
        response = mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            },
            context,
        )
        self.assertNotIn("error", response, response)
        return response["result"]["structuredContent"]

    def test_capability_publishes_safe_boundaries(self):
        value = capability_document(config=self.config)
        contract = value["ticket_workflow_history"]
        self.assertEqual("1", contract["contract_version"])
        self.assertTrue(contract["exact_revision_required"])
        self.assertTrue(contract["ticket_event_required"])
        self.assertTrue(contract["events_append_only"])
        self.assertFalse(contract["remote_writes_enabled"])
        self.assertEqual("same authoritative life.txt file", contract["compound_scope"])
        self.assertTrue(SCHEMAS.issubset(set(contract["schemas"])))

    def test_schema_bundle_contains_seventy_five_documents_and_new_contracts(self):
        bundle = schema_bundle()
        self.assertEqual(75, len(bundle))
        self.assertTrue(SCHEMAS.issubset(set(bundle)))
        self.assertIn("activity", bundle["ticket-v1.schema.json"]["properties"])
        self.assertIn("planning", bundle["ticket-v1.schema.json"]["properties"])
        for name in SCHEMAS:
            schema = bundle[name]
            self.assertEqual(
                "https://json-schema.org/draft/2020-12/schema",
                schema["$schema"],
            )
            self.assertTrue(schema["$id"].startswith("https://"))

    def test_mcp_tools_are_read_only_and_return_activity_workflow_planning(self):
        names = {row["name"]: row for row in mcp.tool_schemas()}
        for name in (
            "get_ticket_workflow",
            "get_ticket_activity",
            "get_ticket_time",
            "get_ticket_planning",
            "validate_ticket_history",
            "validate_ticket_planning",
        ):
            self.assertIn(name, names)
            self.assertTrue(names[name]["annotations"]["readOnlyHint"])
            self.assertFalse(names[name]["annotations"]["destructiveHint"])

        workflow = self.call("get_ticket_workflow", {"role": "administrator"})
        self.assertIn("in_progress", workflow["transitions"])

        revision = ticket_file_revision(self.life)
        comment = apply_comment(
            self.life,
            "BUG-1",
            "MCP-visible history",
            "alice",
            revision,
            config=self.config,
            at="2026-07-25T00:00:00Z",
        )
        version = create_version(
            self.life,
            "v1",
            "web",
            comment["revision_after"],
        )
        create_sprint(
            self.life,
            "Sprint 1",
            "web",
            "2026-07-20",
            "2026-08-02",
            version["revision_after"],
            version="VER-1",
        )

        activity = self.call("get_ticket_activity", {"id": "BUG-1"})
        self.assertEqual(1, len(activity["events"]))
        self.assertEqual("comment", activity["events"][0]["event"])

        time_report = self.call("get_ticket_time", {"id": "BUG-1"})
        self.assertEqual(0, time_report["time"]["entry_count"])

        planning = self.call("get_ticket_planning", {"project": "web"})
        self.assertEqual(1, len(planning["versions"]))
        self.assertEqual(1, len(planning["sprints"]))

        self.assertTrue(self.call("validate_ticket_history")["ok"])
        self.assertTrue(self.call("validate_ticket_planning")["ok"])

    def test_ticket_show_view_is_enriched_without_recalculating_history(self):
        revision = ticket_file_revision(self.life)
        apply_comment(
            self.life,
            "BUG-1",
            "History",
            "alice",
            revision,
            config=self.config,
            at="2026-07-25T00:00:00Z",
        )
        ticket = self.call("get_ticket", {"id": "BUG-1"})
        self.assertEqual(1, ticket["activity"]["event_count"])
        self.assertEqual("comment", ticket["activity"]["latest_event"]["event"])
        self.assertEqual(0, ticket["activity"]["time_logged_seconds"])
        self.assertEqual(
            {"version": None, "sprint": None, "story_points": None},
            ticket["planning"],
        )


if __name__ == "__main__":
    unittest.main()
