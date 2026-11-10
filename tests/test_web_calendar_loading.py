"""Exercise out-of-order Calendar responses using the assembled Web UI."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class CalendarLoadingTests(unittest.TestCase):
    def test_only_latest_request_can_render(self):
        start = HTML_PAGE.index("const CAL_MODES")
        end = HTML_PAGE.index("// ── Fullscreen", start)
        fmt_start = HTML_PAGE.index("function _fmtDate(d)")
        fmt_end = HTML_PAGE.index("\n    }", fmt_start) + len("\n    }")
        script = (
            HTML_PAGE[start:end]
            + HTML_PAGE[fmt_start:fmt_end]
            + """
const assert = require("node:assert/strict");
const grid = {innerHTML: ""};
const title = {textContent: ""};
const document = {
  getElementById: id => ({"calendar": grid, "cal-title": title})[id],
  querySelectorAll: () => [],
};
const appConfig = {};
let params;
const query = () => params;
const firstParam = (p, [key], fallback) => p.get(key) ?? fallback;
const escapeHtml = value => String(value);
const guidedEmptyState = (_icon, heading) => heading;
const _temporalDisplayLabel = () => "";
const agendaDueSoonClass = () => "";
const requests = [];
const api = url => new Promise((resolve, reject) => requests.push({url, resolve, reject}));
function startLoad(date, mode) {
  params = new URLSearchParams({cal: date, calmode: mode});
  const done = loadCalendar();
  return {...requests.shift(), done};
}
const records = (title, when) => ({records: [{title, when, type: "E"}]});

async function main() {
  const old = startLoad("2026-01-31", "month");
  const oldError = startLoad("2026-02-01", "month");
  const latest = startLoad("2026-03-04", "week");
  assert.match(latest.url, /from=2026-03-02&to=2026-03-08/);
  latest.resolve(records("Current appointment", "2026-03-04"));
  await latest.done;
  assert.match(grid.innerHTML, /cal-mode-week/);
  assert.match(grid.innerHTML, /Current appointment/);
  assert.match(title.textContent, /^Week of /);
  const currentGrid = grid.innerHTML;

  old.resolve(records("Old appointment", "2026-01-31"));
  await old.done;
  assert.equal(grid.innerHTML, currentGrid, "older success must not overwrite the current grid");
  oldError.reject(new Error("old failure"));
  await oldError.done;
  assert.equal(grid.innerHTML, currentGrid, "older error must not replace the current grid");

  const oldEmpty = startLoad("2026-02-01", "month");
  const currentError = startLoad("2026-03-04", "week");
  currentError.reject(new Error("current failure"));
  await currentError.done;
  assert.match(grid.innerHTML, /Calendar error: current failure/);
  oldEmpty.resolve({records: []});
  await oldEmpty.done;
  assert.match(grid.innerHTML, /Calendar error: current failure/);

  const recovery = startLoad("2026-03-04", "week");
  recovery.resolve({records: []});
  await recovery.done;
  assert.equal(grid.innerHTML, "Nothing scheduled in this period");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
"""
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
