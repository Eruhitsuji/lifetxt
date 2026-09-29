"""Headless Chromium checks for the Planner phone viewport matrix."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.web_assets import PLANNER_HTML_PAGE

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "browser_planner_probe.mjs"


def browser_path():
    for candidate in (
        os.environ.get("LIFETXT_BROWSER_BIN"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(browser_path(), "Chrome/Chromium unavailable")
class PlannerBrowserTests(unittest.TestCase):
    def test_phone_landscape_and_language_matrix(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", encoding="utf-8", delete=False
        ) as handle:
            handle.write(PLANNER_HTML_PAGE)
            filename = handle.name
        try:
            run = subprocess.run(
                ["node", str(PROBE), browser_path(), filename],
                capture_output=True,
                text=True,
                timeout=90,
            )
        finally:
            os.unlink(filename)
        self.assertEqual(0, run.returncode, run.stderr or run.stdout)
        matrix = json.loads(run.stdout)
        self.assertEqual([320, 360, 390, 430, 667, 390], [x["width"] for x in matrix])
        for item in matrix:
            with self.subTest(item["width"], item["height"]):
                self.assertLessEqual(item["scrollWidth"], item["width"])
                self.assertGreaterEqual(item["dateHeight"], 44)
                self.assertGreaterEqual(item["captureHeight"], 44)
        self.assertEqual("予定", matrix[1]["schedule"])
        self.assertEqual("Schedule", matrix[0]["schedule"])


if __name__ == "__main__":
    unittest.main()
