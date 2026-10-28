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
