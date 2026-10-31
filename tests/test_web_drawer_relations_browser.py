"""Real shell, keyboard and viewport checks for the relations navigation (#1486)."""

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
class DrawerRelationsBrowserTests(unittest.TestCase):
    def test_relations_matrix_and_context(self):
        from lifetxt import bootstrap_legacy_surfaces

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        with tempfile.TemporaryDirectory() as directory:
            life = Path(directory) / "life.txt"
            fixture = (
                '[ ] T "Original" id:origin due:2026-10-31 parent:parent depends_on:blocker\n'
                '[ ] T "Parent" id:parent due:2026-10-31\n'
                '[ ] T "Blocker" id:blocker due:2026-10-31\n'
                '[x] N "Event <img onerror=bad>" id:record parent:origin on:2026-10-31\n'
                '[ ] J "Nearby ' + "長いタイトル" * 40 + '" id:nearby on:2026-10-31\n'
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
                            str(ROOT / "tests/browser_drawer_relations_probe.mjs"),
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
