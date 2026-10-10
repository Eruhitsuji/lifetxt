"""Regression checks for the Items native export and bulk input workflow."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from lifetxt import mutation, web_assets, webapp


_BULK_NODE_CHECK = r"""
const assert = require("node:assert/strict");
const vm = require("node:vm");
const source = process.argv[1];

function classes() {
  const values = new Set();
  return {
    add: key => values.add(key),
    remove: key => values.delete(key),
    contains: key => values.has(key),
  };
}
const modal = {hidden: true, classList: classes()};
const body = {classList: classes()};
const opener = {focus() {}};
const input = {value: "", disabled: false, focus() {this.focused = true;}};
function node() {
  return {
    style: {}, children: [], value: "",
    get textContent() {return this.value;},
    set textContent(value) {this.value = value; this.children = [];},
    appendChild(child) {this.children.push(child);},
  };
}
const preview = node();
const add = {disabled: true};
const elements = {
  "bulk-input-modal": modal,
  "bulk-input-text": input,
  "bulk-input-preview": preview,
  "bulk-input-add": add,
};
let batchCalls = [];
let batchHeaders = [];
let healthCalls = 0;
const context = {
  TextEncoder,
  t: text => text,
  document: {
    body,
    createElement: node,
    createTextNode: text => ({textContent: text}),
    activeElement: opener,
    getElementById: id => elements[id],
    querySelector: selector => selector === ".modal-backdrop.open" && modal.classList.contains("open") ? modal : null,
    addEventListener() {},
  },
  window: {confirm: () => true},
  api: async (path, opts) => {
    if (path === "/api/items/preview") return {ok: true, item_count: 2, diagnostics: [], context_token: "token", source_revision: "r1", review_scope: {context: "fixed_paths"}};
    if (path === "/api/health") {healthCalls++; throw Error("Health must not refresh a reviewed revision");}
    if (path === "/api/items/batch") {
      batchCalls.push(JSON.parse(opts.body));
      batchHeaders.push(opts.headers);
      return {ok: true, saved: 2};
    }
    throw Error("Unexpected API: " + path);
  },
  showToast() {},
  loadItems: async () => {},
};
vm.runInNewContext(source, context);

