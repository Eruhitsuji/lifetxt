import datetime
import unittest

from lifetxt.health import build_health
from lifetxt.parser import parse_text


def _items(text):
    items, _diagnostics = parse_text(text)
    return items


class BuildHealthTests(unittest.TestCase):
    def test_clean_items_produce_no_findings(self):
        items = _items("[x] T Done task\n")
        self.assertEqual(build_health(items, datetime.date(2026, 8, 30)), [])

    def test_w301_stale_open_task(self):
        items = _items("[ ] T Stale task updated:2026-01-01\n")
        findings = build_health(items, datetime.date(2026, 8, 30), since_days=30)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "W301")

    def test_w301_ignored_via_ignore_codes(self):
        items = _items("[ ] T Stale task updated:2026-01-01\n")
        findings = build_health(
            items, datetime.date(2026, 8, 30), since_days=30, ignore_codes=["w301"]
        )
        self.assertEqual(findings, [])

    def test_w303_overdue_task(self):
        items = _items("[ ] T Overdue_task due:2026-01-01\n")
        findings = build_health(items, datetime.date(2026, 8, 30))
        codes = {f["code"] for f in findings}
        self.assertIn("W303", codes)

    def test_kinds_filter_restricts_scan(self):
        items = _items("[ ] T Overdue_task due:2026-01-01\n[ ] H Stale_habit\n")
        findings = build_health(items, datetime.date(2026, 8, 30), kinds=["H"])
        self.assertTrue(findings)
        self.assertTrue(all(f["title"] == "Stale_habit" for f in findings))

    def test_w305_blocked_task(self):
        items = _items("[ ] T Blocker id:b1\n[ ] T Blocked task depends_on:b1\n")
        findings = build_health(items, datetime.date(2026, 8, 30))
        codes = {f["code"] for f in findings}
        self.assertIn("W305", codes)


if __name__ == "__main__":
    unittest.main()
