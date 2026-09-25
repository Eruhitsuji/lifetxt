"""Real-browser layout validation for mobile Quick Capture viewports."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lifetxt.web_assets import HTML_PAGE


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "browser_mobile_capture_probe.mjs"


def _browser_path():
    configured = os.environ.get("LIFETXT_BROWSER_BIN")
    candidates = (
        configured,
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    return next((path for path in candidates if path and os.path.isfile(path)), None)


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
@unittest.skipUnless(_browser_path(), "Chrome/Chromium is not available")
class MobileCaptureBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", encoding="utf-8", delete=False
        ) as handle:
            handle.write(HTML_PAGE)
            html_path = handle.name
        try:
            process = subprocess.run(
                ["node", str(PROBE), _browser_path(), html_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
            )
        finally:
            os.unlink(html_path)
        if process.returncode:
            raise AssertionError(process.stderr or process.stdout)
        evidence = json.loads(process.stdout)
        cls.results = evidence["viewports"]
        cls.interactions = evidence["interactions"]

    def test_every_target_viewport_has_no_horizontal_page_overflow(self):
        self.assertEqual(6, len(self.results))
        for result in self.results:
            with self.subTest(result["name"]):
                self.assertTrue(result["bodyMode"])
                self.assertLessEqual(result["scrollWidth"], result["viewport"]["width"])
                self.assertGreaterEqual(result["card"]["left"], 0)
                self.assertLessEqual(
                    result["card"]["right"], result["viewport"]["width"]
                )
                self.assertLessEqual(
                    result["back"]["right"], result["viewport"]["width"]
                )
                self.assertLess(result["back"]["top"], result["documentHeight"])

    def test_capture_input_is_focused_and_controls_remain_touch_sized(self):
        for result in self.results:
            with self.subTest(result["name"]):
                self.assertEqual("capture-text", result["activeElement"])
                self.assertGreaterEqual(result["input"]["height"], 44)
                self.assertGreaterEqual(result["button"]["height"], 44)
                self.assertGreater(result["input"]["width"], 240)
                self.assertTrue(result["coarsePointer"])

    def test_english_and_japanese_copy_render_in_real_browser(self):
        for result in self.results:
            with self.subTest(result["name"]):
                expected = (
                    "クイックキャプチャ" if result["lang"] == "ja" else "Quick Capture"
                )
                self.assertEqual(expected, result["heading"])

    def test_reduced_height_and_landscape_use_compact_layout(self):
        compact = {result["name"]: result for result in self.results}
        self.assertEqual("none", compact["landscape-keyboard"]["introDisplay"])
        for name in ("landscape-keyboard", "reduced-keyboard"):
            result = compact[name]
            self.assertLess(result["input"]["top"], result["viewport"]["height"])
            self.assertLess(result["button"]["top"], result["viewport"]["height"])

    def test_keyboard_success_refocuses_and_feedback_is_reachable(self):
        success = self.interactions["success"]
        self.assertEqual("", success["value"])
        self.assertEqual("capture-text", success["focused"])
        self.assertIn("Captured: Saved", success["feedback"])
        self.assertGreater(success["feedbackHeight"], 0)

    def test_browser_failure_retains_input_and_refocuses(self):
        failure = self.interactions["failure"]
        self.assertEqual("Fail me", failure["value"])
        self.assertEqual("capture-text", failure["focused"])
        self.assertIn("Capture failed:", failure["feedback"])
        self.assertIn("read-only", failure["feedback"])
        self.assertGreater(failure["feedbackHeight"], 0)

    def test_browser_pending_state_suppresses_duplicate_request(self):
        self.assertTrue(self.interactions["pending"]["disabled"])
        self.assertEqual("true", self.interactions["pending"]["busy"])
        self.assertEqual(1, self.interactions["pendingRequestCount"])


if __name__ == "__main__":
    unittest.main()
