"""Regression coverage for the home workspace's Quick add preview."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class QuickAddPreviewTests(unittest.TestCase):
    def test_only_current_input_or_submit_may_update_the_preview(self):
        self.assertIn('oninput="previewShorthand()"', HTML_PAGE)
        preview = HTML_PAGE.split("// ── Capture shorthand preview", 1)[1]
        preview = preview[
            preview.index("\n") : preview.index("let captureSubmitPending")
        ]
        binding = HTML_PAGE.split("// ── Live parse preview for raw import", 1)[1]
        binding = binding[
            binding.index("\n") : binding.index("function renderRawParsePreview")
        ]
        harness = r"""
const assert = require("node:assert/strict");
const pending = [];
const timers = new Set();
let ready;
const setTimeout = callback => (timers.add(callback), callback);
const clearTimeout = callback => timers.delete(callback);
const classes = new Set();
const listeners = [];
const input = {value: "", classList: {
  add: name => classes.add(name),
  remove: (...names) => names.forEach(name => classes.delete(name)),
}, addEventListener: (_, callback) => listeners.push(callback)};
const message = {};
const document = {
  getElementById: id => ({"quick-line": input, "quick-check-msg": message})[id],
  querySelector() {},
  addEventListener: (_, callback) => { ready = callback; },
};
const api = (path, options) => path === "/api/health" ? {} :
  new Promise((resolve, reject) => pending.push({path, body: JSON.parse(options.body), resolve, reject}));
let itemsReadOnly;
function populateSavedViewsAndAreas() {}
function toggleQuickAdd() {}
function showToast() {}
async function refreshAll() {}
function edit(value) {
  input.value = value;
  previewShorthand();
  listeners.forEach(callback => callback());
}
function runPreview() {
  assert.equal(timers.size, 1, "one debounce per Quick add edit");
  const callback = timers.values().next().value;
  timers.delete(callback);
  const done = callback();
  const request = pending.shift();
  assert.equal(request.path, "/api/quick/resolve");
  assert.equal(request.body.text, input.value.trim());
  return {...request, done};
}
const result = title => ({title, details: {project: ["home"]}});
"""
        scenarios = r"""
(async () => {
  await ready();
  edit("A");
  const first = runPreview();
  edit("B");
  const second = runPreview();
  second.resolve(result("B")); await second.done;
  first.reject(Error("outdated")); await first.done;
  assert.match(message.textContent, /B/);
  assert.deepEqual([...classes], ["ok"]);

  edit("A");
  const sameText = runPreview();
  edit("");
  edit("A");
  sameText.resolve(result("obsolete A")); await sameText.done;
  assert.equal(message.textContent, "");
  assert.equal(classes.size, 0);
  const current = runPreview();
  current.reject(Error("current error")); await current.done;
  assert.equal(message.textContent, "current error");
  assert.deepEqual([...classes], ["err"]);

  edit("C");
  const beforeClear = runPreview();
  edit("");
  beforeClear.resolve(result("cleared")); await beforeClear.done;
  assert.equal(message.textContent, "");
  assert.equal(timers.size, 0);

  edit("D");
  const beforeSubmit = runPreview();
  const saving = quickAddLine();
  const capture = pending.shift();
  assert.equal(capture.path, "/api/items/capture");
  capture.resolve({}); await saving;
  beforeSubmit.reject(Error("pre-submit error")); await beforeSubmit.done;
  assert.equal(input.value, "");
  assert.equal(message.textContent, "");

  edit("E");
  const failing = quickAddLine();
  const failedCapture = pending.shift();
  assert.equal(timers.size, 0);
  edit("F");
  failedCapture.reject(Error("save failure")); await failing;
  assert.equal(message.textContent, "");
  console.log("passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-"],
            input=harness + preview + binding + scenarios,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("passed", result.stdout.strip())
