"""Real shell, keyboard and viewport checks for the history redesign (#1484)."""

import json
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
except ImportError:
    uvicorn = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    uvicorn and shutil.which("node") and browser_path(), "Web/Node/Chromium required"
)
class DrawerHistoryBrowserTests(unittest.TestCase):
    def test_history_matrix_and_canonical_filters(self):
        from lifetxt import bootstrap_legacy_surfaces

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        with tempfile.TemporaryDirectory() as directory:
            life = Path(directory) / "life.txt"
            fixture = (
                '[ ] T "Done" id:history due:2026-10-30 do:2026-10-31 '
                'done:2026-10-30T20:10:17Z custom:Done est:30m elapsed:40m body:"Body & long text '
                + "x" * 200
                + '"\n'
            )
            life.write_text(fixture, encoding="utf-8")
            app = create_app(
                paths=[str(life)],
                writable_path=str(life),
                config={"defaults": {"timezone": "Asia/Tokyo"}},
            )
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                base = f"http://127.0.0.1:{listener.getsockname()[1]}"
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
                            str(ROOT / "tests/browser_drawer_history_probe.mjs"),
                            browser_path(),
                            base,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
            self.assertEqual(0, run.returncode, run.stderr or run.stdout)
            evidence = json.loads(run.stdout)
            self.assertEqual(12, len(evidence["cases"]))
            self.assertTrue(evidence["noWrites"])
            self.assertEqual(fixture, life.read_text(encoding="utf-8"))
