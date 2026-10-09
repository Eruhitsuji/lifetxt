"""Execute the shipped Planner JavaScript against a disposable Web server.

The Node DOM shim tests event handlers and HTTP contracts, not browser layout.
"""

import importlib.util
import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from lifetxt import webapp

ROOT = Path(__file__).resolve().parents[1]
WEB_AVAILABLE = all(
    importlib.util.find_spec(name) is not None for name in ("fastapi", "uvicorn")
)


@unittest.skipUnless(WEB_AVAILABLE, "Web extras unavailable")
@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class PlannerRevisionTests(unittest.TestCase):
    def test_planner_mutations_observe(self):
        self.run_probe("observe")

    def test_planner_mutations_required(self):
        self.run_probe("required")

    def run_probe(self, mode):
        import uvicorn

        version = subprocess.check_output(["node", "--version"], text=True)
        if int(version.lstrip("v").split(".")[0]) < 18:
            self.skipTest("Node 18+ fetch runtime required")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "life.txt"
            path.write_text(
                "[ ] T Task id:t1\n[ ] T Line_Task\n"
                "[ ] H Habit id:h1\n[ ] H Stale_Habit id:h2\n"
                "[N] N Note id:n1 body:Original\n",
                encoding="utf-8",
            )
            app = webapp.create_app(
                paths=[str(path)],
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
                    while not server.started and thread.is_alive():
                        if time.monotonic() > deadline:
                            self.fail("Disposable Web server did not start")
                        time.sleep(0.01)
                    self.assertTrue(server.started)
                    result = subprocess.run(
                        [
                            "node",
                            str(ROOT / "tests/planner_revision_probe.mjs"),
                            f"http://127.0.0.1:{sock.getsockname()[1]}",
                            str(ROOT / "lifetxt/web_planner.js"),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertEqual(
                        0, result.returncode, result.stderr or result.stdout
                    )
                    report = json.loads(result.stdout)
                    self.assertEqual(0, report["legacy_fallback_total"])
                    self.assertGreaterEqual(report["protected_writes"], 12)
                    self.assertEqual(mode, report["revision_mode"])
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive(), "Server did not stop")
