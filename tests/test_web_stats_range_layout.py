"""Stats breakdown date controls reuse the shared form layout (#1524)."""

import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from lifetxt.web_assets import HTML_PAGE
from tests.test_web_i18n import _ja_dictionary


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class StatsRangeLayoutTests(unittest.TestCase):
    def test_dates_have_visible_associated_shared_labels(self):
        for field, text in (("breakdown-from", "From"), ("breakdown-to", "To")):
            self.assertRegex(
                HTML_PAGE,
                rf'<label class="web-field-label" for="{field}"><span>{text}</span><input',
            )

    def test_controls_retain_handlers_and_use_shared_sizes(self):
        parser = Controls()
        parser.feed(HTML_PAGE)
        for field in ("breakdown-from", "breakdown-to"):
            control = next(a for tag, a in parser.tags if a.get("id") == field)
            self.assertEqual("date", control["type"])
            self.assertEqual("loadStatsBreakdown()", control["oninput"])
            self.assertNotIn("style", control)
        button = next(
            a
            for tag, a in parser.tags
            if tag == "button"
            and "getElementById('breakdown-from').value=''" in a.get("onclick", "")
        )
        self.assertIn(
            "getElementById('breakdown-to').value='';loadStatsBreakdown()",
            button["onclick"],
        )
        self.assertNotIn("style", button)

    def test_range_bar_wraps_and_aligns_to_input_bottom(self):
        rule = re.search(r"\.stats-range-bar\s*\{([^}]+)\}", HTML_PAGE)
        self.assertIsNotNone(rule)
        for value in ("display: flex", "align-items: flex-end", "flex-wrap: wrap"):
            self.assertIn(value, rule.group(1))


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class StatsBreakdownLoadingTests(unittest.TestCase):
    def test_latest_date_request_controls_display_and_failed_reads_can_be_retried(self):
        start = HTML_PAGE.index("    let statsBreakdownGeneration =")
        end = HTML_PAGE.index("    function toggleNotifPanel(", start)
        script = r"""
const assert = require("node:assert/strict");
const {source, ja} = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const vm = require("node:vm");
const elements = {
  "stats-breakdown": {innerHTML: ""},
  "breakdown-from": {value: "2026-11-01"},
  "breakdown-to": {value: "2026-11-08"},
};
const requests = [];
let language = "ja";
const context = vm.createContext({
  document: {getElementById: id => elements[id]},
  t: text => language === "ja" ? ja[text] || text : text,
  escapeHtml: text => text,
  ITEM_TYPE_NAMES: {T: "Task"},
  STATUS_LABEL: {"[x]": "done"},
  api: url => new Promise((resolve, reject) => requests.push({url, resolve, reject})),
});
vm.runInContext(source, context);
const load = () => vm.runInContext("loadStatsBreakdown()", context);
const markup = () => elements["stats-breakdown"].innerHTML;
(async () => {
  const older = load();
  assert.match(markup(), /統計の内訳を読み込み中/);
  elements["breakdown-from"].value = "2026-11-04";
  const latest = load();
  assert.equal(requests[1].url, "/api/stats/summary?from=2026-11-04&to=2026-11-08");
  requests[1].reject(new Error("private server detail"));
  await latest;
  assert.match(markup(), /統計の内訳を取得できませんでした/);
  assert.match(markup(), /内訳を再読み込み/);
  assert.doesNotMatch(markup(), /private server detail/);
  const error = markup();
  requests[0].resolve({by_type: {T: 99}});
  await older;
  assert.equal(markup(), error);

  const retry = vm.runInContext(markup().match(/onclick="([^"]+)"/)[1], context);
  assert.equal(requests[2].url, requests[1].url);
  elements["breakdown-from"].value = "";
  elements["breakdown-to"].value = "";
  language = "en";
  const allDates = load();
  assert.equal(requests[3].url, "/api/stats/summary");
  requests[3].resolve({by_type: {}, by_status: {}});
  await allDates;
  assert.match(markup(), /No statistics breakdown data/);
  const empty = markup();
  requests[2].reject(new Error("outdated failure"));
  await retry;
  assert.equal(markup(), empty);

  const successful = load();
  requests[4].resolve({by_type: {T: 2}, by_status: {"[x]": 1}});
  await successful;
  assert.match(markup(), /Task/);
  assert.match(markup(), /done/);
  assert.doesNotMatch(markup(), /Reload breakdown/);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps({"source": HTML_PAGE[start:end], "ja": _ja_dictionary()}),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
