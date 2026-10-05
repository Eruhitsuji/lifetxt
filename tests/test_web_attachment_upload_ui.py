"""Execute the packaged upload UI with Node; no optional Web dependencies."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "lifetxt/web_assets_js_21.js"

HARNESS = r"""
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.dataset = {}; this.attrs = {}; this.value = ""; this.disabled = false; this.files = []; this.textContent = ""; }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, fn) { this[k] = fn; }
  set innerHTML(_) { throw Error("Untrusted HTML rendering"); }
}
const document = {createElement: tag => new Element(tag)};
const t = value => value;
const _drawerIdFor = item => item.id || item.details?.id?.[0] || "";
let display = false;
const isDisplayMode = () => display;
let drawerEditing = false;
let refreshed = 0, opened = 0;
let current = {id: "sample", editable: true, status: "[ ]", type: "T", title: "Sample", details: {id: ["sample"]}};
let revision = "a".repeat(64);
let policy = {contract_version: "1", max_upload_bytes: 32, upload_enabled: true};
let fail = null, hold = null, mismatch = false;
let calls = [], postCalls = [];
let refreshFails = false;
const refreshAll = async () => { refreshed++; if (refreshFails) throw Error("Refresh failed"); };
const openDrawer = () => { opened++; disposeAttachmentUpload(); };
async function api(path, options) {
  calls.push({path, options});
  if (path === "/api/attachments/upload" && options?.method === "POST") {
    postCalls.push(options);
    if (hold) await hold;
    if (fail) throw fail;
    return {contract_version: "1", display_name: options.body.name, size_bytes: options.body.size,
      media_type: "text/plain", source_revision: "b".repeat(64), attachment_id: "opaque-not-authority",
      path: "/DO-NOT-RENDER", url: "https://DO-NOT-USE"};
  }
  if (path === "/api/attachments/upload") return policy;
  if (path === "/api/capabilities") return {remote_clock: {client_time_header: "X-Test-Time"}};
  if (path === "/api/revision") { const result = {revision}; if (mismatch) revision = "c".repeat(64); return result; }
  if (path.startsWith("/api/items/id/")) return {item: current};
  throw Error(path);
}
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
async function mount(item = current) {
  disposeAttachmentUpload();
  const root = new Element("div"); mountAttachmentUpload(item, root); await settle();
  return attachmentUploadView;
}
const makeFile = (name, size) => ({name, size, arrayBuffer() { throw Error("File read before size check"); }, text() { throw Error("File read"); }});
const choose = (view, name, size) => { view.input.files = [makeFile(name, size)]; selectAttachmentFile(view); };
const results = {};
results.names = ["report.txt", '<img onerror="x">.txt', "日本語📝.txt", "e\u0301.txt"].map(attachmentNameValid);
results.clockFeedback = attachmentErrorMessage({status: 409, detail: {error: "CLOCK_SKEW"}});
results.badNames = ["../bad", "CON.txt", "bad\u202etxt", "bad\0.txt", "bad:txt", "bad.", " ", "é".repeat(128)].map(attachmentNameValid);
let view = await mount();
results.ready = view.ready && view.limit === 32 && !view.input.disabled;
choose(view, "large.txt", 33); results.oversize = !view.file && view.submit.disabled && postCalls.length === 0;
choose(view, "empty.txt", 0); results.empty = !view.file;
choose(view, "bad\u202etxt", 2); results.bidi = !view.file && !view.selected.textContent.includes("\u202e");
choose(view, '<img onerror="x">.txt', 3);
results.safeSelection = view.selected.textContent.includes('<img onerror="x">');
await submitAttachmentUpload(view);
results.success = {opened, refreshed, body: postCalls[0].body.name, headers: postCalls[0].headers,
  receipt: lastAttachmentUpload, retained: view.file, cleared: view.input.value};
