"""Calendar navigation preserves adjacent periods around month boundaries."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class CalendarNavigationTests(unittest.TestCase):
    def test_month_end_clamps_and_week_navigation_stays_seven_days(self):
        start = HTML_PAGE.index("const CAL_MODES")
        end = HTML_PAGE.index("function calToday()", start)
        fmt_start = HTML_PAGE.index("function _fmtDate(d)")
        fmt_end = HTML_PAGE.index("\n    }", fmt_start) + len("\n    }")
        script = (
            HTML_PAGE[start:end]
            + HTML_PAGE[fmt_start:fmt_end]
            + """
const assert = require("node:assert/strict");
const location = {pathname: "/", search: ""};
const query = () => new URLSearchParams(location.search);
const history = {
  replaceState: (_state, _title, url) => { location.search = new URL(url, "http://localhost").search; }
};
let loaded = [];
const loadCalendar = () => loaded.push(_fmtDate(calAnchor));

for (const [mode, start, delta, expected] of [
  ["month", "2026-01-31", 1, ["2026-02-28", "2026-03-28"]],
  ["month", "2026-03-31", -1, ["2026-02-28", "2026-01-28"]],
  ["month", "2028-01-31", 1, ["2028-02-29"]],
  ["month", "2026-12-31", 1, ["2027-01-31"]],
  ["month", "2026-01-31", -1, ["2025-12-31"]],
  ["month", "2026-05-15", 1, ["2026-06-15"]],
  ["week", "2026-01-31", 1, ["2026-02-07"]],
  ["week", "2026-03-01", -1, ["2026-02-22"]],
]) {
  calAnchor = _calParseAnchor(start);
  calMode = mode;
  location.search = "?view=calendar&lang=ja";
  loaded = [];
  for (const date of expected) {
    _calExpandedDays.add(_fmtDate(calAnchor));
    calShift(delta);
    assert.equal(query().get("cal"), date, `${mode}: ${start}, shift ${delta}`);
    assert.equal(query().get("calmode"), mode);
    assert.equal(query().get("view"), "calendar");
    assert.equal(query().get("lang"), "ja");
    assert.equal(_calExpandedDays.size, 0);
  }
  assert.deepEqual(loaded, expected);
}
"""
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
