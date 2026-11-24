"""Exercise out-of-order Calendar responses using the assembled Web UI."""

import os
import shutil
import tempfile
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
        grid_start = HTML_PAGE.index("// ── Calendar time grid")
        grid_end = HTML_PAGE.index("</script>", grid_start)
        script = (
            HTML_PAGE[start:end]
            + HTML_PAGE[fmt_start:fmt_end]
            + HTML_PAGE[grid_start:grid_end]
            + """
const assert = require("node:assert/strict");
let onCalendarClick;
const grid = {innerHTML: "", querySelector: () => ({
  addEventListener: (_type, listener) => { onCalendarClick = listener; },
  style: {setProperty: () => {}}, offsetWidth: 0, clientWidth: 0, scrollTop: 0,
})};
const title = {textContent: ""};
const document = {
  getElementById: id => ({"calendar": grid, "cal-title": title})[id],
  querySelectorAll: () => [],
};
const appConfig = {};
function uiLocale() { return undefined; }
let params;
const query = () => params;
const firstParam = (p, [key], fallback) => p.get(key) ?? fallback;
const escapeHtml = value => String(value);
const t = value => value;
const location = {pathname: "/"};
const history = {replaceState: (_state, _unused, url) => { agendaUrl = new URL(url, "http://localhost"); }, pushState: (_state, _unused, url) => { agendaUrl = new URL(url, "http://localhost"); }};
let agendaUrl;
const applyUrlToControls = () => {};
const loadAgenda = () => {};
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
  assert.match(grid.innerHTML, /cal-tg-week/);
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

  const monthLoad = startLoad("2026-03-04", "month");
  monthLoad.resolve(records("Current appointment", "2026-03-04"));
  await monthLoad.done;
  assert.match(grid.innerHTML, /cal-mode-month/);
  assert.match(grid.innerHTML, /<button type="button" class="cal-daylink"/);
  assert.ok(grid.innerHTML.includes('aria-label="Open day: 2026-03-04" ' +
    'aria-describedby="cal-count-2026-03-04"><span>4</span>' +
    '<span class="cal-count" id="cal-count-2026-03-04">1</span></button>'));
  assert.ok(grid.innerHTML.includes('aria-label="Open day: 2026-03-05"><span>5</span></button>'));
  const day = {dataset: {calendarDay: "2026-03-04"}};
  onCalendarClick({target: {closest: selector => selector === ".cal-entry, .cal-more, .cal-span-bar" ? {} : day}});
  assert.equal(agendaUrl, undefined, "entry and overflow clicks stay in the calendar");
  onCalendarClick({target: {closest: selector => selector === "[data-calendar-day]" ? day : null}});
  assert.equal(agendaUrl.searchParams.get("calmode"), "day");
  assert.equal(agendaUrl.searchParams.get("cal"), "2026-03-04");

  const recovery = startLoad("2026-03-04", "week");
  recovery.resolve({records: []});
  await recovery.done;
  assert.equal(grid.innerHTML, "Nothing scheduled in this period");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
"""
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "harness.js")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(script)
            result = subprocess.run(
                ["node", path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
            )
        self.assertEqual(0, result.returncode, result.stderr)
