import datetime
import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt.cli import main
from lifetxt.model import Item
from lifetxt.priority_matrix import classify_item, matrix_rows, next_transition
from lifetxt.timezone_policy import timezone_context
from lifetxt.validator import validate_item


class PriorityMatrixTests(unittest.TestCase):
    def setUp(self):
        self.zone = timezone_context("Asia/Tokyo")
        self.zone.__enter__()
        self.addCleanup(self.zone.__exit__, None, None, None)
        self.reference = datetime.datetime(2026, 9, 26, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=9)))

    def item(self, importance=None, due=None, status="[ ]"):
        details = {}
        if importance is not None:
            details["importance"] = [importance]
        if due is not None:
            details["due"] = [due]
        return Item(status, "T", "Report", details)

    def test_date_only_due_today_expires_at_end_of_local_day(self):
        item = self.item("high", "2026-09-26")
        self.assertEqual(classify_item(item, self.reference)["urgency"], "high")
        midnight = datetime.datetime(2026, 9, 27, tzinfo=self.reference.tzinfo)
        self.assertEqual(classify_item(item, midnight)["urgency"], "critical")

    def test_exact_boundaries_and_offsets(self):
        deadline = self.reference + datetime.timedelta(hours=24)
        item = self.item("high", deadline.isoformat(timespec="minutes"))
        self.assertEqual(classify_item(item, self.reference)["urgency"], "high")
        self.assertEqual(classify_item(item, self.reference - datetime.timedelta(microseconds=1))["urgency"], "normal")
        deadline = self.reference + datetime.timedelta(days=7)
        item = self.item("normal", deadline.isoformat(timespec="minutes"))
        self.assertEqual(classify_item(item, self.reference)["urgency"], "normal")
        self.assertEqual(classify_item(item, self.reference - datetime.timedelta(microseconds=1))["urgency"], "low")
        offset_due = self.reference.astimezone(datetime.timezone.utc).isoformat(timespec="minutes")
        self.assertEqual(classify_item(self.item("low", offset_due), self.reference)["quadrant"], "Q3")

    def test_missing_invalid_and_inactive(self):
        items = [self.item("high"), self.item(), self.item("bad"), self.item("low", "bad"),
                 self.item("high", status="[x]"), self.item("high", status="[-]"),
                 self.item("high", status="[>]"), self.item("high", status="[?]")]
        groups = matrix_rows(items, self.reference)
        self.assertEqual([len(groups[key]) for key in ("Q1", "Q2", "Q3", "Q4", "unclassified")], [0, 1, 0, 0, 3])
        self.assertEqual(len(matrix_rows(items, self.reference, "Q2")["Q2"]), 1)
        self.assertTrue(any(d.code == "W231" for d in validate_item(items[2])))
        self.assertFalse(any(d.code == "W231" for d in validate_item(items[1])))

    def test_priority_does_not_affect_classification_or_matrix_order(self):
        first = self.item("high", "2026-09-26")
        second = self.item("high", "2026-09-26")
        first.title, second.title = "Lower explicit priority", "Higher explicit priority"
        first.details["priority"] = ["C"]
        second.details["priority"] = ["A"]

        first_result = classify_item(first, self.reference)
        second_result = classify_item(second, self.reference)
        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result["quadrant"], "Q1")
        self.assertEqual(
            [row["title"] for row in matrix_rows([first, second], self.reference)["Q1"]],
            ["Lower explicit priority", "Higher explicit priority"],
        )

    def test_priority_without_valid_importance_remains_unclassified(self):
        item = self.item(due="2026-09-26")
        item.details["priority"] = ["A"]

        result = classify_item(item, self.reference)
        self.assertIsNone(result["importance"])
        self.assertEqual(result["quadrant"], "unclassified")
        self.assertEqual(len(matrix_rows([item], self.reference)["unclassified"]), 1)

    def test_manual_priority_is_included_only_when_requested(self):
        item = self.item("high", "2026-09-26")
        item.details["priority"] = ["A"]

        default_row = matrix_rows([item], self.reference)["Q1"][0]
        detailed_row = matrix_rows(
            [item], self.reference, include_priority=True
        )["Q1"][0]
        self.assertNotIn("priority", default_row)
        self.assertEqual(detailed_row["priority"], "A")
        self.assertEqual(detailed_row["quadrant"], "Q1")

    def test_stable_group_order(self):
        a = self.item("high", "2026-09-26")
        b = self.item("high", "2026-09-26")
        a.title, b.title = "First", "Second"
        self.assertEqual([r["title"] for r in matrix_rows([a, b], self.reference)["Q1"]], ["First", "Second"])

    def test_horizon_moves_important_task_to_q1_at_seven_day_boundary(self):
        item = self.item("high", "2026-10-10")

        transition = next_transition(item, self.reference)

        self.assertEqual(classify_item(item, self.reference)["quadrant"], "Q2")
        self.assertEqual(transition["next_quadrant"], "Q1")
        self.assertEqual(transition["next_at"], "2026-10-03T23:59:59.999999+09:00")

    def test_horizon_moves_nonimportant_task_to_urgent_quadrant(self):
        item = self.item("normal", "2026-10-10")

        transition = next_transition(item, self.reference)

        self.assertEqual(classify_item(item, self.reference)["quadrant"], "Q4")
        self.assertEqual(transition["next_quadrant"], "Q3")

    def test_horizon_is_absent_at_and_after_exact_threshold(self):
        item = self.item("high", "2026-10-10")
        boundary = datetime.datetime.fromisoformat("2026-10-03T23:59:59.999999+09:00")

        self.assertIsNotNone(
            next_transition(item, boundary - datetime.timedelta(microseconds=1))
        )
        self.assertIsNone(next_transition(item, boundary))
        self.assertIsNone(
            next_transition(item, boundary + datetime.timedelta(microseconds=1))
        )

    def test_horizon_handles_timezones_and_no_future_transition(self):
        offset_due = "2026-10-10T12:00:00+00:00"
        item = self.item("high", offset_due)

        transition = next_transition(item, self.reference)

        self.assertEqual(transition["next_at"], "2026-10-03T21:00:00+09:00")
        self.assertIsNone(next_transition(self.item("high"), self.reference))
        self.assertIsNone(
            next_transition(self.item("high", "2026-09-20"), self.reference)
        )
        self.assertIsNone(next_transition(self.item("high", "bad"), self.reference))

    def test_horizon_is_unclassified_for_invalid_importance_and_excludes_inactive(self):
        items = [
            self.item("invalid", "2026-10-10"),
            self.item("high", "2026-10-10", status="[x]"),
            self.item("high", "2026-10-10", status="[-]"),
        ]

        self.assertIsNone(next_transition(items[0], self.reference))
        groups = matrix_rows(items, self.reference, include_horizon=True)
        self.assertEqual(len(groups["unclassified"]), 1)
        self.assertIsNone(groups["unclassified"][0]["next_at"])
        self.assertEqual(sum(map(len, groups.values())), 1)

    def test_horizon_is_opt_in_in_matrix_rows_and_cli(self):
        from lifetxt.timezone_policy import clock_context

        item = self.item("high", "2026-10-10")
        default_row = matrix_rows([item], self.reference)["Q2"][0]
        horizon_row = matrix_rows([item], self.reference, include_horizon=True)["Q2"][0]
        self.assertNotIn("next_at", default_row)
        self.assertEqual(horizon_row["next_quadrant"], "Q1")

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            content = '[ ] T "Submit report" importance:high due:2026-10-10\n'
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            output = io.StringIO()
            with clock_context(self.reference), contextlib.redirect_stdout(output):
                code = main(["list", "--horizon", path])
            self.assertEqual(code, 0)
            self.assertIn("Q1 in 7 days (2026-10-03)", output.getvalue())
            output = io.StringIO()
            with clock_context(self.reference), contextlib.redirect_stdout(output):
                code = main(["list", "--horizon", "--json", path])
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["Q2"][0]["next_quadrant"], "Q1")
            self.assertEqual(
                payload["Q2"][0]["next_at"],
                "2026-10-03T23:59:59.999999+09:00",
            )
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), content)

    def test_cli_groups_and_filters_without_rewriting_source(self):
        from lifetxt.timezone_policy import clock_context

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            content = '[ ] T "Submit report" importance:high due:2026-09-26\n[x] T Finished importance:high due:2026-09-26\n'
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            output = io.StringIO()
            with clock_context(self.reference), contextlib.redirect_stdout(output):
                code = main(["list", "--matrix", "--quadrant", "Q1", path])
            self.assertEqual(code, 0)
            self.assertIn("Submit report", output.getvalue())
            self.assertNotIn("Finished", output.getvalue())
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), content)


if __name__ == "__main__":
    unittest.main()
