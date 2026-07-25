import json
import unittest
from pathlib import Path
from datetime import datetime, timezone

from lifetxt.ticket_projects import (
    build_ticket_project_report,
    format_attention,
    format_board,
    format_summary,
    parse_datetime,
    parse_duration_hours,
)


class FakeItem(object):
    def __init__(self, status, item_type, title, details=None):
        self.status = status
        self.kind = item_type
        self.title = title
        self.details = details or {}


def ticket(title, ticket_id, project="alpha", ticket_status="open", **details):
    values = {
        "record": ["ticket"],
        "id": [ticket_id],
        "project": [project],
        "ticket_status": [ticket_status],
    }
    for key, value in details.items():
        values[key] = value if isinstance(value, list) else [value]
    coarse = "[x]" if ticket_status in ("closed", "done") else "[ ]"
    return FakeItem(coarse, "T", title, values)


class TicketProjectReportTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)

    def test_filters_non_ticket_tasks_and_builds_project_summary(self):
        items = [
            ticket("Open bug", "T-1", priority="high"),
            ticket("Finished", "T-2", ticket_status="closed"),
            FakeItem("[ ]", "T", "Ordinary task", {"project": ["alpha"]}),
        ]
        report = build_ticket_project_report(items, reference_time=self.now)
        self.assertEqual(report["summary"]["total"], 2)
        self.assertEqual(report["summary"]["open"], 1)
        self.assertEqual(report["summary"]["progress_percent"], 50.0)
        self.assertEqual(report["projects"][0]["by_status"], {"closed": 1, "open": 1})

    def test_attention_categories_are_transparent_and_non_exclusive(self):
        items = [
            ticket(
                "Security blocker",
                "T-1",
                ticket_status="blocked",
                severity="critical",
                due="2026-07-20",
                updated="2026-06-01T00:00:00Z",
            )
        ]
        report = build_ticket_project_report(items, reference_time=self.now, stale_after_days=14)
        row = report["tickets"][0]
        self.assertTrue(row["blocked"])
        self.assertTrue(row["overdue"])
        self.assertTrue(row["unassigned"])
        self.assertTrue(row["high_severity"])
        self.assertTrue(row["stale"])
        self.assertIn("Security blocker", format_attention(report))
        self.assertIn("dependency unknown", format_summary(report))

    def test_date_only_due_is_not_overdue_until_next_utc_midnight(self):
        report = build_ticket_project_report(
            [ticket("Due today", "T-1", due="2026-07-25")], reference_time=self.now
        )
        self.assertFalse(report["tickets"][0]["overdue"])
        after_midnight = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)
        report = build_ticket_project_report(
            [ticket("Due yesterday", "T-1", due="2026-07-25")], reference_time=after_midnight
        )
        self.assertTrue(report["tickets"][0]["overdue"])

    def test_open_dependency_marks_ticket_blocked(self):
        items = [ticket("Dependency", "T-1"), ticket("Dependent", "T-2", depends_on="T-1")]
        report = build_ticket_project_report(items, reference_time=self.now)
        dependent = next(row for row in report["tickets"] if row["id"] == "T-2")
        self.assertTrue(dependent["blocked"])
        self.assertEqual(dependent["unresolved_dependencies"], ["T-1"])
        self.assertFalse(dependent["dependency_unknown"])

    def test_closed_dependency_does_not_block(self):
        items = [
            ticket("Dependency", "T-1", ticket_status="closed"),
            ticket("Dependent", "T-2", depends_on="T-1"),
        ]
        report = build_ticket_project_report(items, reference_time=self.now)
        dependent = next(row for row in report["tickets"] if row["id"] == "T-2")
        self.assertFalse(dependent["blocked"])
        self.assertFalse(dependent["dependency_unknown"])

    def test_missing_dependency_is_reported_without_guessing_blocked_state(self):
        report = build_ticket_project_report(
            [ticket("Dependent", "T-2", depends_on="T-missing")], reference_time=self.now
        )
        row = report["tickets"][0]
        self.assertFalse(row["blocked"])
        self.assertTrue(row["dependency_unknown"])
        self.assertEqual(row["unevaluated_dependencies"], ["T-missing"])
        self.assertEqual(report["summary"]["dependency_unknown"], 1)

    def test_project_filter_is_applied_before_dependency_evaluation(self):
        items = [
            ticket("Other dependency", "T-1", project="beta"),
            ticket("Scoped ticket", "T-2", project="alpha", depends_on="T-1"),
        ]
        report = build_ticket_project_report(items, reference_time=self.now, project="alpha")
        self.assertEqual(report["summary"]["total"], 1)
        self.assertFalse(report["tickets"][0]["blocked"])
        self.assertTrue(report["tickets"][0]["dependency_unknown"])
        self.assertIn("Project filtering occurs before dependency evaluation", " ".join(report["caveats"]))

    def test_estimate_elapsed_coverage_and_variance(self):
        items = [
            ticket("Measured", "T-1", est="1d", elapsed="10h"),
            ticket("Estimate only", "T-2", est="2h"),
            ticket("Invalid", "T-3", est="soon", elapsed="1h"),
        ]
        project = build_ticket_project_report(items, reference_time=self.now)["projects"][0]
        self.assertEqual(project["estimate_hours"], 10.0)
        self.assertEqual(project["estimate_ticket_count"], 2)
        self.assertEqual(project["elapsed_hours"], 11.0)
        self.assertEqual(project["elapsed_ticket_count"], 2)
        self.assertEqual(project["paired_variance_hours"], 2.0)
        self.assertEqual(project["paired_variance_ticket_count"], 1)

    def test_duration_parser_rejects_partial_values(self):
        self.assertEqual(parse_duration_hours("1w 2d 3h 30m"), 59.5)
        self.assertEqual(parse_duration_hours("2.5"), 2.5)
        self.assertIsNone(parse_duration_hours("1h later"))
        self.assertIsNone(parse_duration_hours(""))

    def test_iso_datetime_parser_normalizes_offsets(self):
        parsed = parse_datetime("2026-07-25T21:00:00+09:00")
        self.assertEqual(parsed, self.now)
        self.assertEqual(parse_datetime("2026-07-25"), datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc))
        self.assertIsNone(parse_datetime("tomorrow"))

    def test_board_order_is_deterministic(self):
        items = [
            ticket("Low", "T-2", priority="low"),
            ticket("High", "T-1", priority="high"),
            ticket("Done", "T-3", ticket_status="closed"),
        ]
        report = build_ticket_project_report(items, reference_time=self.now)
        self.assertEqual([row["id"] for row in report["board"]["open"]], ["T-1", "T-2"])
        rendered = format_board(report)
        self.assertLess(rendered.index("## open"), rendered.index("## closed"))

    def test_defaults_follow_ticket_core_statuses_and_severities(self):
        report = build_ticket_project_report([
            ticket("Won't fix", "T-1", ticket_status="wont_fix", severity="critical"),
            ticket("Major", "T-2", severity="major"),
            ticket("Critical", "T-3", severity="critical"),
        ], reference_time=self.now)
        self.assertEqual(report["summary"]["terminal"], 1)
        self.assertEqual(report["summary"]["high_severity"], 1)
        self.assertIn("wont_fix", report["configuration"]["terminal_statuses"])

    def test_terminal_and_severity_sets_are_configurable(self):
        items = [ticket("Released", "T-1", ticket_status="shipped", severity="sev1")]
        report = build_ticket_project_report(
            items,
            reference_time=self.now,
            terminal_statuses=["shipped"],
            high_severities=["sev1"],
        )
        self.assertEqual(report["summary"]["terminal"], 1)
        self.assertEqual(report["summary"]["high_severity"], 0)
        self.assertEqual(report["configuration"]["terminal_statuses"], ["shipped"])

    def test_report_matches_published_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is not installed")
        report = build_ticket_project_report(
            [
                ticket("Open", "T-1", depends_on="missing", est="2h", elapsed="3h"),
                ticket("Closed", "T-2", ticket_status="closed"),
            ],
            reference_time=self.now,
        )
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "ticket-project-report-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(report)

    def test_negative_stale_window_is_rejected(self):
        with self.assertRaises(ValueError):
            build_ticket_project_report([], reference_time=self.now, stale_after_days=-1)

    def test_unassigned_project_bucket(self):
        item = ticket("No project", "T-1")
        item.details.pop("project")
        report = build_ticket_project_report([item], reference_time=self.now)
        self.assertEqual(report["projects"][0]["project"], "(unassigned-project)")


if __name__ == "__main__":
    unittest.main()