async function main() {
  context.openBulkInput();
  assert.equal(modal.hidden, false, "modal must remove hidden");
  assert.equal(modal.classList.contains("open"), true, "CSS .open must be applied");
  assert.equal(input.focused, true, "editor must receive focus");
  input.value = "[ ] T First\n[ ] T Second\n";
  await context.previewBulkInput();
  assert.equal(add.disabled, false, "a valid preview enables save");
  input.value = "[ ] T Changed\n[ ] T Another\n";
  context.invalidateBulkPreview(); // the textarea's oninput callback
  assert.equal(add.disabled, true, "editing disables stale preview");
  await context.addAllBulkInput();
  assert.equal(batchCalls.length, 0, "old preview must never be saved");
  await context.previewBulkInput();
  await context.addAllBulkInput();
  assert.equal(batchCalls.length, 1);
  assert.equal(batchCalls[0].text, "[ ] T Changed\n[ ] T Another\n");
  assert.equal(batchCalls[0].expected_source_revision, "r1");
  assert.equal(batchCalls[0].context_token, "token");
  assert.equal(batchHeaders[0]["If-Match"], "r1");
  assert.equal(healthCalls, 0);
  assert.equal(modal.hidden, true, "modal closes after success");
  assert.equal(modal.classList.contains("open"), false);

  context.openBulkInput();
  input.value = "[ ] T Stale\n";
  let resolveParse;
  const oldApi = context.api;
  context.api = async (path, opts) => path === "/api/items/preview" ?
    new Promise(resolve => { resolveParse = resolve; }) : oldApi(path, opts);
  const pending = context.previewBulkInput();
  input.value = "[ ] T New\n";
  context.invalidateBulkPreview();
  resolveParse({ok: true, item_count: 1, diagnostics: []});
  await pending;
  assert.equal(add.disabled, true, "a stale async preview must not enable saving");
  context.api = oldApi;
  const full = {
    ok: true, item_count: 12, context_token: "full-token", source_revision: "r1",
    items: Array.from({length: 12}, (_, i) => ({
      title: "Record " + i, details: {body: ["<script>literal body " + i + "</script>"], due: ["2026-10-12"]},
    })),
    diagnostics: Array.from({length: 12}, (_, i) => ({
      severity: "warning", code: "W215", scope: "batch", source: "batch", line: i + 1, message: "Missing " + i,
    })), review_scope: {context: "checked_manifest", source_count: 2, omitted_records: 0, omitted_diagnostics: 0},
  };
  context.api = async (path, opts) => path === "/api/items/preview" ? full : oldApi(path, opts);
  await context.previewBulkInput();
  assert.equal(add.disabled, false, "warnings alone permit adding");
  const sections = preview.children.filter(n => n.children?.length === 2);
  assert.equal(sections.length, 15, "original, all 12 records, diagnostics and coverage are inspectable");
  assert.ok(sections[12].children[1].textContent.includes("literal body 11"), "last body is not truncated");
  assert.ok(sections[13].children[1].textContent.includes("Missing 11"), "last diagnostic is not truncated");
  assert.equal(sections[1].children[1].children.length, 0, "body markup stays text");
  context.api = async (path, opts) => path === "/api/items/preview" ? {...full, read_only: true} : oldApi(path, opts);
  await context.previewBulkInput();
  assert.equal(add.disabled, true, "read-only review never enables Add all");
  context.api = async () => {throw Object.assign(Error("private path must not appear"), {detail:{reason:"source_membership_changed"}});};
  await context.previewBulkInput();
  assert.equal(add.disabled, true, "failed review cannot enable Add all");
  assert.ok(preview.textContent.includes("Reload the server"));
  assert.ok(!preview.textContent.includes("private path"));
  assert.equal(input.disabled, false, "review failure leaves correction/retry usable");
  context.api = oldApi;
  await context.previewBulkInput();
  assert.equal(add.disabled, false, "a fresh successful review recovers");
  context.api = async () => ({ok:true, item_count:1, diagnostics:[]});
  await context.previewBulkInput();
  assert.equal(add.disabled, true, "text-only parse response is not a contextual review");
  const errors = [
    [409, "CONTEXT_CHANGED", "source_membership_changed", "Reload the server"],
    [409, "CONTEXT_CHANGED", "source_unavailable", "Check the sources"],
    [409, "CONTEXT_CHANGED", "snapshot_unstable", "Wait for edits"],
    [409, "CONTEXT_CHANGED", "context_or_input_changed", "Workspace or input changed"],
    [409, "CONFLICT", "", "Writable file changed"],
    [409, "CLOCK_SKEW", "", "Check device time"],
    [403, "READ_ONLY", "", "Read-only"],
    [422, "DUPLICATE_ID", "", "Duplicate IDs"],
    [422, "VALIDATION_ERROR", "", "Syntax or validation"],
    [413, "INPUT_TOO_LARGE", "", "512 KiB"],
    [428, "REVISION_REQUIRED", "", "Refresh the page"],
    [500, "", "", "Inspect Items and IDs"],
    [undefined, "", "", "Inspect Items and IDs"],
  ];
  for (const [status, code, reason, message] of errors) {
    let attempts = 0;
    context.api = async (path, opts) => {
      if (path === "/api/items/preview") return full;
      if (path === "/api/items/batch") {
        attempts++;
        assert.equal(JSON.parse(opts.body).context_token, "full-token");
        assert.equal(opts.headers["If-Match"], "r1");
        throw Object.assign(Error("private path or token"), {status, detail:{error:code, reason}});
      }
      throw Error("Unexpected request " + path);
    };
    const retainedText = input.value;
    await context.previewBulkInput();
    assert.equal(add.disabled, false, "explicit successful re-Preview recovers");
    await context.addAllBulkInput();
    assert.equal(add.disabled, true, "failed save clears reviewed binding");
    assert.equal(input.value, retainedText, "failed save keeps input");
    assert.equal(input.disabled, false, "correction remains available");
    assert.ok(preview.textContent.includes(message), preview.textContent);
    assert.ok(!preview.textContent.includes("private path or token"));
    await context.addAllBulkInput();
    assert.equal(attempts, 1, "never retry without explicit re-Preview");
  }
  context.api = oldApi;
  await context.previewBulkInput();
  context.window.confirm = () => {context.closeBulkInput(); context.openBulkInput(); return true;};
  const callsBeforeReset = batchCalls.length;
  await context.addAllBulkInput();
  assert.equal(batchCalls.length, callsBeforeReset, "same-text modal reset invalidates confirmation generation");
  assert.equal(add.disabled, true);
  context.window.confirm = () => true;
  let resolveSave, pendingCalls = 0;
  context.api = async (path, opts) => {
    if (path === "/api/items/preview") return full;
    pendingCalls++;
    return new Promise(resolve => {resolveSave = resolve;});
  };
  await context.previewBulkInput();
  const savePending = context.addAllBulkInput();
  await context.addAllBulkInput();
  await context.previewBulkInput();
  context.closeBulkInput();
  assert.equal(modal.hidden, false, "pending save prevents modal close");
  assert.equal(input.disabled, true);
  assert.equal(pendingCalls, 1, "double click never sends a second batch");
  resolveSave({ok:true, saved:12});
  await savePending;
  assert.equal(modal.hidden, true);
  context.openBulkInput();
  input.value = "[ ] T A\n[ ] T B\n";
  context.api = oldApi;
  const notices = [];
  context.showToast = (message, type) => notices.push({message, type});
  context.loadItems = async () => {throw Error("Refresh only failed");};
  await context.previewBulkInput();
  await context.addAllBulkInput();
  assert.equal(modal.hidden, true, "known successful save remains closed");
  assert.equal(input.value, "", "known success clears input despite failed refresh");
  assert.equal(notices.at(-1).type, "warning");
  assert.ok(notices.at(-1).message.includes("Records saved"));
  context.closeBulkInput();
  assert.equal(modal.hidden, true);
  assert.equal(body.classList.contains("modal-open"), false);
}
main().catch(error => {console.error(error); process.exitCode = 1;});
"""

_EXPORT_NODE_CHECK = r"""
const assert = require("node:assert/strict");
const vm = require("node:vm");
const source = process.argv[1];
const savedView = {value: "team-view"};
const area = {value: ""};
const requests = [];
const notices = [];
let responseOk = true;
const context = {
  currentItems: [], // display limit must not block full native export
  URLSearchParams, Date,
  URL: {createObjectURL: () => "blob:test", revokeObjectURL() {}},
  location: {search: "?text=old-filter&limit=1"},
  document: {
    body: {appendChild() {}},
    getElementById: id => id === "saved-view-select" ? savedView :
      id === "area-select" ? area : null,
    createElement: () => ({click() {}, remove() {}}),
  },
  itemQueryParams: () => new URLSearchParams("kind=T&text=current&limit=1"),
  fetch: async url => {
    requests.push(url);
    return responseOk ? {
      ok: true,
      headers: {get: name => name === "X-Lifetxt-Count" ? "3" : null},
      blob: async () => ({}),
    } : {ok: false, status: 403, json: async () => ({message: "Denied"})};
  },
  showToast: (message, type) => notices.push([message, type]),
  setTimeout() {},
};
vm.runInNewContext(source, context);

