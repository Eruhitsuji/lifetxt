"""Regression for Items refreshing away the URL before deep-link resolution."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DeepLinkUrlRetentionTests(unittest.TestCase):
    def test_items_load_preserves_detail_target_without_leaking_it_to_list_api(self):
        start = HTML_PAGE.index("function itemQueryParams()")
        end = HTML_PAGE.index("\n    function initItemFilterControls()", start)
        layout_start = HTML_PAGE.index("    function itemsLayoutAvailable()")
        layout_end = HTML_PAGE.index("    function addBoardTask(", layout_start)
        source = HTML_PAGE[start:end] + HTML_PAGE[layout_start:layout_end]
        harness = r"""
let currentItems = [], selectedItem = null;
const controls = {
  kind: {value: ""}, search: {value: ""}, limit: {value: ""},
  sort: {value: "line"}, order: {value: "desc"},
  "open-only": {checked: false}, "group-by": {value: ""}, "items-layout-control": {},
  "items-layout-list": {setAttribute(name, value) {this[name] = value;}},
  "items-layout-board": {setAttribute(name, value) {this[name] = value;}},
};
global.document = {getElementById: id => controls[id] || null};
global.location = {pathname: "/", href: ""};
global.history = {replaceState: (_state, _title, path) => {
  location.href = new URL(path, "https://example.invalid").href;
}};
history.pushState = history.replaceState;
location.hash = "";
const isKioskMode = () => query().get("mode") === "kiosk";
const isDisplayMode = () => query().get("mode") === "display";
const currentView = () => query().get("view");
function query() { return new URL(location.href).searchParams; }
function firstParam(params, keys, fallback) {
  for (const key of keys) if (params.has(key)) return params.get(key);
  return fallback;
}
function boolParam(params, keys) { return keys.some(key => params.get(key) === "true"); }
function applyKioskFilterParams() {}
function renderDiagnostics() {}
function renderItems() {}
function updateTagSuggestions() {}
function syncStatusFilterBtns() {}
function selectItem() {}
async function api(path) { calls.push(path); return {items: [], diagnostics: []}; }
const calls = [], results = [];
async function scenario(url, expectedTarget) {
  location.href = "https://example.invalid/" + url;
  Object.assign(controls.search, {value: ""});
  await loadItems();
  const afterLoad = location.href;
  const target = query().get("id") || query().get("line");
  if (target !== expectedTarget) throw Error("initial deep-link target lost: " + afterLoad);
  controls.search.value = "fixture";
  await loadItems();
  const afterFilter = location.href;
  if ((query().get("id") || query().get("line")) !== expectedTarget) throw Error("filter lost target");
  results.push({afterLoad, afterFilter, api: calls.splice(0)});
}
(async () => {
  await scenario("?id=task-001&theme=dark&items_layout=board", "task-001");
  await scenario("?line=42&view=items", "42");
  await scenario("?view=messages&id=msg-1", "msg-1");
  for (const result of results) {
    if (result.api.length !== 2 || result.api.some(path => /[?&](?:id|line|items_layout)=/.test(path))) throw Error("UI state leaked to list API");
  }
  const assert = require("node:assert/strict");
  location.href = "https://example.invalid/?view=items&project=demo&id=task-001";
  const initialUrl = location.href;
  syncItemsLayoutFromUrl();
  assert.equal(itemsBoardActive(), false);
  changeItemsLayout("board");
  const boardUrl = location.href;
  assert.equal(query().get("items_layout"), "board");
  assert.equal(query().get("project"), "demo");
  assert.equal(query().get("id"), "task-001");
  changeItemsLayout("list");
  assert.equal(query().has("items_layout"), false);
  for (const [url, active] of [[initialUrl, false], [boardUrl, true],
      [boardUrl + "&mode=kiosk", false], [boardUrl + "&mode=display", false],
      [boardUrl.replace("view=items", "view=messages"), false],
      [boardUrl.replace("items_layout=board", "items_layout=future"), false]]) {
    location.href = url;
    syncItemsLayoutFromUrl();
    assert.equal(itemsBoardActive(), active);
    assert.equal(controls["items-layout-board"]["aria-pressed"], String(active));
  }
  console.log(JSON.stringify(results));
})().catch(e => {console.error(e); process.exitCode = 1});
"""
        result = subprocess.run(
            ["node", "-e", source + harness], capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode, result.stderr)
        cases = json.loads(result.stdout)
        self.assertIn("theme=dark", cases[0]["afterLoad"])
        self.assertIn("items_layout=board", cases[0]["afterLoad"])
        self.assertIn("items_layout=board", cases[0]["afterFilter"])
        self.assertIn("view=messages", cases[2]["afterFilter"])
