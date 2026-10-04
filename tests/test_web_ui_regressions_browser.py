"""Real browser coverage for #1092 against the real parse API and Web shell."""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from tests.test_web_planner_browser import browser_path

try:
    import uvicorn
    from lifetxt.webapp import create_app
except ImportError:
    uvicorn = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(uvicorn, "Web extras unavailable")
@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(browser_path(), "Chrome/Chromium unavailable")
class WebUIRegressionsBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            records = Path(directory) / "life.txt"
            records.write_text(
                '[ ] T "Browser fixture" id:drawer-test\n', encoding="utf-8"
            )
            app = create_app(paths=[str(records)], writable_path=str(records))
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
                server = uvicorn.Server(
                    uvicorn.Config(app, log_level="error", ws="none")
                )
                thread = threading.Thread(
                    target=server.run, kwargs={"sockets": [listener]}, daemon=True
                )
                thread.start()
                try:
                    run = subprocess.run(
                        [
                            "node",
                            str(ROOT / "tests/browser_ui_regressions_probe.mjs"),
                            browser_path(),
                            base_url,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=90,
                    )
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
            if run.returncode:
                raise AssertionError(run.stderr or run.stdout)
            cls.evidence = json.loads(run.stdout)
            if os.environ.get("LIFETXT_BROWSER_EVIDENCE"):
                Path(os.environ["LIFETXT_BROWSER_EVIDENCE"]).write_text(
                    json.dumps(cls.evidence, indent=2), encoding="utf-8"
                )

    def test_raw_import_first_click_cancel_reopen_and_real_parse_feedback(self):
        self.assertEqual(8, len(self.evidence["viewports"]))
        for case in self.evidence["viewports"]:
            with self.subTest(
                width=case["width"], lang=case["lang"], dark=case["dark"]
            ):
                for key in (
                    "initial",
                    "opened",
                    "guidance",
                    "closed",
                    "reopened",
                    "invalid",
                    "validPreview",
                    "populated",
                ):
                    self.assertTrue(case["raw"][key], key)
                self.assertIn(
                    "プレビュー" if case["lang"] == "ja" else "preview",
                    case["raw"]["help"],
                )

    def test_more_links_share_button_geometry_color_hover_and_keyboard_focus(self):
        for case in self.evidence["viewports"]:
            with self.subTest(
                width=case["width"], lang=case["lang"], dark=case["dark"]
            ):
                self.assertLessEqual(case["scrollWidth"], case["width"])
                for link in case["nav"].values():
                    for state, sibling in (
                        ("normal", "sibling"),
                        ("hover", "siblingHover"),
                        ("focus", "siblingFocus"),
                        ("pressed", "siblingPressed"),
                    ):
                        self.assertEqual(link[sibling], link[state], state)
                    self.assertEqual("solid", link["focus"]["outlineStyle"])
                    self.assertGreaterEqual(
                        link["rect"]["height"], 44 if case["width"] == 390 else 37
                    )
                    self.assertGreaterEqual(link["rect"]["left"], 0)
                    self.assertLessEqual(link["rect"]["right"], case["width"])
                    if case["width"] == 390:
                        self.assertEqual(
                            link["rect"]["width"], link["siblingRect"]["width"]
                        )
                        self.assertEqual(
                            link["rect"]["height"], link["siblingRect"]["height"]
                        )

    def test_editable_and_readonly_drawer_more_is_secondary_and_keyboard_operable(self):
        for case in self.evidence["viewports"]:
            for drawer in case["drawers"]:
                with self.subTest(width=case["width"], editable=drawer["editable"]):
                    self.assertEqual(drawer["sibling"], drawer["normal"])
                    self.assertEqual(drawer["siblingHover"], drawer["hover"])
                    if drawer["editable"]:
                        self.assertEqual(drawer["siblingPressed"], drawer["pressed"])
                    self.assertTrue(drawer["focused"])
                    self.assertEqual("solid", drawer["focus"]["outlineStyle"])
                    self.assertTrue(drawer["keyboardOpened"])
                    self.assertTrue(drawer["keyboardClosed"])
                    self.assertTrue(drawer["pointerOpened"])
                    self.assertTrue(drawer["pointerClosed"])
                    self.assertGreaterEqual(
                        drawer["rect"]["height"], 44 if case["width"] == 390 else 37
                    )

    def test_more_links_keep_native_keyboard_navigation(self):
        self.assertEqual(
            {"/planner": "/planner", "/capture": "/capture"},
            self.evidence["links"],
        )
