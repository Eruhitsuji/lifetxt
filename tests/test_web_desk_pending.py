"""Node-driven tests for the Desk loading and pending-write behavior (#1821)."""

import json
import shutil
import subprocess
import unittest
from importlib import resources

SCRIPT = resources.files("lifetxt").joinpath("web_desk.js").read_text("utf-8")


def _between(start, end):
    begin = SCRIPT.index(start)
    return SCRIPT[begin : SCRIPT.index(end, begin)]


@unittest.skipUnless(shutil.which("node"), "node is not available")
class DeskPendingTests(unittest.TestCase):
    def run_node(self, body):
        code = (
            "let pending = false, order = [], fresh = true;\n"
            "const t = {busy: 'busy', saving: 'saving', saved: 'saved', staleView: 'stale'};\n"
            "const say = text => order.push(text);\n"
            "const load = async () => { order.push('load:' + pending); return fresh; };\n"
            + _between("function busy()", "\n  function responseRevision")
            + _between("async function mutate(action)", "const putBody")
            + "(async () => {\n"
            + body
            + "\nconsole.log(JSON.stringify(order));\n})();"
        )
        result = subprocess.run(
            ["node", "-e", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_write_stays_pending_until_the_screen_is_refreshed(self):
        order = self.run_node(
            "const first = mutate(async () => 'ok');\n"
            "await mutate(async () => { order.push('second ran'); });\n"
            "await first; order.push('pending:' + pending);"
        )
        self.assertEqual(order, ["saving", "busy", "load:true", "ok", "pending:false"])

    def test_failed_write_reloads_once_and_is_not_retried(self):
        order = self.run_node(
            "await mutate(async () => { order.push('write'); throw Error('conflict'); });"
        )
        self.assertEqual(order, ["saving", "write", "load:true", "conflict"])

    def test_failed_refresh_is_reported_with_the_save_result(self):
        order = self.run_node("fresh = false; await mutate(async () => 1);")
        self.assertEqual(order[-1], "saved stale")


@unittest.skipUnless(shutil.which("node"), "node is not available")
class DeskRefreshTests(unittest.TestCase):
    def test_manual_and_automatic_refresh_share_the_same_request(self):
        setup = """
const assert = require("node:assert/strict");
const options = [0, 15000, 30000, 60000, 300000].map(value => ({value: String(value)}));
const interval = {options, setAttribute() {}};
const button = {setAttribute() {}, removeAttribute() {}};
const $ = id => id === "desk-refresh" ? button : interval;
const document = {visibilityState: "visible"};
let timer = null, saved = "invalid", releaseConfig, configs = 0, loads = 0, pending = false;
const DEFAULT_REFRESH_MS = 60000;
let refreshMs = DEFAULT_REFRESH_MS, refreshTimer = null, refreshing = null, nextDateCheck = 0;
const localStorage = {getItem: () => saved, setItem: (_key, value) => {saved = value;}};
const setInterval = (callback, ms) => (timer = {callback, ms});
const clearInterval = () => {timer = null;};
const diagnostics = [];
const t = {loading: "loading", refreshed: "refreshed", refreshFailed: "failed"};
const say = message => diagnostics.push(message);
const busy = () => say("busy");
const syncConfig = () => {configs++; return new Promise(resolve => {releaseConfig = resolve;});};
const load = async () => {loads++; return true;};
"""
        scenario = """
(async () => {
  initRefresh();
  scheduleRefresh();
  assert.equal(interval.value, "60000");
  assert.equal(timer.ms, 60000);
  interval.value = "15000";
  interval.onchange();
  assert.equal(saved, "15000");
  assert.equal(timer.ms, 15000);
  document.visibilityState = "hidden";
  scheduleRefresh();
  assert.equal(timer, null);
  document.visibilityState = "visible";
  scheduleRefresh();
  timer.callback();
  const manual = button.onclick();
  assert.equal(configs, 1);
  releaseConfig();
  await manual;
  assert.equal(loads, 1);
  assert.deepEqual(diagnostics, ["loading", "refreshed"]);

  interval.value = "0";
  interval.onchange();
  assert.equal(timer, null);
  initRefresh();
  assert.equal(interval.value, "0");
  const last = button.onclick();
  assert.equal(configs, 2);
  releaseConfig();
  await last;
  assert.equal(loads, 2);

  const inFlight = button.onclick();
  pending = true;
  await button.onclick();
  releaseConfig();
  await inFlight;
  assert.equal(loads, 2);
  assert.equal(diagnostics.at(-1), "busy");
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
        result = subprocess.run(
            ["node"],
            input=(
                setup
                + _between("async function refreshDesk", "function syncTimers")
                + scenario
            ),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class DeskLoadingCopyTests(unittest.TestCase):
    def test_unloaded_calendar_is_not_presented_as_empty(self):
        update_next = _between("function updateNext(d)", "// ---- Tasks ----")
        self.assertLess(update_next.index("t.loading"), update_next.index("t.noNext"))
        timeline = _between("function renderTimeline()", "function updateNext")
        self.assertLess(timeline.index("t.loading"), timeline.index("t.noEvents"))


if __name__ == "__main__":
    unittest.main()
