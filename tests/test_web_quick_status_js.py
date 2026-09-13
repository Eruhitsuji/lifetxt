"""Behavioral coverage for the Web Quick Status standard/custom picker."""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _script_block():
    match = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S)
    assert match is not None
    script = match.group(1)
    start = script.index("function standardStatusStates")
    end = script.index("// ── Capture shorthand preview", start)
    return script[start:end]


_HARNESS = r"""
%s

const elements = {
  "presence-state-select": {value: "", innerHTML: ""},
  "presence-state-custom": {
    value: "", hidden: true, disabled: true, required: false, focused: false,
    setAttribute: function(name, value) { this[name] = value; },
    focus: function() { this.focused = true; },
  },
  "presence-title": {value: ""},
};
global.document = {getElementById: id => elements[id] || null};
let appConfig = {status_states: ["available", "busy", "focus", "", 7]};
const escapeHtml = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const t = value => value;
let apiCalls = [];
let apiImpl = async (path, options) => ({closed: [], unchanged: ""});
const api = async (path, options) => {
  apiCalls.push({path, body: options && options.body ? JSON.parse(options.body) : null});
  return apiImpl(path, options);
};
let toasts = [];
const showToast = (message, kind) => toasts.push({message, kind});
let loads = 0;
let refreshes = 0;
const loadPresence = async () => { loads += 1; };
const refreshAll = async () => { refreshes += 1; };

async function main() {
  const results = {};
  setupQuickPresencePicker();
  results.shared_options = elements["presence-state-select"].innerHTML;
  results.initial = {
    value: elements["presence-state-select"].value,
    hidden: elements["presence-state-custom"].hidden,
    disabled: elements["presence-state-custom"].disabled,
  };

  elements["presence-state-custom"].value = "Keep-Me";
  elements["presence-state-select"].value = "__custom__";
  quickPresenceStateChanged();
  results.custom_mode = {
    value: elements["presence-state-custom"].value,
    hidden: elements["presence-state-custom"].hidden,
    disabled: elements["presence-state-custom"].disabled,
    required: elements["presence-state-custom"].required,
    focused: elements["presence-state-custom"].focused,
  };
  elements["presence-state-select"].value = "focus";
  syncQuickPresenceStateMode();
  results.back_to_standard = {
    value: elements["presence-state-custom"].value,
    hidden: elements["presence-state-custom"].hidden,
    disabled: elements["presence-state-custom"].disabled,
  };

  elements["presence-title"].value = "Deep work";
  results.standard_payload = quickPresencePayload();
  elements["presence-state-select"].value = "__custom__";
  elements["presence-state-custom"].value = "On-Call";
  results.custom_payload = quickPresencePayload();

  apiCalls = []; toasts = []; loads = 0; refreshes = 0;
  apiImpl = async () => ({closed: ["old"], unchanged: ""});
  await setPresence();
  results.custom_submit = {
    call: apiCalls[0], toast: toasts[0], loads, refreshes,
    custom: elements["presence-state-custom"].value,
    title: elements["presence-title"].value,
  };

  apiCalls = []; toasts = [];
  elements["presence-state-select"].value = "__custom__";
  elements["presence-state-custom"].value = "";
  await setPresence();
  results.empty_custom = {calls: apiCalls.length, toast: toasts[0]};

  apiCalls = []; toasts = [];
  elements["presence-state-select"].value = "busy";
  apiImpl = async () => ({closed: [], unchanged: "busy"});
  await setPresence();
  results.same_state = {call: apiCalls[0], toast: toasts[0]};

  apiCalls = []; toasts = [];
  elements["presence-state-select"].value = "__custom__";
  elements["presence-state-custom"].value = "preserve-on-error";
  apiImpl = async () => { throw new Error("read only"); };
  await setPresence();
  results.failure = {
    calls: apiCalls.length, toast: toasts[0],
    custom: elements["presence-state-custom"].value,
  };

  apiCalls = []; toasts = [];
  apiImpl = async () => ({closed: ["old"]});
  await endPresence();
  results.end = {call: apiCalls[0], toast: toasts[0]};
  return results;
}

main().then(results => console.log(JSON.stringify(results))).catch(error => {
  console.error(error);
  process.exit(1);
});
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class QuickStatusJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            ["node", "-e", _HARNESS % _script_block()],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.results = json.loads(proc.stdout)

    def test_picker_uses_config_states_and_starts_in_standard_mode(self):
        options = self.results["shared_options"]
        for state in ("available", "busy", "focus"):
            self.assertIn('value="%s"' % state, options)
        self.assertNotIn('value="7"', options)
        self.assertEqual("available", self.results["initial"]["value"])
        self.assertTrue(self.results["initial"]["hidden"])
        self.assertTrue(self.results["initial"]["disabled"])

    def test_switching_modes_preserves_custom_text_and_precedence(self):
        custom = self.results["custom_mode"]
        self.assertEqual("Keep-Me", custom["value"])
        self.assertFalse(custom["hidden"])
        self.assertFalse(custom["disabled"])
        self.assertTrue(custom["required"])
        self.assertTrue(custom["focused"])
        standard = self.results["back_to_standard"]
        self.assertEqual("Keep-Me", standard["value"])
        self.assertTrue(standard["hidden"])
        self.assertTrue(standard["disabled"])

    def test_standard_custom_and_optional_title_payloads(self):
        self.assertEqual(
            {"state": "focus", "title": "Deep work"},
            self.results["standard_payload"],
        )
        self.assertEqual(
            {"state": "On-Call", "title": "Deep work"},
            self.results["custom_payload"],
        )

    def test_custom_submit_reuses_status_endpoint_and_clears_after_success(self):
        result = self.results["custom_submit"]
        self.assertEqual("/api/status", result["call"]["path"])
        self.assertEqual(
            {"state": "On-Call", "title": "Deep work"}, result["call"]["body"]
        )
        self.assertEqual("success", result["toast"]["kind"])
        self.assertEqual(1, result["loads"])
        self.assertEqual(1, result["refreshes"])
        self.assertEqual("", result["custom"])
        self.assertEqual("", result["title"])

    def test_empty_custom_is_rejected_without_api_call(self):
        result = self.results["empty_custom"]
        self.assertEqual(0, result["calls"])
        self.assertEqual("error", result["toast"]["kind"])

    def test_same_state_response_remains_a_noop(self):
        result = self.results["same_state"]
        self.assertEqual({"state": "busy"}, result["call"]["body"])
        self.assertEqual("Already busy.", result["toast"]["message"])
        self.assertEqual("info", result["toast"]["kind"])

    def test_failure_does_not_clear_or_report_success(self):
        result = self.results["failure"]
        self.assertEqual(1, result["calls"])
        self.assertEqual("preserve-on-error", result["custom"])
        self.assertEqual("error", result["toast"]["kind"])

    def test_end_does_not_depend_on_picker_state(self):
        result = self.results["end"]
        self.assertEqual({"end": True}, result["call"]["body"])
        self.assertEqual("success", result["toast"]["kind"])


class QuickStatusMarkupTests(unittest.TestCase):
    def test_fields_are_accessibly_labeled_and_enter_remains_available(self):
        for fragment in (
            'id="presence-bar"',
            'aria-label="Quick Status"',
            'id="presence-state-select" aria-label="Status state"',
            'id="presence-state-custom" placeholder="Custom status" aria-label="Custom status"',
            'id="presence-title" placeholder="Activity / title (optional)" aria-label="Activity or title (optional)"',
            "event.key==='Enter'",
        ):
            self.assertIn(fragment, HTML_PAGE)

    def test_narrow_layout_wraps_instead_of_horizontally_hiding_fields(self):
        self.assertIn(
            ".presence-quick-bar { flex-wrap: wrap; overflow-x: visible; }",
            HTML_PAGE,
        )


if __name__ == "__main__":
    unittest.main()
