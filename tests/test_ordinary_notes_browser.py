"""#1020 ordinary/raw browsing controls in Existing and Remote Web UI."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.remote_web import _remote_page
from lifetxt.web_assets import HTML_PAGE
from tests.test_web_planner_browser import browser_path


@unittest.skipUnless(
    shutil.which("node") and browser_path(), "Node/Chromium unavailable"
)
class OrdinaryNotesBrowserTests(unittest.TestCase):
    def test_ordinary_and_raw_web_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            web, remote = Path(temp) / "web.html", Path(temp) / "remote.html"
            web.write_text(HTML_PAGE, encoding="utf-8")
            remote.write_text(_remote_page("test"), encoding="utf-8")
            run = subprocess.run(
                [
                    "node",
                    str(Path(__file__).with_name("browser_ordinary_notes_probe.mjs")),
                    browser_path(),
                    str(web),
                    str(remote),
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
        self.assertEqual(0, run.returncode, run.stderr or run.stdout)
        for row in json.loads(run.stdout):
            with self.subTest(width=row["width"], lang=row["lang"]):
                self.assertIn("ordinary_notes=true", row["ordinary"]["url"])
                self.assertNotIn("kind=", row["ordinary"]["url"])
                self.assertEqual(12, row["ordinary"]["count"])
                self.assertEqual(
                    "通常のメモ" if row["lang"] == "ja" else "Ordinary Notes",
                    row["ordinary"]["label"],
                )
                self.assertEqual(
                    "通常のメモ" if row["lang"] == "ja" else "Ordinary Notes",
                    row["first"]["label"],
                )
                self.assertIn("kind=N", row["raw"]["url"])
                self.assertEqual(32, row["raw"]["count"])
                self.assertEqual(20, len(row["first"]["data"]["items"]))
                self.assertEqual(24, row["first"]["data"]["total"])
                self.assertTrue(row["first"]["nextVisible"])
                self.assertLessEqual(row["first"]["scrollWidth"], row["width"])
                self.assertEqual(4, len(row["next"]["data"]["items"]))
                self.assertEqual("n20", row["next"]["data"]["items"][0]["id"])
                self.assertTrue(row["next"]["nextHidden"])
