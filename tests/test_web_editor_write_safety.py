"""Exercise the shipped editor save function with delayed synthetic responses."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class EditorWriteSafetyTests(unittest.TestCase):
    def test_create_pending_unknown_and_known_rejection(self):
        start = HTML_PAGE.index("let editorSavePending = false;")
        save = HTML_PAGE.index("async function saveItem(event)", start)
        end = HTML_PAGE.index("\n    async function deleteSelected()", save)
        # newItem depends on the browser modal; only the save closure is needed.
        source = HTML_PAGE[start:HTML_PAGE.index("    function newItem()", start)] + HTML_PAGE[save:end]
        harness = r"""
let selectedItem = null;
let calls = [], pending = [], errors = [], closed = 0, refreshed = 0;
const elements = {"save-button": {disabled:false}, "editor-note": {textContent:""}};
global.document = {getElementById: id => elements[id]};
function editorPayload() { return {title:"Synthetic"}; }
function api(path, options) {
  calls.push({path, method:options.method});
  return new Promise((resolve, reject) => pending.push({resolve, reject}));
}
function showToast() {}
function showActionableError(title, error, options = {}) { errors.push({title, retry:!!options.retry}); }
function closeEditorModal() { closed++; }
async function refreshAll() { refreshed++; }
function t(s) { return s; }
const event = {preventDefault() {}};
async function tick() { await new Promise(resolve => setImmediate(resolve)); }
(async () => {
  // A repeated click and Enter while the first request is outstanding.
  const first = saveItem(event);
  await saveItem(event);
  if (calls.length !== 1 || !elements["save-button"].disabled) throw Error("pending guard");
  pending.shift().reject(Error("Failed to fetch"));
  await first;
  if (calls.length !== 1 || !elements["save-button"].disabled || errors[0].retry || !elements["editor-note"].textContent.includes("unknown")) throw Error("unknown outcome");
  await saveItem(event);
  if (calls.length !== 1) throw Error("unknown outcome resent");
  // A fresh editor session after checking the list permits another attempt.
  editorCreateOutcomeUnknown = false;
  const conflict = saveItem(event);
  pending.shift().reject(Object.assign(Error("Conflict"), {status:409}));
  await conflict;
  if (elements["save-button"].disabled || errors[1].retry) throw Error("known rejection");
  const success = saveItem(event);
  pending.shift().resolve({});
  await success;
  if (calls.length !== 3 || closed !== 1 || refreshed !== 1) throw Error("success");
  console.log(JSON.stringify({calls:calls.length, errors:errors.length}));
})().catch(error => {console.error(error); process.exitCode=1});
"""
        result = subprocess.run(["node", "-e", source + harness], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"calls": 3, "errors": 2}, json.loads(result.stdout))
