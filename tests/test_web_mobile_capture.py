"""Route, markup, and browser-behavior coverage for mobile Quick Capture."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt import webapp
from lifetxt.web_assets import HTML_PAGE


def _capture_script():
    script = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S).group(1)
    start = script.index("let captureSubmitPending")
    end = script.index("// ── Keyboard shortcuts", start)
    return script[start:end]


_HARNESS = r"""
%s

function element(value = "") {
  return {
    value, textContent: "", className: "", disabled: false, attributes: {}, focused: 0,
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    focus() { this.focused += 1; },
  };
}
const input = element();
const button = element();
const feedback = element();
const bodyClasses = new Set();
const elements = {"capture-text": input, "capture-submit": button, "capture-feedback": feedback};
global.document = {
  title: "life.txt",
  body: {classList: {add(name) { bodyClasses.add(name); }}},
  getElementById(id) { return elements[id] || null; },
};
global.location = {pathname: "/capture"};
global.requestAnimationFrame = callback => callback();
let appConfig = {ids: {key: "id"}};
const t = value => value;
const actionableErrorText = error => error.message || "Try again";
let calls = [];
let apiImpl = async () => ({item: {title: "Saved", details: {id: ["T-1"]}}});
const api = async (path, options) => {
  calls.push({path, body: JSON.parse(options.body)});
  return apiImpl(path, options);
};

async function main() {
  const results = {};
  results.initialized = initializeCaptureMode();
  results.bodyClass = bodyClasses.has("capture-mode");
  results.initialFocus = input.focused;

  input.value = "Buy milk @home ^tomorrow";
  await submitCapture();
  results.success = {
    call: calls[0], value: input.value, feedback: feedback.textContent,
    className: feedback.className, focused: input.focused, disabled: button.disabled,
  };

  calls = [];
  input.value = "[ ] T Full_line id:T-2";
  await submitCapture();
  results.fullLine = calls[0];

  calls = [];
  input.value = "Keep this text";
  apiImpl = async () => { const error = new Error("read only"); error.status = 403; throw error; };
  await submitCapture();
  results.failure = {calls: calls.length, value: input.value, feedback: feedback.textContent, className: feedback.className};

  calls = [];
  input.value = "Only once";
  let release;
  apiImpl = () => new Promise(resolve => { release = resolve; });
  const first = submitCapture();
  const second = submitCapture();
  results.pending = {calls: calls.length, disabled: button.disabled, busy: button.attributes["aria-busy"]};
  release({item: {title: "Once", details: {id: ["T-3"]}}});
  await Promise.all([first, second]);
  results.afterPending = {calls: calls.length, disabled: button.disabled, busy: button.attributes["aria-busy"] || null};
  return results;
}

main().then(result => console.log(JSON.stringify(result))).catch(error => {
  console.error(error);
  process.exit(1);
});
"""


class MobileCaptureRouteTests(unittest.TestCase):
    def test_capture_route_reuses_shell_and_no_store_policy(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("web extras unavailable")
        response = TestClient(webapp.create_app(paths=[])).get("/capture")
        self.assertEqual(200, response.status_code)
        self.assertEqual(webapp.HTML_PAGE.encode("utf-8"), response.content)
        self.assertEqual("no-store", response.headers.get("cache-control"))

    def test_read_only_capture_surface_is_visible_but_cannot_mutate(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("web extras unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            Path(path).write_text("", encoding="utf-8")
            client = TestClient(
                webapp.create_app(paths=[path], writable_path=path, read_only=True)
            )
            self.assertEqual(200, client.get("/capture").status_code)
            response = client.post("/api/items/capture", json={"text": "Blocked"})
            self.assertEqual(403, response.status_code)
            self.assertEqual("", Path(path).read_text(encoding="utf-8"))


class MobileCaptureMarkupTests(unittest.TestCase):
    def test_capture_surface_is_small_accessible_and_home_screen_sized(self):
        for fragment in (
            'data-page="capture"',
            'aria-labelledby="capture-heading"',
            'id="capture-form"',
            'id="capture-text"',
            'aria-describedby="capture-syntax capture-feedback"',
            'id="capture-feedback" class="capture-feedback" role="status" aria-live="polite"',
            'href="/">Open full Web UI</a>',
            "safe-area-inset-top",
            "min-height: 100dvh",
            "max-height: 520px",
            "body { overflow-x: hidden; }",
        ):
            self.assertIn(fragment, HTML_PAGE)

    def test_capture_copy_has_japanese_dictionary_entries(self):
        for text in (
            "Quick Capture",
            "Capture one thought to your authoritative life.txt.",
            "What do you want to remember?",
            "Open full Web UI",
            "Captured:",
            "Capture failed:",
        ):
            self.assertRegex(
                HTML_PAGE, rf'"{re.escape(text)}":\s*"[^\"]*[ぁ-んァ-ン一-龯]'
            )


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class MobileCaptureJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            ["node", "-e", _HARNESS % _capture_script()],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.result = json.loads(proc.stdout)

    def test_path_initializes_capture_mode_and_focus(self):
        self.assertTrue(self.result["initialized"])
        self.assertTrue(self.result["bodyClass"])
        self.assertEqual(1, self.result["initialFocus"])

    def test_success_reuses_capture_endpoint_clears_and_refocuses(self):
        result = self.result["success"]
        self.assertEqual("/api/items/capture", result["call"]["path"])
        self.assertEqual({"text": "Buy milk @home ^tomorrow"}, result["call"]["body"])
        self.assertEqual("", result["value"])
        self.assertIn("Captured: Saved (T-1)", result["feedback"])
        self.assertEqual("capture-feedback ok", result["className"])
        self.assertGreaterEqual(result["focused"], 2)
        self.assertFalse(result["disabled"])

    def test_full_line_reuses_existing_raw_quick_add_path(self):
        self.assertEqual("/api/items/raw", self.result["fullLine"]["path"])
        self.assertEqual(
            {"line": "[ ] T Full_line id:T-2"}, self.result["fullLine"]["body"]
        )

    def test_failure_preserves_text_and_reports_no_success(self):
        result = self.result["failure"]
        self.assertEqual(1, result["calls"])
        self.assertEqual("Keep this text", result["value"])
        self.assertEqual("capture-feedback err", result["className"])
        self.assertIn("Capture failed: read only", result["feedback"])
        self.assertNotIn("Captured:", result["feedback"])

    def test_pending_request_suppresses_duplicate_submission(self):
        self.assertEqual(1, self.result["pending"]["calls"])
        self.assertTrue(self.result["pending"]["disabled"])
        self.assertEqual("true", self.result["pending"]["busy"])
        self.assertEqual(1, self.result["afterPending"]["calls"])
        self.assertFalse(self.result["afterPending"]["disabled"])
        self.assertIsNone(self.result["afterPending"]["busy"])


if __name__ == "__main__":
    unittest.main()
