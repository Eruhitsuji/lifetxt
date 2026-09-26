import datetime
import contextlib
import io
import os
import tempfile
import unittest

from lifetxt.cli import main
from lifetxt.model import Item
from lifetxt.priority_matrix import classify_item, matrix_rows
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

    def test_stable_group_order(self):
        a = self.item("high", "2026-09-26")
        b = self.item("high", "2026-09-26")
        a.title, b.title = "First", "Second"
        self.assertEqual([r["title"] for r in matrix_rows([a, b], self.reference)["Q1"]], ["First", "Second"])

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
