"""Node.js-driven behavioral tests for the Web UI's actionable, retryable
error surface (#798): ``actionableErrorText``/``showActionableError``/
``renderActionableError`` in ``lifetxt/web_assets_js_18.js``.

These functions never invent a second error-reporting mechanism: they
classify an ``Error`` the existing ``api()`` helper already throws (with a
``status``/``message`` shape set in ``lifetxt/web_assets_js_01.js``) into a
human-readable message, and either reuse the existing ``showToast`` toast
system or render a small dismissible-by-retry block into the existing
``#toast-container`` element. This mirrors this project's established
"targeted Node.js run of the extracted function source" verification style
(tests/test_web_context_create_js.py) rather than booting a full browser.
"""

import re
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _extract_script():
    match = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S)
    assert match is not None
    return match.group(1)


def _extract_functions_under_test(full_script):
    start = full_script.index("function actionableErrorText(")
    end_anchor = full_script.index("function renderActionableError(")
    end = full_script.index("\n    }\n", end_anchor) + len("\n    }\n")
    return full_script[start:end]


_HARNESS = """
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

%s

// ---- minimal DOM stub for the functions under test ----
class FakeElement {
  constructor() {
    this._html = "";
    this.listeners = {};
    this.focused = false;
  }
  set innerHTML(value) { this._html = value; }
  get innerHTML() { return this._html; }
  querySelector(selector) {
    if (selector === "[data-retry]") return this._retryEl || (this._retryEl = new FakeElement());
    if (selector === ".actionable-error") return this._blockEl || (this._blockEl = new FakeElement());
    return null;
  }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  focus() { this.focused = true; }
}

const toasts = [];
global.showToast = (message, type, duration) => { toasts.push({message, type, duration}); };

const results = {};

// 1. Status-based classification.
results.conflict = actionableErrorText({status: 409, message: "stale"});
results.messageConflict = actionableErrorText({status: 0, message: "Revision changed since load"});
results.forbidden = actionableErrorText({status: 403, message: "nope"});
results.unauthorized = actionableErrorText({status: 401, message: "nope"});
results.serverError = actionableErrorText({status: 500, message: "boom"});
results.networkError = actionableErrorText({message: "Failed to fetch"});
results.genericMessage = actionableErrorText({status: 422, message: "Missing title"});
results.noMessage = actionableErrorText({});

// 2. showActionableError without a retry option falls back to the toast system.
toasts.length = 0;
showActionableError("Could not save.", {status: 500, message: "boom"});
results.toastCount = toasts.length;
results.toastType = toasts[0] && toasts[0].type;
results.toastMentionsTitle = !!(toasts[0] && toasts[0].message.includes("Could not save."));

// 3. showActionableError with a retry option renders into the container and wires the button.
const container = new FakeElement();
global.document = { getElementById: (id) => (id === "toast-container" ? container : null) };
let retried = false;
showActionableError("Could not save this record.", {status: 409, message: "stale"}, {retry: () => { retried = true; }});
results.rendered = container.innerHTML.includes("Could not save this record.");
results.renderedConflictText = container.innerHTML.includes("changed after you opened it");
results.retryButtonPresent = container.innerHTML.includes("data-retry");
results.focusedBlock = container._blockEl ? container._blockEl.focused : false;
container._retryEl.listeners.click();
results.retryFired = retried;

// 4. renderActionableError is a no-op when given no container (never throws).
renderActionableError(null, "title", {message: "x"}, () => {});
results.noContainerOk = true;

console.log(JSON.stringify(results));
"""


def _run(script_body):
    proc = subprocess.run(
        ["node", "-e", script_body],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(f"node script failed: {proc.stderr}\n{proc.stdout}")
    return proc.stdout.strip().splitlines()[-1]


class ActionableErrorJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            subprocess.run(
                ["node", "--version"], capture_output=True, timeout=10, check=True
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise unittest.SkipTest("node is not available in this environment")

    def _results(self):
        import json

        full_script = _extract_script()
        under_test = _extract_functions_under_test(full_script)
        out = _run(_HARNESS % under_test)
        return json.loads(out)

    def test_status_based_classification(self):
        results = self._results()
        self.assertIn("changed after you opened it", results["conflict"])
        self.assertIn("changed after you opened it", results["messageConflict"])
        self.assertIn("read-only or you do not have permission", results["forbidden"])
        self.assertIn(
            "read-only or you do not have permission", results["unauthorized"]
        )
        self.assertIn("Check the connection", results["serverError"])
        self.assertIn("Check the connection", results["networkError"])
        self.assertEqual(results["genericMessage"], "Missing title")
        self.assertTrue(results["noMessage"])

    def test_no_retry_falls_back_to_toast(self):
        results = self._results()
        self.assertEqual(results["toastCount"], 1)
        self.assertEqual(results["toastType"], "error")
        self.assertTrue(results["toastMentionsTitle"])

    def test_retry_option_renders_actionable_block_and_wires_retry(self):
        results = self._results()
        self.assertTrue(results["rendered"])
        self.assertTrue(results["renderedConflictText"])
        self.assertTrue(results["retryButtonPresent"])
        self.assertTrue(results["focusedBlock"])
        self.assertTrue(results["retryFired"])

    def test_render_with_no_container_does_not_throw(self):
        results = self._results()
        self.assertTrue(results["noContainerOk"])


if __name__ == "__main__":
    unittest.main()
