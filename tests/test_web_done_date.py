"""Task completion date UI and existing atomic persistence contract (#861)."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from lifetxt.web_assets import HTML_PAGE

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class CompletionDateInteractionTests(unittest.TestCase):
    def run_js(self, scenario, timezone="Asia/Tokyo"):
        start = HTML_PAGE.index("    let drawerDoneSaving = false;")
        end = HTML_PAGE.index("    async function drawerComplete()", start)
        cancel_start = HTML_PAGE.index("    function drawerCancelEdit()")
        cancel_end = HTML_PAGE.index(
            "    async function drawerSaveEdit()", cancel_start
        )
        script = r"""
const assert = require("node:assert/strict");
let drawerItem = {line: 2, id: "task-1", editable: true, type: "T", status: "[ ]", title: "Task", details: {id: ["task-1"], tag: ["keep"]}};
let drawerEditing = false;
let appConfig = {};
const calls = [], errors = [], toasts = [];
const t = value => value;
let undo, reopened, fail = false, release;
let pause = false;
const elements = Object.fromEntries(["drawer-head-btns", "drawer-body", "drawer-done-form", "drawer-done-date", "drawer-done-time"].map(id => [id, {innerHTML: "", value: "", focus() {}, reportValidity() { return true; }}]));
const document = {getElementById: id => elements[id]};
const escapeHtml = value => String(value).replaceAll("<", "&lt;");
const api = async (path, options) => {
  calls.push({path, body: JSON.parse(options.body)});
  if (fail) throw new Error("Conflict");
  if (pause) await new Promise(resolve => {release = resolve;});
};
const registerUndo = (message, callback) => {undo = callback;};
const closeDrawer = () => {drawerItem = null;};
const refreshAll = async () => {};
const openDrawer = item => {reopened = item;};
const showActionableError = (message, error) => errors.push([message, error.message]);
const showToast = (...args) => toasts.push(args);
"""
        script += HTML_PAGE[start:end] + HTML_PAGE[cancel_start:cancel_end]
        script += (
            "\n(async () => {\n"
            + scenario
            + "\n})().catch(e => {console.error(e);process.exit(1);});"
        )
        result = subprocess.run(
            [shutil.which("node"), "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "TZ": timezone},
            timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_now_writes_status_and_seconds_timestamp_once_and_undo_restores(self):
        self.run_js(r"""
