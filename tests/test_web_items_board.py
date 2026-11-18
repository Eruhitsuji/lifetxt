"""Exercise board writes against the existing revision-bound item contract."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class ItemsBoardTests(unittest.TestCase):
    def test_move_keeps_payload_and_refreshes_without_retry(self):
        start = HTML_PAGE.index("    const BOARD_COLUMNS")
        end = HTML_PAGE.index("    function buildBoardCard", start)
        board = HTML_PAGE[start:end]
        start = HTML_PAGE.index("    const bulkDoneCopy")
        end = HTML_PAGE.index("    function bulkDoneSkip", start)
        payload_helpers = HTML_PAGE[start:end]
        result = subprocess.run(
            ["node"],
            input=board + payload_helpers + """
const assert = require("node:assert/strict");
const task = {type: "T", status: "[ ]", title: "A task", editable: true,
  line: 4, details: {id: ["a"], due: ["2026-12-01"], project: ["work"]}};
const revision = "a".repeat(64);
const calls = [];
let mode = "ok";
let reloads = 0;
let itemsReadOnly = false;
const root = {setAttribute() {}, removeAttribute() {}};
const document = {activeElement: {}, body: {}, getElementById(id) {
  return id === "items" ? root : {value: "board"};
}};
const isKioskMode = () => false;
const isDisplayMode = () => false;
const currentView = () => "items";
const t = text => text;
const showToast = title => calls.push(title);
const showActionableError = title => calls.push(title);
async function reloadItemsBoard() { reloads++; }
async function bulkDoneSnapshot(original, expected) {
  assert.equal(original, task);
  assert.equal(expected, task);
  if (mode === "stale") throw Error("Record changed");
  return {item: task, revision, path: "/api/items/id/a"};
}
async function api(path, options) {
  calls.push({path, options});
  if (mode === "lost") throw Error("Network error");
  return {item: {status: JSON.parse(options.body).status}};
}
(async () => {
  await Promise.all([moveBoardTask(task, "[/]"), moveBoardTask(task, "[x]")]);
  const [{path, options}, success] = calls;
  assert.equal(path, "/api/items/id/a");
  assert.equal(options.headers["If-Match"], '"' + revision + '"');
  assert.deepEqual(JSON.parse(options.body), {
    type: "T", status: "[/]", title: task.title, details: task.details
  });
  assert.equal(task.status, "[ ]");
  assert.equal(success, "Task moved.");
  assert.equal(calls.length, 2);
  assert.equal(reloads, 1);

  mode = "stale";
  calls.length = 0;
  await moveBoardTask(task, "[x]");
  assert.deepEqual(calls, ["Could not move this task."]);
  assert.equal(reloads, 2);

  mode = "lost";
  calls.length = 0;
  await moveBoardTask(task, "[x]");
  assert.equal(calls.length, 2);
  assert.equal(calls[1], "Outcome unknown. Inspect the record before retrying.");
  assert.equal(reloads, 3);

  calls.length = 0;
  await moveBoardTask({...task, editable: false}, "[x]");
  await moveBoardTask({...task, generated: true}, "[x]");
  await moveBoardTask(task, "[>]");
  await moveBoardTask(task, "[ ]");
  itemsReadOnly = true;
  await moveBoardTask(task, "[x]");
  assert.deepEqual(calls, []);
  assert.equal(reloads, 3);
})().catch(error => { console.error(error); process.exitCode = 1; });
""",
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
