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
    hidden: false, children: [],
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    focus() { this.focused += 1; },
    replaceChildren() { this.children = []; },
    append(...values) { this.children.push(...values); },
  };
}
const input = element();
const button = element();
const feedback = element();
const syntax = element("quick");
const confirm = element(); confirm.hidden = true;
const preview = element(); preview.hidden = true;
const previewFields = element();
const previewDiagnostics = element();
const syntaxHelp = element();
const bodyClasses = new Set();
const elements = {
  "capture-text": input, "capture-submit": button, "capture-feedback": feedback,
  "capture-input-syntax": syntax, "capture-confirm": confirm, "capture-preview": preview,
  "capture-preview-fields": previewFields, "capture-preview-diagnostics": previewDiagnostics,
  "capture-syntax": syntaxHelp,
};
global.document = {
  title: "life.txt",
  body: {classList: {add(name) { bodyClasses.add(name); }}},
  getElementById(id) { return elements[id] || null; },
  createElement() { return element(); },
};
global.location = {pathname: "/capture"};
global.requestAnimationFrame = callback => callback();
let appConfig = {ids: {key: "id"}};
const t = value => value;
const actionableErrorText = error => error.message || "Try again";
let calls = [];
let apiImpl = async () => ({item: {title: "Saved", details: {id: ["T-1"]}}});
const api = async (path, options) => {
  calls.push({path, body: JSON.parse(options.body), headers: options.headers || {}});
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

  calls = [];
  syntax.value = "todo";
  captureSyntaxChanged();
  input.value = "(A) Prepare proposal +Work @office due:2026-10-30";
  apiImpl = async path => path === "/api/quick/resolve" ? {
    title: "Prepare proposal", status: "[ ]", type: "T",
    details: {priority: ["A"], project: ["Work"], context: ["office"], due: ["2026-10-30"]},
    diagnostics: [], context_token: "batch-preview-v1:" + "a".repeat(64),
    source_revision: "b".repeat(64), read_only: false,
  } : {item: {title: "Prepare proposal", details: {id: ["T-4"]}}};
  await submitCapture();
  results.todoPreview = {
    call: calls[0], previewHidden: preview.hidden, confirmHidden: confirm.hidden,
    fields: previewFields.children.map(child => child.textContent),
    diagnostics: previewDiagnostics.textContent,
  };
  await confirmTodoCapture();
  results.todoConfirm = {call: calls[1], value: input.value, previewHidden: preview.hidden, confirmHidden: confirm.hidden};
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
            'aria-describedby="capture-mode-help capture-syntax capture-feedback"',
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
            "Input syntax",
            "todo.txt (preview required)",
            "Confirm and capture",
            "Review todo.txt mapping",
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

    def test_full_line_uses_common_capture_contract(self):
        self.assertEqual("/api/items/capture", self.result["fullLine"]["path"])
        self.assertEqual(
            {"text": "[ ] T Full_line id:T-2"}, self.result["fullLine"]["body"]
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

    def test_todo_mode_previews_every_field_then_confirms_bound_revision(self):
        preview = self.result["todoPreview"]
        self.assertEqual("/api/quick/resolve", preview["call"]["path"])
        self.assertEqual("todo", preview["call"]["body"]["syntax"])
        self.assertFalse(preview["previewHidden"])
        self.assertFalse(preview["confirmHidden"])
        for value in (
            "title",
            "Prepare proposal",
            "status",
            "[ ]",
            "priority",
            "A",
            "project",
            "Work",
            "context",
            "office",
            "due",
            "2026-10-30",
        ):
            self.assertIn(value, preview["fields"])
        self.assertIn("Warnings: none.", preview["diagnostics"])

        confirmed = self.result["todoConfirm"]
        self.assertEqual("/api/items/capture", confirmed["call"]["path"])
        self.assertEqual("todo", confirmed["call"]["body"]["syntax"])
        self.assertEqual(
            "b" * 64, confirmed["call"]["body"]["expected_source_revision"]
        )
        self.assertEqual("b" * 64, confirmed["call"]["headers"]["If-Match"])
        self.assertEqual("", confirmed["value"])
        self.assertTrue(confirmed["previewHidden"])
        self.assertTrue(confirmed["confirmHidden"])


class TodoCaptureApiTests(unittest.TestCase):
    def setUp(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("web extras unavailable")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "life.txt"
        self.path.write_text("", encoding="utf-8")
        self.client = TestClient(
            webapp.create_app(paths=[str(self.path)], writable_path=str(self.path))
        )

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def preview(self, text):
        return self.client.post(
            "/api/quick/resolve", json={"text": text, "syntax": "todo"}
        )

    def test_preview_and_confirm_preserve_todo_mapping(self):
        text = "(A) 2026-10-26 Prepare proposal +Work @職場 due:2026-10-30 owner:alice"
        preview = self.preview(text)
        self.assertEqual(200, preview.status_code, preview.text)
        data = preview.json()
        self.assertEqual("todo", data["mode"])
        self.assertEqual("Prepare proposal", data["title"])
        self.assertEqual(["A"], data["details"]["priority"])
        self.assertEqual(["2026-10-26"], data["details"]["created"])
        self.assertEqual(["Work"], data["details"]["project"])
        self.assertEqual(["職場"], data["details"]["context"])
        self.assertEqual(["2026-10-30"], data["details"]["due"])
        self.assertEqual(["alice"], data["details"]["owner"])
        self.assertTrue(data["context_token"].startswith("batch-preview-v1:"))
        self.assertEqual([], data["diagnostics"])

        response = self.client.post(
            "/api/items/capture",
            headers={"If-Match": data["source_revision"]},
            json={
                "text": text,
                "syntax": "todo",
                "context_token": data["context_token"],
                "expected_source_revision": data["source_revision"],
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        saved = self.path.read_text(encoding="utf-8")
        self.assertIn("priority:A", saved)
        self.assertIn("project:Work", saved)
        self.assertIn("context:職場", saved)
        self.assertIn("owner:alice", saved)

    def test_changed_input_or_missing_preview_cannot_write(self):
        preview = self.preview("First +Work").json()
        before = self.path.read_text(encoding="utf-8")
        missing = self.client.post(
            "/api/items/capture",
            headers={"If-Match": preview["source_revision"]},
            json={"text": "First +Work", "syntax": "todo"},
        )
        self.assertEqual(428, missing.status_code)
        changed = self.client.post(
            "/api/items/capture",
            headers={"If-Match": preview["source_revision"]},
            json={
                "text": "Second +Work",
                "syntax": "todo",
                "context_token": preview["context_token"],
                "expected_source_revision": preview["source_revision"],
            },
        )
        self.assertEqual(409, changed.status_code)
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))

    def test_invalid_or_multiline_todo_preview_cannot_write(self):
        before = self.path.read_text(encoding="utf-8")
        for text in ("", "First\nSecond", "2026-99-99 Invalid"):
            with self.subTest(text=text):
                response = self.preview(text)
                self.assertIn(response.status_code, (400, 422))
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))

    def test_stale_writable_revision_requires_a_fresh_preview(self):
        preview = self.preview("First +Work").json()
        self.path.write_text('[ ] T "External"\n', encoding="utf-8")
        response = self.client.post(
            "/api/items/capture",
            headers={"If-Match": preview["source_revision"]},
            json={
                "text": "First +Work",
                "syntax": "todo",
                "context_token": preview["context_token"],
                "expected_source_revision": preview["source_revision"],
            },
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual('[ ] T "External"\n', self.path.read_text(encoding="utf-8"))

    def test_other_workspace_source_change_invalidates_context_token(self):
        other = Path(self.temp_dir.name) / "other.txt"
        other.write_text('[ ] T "Context" id:context-1\n', encoding="utf-8")
        from fastapi.testclient import TestClient

        client = TestClient(
            webapp.create_app(
                paths=[str(self.path), str(other)], writable_path=str(self.path)
            )
        )
        preview = client.post(
            "/api/quick/resolve",
            json={"text": "First +Work", "syntax": "todo"},
        ).json()
        other.write_text('[ ] T "Changed context" id:context-1\n', encoding="utf-8")
        response = client.post(
            "/api/items/capture",
            headers={"If-Match": preview["source_revision"]},
            json={
                "text": "First +Work",
                "syntax": "todo",
                "context_token": preview["context_token"],
                "expected_source_revision": preview["source_revision"],
            },
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("", self.path.read_text(encoding="utf-8"))

    def test_completed_todo_is_previewed_and_override_is_rejected(self):
        preview = self.preview("x 2026-10-27 2026-10-26 Done +Work")
        self.assertEqual(200, preview.status_code, preview.text)
        data = preview.json()
        self.assertEqual("[x]", data["status"])
        self.assertEqual(["2026-10-27"], data["details"]["done"])
        self.assertEqual(["2026-10-26"], data["details"]["created"])
        response = self.client.post(
            "/api/items/capture",
            headers={"If-Match": data["source_revision"]},
            json={
                "text": "x 2026-10-27 2026-10-26 Done +Work",
                "syntax": "todo",
                "type": "E",
                "context_token": data["context_token"],
                "expected_source_revision": data["source_revision"],
            },
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("", self.path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