async function main() {
  await context.exportItems("life");
  let q = new URLSearchParams(requests.pop().split("?")[1]);
  assert.equal(q.get("saved_view"), "team-view");
  assert.equal(q.has("text"), false, "stale filters must not leak into Saved Views");
  assert.equal(q.has("limit"), false);
  savedView.value = "";
  area.value = "work";
  await context.exportItems("life");
  q = new URLSearchParams(requests.pop().split("?")[1]);
  assert.equal(q.get("area"), "work");
  assert.equal(q.get("open_only"), "true");
  area.value = "";
  await context.exportItems("life");
  q = new URLSearchParams(requests.pop().split("?")[1]);
  assert.equal(q.get("kind"), "T");
  assert.equal(q.get("text"), "current");
  assert.equal(q.has("limit"), false);
  responseOk = false;
  await context.exportItems("life");
  assert.equal(notices.at(-1)[1], "error", "failed export must not show success");
}
main().catch(error => {console.error(error); process.exitCode = 1;});
"""


class NativeWebWorkflowTests(unittest.TestCase):
    def test_items_txt_export_is_visible_and_bulk_modal_uses_css_open(self):
        page = web_assets.HTML_PAGE
        self.assertIn('id="items-export-life"', page)
        self.assertIn("onclick=\"exportItems('life')\"", page)
        self.assertIn('oninput="invalidateBulkPreview()"', page)
        self.assertEqual(page.count("function openBulkInput()"), 1)
        self.assertEqual(page.count("function previewBulkInput()"), 1)
        self.assertIn(".modal-backdrop.open { display: flex; }", page)

    def _run_node(self, expression, runner):
        match = re.search(expression, web_assets.HTML_PAGE, re.DOTALL)
        self.assertIsNotNone(match)
        proc = subprocess.run(
            ["node", "-e", runner, match.group(0)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    @unittest.skipUnless(
        shutil.which("node"), "node is required for browser handler VM checks"
    )
    def test_bulk_modal_preview_and_atomic_save_wiring(self):
        self._run_node(
            r"// All bulk handlers live at page scope;.*?(?=    // ── Dark mode)",
            _BULK_NODE_CHECK,
        )

    @unittest.skipUnless(
        shutil.which("node"), "node is required for native export VM checks"
    )
    def test_native_export_uses_correct_scope_and_checks_response(self):
        self._run_node(
            r"    // ── Export filtered items.*?(?=    // ── Undo for destructive actions)",
            _EXPORT_NODE_CHECK,
        )

    def test_native_api_preview_batch_and_full_export(self):
        try:
            from fastapi.testclient import TestClient
        except (ImportError, RuntimeError):
            self.skipTest("Web optional dependencies unavailable")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('[ ] T "Existing" id:existing\n')
            client = TestClient(webapp.create_app(paths=[path], writable_path=path))
            batch = '[ ] T "First" id:first\n[ ] T "Second" id:second\n'
            preview = client.post("/api/items/parse", json={"line": batch})
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertEqual(preview.json()["item_count"], 2)
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            revision = health.json()["source_revision"]
            response = client.post(
                "/api/items/batch",
                json={"text": batch, "expected_source_revision": revision},
            )
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["saved"], 2)
            exported = client.get("/api/items/export?kind=T&limit=1")
            self.assertEqual(exported.status_code, 200, exported.text)
            self.assertEqual(exported.headers["x-lifetxt-count"], "3")
            self.assertIn("Existing", exported.text)
            self.assertIn("First", exported.text)
            self.assertIn("Second", exported.text)
            with open(path, encoding="utf-8") as handle:
                before = handle.read()
            again = client.post(
                "/api/items/batch",
                json={"text": batch, "expected_source_revision": revision},
            )
            self.assertIn(again.status_code, (409, 422))
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), before)

    def test_batch_rejects_all_workspace_and_all_batch_id_collisions(self):
        try:
            from fastapi.testclient import TestClient
        except (ImportError, RuntimeError):
            self.skipTest("Web optional dependencies unavailable")
        with tempfile.TemporaryDirectory() as folder:
            writable = os.path.join(folder, "life.txt")
            other = os.path.join(folder, "archive.txt")
            with open(writable, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Writable id:shared\n")
            with open(other, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Other id:from-other\n")
            client = TestClient(
                webapp.create_app(paths=[writable, other], writable_path=writable)
            )
            revision = client.get("/api/health").json()["source_revision"]
            with open(writable, encoding="utf-8") as handle:
                before = handle.read()
            for batch in (
                "[ ] T New id:from-other\n",
                "[ ] T New id:shared\n",
                "[ ] T A id:batch\n[ ] T B id:batch\n",
                "[ ] T A id:first id:from-other\n",
            ):
                response = client.post(
                    "/api/items/batch",
                    json={"text": batch, "expected_source_revision": revision},
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"], "DUPLICATE_ID")
                with open(writable, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), before)

    def test_batch_rejects_unsupported_input_and_writable_format(self):
        try:
            from fastapi.testclient import TestClient
        except (ImportError, RuntimeError):
            self.skipTest("Web optional dependencies unavailable")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Existing id:existing\n")
            client = TestClient(webapp.create_app(paths=[path], writable_path=path))
            preview = client.post(
                "/api/items/parse",
                json={"line": "#! format_version: 2\n[ ] T Future id:future\n"},
            )
            self.assertEqual(preview.status_code, 422, preview.text)
            self.assertEqual(preview.json()["error"], "UNSUPPORTED_FORMAT")
            revision = client.get("/api/health").json()["source_revision"]
            batch = client.post(
                "/api/items/batch",
                json={
                    "text": "#! format_version: 2\n[ ] T Future id:future\n",
                    "expected_source_revision": revision,
                },
            )
            self.assertEqual(batch.status_code, 422, batch.text)
            self.assertEqual(batch.json()["error"], "UNSUPPORTED_FORMAT")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("#! format_version: 2\n[ ] T Future id:future\n")
            new_revision = mutation.read_text_snapshot(path).content_hash
            rejected = client.post(
                "/api/items/batch",
                json={
                    "text": "[ ] T New id:new\n",
                    "expected_source_revision": new_revision,
                },
            )
            self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertEqual(rejected.json()["error"], "UNSUPPORTED_FORMAT_VERSION")


if __name__ == "__main__":
    unittest.main()
