"""Stats shared date controls, range validation and breakdown refresh."""

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
    def test_date_group_explains_the_scope_in_both_languages(self):
        parser = Controls()
        parser.feed(HTML_PAGE)
        group = next(a for _, a in parser.tags if a.get("class") == "stats-range-bar")
        self.assertEqual("group", group["role"])
        labels = (
            (
                "aria-labelledby",
                "h3",
                "stats-range-title",
                "Statistics period",
                "統計の共通期間",
            ),
            (
                "aria-describedby",
                "p",
                "stats-breakdown-range-help",
                "The same inclusive calendar dates apply to the chart and breakdown. "
                "Empty end means workspace today; empty start means 29 days before end.",
                "グラフと内訳に同じ暦日範囲（両端を含む）を適用します。終了日が空欄ならワークスペースの今日、開始日が空欄なら終了日の29日前です。",
            ),
        )
        dictionary = _ja_dictionary()
        for attribute, tag, element_id, english, japanese in labels:
            with self.subTest(attribute=attribute):
                self.assertEqual(element_id, group[attribute])
                self.assertIn(f'<{tag} id="{element_id}">{english}</{tag}>', HTML_PAGE)
                self.assertEqual(japanese, dictionary[english])

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
            self.assertEqual("refreshStatsView()", control["oninput"])
            self.assertNotIn("style", control)
        button = next(
            a
            for tag, a in parser.tags
            if tag == "button"
            and a.get("onclick") == "resetStatsRange()"
        )
        self.assertEqual("resetStatsRange()", button["onclick"])
        self.assertNotIn("style", button)

    def test_range_bar_wraps_and_aligns_to_input_bottom(self):
        rule = re.search(r"\.stats-range-bar\s*\{([^}]+)\}", HTML_PAGE)
        self.assertIsNotNone(rule)
        for value in ("display: flex", "align-items: flex-end", "flex-wrap: wrap"):
            self.assertIn(value, rule.group(1))


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class StatsBreakdownLoadingTests(unittest.TestCase):
    def test_latest_date_request_controls_display_and_failed_reads_can_be_retried(self):
        start = HTML_PAGE.index("    function statsDate(")
        end = HTML_PAGE.index("    function toggleNotifPanel(", start)
        script = r"""
const assert = require("node:assert/strict");
const {source, ja} = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const vm = require("node:vm");
const elements = {
  "stats-breakdown": {innerHTML: ""},
  "stats-range-status": {textContent: ""},
  "stats-breakdown-applied": {textContent: ""},
  "breakdown-from": {value: "2026-11-01"},
  "breakdown-to": {value: "2026-11-08"},
};
const requests = [];
let language = "ja";
const context = vm.createContext({
  document: {getElementById: id => elements[id]},
  appConfig: {today: "2026-11-08"},
  t: text => language === "ja" ? ja[text] || text : text,
  escapeHtml: text => text,
  ITEM_TYPE_NAMES: {T: "Task"},
  STATUS_LABEL: {"[x]": "done"},
  api: url => new Promise((resolve, reject) => requests.push({url, resolve, reject})),
});
vm.runInContext(source, context);
const load = () => vm.runInContext("loadStatsBreakdown()", context);
const markup = () => elements["stats-breakdown"].innerHTML;
const selected = () => vm.runInContext("statsRangeSelection()", context);
const response = (index, fields) => {
  const url = new URL(requests[index].url, "https://example.test");
  requests[index].resolve({...fields, range: {from: url.searchParams.get("from"), to: url.searchParams.get("to")}});
};
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
  response(0, {by_type: {T: 99}});
  await older;
  assert.equal(markup(), error);

  const retry = vm.runInContext(markup().match(/onclick="([^"]+)"/)[1], context);
  assert.equal(requests[2].url, requests[1].url);
  elements["breakdown-from"].value = "";
  elements["breakdown-to"].value = "";
  language = "en";
  const allDates = load();
  assert.equal(requests[3].url, "/api/stats/summary?from=2026-10-10&to=2026-11-08");
  response(3, {by_type: {}, by_status: {}});
  await allDates;
  assert.match(markup(), /No statistics breakdown data/);
  const empty = markup();
  requests[2].reject(new Error("outdated failure"));
  await retry;
  assert.equal(markup(), empty);

  const successful = load();
  response(4, {by_type: {T: 2}, by_status: {"[x]": 1}});
  await successful;
  assert.match(markup(), />By Type</);
  assert.match(markup(), />By Status</);
  assert.match(markup(), /Task/);
  assert.match(markup(), /done/);
  assert.doesNotMatch(markup(), /No entries/);
  assert.doesNotMatch(markup(), /Reload breakdown/);

  const typeOnly = load();
  response(5, {by_type: {T: 2}, by_status: {}});
  await typeOnly;
  assert.match(markup(), /By Status<\/div>\s*<div[^>]*><em>No entries<\/em>/);

  language = "ja";
  const statusOnly = load();
  response(6, {by_type: {}, by_status: {"[x]": 1}});
  await statusOnly;
  assert.match(markup(), /種別別<\/div>\s*<div[^>]*><em>該当なし<\/em>/);
  assert.match(markup(), />ステータス別</);
  assert.match(markup(), /done/);
  assert.doesNotMatch(markup(), /By Type|By Status|No entries|<em>none<\/em>/);
  assert.match(elements["stats-breakdown-applied"].textContent, /適用された期間/);
  elements["breakdown-to"].value = "2024-03-01";
  assert.equal(selected().from, "2024-02-01");
  elements["breakdown-from"].value = "2024-03-01";
  assert.equal(selected().to, "2024-03-01");
  const single = load();
  elements["breakdown-from"].value = "2024-03-02";
  await load();
  assert.equal(requests.length, 8);
  assert.equal(markup(), "");
  assert.equal(elements["stats-breakdown-applied"].textContent, "");
  response(7, {by_type: {T: 7}});
  await single;
  assert.equal(markup(), "");
  assert.match(elements["stats-range-status"].textContent, /開始日/);
  elements["breakdown-from"].value = "2026-02-30";
  assert.equal(selected(), null);
  elements["breakdown-from"].value = "2026-11-01";
  elements["breakdown-to"].value = "";
  assert.equal(selected().to, "2026-11-08");
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
