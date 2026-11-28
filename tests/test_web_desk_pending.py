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


class DeskLoadingCopyTests(unittest.TestCase):
    def test_unloaded_calendar_is_not_presented_as_empty(self):
        update_next = _between("function updateNext(d)", "// ---- Tasks ----")
        self.assertLess(update_next.index("t.loading"), update_next.index("t.noNext"))
        timeline = _between("function renderTimeline()", "function updateNext")
        self.assertLess(timeline.index("t.loading"), timeline.index("t.noEvents"))


if __name__ == "__main__":
    unittest.main()
