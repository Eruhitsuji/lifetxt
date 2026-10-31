"""Planner card operation placement regression (#1492)."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from lifetxt.web_assets import PLANNER_HTML_PAGE
from tests.test_web_planner_browser import browser_path


@unittest.skipUnless(
    shutil.which("node") and browser_path(),
    "Node and LIFETXT_BROWSER_BIN required",
)
class PlannerActionsBrowserTests(unittest.TestCase):
    def test_operations_align_and_keyboard_details_work(self):
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / "page.html"
            html.write_text(PLANNER_HTML_PAGE, encoding="utf-8")
            result = subprocess.run(
                [
                    "node",
                    str(Path(__file__).with_name("browser_planner_actions_probe.mjs")),
                    browser_path(),
                    str(html),
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(16, len(json.loads(result.stdout)["viewports"]))