const original = JSON.parse(JSON.stringify(drawerItem));
drawerDoneDate();
const html = elements["drawer-body"].innerHTML;
const handler = html.match(/onclick="([^"]+)"/)[1];
const before = Date.now();
await eval(handler);
assert.equal(calls.length, 1);
assert.equal(calls[0].path, "/api/items/id/task-1");
assert.equal(calls[0].body.status, "[x]");
assert.match(calls[0].body.details.done[0], /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
assert.ok(Math.abs(Date.parse(calls[0].body.details.done[0]) - before) < 1500);
assert.deepEqual(calls[0].body.details.tag, ["keep"]);
await undo();
assert.deepEqual(calls[1].body, {status: original.status, type: original.type, title: original.title, details: original.details});
""")

    def test_custom_date_and_explicit_overwrite_do_not_mutate_original(self):
        self.run_js(r"""
drawerItem.details.done = ["2025-01-01"];
const original = JSON.stringify(drawerItem);
drawerDoneDate();
assert.ok(elements["drawer-body"].innerHTML.includes("replace the existing done value"));
assert.equal(calls.length, 0);
elements["drawer-done-date"].value = "2026-09-19";
await drawerSaveDoneDate();
assert.deepEqual(calls[0].body.details.done, ["2026-09-19"]);
await undo();
assert.deepEqual(calls[1].body.details.done, ["2025-01-01"]);
assert.equal(JSON.parse(original).details.done[0], "2025-01-01");
""")

    def test_custom_time_keeps_the_selected_instant_across_timezone(self):
        self.run_js(r"""
elements["drawer-done-date"].value = "2026-09-19";
elements["drawer-done-time"].value = "00:15";
await drawerSaveDoneDate();
assert.deepEqual(calls[0].body.details.done, ["2026-09-18T15:15:00Z"]);
""")

    def test_cancel_and_invalid_input_make_no_write(self):
        self.run_js(r"""
const original = JSON.stringify(drawerItem);
drawerDoneDate();
drawerCancelEdit();
assert.equal(JSON.stringify(reopened), original);
assert.equal(drawerEditing, false);
elements["drawer-done-form"].reportValidity = () => false;
await drawerSaveDoneDate();
assert.equal(calls.length, 0);
""")

    def test_dst_gap_refused_instead_of_silently_normalized(self):
        self.run_js(
            r"""
elements["drawer-done-date"].value = "2026-03-08";
elements["drawer-done-time"].value = "02:30";
await drawerSaveDoneDate();
assert.equal(calls.length, 0);
assert.equal(toasts.length, 1);
""",
            timezone="America/New_York",
        )

    def test_plain_done_preserves_existing_done_and_idless_fallback(self):
        self.run_js(r"""
delete drawerItem.id;
delete drawerItem.details.id;
drawerItem.details.done = ["2025-01-01"];
await drawerMarkDone();
assert.equal(calls[0].path, "/api/items/2");
assert.deepEqual(calls[0].body.details.done, ["2025-01-01"]);
""")

    def test_disabled_records_and_non_tasks_do_not_offer_custom_completion(self):
        self.run_js(r"""
for (const update of [{editable: false}, {status: "[x]"}, {status: "[-]"}, {type: "H"}]) {
  drawerItem = {...drawerItem, editable: true, status: "[ ]", type: "T", ...update};
  drawerDoneDate();
  await drawerMarkDone("2026-09-19");
}
assert.equal(calls.length, 0);
assert.equal(elements["drawer-body"].innerHTML, "");
""")

    def test_failed_save_retains_original_and_can_retry(self):
        self.run_js(r"""
const original = JSON.stringify(drawerItem);
fail = true;
await drawerMarkDone("2026-09-19");
assert.equal(JSON.stringify(drawerItem), original);
assert.equal(errors.length, 1);
assert.equal(undo, undefined);
assert.equal(drawerDoneSaving, false);
fail = false;
await drawerMarkDone("2026-09-19");
assert.equal(calls.length, 2);
""")

    def test_double_submit_has_only_one_write(self):
        self.run_js(r"""
pause = true;
const first = drawerMarkDone("2026-09-19");
await drawerMarkDone("2026-09-20");
assert.equal(calls.length, 1);
release();
await first;
""")


@unittest.skipIf(TestClient is None, "web extras unavailable")
class CompletionDatePersistenceTests(unittest.TestCase):
    def setUp(self):
        from lifetxt.webapp import create_app

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "life.txt"
        self.path.write_text("[ ] T Task id:task-1 tag:keep\n", encoding="utf-8")
        self.app = create_app(
            [str(self.path)],
            writable_path=str(self.path),
            config={"web": {"revision_mode": "required"}},
        )
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def complete(self, value, revision=None):
        revision = revision or self.client.get("/api/revision").headers["etag"]
        return self.client.put(
            "/api/items/id/task-1",
            headers={"If-Match": revision},
            json={
                "status": "[x]",
                "details": {"id": ["task-1"], "tag": ["keep"], "done": [value]},
            },
        )

    def test_date_and_timestamp_survive_reload_with_one_completed_event(self):
        from lifetxt.parser import parse_text

        for value in ["2026-09-19", "2026-09-18T15:15:00Z"]:
            with self.subTest(value=value):
                self.path.write_text(
                    "[ ] T Task id:task-1 tag:keep\n", encoding="utf-8"
                )
                response = self.complete(value)
                self.assertEqual(200, response.status_code, response.text)
                with TestClient(self.app) as reload_client:
                    item = reload_client.get("/api/items/id/task-1").json()["item"]
                self.assertEqual("[x]", item["status"])
                self.assertEqual([value], item["details"]["done"])
                items, diagnostics = parse_text(self.path.read_text(encoding="utf-8"))
                events = [i for i in items if i.details.get("event") == ["completed"]]
                self.assertEqual(1, len(events))
                self.assertFalse([d for d in diagnostics if d.severity == "error"])

    def test_stale_revision_changes_neither_state_nor_history(self):
        revision = self.client.get("/api/revision").headers["etag"]
        self.path.write_text("[ ] T Changed id:task-1 tag:keep\n", encoding="utf-8")
        before = self.path.read_bytes()
        response = self.complete("2026-09-19", revision)
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual(before, self.path.read_bytes())
