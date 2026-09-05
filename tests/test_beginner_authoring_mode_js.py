"""Node.js-driven behavioral tests for the Web UI's beginner authoring-mode
JavaScript (#634): `refreshAuthoringModeOptions`/`toggleAuthoringMode` in
`lifetxt/web_assets_js_05.js`.

Extracts the real assembled Web UI script from `lifetxt.web_assets.HTML_PAGE`
(the same source served to a browser) and drives it under Node with a small
DOM/localStorage stub -- no headless browser dependency. Skips gracefully
when `node` is not on PATH, matching this project's dependency-light CI
posture; these assertions are exercised for real whenever Node is available.
"""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _extract_script():
    match = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S)
    assert match is not None
    return match.group(1)


def _extract_functions_under_test(full_script):
    """Pull just the authoring-mode declarations out of the full ~300KB
    assembled app script, mirroring this project's established "targeted
    Node.js run of the extracted function source" verification style
    rather than booting the entire browser-only application under Node.
    """
    names = (
        "let beginnerProfileVocabulary",
        "const AUTHORING_FULL_STATUSES",
        "const AUTHORING_FULL_TYPES",
        "function authoringModePreference",
        "function setAuthoringModePreference",
        "function _authoringVisibleValues",
        "function refreshAuthoringModeOptions",
        "function toggleAuthoringMode",
    )
    start = min(full_script.index(name) for name in names)
    # Each declaration is self-contained; stop once the last one's function
    # body closes (its matching top-level "}" line).
    end_anchor = full_script.index("function toggleAuthoringMode")
    end = full_script.index("\n    }\n", end_anchor) + len("\n    }\n")
    return full_script[start:end]


_HARNESS = """
%s

// ---- minimal DOM/localStorage/i18n stub for the functions under test ----
const store = {};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};
// The real t() (web_assets_js_02.js) looks up UI_STRINGS by the English
// source text; stubbed here as an English passthrough since this harness
// only exercises the authoring-mode functions, not the translator itself.
global.t = (text) => text;

function makeSelect(options, value) {
  return {
    _options: options.slice(),
    value: value,
    get innerHTML() { return this._html || ""; },
    set innerHTML(html) {
      this._html = html;
      const values = [...html.matchAll(/<option[^>]*>([^<]*)<\\/option>/g)].map(m => m[1]);
      this._options = values;
      const selectedMatch = html.match(/<option selected>([^<]*)<\\/option>/);
      this.value = selectedMatch ? selectedMatch[1] : (values[0] || "");
    },
  };
}

const elements = {
  "edit-status": makeSelect(["[ ]"], "[ ]"),
  "edit-type": makeSelect(["T"], "T"),
  "authoring-advanced-toggle": { textContent: "" },
};
global.document = {
  getElementById: (id) => elements[id] || null,
};

const results = {};

// Case 1: default mode is "full" -- every status/type option present.
refreshAuthoringModeOptions("[ ]", "T");
results.default_mode_statuses = elements["edit-status"]._options;
results.default_mode_types = elements["edit-type"]._options;
results.default_toggle_text = elements["authoring-advanced-toggle"].textContent;

// Case 2: switch to beginner mode -- only the beginner subset shown.
toggleAuthoringMode();
refreshAuthoringModeOptions("[ ]", "T");
results.beginner_mode_statuses = elements["edit-status"]._options;
results.beginner_mode_types = elements["edit-type"]._options;
results.beginner_toggle_text = elements["authoring-advanced-toggle"].textContent;

// Case 3: opening an existing advanced record (status "[/]", type "D") in
// beginner mode must keep that value visible/selected, never silently drop it.
refreshAuthoringModeOptions("[/]", "D");
results.beginner_mode_preserves_advanced_status = elements["edit-status"]._options;
results.beginner_mode_preserves_advanced_type = elements["edit-type"]._options;
results.beginner_mode_selected_status = elements["edit-status"].value;
results.beginner_mode_selected_type = elements["edit-type"].value;

// Case 4: toggling back to full mode restores every option.
toggleAuthoringMode();
refreshAuthoringModeOptions("[ ]", "T");
results.full_mode_after_toggle_back_statuses = elements["edit-status"]._options;

console.log(JSON.stringify(results));
"""


class BeginnerAuthoringModeJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            raise unittest.SkipTest("node is not available on PATH")
        cls.results = cls._run()

    @classmethod
    def _run(cls):
        script = _HARNESS % _extract_functions_under_test(_extract_script())
        proc = subprocess.run(
            [cls.node, "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise AssertionError("node harness failed: %s" % proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_default_mode_shows_every_status_and_type(self):
        self.assertEqual(
            ["[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]"],
            self.results["default_mode_statuses"],
        )
        self.assertEqual(
            ["T", "E", "D", "R", "H", "N", "S", "M", "J"],
            self.results["default_mode_types"],
        )
        self.assertEqual("Hide advanced options", self.results["default_toggle_text"])

    def test_beginner_mode_shows_only_the_beginner_subset(self):
        self.assertEqual(["[ ]", "[x]", "[N]"], self.results["beginner_mode_statuses"])
        self.assertEqual(["T", "E", "N"], self.results["beginner_mode_types"])
        self.assertEqual("Show advanced options", self.results["beginner_toggle_text"])

    def test_beginner_mode_never_drops_an_advanced_value_already_on_a_record(self):
        self.assertIn("[/]", self.results["beginner_mode_preserves_advanced_status"])
        self.assertIn("D", self.results["beginner_mode_preserves_advanced_type"])
        self.assertEqual("[/]", self.results["beginner_mode_selected_status"])
        self.assertEqual("D", self.results["beginner_mode_selected_type"])

    def test_toggling_back_to_full_mode_restores_every_option(self):
        self.assertEqual(
            ["[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]"],
            self.results["full_mode_after_toggle_back_statuses"],
        )


if __name__ == "__main__":
    unittest.main()
