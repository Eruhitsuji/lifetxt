"""Input bars honor the effective reduced-motion preference (#1512)."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class InputBarMotionTests(unittest.TestCase):
    def test_scroll_preference_and_focus_for_both_input_bars(self):
        start = HTML_PAGE.index("    function focusBarInput(")
        end = HTML_PAGE.index("    function standardStatusStates()", start)
        script = r"""
const vm = require('node:vm'), assert = require('node:assert/strict');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
let reduced = false, scrollSupported = true, missing = false;
const calls = [], bars = {'quick-add-bar': {style: {}}, 'presence-bar': {style: {}}};
const sandbox = {
 document: {
  body: {classList: {contains: name => name === 'reduce-motion' && reduced}},
  getElementById: id => bars[id] || (missing ? null : {
   focus: () => calls.push('focus:' + id), select: () => calls.push('select:' + id),
   ...(scrollSupported ? {scrollIntoView: options => calls.push(JSON.parse(JSON.stringify(options)))} : {})
  })
 }, revealItemsPage: () => calls.push('reveal'), loadPresence: () => calls.push('presence')
};
vm.createContext(sandbox); vm.runInContext(source, sandbox);
for (const reduce of [false, true, false]) {
 reduced = reduce;
 for (const [action, id, select] of [
  ['toggleQuickAdd(true)', 'quick-line', true],
  ['togglePresence(true)', 'presence-state-select', false]
 ]) {
  calls.length = 0; vm.runInContext(action, sandbox);
  assert.ok(calls.includes('focus:' + id));
  assert.equal(calls.includes('select:' + id), select);
  assert.deepEqual(calls.at(-1), {block: 'center', behavior: reduce ? 'instant' : 'smooth'});
 }
}
scrollSupported = false; calls.length = 0;
vm.runInContext("focusBarInput('quick-line', true)", sandbox);
assert.deepEqual(calls, ['focus:quick-line', 'select:quick-line']);
missing = true; calls.length = 0;
vm.runInContext("focusBarInput('missing', true)", sandbox);
assert.deepEqual(calls, []);
for (const action of ['toggleQuickAdd(false)', 'togglePresence(false)']) {
 calls.length = 0; vm.runInContext(action, sandbox); assert.deepEqual(calls, []);
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(HTML_PAGE[start:end]),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
