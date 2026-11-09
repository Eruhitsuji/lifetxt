"""Verify Calendar's repeat marker against records from the real agenda model."""

from datetime import datetime
import json
import shutil
import subprocess
import unittest

from lifetxt.agenda import agenda_records
from lifetxt.parser import parse_text
from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class CalendarRepeatBadgeTests(unittest.TestCase):
    def test_only_recurring_records_receive_the_repeat_marker(self):
        items, diagnostics = parse_text(
            "[ ] E Appointment from:2026-11-09T09:00 to:2026-11-09T10:00\n"
            "[ ] E Conference on:2026-11-09 on:2026-11-10\n"
            "[ ] H Practice repeat:daily at:18:00\n"
        )
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        records = agenda_records(
            items, datetime(2026, 11, 9), datetime(2026, 11, 10, 23, 59)
        )
        by_title = {record["title"]: record for record in records}
        self.assertIn("occurrence_start", by_title["Appointment"])
        self.assertIn("occurrence_start", by_title["Conference"])
        self.assertIn("repeat_rule", by_title["Practice"])
        start = HTML_PAGE.index("function _calRecordDayPlacements")
        end = HTML_PAGE.index("async function loadCalendar", start)
        script = (
            HTML_PAGE[start:end]
            + r"""
const records = JSON.parse(process.argv[1]);
const _temporalDisplayLabel = () => "";
const agendaDueSoonClass = () => "";
const escapeHtml = value => String(value);
const rendered = Object.fromEntries(records.map(record => {
  const placements = _calRecordDayPlacements(record);
  return [record.title, placements.map(({when}, index) =>
    _calEntryHtml(record, when, index + 1, placements.length))];
}));
console.log(JSON.stringify(rendered));
"""
        )
        result = subprocess.run(
            ["node", "-e", script, json.dumps(records)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        rendered = json.loads(result.stdout)
        self.assertEqual(1, len(rendered["Appointment"]))
        self.assertEqual(2, len(rendered["Conference"]))
        self.assertEqual(2, len(rendered["Practice"]))
        for entry in rendered["Appointment"] + rendered["Conference"]:
            self.assertNotIn("↻", entry)
        self.assertIn(">1/2</span>", rendered["Conference"][0])
        self.assertIn(">2/2</span>", rendered["Conference"][1])
        for entry in rendered["Practice"]:
            self.assertIn("↻", entry)
