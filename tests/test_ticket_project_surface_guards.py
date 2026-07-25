import unittest
from datetime import datetime, timezone

from lifetxt.parser import parse_text
from lifetxt.ticket_project_surfaces import (
    build_configured_ticket_project_report,
    effective_stale_after_days,
)


class TicketProjectSurfaceGuardTests(unittest.TestCase):
    def test_invalid_stale_configuration_fails_loudly(self):
        for value in (True, -1, "not-a-number"):
            config = {"ticketing": {"report": {"stale_after_days": value}}}
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    effective_stale_after_days(config)

    def test_alias_normalization_does_not_mutate_authoritative_items(self):
        items, diagnostics = parse_text(
            "[ ] T Alias_ticket record:ticket id:TK-1 ticket_status:new project:website\n"
        )
        self.assertFalse([row for row in diagnostics if row.severity == "error"])
        original_project = list(items[0].details["project"])
        report = build_configured_ticket_project_report(
            items,
            config={"projects": {"web": {"aliases": ["website"]}}},
            project="web",
            reference_time=datetime(2026, 7, 25, tzinfo=timezone.utc),
        )
        self.assertEqual(["website"], original_project)
        self.assertEqual(["website"], items[0].details["project"])
        self.assertEqual("web", report["tickets"][0]["project"])


if __name__ == "__main__":
    unittest.main()
