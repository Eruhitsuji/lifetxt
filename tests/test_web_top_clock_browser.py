"""Real browser Top clock layout, ticking, and navigation regression checks."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.web_assets import HTML_PAGE
from tests.test_web_mobile_capture_browser import _browser_path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(_browser_path(), "Chrome/Chromium is not available")
class TopClockBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", encoding="utf-8", delete=False
        ) as handle:
            handle.write(HTML_PAGE)
            html_path = handle.name
        try:
            process = subprocess.run(
                [
                    "node",
                    str(ROOT / "tests/browser_top_clock_probe.mjs"),
                    _browser_path(),
                    html_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        finally:
            os.unlink(html_path)
        if process.returncode:
            raise AssertionError(process.stderr or process.stdout)
        cls.evidence = json.loads(process.stdout)

    def test_mobile_language_theme_matrix_has_no_header_or_nav_overflow(self):
        cases = self.evidence["viewports"]
        self.assertEqual(16, len(cases))
        for result in cases:
            with self.subTest(
                width=result["width"], lang=result["lang"], dark=result["dark"]
            ):
                self.assertFalse(result["hidden"])
                self.assertRegex(
                    result["text"], r"^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2} [AP]M$"
                )
                self.assertEqual("TIME", result["tag"])
                self.assertEqual("off", result["live"])
                self.assertEqual("tabular-nums", result["numerals"])
                self.assertTrue(result["dateTime"].endswith("Z"))
                self.assertLessEqual(result["scrollWidth"], result["width"])
                for key in ("rect", "header", "nav"):
                    self.assertGreaterEqual(result[key]["left"], 0)
                    self.assertLessEqual(result[key]["right"], result["width"])
                self.assertEqual(4, result["primaryButtons"])

    def test_seconds_tick_without_extra_requests(self):
        ticking = self.evidence["ticking"]
        self.assertNotEqual(ticking["before"], ticking["after"])
        self.assertEqual(0, ticking["requests"])

    def test_configuration_and_kiosk_navigation(self):
        self.assertTrue(all(self.evidence["modes"].values()))