policy.upload_enabled = false;
view = await mount(); results.readonlyPolicy = !view.ready && view.input.disabled;
policy.upload_enabled = true;
results.readonlyItem = await mount({...current, editable: false}) === null;
results.generated = await mount({...current, generated: true}) === null;
results.missingId = await mount({...current, id: "", details: {}}) === null;
display = true; results.display = await mount() === null; display = false;
view = await mount({...current, title: "Old snapshot"}); results.staleVisible = !view.ready && view.needsRefresh;
mismatch = true; view = await mount(); results.changingSource = !view.ready && view.needsRefresh; mismatch = false; revision = "a".repeat(64);
results.errors = [];
for (const status of [409, 401, 403, 413, 415, 429, 503, 0]) {
  view = await mount(); choose(view, "report.txt", 3); fail = {status, message: '<script>bad</script> /private/path'};
  const before = postCalls.length;
  await submitAttachmentUpload(view); await submitAttachmentUpload(view);
  results.errors.push({status, count: postCalls.length - before, disabled: view.input.disabled,
    needsRefresh: view.needsRefresh, file: view.file, feedback: view.feedback.textContent});
}
fail = null; view = await mount(); choose(view, "once.txt", 3);
let release; hold = new Promise(resolve => release = resolve);
const pending = submitAttachmentUpload(view); await settle(); await submitAttachmentUpload(view);
results.pending = view.submit.disabled && view.input.disabled && view.refresh.disabled && view.root.attrs["aria-busy"] === "true";
const beforeNavigate = opened; const previous = view;
view = await mount(); choose(view, "other.txt", 3); await submitAttachmentUpload(view);
results.navigation = !view.file && previous.file === null;
release(); await pending; hold = null;
results.noLateOpen = opened === beforeNavigate;
results.finished = !attachmentUploadPending && !view.input.disabled;
view = await mount(); choose(view, "draft.txt", 3); drawerEditing = true;
const beforeEdit = opened; await submitAttachmentUpload(view); results.noEditorOverwrite = opened === beforeEdit; drawerEditing = false;
view = await mount(); choose(view, "refresh.txt", 3); refreshFails = true; await submitAttachmentUpload(view);
results.refreshFailure = view.needsRefresh && view.feedback.textContent.includes("Attached, but");
refreshFails = false; await view.refresh.click(); await settle(); results.explicitRefresh = opened > beforeEdit;
process.stdout.write(JSON.stringify(results));
"""


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class AttachmentUploadUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "probe.js"
            script.write_text(
                "async function main() {\n"
                + SOURCE.read_text(encoding="utf-8")
                + HARNESS
                + "\n}\nmain().catch(e => { console.error(e); process.exitCode = 1; });",
                encoding="utf-8",
            )
            run = subprocess.run(
                ["node", str(script)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        if run.returncode:
            raise AssertionError(run.stderr)
        cls.evidence = json.loads(run.stdout)

    def test_filename_text_and_unicode_policy(self):
        self.assertTrue(all(self.evidence["names"]))
        self.assertFalse(any(self.evidence["badNames"]))
        self.assertTrue(self.evidence["safeSelection"])
        self.assertTrue(self.evidence["bidi"])

    def test_policy_and_known_size_gates_before_reading(self):
        for key in (
            "ready",
            "oversize",
            "empty",
            "readonlyPolicy",
            "readonlyItem",
            "generated",
            "missingId",
            "display",
        ):
            self.assertTrue(self.evidence[key], key)

    def test_stable_snapshot_matches_the_visible_record(self):
        self.assertTrue(self.evidence["staleVisible"])
        self.assertTrue(self.evidence["changingSource"])

    def test_raw_file_exact_revision_marker_and_clock_contract(self):
        result = self.evidence["success"]
        self.assertEqual(1, result["opened"])
        self.assertEqual(1, result["refreshed"])
        headers = result["headers"]
        self.assertEqual("application/octet-stream", headers["Content-Type"])
        self.assertEqual("a" * 64, headers["X-Lifetxt-Expected-Revision"])
        self.assertEqual("1", headers["X-Lifetxt-Upload"])
        self.assertEqual("sample", headers["X-Lifetxt-Item-Id"])
        self.assertTrue(headers["X-Test-Time"].endswith("Z"))
        self.assertIn("%3Cimg", headers["X-Lifetxt-Filename"])

    def test_receipt_has_only_safe_metadata_and_selection_is_released(self):
        result = self.evidence["success"]
        self.assertEqual(
            {"itemId", "display_name", "media_type", "size_bytes"},
            set(result["receipt"]),
        )
        self.assertIsNone(result["retained"])
        self.assertEqual("", result["cleared"])

    def test_post_failures_require_explicit_refresh_and_never_retry(self):
        for result in self.evidence["errors"]:
            with self.subTest(status=result["status"]):
                self.assertEqual(1, result["count"])
                self.assertTrue(result["disabled"])
                self.assertTrue(result["needsRefresh"])
                self.assertIsNone(result["file"])
                self.assertNotIn("script", result["feedback"])
                self.assertNotIn("private/path", result["feedback"])

    def test_pending_navigation_and_editor_lifecycle(self):
        for key in (
            "pending",
            "navigation",
            "noLateOpen",
            "finished",
            "noEditorOverwrite",
        ):
            self.assertTrue(self.evidence[key], key)

    def test_committed_upload_refresh_failure_is_distinct_from_upload_failure(self):
        self.assertTrue(self.evidence["refreshFailure"])
        self.assertTrue(self.evidence["explicitRefresh"])

    def test_clock_failure_does_not_masquerade_as_a_source_conflict(self):
        self.assertIn("device time", self.evidence["clockFeedback"])
        self.assertNotIn("source changed", self.evidence["clockFeedback"])

    def test_no_client_persistence_readers_or_debug_content(self):
        source = SOURCE.read_text(encoding="utf-8")
        for token in (
            "localStorage",
            "sessionStorage",
            "console.",
            "FileReader",
            "createObjectURL",
            "innerHTML",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
