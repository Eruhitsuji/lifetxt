"""Exercise the shared layout URL codec as shipped on both Web pages."""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.web_assets import DESK_HTML_PAGE, PLANNER_HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class LayoutUrlTests(unittest.TestCase):
    def test_versioned_layout_round_trips_without_losing_url_context(self):
        for surface, page in (("desk", DESK_HTML_PAGE), ("planner", PLANNER_HTML_PAGE)):
            with self.subTest(surface=surface):
                codec = re.search(r"const layoutUrl = \{.*?\n\};", page, re.S).group()
                source = (
                    codec
                    + "\n"
                    + r"""
const assert = require("node:assert/strict");
const location = {href: "https://example.test/desk?lang=en&preset=tasks&keep=1&keep=2#calendar"};
const state = {retained: true};
const history = {
  state,
  replaceState(passedState, title, url) {
    assert.equal(passedState, state);
    location.href = String(url);
  },
};
const layout = {cols: [["clock"], ["tasks"]], hidden: [], split: 65};
layoutUrl.write(layout);
const url = new URL(location.href);
assert.equal(url.pathname, "/desk");
assert.equal(url.hash, "#calendar");
assert.equal(url.searchParams.get("lang"), "en");
assert.equal(url.searchParams.get("preset"), "tasks");
assert.deepEqual(url.searchParams.getAll("keep"), ["1", "2"]);
assert.deepEqual(layoutUrl.read(url.searchParams), {v: 1, ...layout});
layoutUrl.write({...layout, split: 60});
assert.equal(new URL(location.href).searchParams.getAll("layout").length, 1);

for (const values of [
  [], ["{"], ["null"], ["[]"], ['{"v":2}'],
  ['{"v":1}', '{"v":1}'],
  [JSON.stringify({v: 1, ignored: "x".repeat(2048)})],
]) {
  const params = new URLSearchParams(values.map(value => ["layout", value]));
  assert.equal(layoutUrl.read(params), null);
}
"""
                )
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "layout-test.cjs"
                    path.write_text(source, encoding="utf-8")
                    run = subprocess.run(
                        ["node", str(path)],
                        capture_output=True,
                        encoding="utf-8",
                        timeout=10,
                    )
                self.assertEqual(run.returncode, 0, run.stderr)
