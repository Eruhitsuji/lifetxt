import datetime
import unittest
from collections import OrderedDict

from lifetxt.model import Item
from lifetxt.personal_context import (
    context_capsule,
    context_health,
    decision_memory,
    explain_personal_context_item,
)
from lifetxt.timezone_policy import UTC, clock_context, timezone_context


class PersonalContextTests(unittest.TestCase):
    def note(self, title, **details):
        normalized = OrderedDict()
        for key, value in details.items():
            values = value if isinstance(value, (list, tuple)) else [value]
            normalized[key] = [str(entry) for entry in values]
        return Item(status="[ ]", kind="N", title=title, details=normalized)

    def items(self):
        return [
            self.note(
                "Current",
                id="current",
                person="self",
                tag="preference",
                source="user",
                updated="2026-08-20T00:00:00+00:00",
            ),
            self.note(
                "Stale",
                id="stale",
                person="self",
                tag="preference",
                source="user",
                updated="2026-07-01T00:00:00+00:00",
            ),
            self.note(
                "Old",
                id="old",
                person="self",
                tag="preference",
                source="user",
                updated="2026-08-20T00:00:00+00:00",
            ),
            self.note(
                "New",
                id="new",
                person="self",
                tag="preference",
                source="user",
                updated="2026-08-21T00:00:00+00:00",
                corrects="old",
            ),
            self.note(
                "Broken",
                id="broken",
                person="self",
                tag="preference",
                updated="2026-08-22T00:00:00+00:00",
                ref="missing-id",
            ),
            self.note(
                "Decision A",
                id="decision-a",
                person="self",
                tag="decision",
                project="alpha",
                source="user",
                updated="2026-08-23T00:00:00+00:00",
            ),
            self.note(
                "Decision B",
                id="decision-b",
                person="self",
                tag="decision",
                project="beta",
                source="user",
                updated="2026-08-23T00:00:00+00:00",
            ),
        ]

    def clock(self):
        return datetime.datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    def test_health_reports_state_and_quality_findings(self):
        with timezone_context("UTC"), clock_context(self.clock()):
            report = context_health(self.items(), stale_after_days=14)
        self.assertEqual(report["counts"]["total"], 7)
        self.assertEqual(report["counts"]["current"], 5)
        self.assertEqual(report["counts"]["stale"], 1)
        self.assertEqual(report["counts"]["superseded"], 1)
        self.assertEqual(report["counts"]["missing_source"], 1)
        self.assertEqual(report["counts"]["broken_reference"], 1)

    def test_why_explains_correction(self):
        with timezone_context("UTC"), clock_context(self.clock()):
            report = explain_personal_context_item(self.items(), "old")
        self.assertEqual(report["state"], "superseded")
        self.assertEqual(report["corrected_by"][0]["id"], "new")
        link = next(row for row in report["links"] if row["relation"] == "corrects")
        self.assertEqual(link["direction"], "incoming")

    def test_why_rejects_unknown_id(self):
        with self.assertRaisesRegex(ValueError, "Item ID not found"):
            explain_personal_context_item(self.items(), "unknown")

    def test_capsule_is_deterministic_and_filters_lifecycle(self):
        with timezone_context("UTC"), clock_context(self.clock()):
            first = context_capsule(self.items(), stale_after_days=14)
            second = context_capsule(self.items(), stale_after_days=14)
            expanded = context_capsule(
                self.items(), include_stale=True, stale_after_days=14
            )
        self.assertEqual(first["revision"], second["revision"])
        ids = [row["id"] for row in first["items"]]
        self.assertNotIn("old", ids)
        self.assertNotIn("stale", ids)
        self.assertIn("new", ids)
        self.assertIn("stale", [row["id"] for row in expanded["items"]])

    def test_decision_memory_reuses_project_and_tag(self):
        with timezone_context("UTC"), clock_context(self.clock()):
            report = decision_memory(self.items(), project="beta", stale_after_days=14)
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["items"][0]["id"], "decision-b")

    def test_decision_memory_applies_project_before_limit(self):
        with timezone_context("UTC"), clock_context(self.clock()):
            report = decision_memory(
                self.items(), project="beta", limit=1, stale_after_days=14
            )
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["items"][0]["id"], "decision-b")


if __name__ == "__main__":
    unittest.main()
