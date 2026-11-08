"""Items filter reachability across the 680px disclosure breakpoint (#1453)."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.web_assets import HTML_PAGE


class ItemsFilterFallbackTests(unittest.TestCase):
    def test_filters_are_open_without_javascript(self):
        tag = re.search(r'<details[^>]*id="items-filter-disclosure"[^>]*>', HTML_PAGE)
        self.assertIsNotNone(tag)
        self.assertRegex(tag.group(), r"\sopen(?:\s|>)")


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class ItemsFilterResponsiveTests(unittest.TestCase):
    def test_initial_state_and_breakpoint_changes_preserve_filter_values(self):
        start = HTML_PAGE.index("    function setupItemsFilterDisclosure()")
        end = HTML_PAGE.index("    setupItemsFilterDisclosure();", start)
        source = HTML_PAGE[start:end]
        harness = r"""
const assert = require('node:assert/strict');
let disclosure, media, listener;
global.document = {getElementById: () => disclosure};
global.window = {matchMedia: query => {
  assert.equal(query, '(max-width: 680px)'); return media;
}};
function scenario(compact) {
  disclosure = {open: true};
  media = {matches: compact, addEventListener: (type, callback) => {
    assert.equal(type, 'change'); listener = callback;
  }};
  setupItemsFilterDisclosure();
  assert.equal(disclosure.open, !compact);
  // The disclosure only owns open state, never the controls or URL.
  disclosure.values = {kind: 'T', sort: 'title', order: 'desc', limit: '25'};
  const before = JSON.stringify(disclosure.values);
  disclosure.open = false;
  media.matches = false; listener();
  assert.equal(disclosure.open, true);
  media.matches = true; listener();
  assert.equal(disclosure.open, false);
  assert.equal(JSON.stringify(disclosure.values), before);
}
scenario(false); scenario(true);
disclosure = null; setupItemsFilterDisclosure();
"""
        result = subprocess.run(
            ["node", "-e", source + harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class ItemsEmptyStateTests(unittest.TestCase):
    def test_first_task_is_only_offered_for_unfiltered_writable_items(self):
        start = HTML_PAGE.index("    function itemsEmptyStateMarkup()")
        end = HTML_PAGE.index("    function renderItems(", start)
        source = HTML_PAGE[start:end]
        harness = r"""
const assert = require("node:assert/strict");
let itemsEmptyKind = "unfiltered";
let itemsReadOnly = false;
let display = false;
let kiosk = false;
const isKioskMode = () => kiosk;
const isDisplayMode = () => display;
const guidedEmptyState = (_icon, title, hint) => [title, hint].join(" ");
const firstTask = /Create your first task/;
assert.match(itemsEmptyStateMarkup(), firstTask);
for (const kind of ["filtered", "scoped"]) {
  itemsEmptyKind = kind;
  assert.match(itemsEmptyStateMarkup(), /No items match/);
  assert.match(itemsEmptyStateMarkup(), /clearItemsEmptyFilters/);
  assert.doesNotMatch(itemsEmptyStateMarkup(), firstTask);
}
itemsEmptyKind = "unfiltered";
itemsReadOnly = true;
assert.match(itemsEmptyStateMarkup(), /read-only/);
assert.doesNotMatch(itemsEmptyStateMarkup(), firstTask);
itemsReadOnly = null;
assert.doesNotMatch(itemsEmptyStateMarkup(), firstTask);
itemsReadOnly = false;
display = true;
assert.doesNotMatch(itemsEmptyStateMarkup(), firstTask);
display = false;
kiosk = true;
assert.doesNotMatch(itemsEmptyStateMarkup(), firstTask);
"""
        result = subprocess.run(
            ["node", "-e", source + harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class SavedFilterLoadingTests(unittest.TestCase):
    def test_failure_and_empty_result_are_distinct_and_retry_is_independent(self):
        start = HTML_PAGE.index("    async function populateSavedViewsAndAreas(")
        end = HTML_PAGE.index("    // /saved and /area", start)
        source = HTML_PAGE[start:end]
        harness = r"""
const assert = require("node:assert/strict");
function makeSelect() {
  return {
    options: [{value: ""}], value: "", dataset: {},
    replaceChildren(...children) { this.options = children; },
    setAttribute() {}, removeAttribute() {},
  };
}
class Option {
  constructor(textContent, value) { Object.assign(this, {textContent, value}); }
  setAttribute(name) { assert.equal(name, "data-no-i18n"); }
}
const view = makeSelect(), area = makeSelect(), retry = {};
const elements = {
  "saved-view-select": view, "area-select": area, "saved-filters-retry": retry,
};
const document = {getElementById: id => elements[id]};
const t = text => text;
let shouldFail = true, areaRequests = 0;
async function api(path) {
  if (path === "/api/areas") {
    areaRequests++;
    return {areas: [{name: "Work", task_done: 1, task_total: 2}]};
  }
  if (shouldFail) throw Error("offline");
  return {views: []};
}
(async () => {
  const load = populateSavedViewsAndAreas();
  assert.equal(view.options[0].textContent, "Loading saved views…");
  await load;
  assert.equal(view.options[0].textContent, "Could not load saved views");
  assert.equal(view.disabled, true);
  assert.equal(retry.hidden, false);
  assert.equal(area.disabled, false);
  assert.equal(area.options[1].textContent, "Work (1/2)");
  area.value = "Work";
  shouldFail = false;
  await populateSavedViewsAndAreas(true);
  assert.equal(view.options[0].textContent, "No saved views");
  assert.equal(retry.hidden, true);
  assert.equal(areaRequests, 1);
  assert.equal(area.value, "Work");
  await populateSavedViewsAndAreas();
  assert.equal(area.options.length, 2);
  assert.equal(area.value, "Work");
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-e", source + harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)


def _browser_path():
    configured = os.environ.get("LIFETXT_BROWSER_BIN")
    return configured if configured and os.path.isfile(configured) else None


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(_browser_path(), "Set LIFETXT_BROWSER_BIN to Chrome/Chromium")
class ItemsFilterBrowserTests(unittest.TestCase):
    def test_native_disclosure_keyboard_resize_and_existing_query_handlers(self):
        probe = Path(__file__).with_name("browser_items_filters_probe.mjs")
        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory) / "items.html"
            html_path.write_text(HTML_PAGE, encoding="utf-8")
            result = subprocess.run(
                ["node", str(probe), _browser_path(), str(html_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(
            [1280, 681, 680, 390], [v["width"] for v in evidence["viewports"]]
        )
