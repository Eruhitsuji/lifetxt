"""Shipped State JavaScript interaction and optional real-engine checks."""

import json
import importlib.util
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from lifetxt import webapp
from lifetxt.web_assets import STATE_HTML_PAGE
from tests.test_web_planner_browser import browser_path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class StateInteractionTests(unittest.TestCase):
    def test_dom_interactions_transport_failures_and_snapshot_races(self):
        result = subprocess.run(
            [
                "node",
                str(ROOT / "tests/state_ui_probe.mjs"),
                str(ROOT / "lifetxt/web_state.html"),
                str(ROOT / "lifetxt/web_state.js"),
            ],
            capture_output=True,
            text=True,
            timeout=40,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertGreaterEqual(report["checks"], 190)
        self.assertEqual(22, report["scenarios"])


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(browser_path(), "Chrome/Chromium unavailable")
class StateBrowserTests(unittest.TestCase):
    def test_native_viewport_theme_language_focus_keyboard_and_accessibility(self):
        evidence = os.environ.get("LIFETXT_REVISION_EVIDENCE_DIR")
        evidence_path = Path(evidence) if evidence else None
        if evidence_path:
            evidence_path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.html"
            path.write_text(STATE_HTML_PAGE, encoding="utf-8")
            result = subprocess.run(
                [
                    "node",
                    str(ROOT / "tests/browser_state_probe.mjs"),
                    browser_path(),
                    str(path),
                ]
                + ([str(evidence_path / "state-browser.png")] if evidence_path else []),
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(20, len(report["matrix"]))
        self.assertTrue(all(item["reachable"] for item in report["matrix"]))
        self.assertEqual([400, 401, 403, 409, 500, "network"], report["failures"])
        self.assertIn("not physical iOS", report["safeArea"])
        self.assertIn("passed", report["interaction"])
        if evidence_path:
            (evidence_path / "state-browser.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    @unittest.skipUnless(importlib.util.find_spec("uvicorn"), "Web extras unavailable")
    def test_real_browser_status_mutations_observe_and_required(self):
        import uvicorn

        for mode in ("observe", "required"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "life.txt"
                path.write_text(
                    "[/] S Other from:2026-01-01T09:00 state:meeting person:other id:other\n",
                    encoding="utf-8",
                )
                app = webapp.create_app(
                    [str(path)],
                    writable_path=str(path),
                    config={"web": {"revision_mode": mode}},
                )
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    server = uvicorn.Server(
                        uvicorn.Config(app, log_level="error", lifespan="off")
                    )
                    thread = threading.Thread(
                        target=server.run, kwargs={"sockets": [sock]}, daemon=True
                    )
                    thread.start()
                    try:
                        deadline = time.monotonic() + 10
                        while (
                            not server.started
                            and thread.is_alive()
                            and time.monotonic() < deadline
                        ):
                            time.sleep(0.01)
                        self.assertTrue(server.started)
                        result = subprocess.run(
                            [
                                "node",
                                str(ROOT / "tests/browser_state_live_probe.mjs"),
                                browser_path(),
                                f"http://127.0.0.1:{sock.getsockname()[1]}",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=90,
                        )
                        self.assertEqual(
                            0, result.returncode, result.stderr or result.stdout
                        )
                        report = json.loads(result.stdout)
                        self.assertEqual(0, report["legacyFallback"])
                        self.assertEqual("/state", report["manifest"])
                        self.assertIn("browser back", report["navigation"])
                        evidence = os.environ.get("LIFETXT_REVISION_EVIDENCE_DIR")
                        if evidence:
                            output = Path(evidence)
                            output.mkdir(parents=True, exist_ok=True)
                            (output / f"state-live-{mode}.json").write_text(
                                json.dumps(report, indent=2), encoding="utf-8"
                            )
                    finally:
                        server.should_exit = True
                        thread.join(timeout=10)
                        self.assertFalse(
                            thread.is_alive(), "Disposable server did not stop"
                        )


if __name__ == "__main__":
    unittest.main()
