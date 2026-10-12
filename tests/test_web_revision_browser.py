"""Real Chrome/Chromium + HTTP revision evidence, never a DOM shim pass."""

import datetime
import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests.test_web_planner_browser import browser_path

ROOT = Path(__file__).resolve().parents[1]


def require_revision_browser(test):
    missing = []
    if not all(importlib.util.find_spec(x) for x in ("fastapi", "uvicorn")):
        missing.append("Web extras")
    if not shutil.which("node"):
        missing.append("Node 22+ native WebSocket")
    elif subprocess.run(
        ["node", "-e", "process.exit(typeof WebSocket === 'function' ? 0 : 1)"],
        timeout=10,
        capture_output=True,
    ).returncode:
        missing.append("Node 22+ native WebSocket")
    if not browser_path():
        missing.append("Chrome/Chromium")
    if missing:
        reason = "Real revision browser dependency missing: " + ", ".join(missing)
        if os.environ.get("LIFETXT_REQUIRE_REVISION_BROWSER") == "1":
            test.fail(reason)
        test.skipTest(reason)


class RevisionBrowserTests(unittest.TestCase):
    def test_observe(self):
        self.run_probe("observe")

    def test_required(self):
        self.run_probe("required")

    def run_probe(self, mode):
        require_revision_browser(self)

        import uvicorn
        from fastapi.responses import Response

        from lifetxt import bootstrap_legacy_surfaces

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        with tempfile.TemporaryDirectory(prefix="lifetxt-revision-") as directory:
            root = Path(directory)
            source = root / "life.txt"
            source.write_text('[ ] T "Revision fixture" id:t1\n', encoding="utf-8")
            app = create_app(
                paths=[str(source)],
                writable_path=str(source),
                config={
                    "web": {"revision_mode": mode},
                    "timezone": "UTC",
                },
            )
            writes = []

            @app.get("/favicon.ico", status_code=204)
            def fixture_favicon():
                # Chromium may request this implicitly. Keep the revision fixture
                # free of unrelated HTTP errors without weakening the error gate.
                return Response(status_code=204)

            @app.middleware("http")
            async def observe_wire(request, call_next):
                if (
                    request.url.path == "/api/items/capture"
                    and request.method == "POST"
                ):
                    writes.append({"precondition": request.headers.get("if-match")})
                from lifetxt.timezone_policy import clock_context

                with clock_context(
                    datetime.datetime(2031, 2, 3, 12, tzinfo=datetime.timezone.utc)
                ):
                    return await call_next(request)

            @app.get("/__test/state")
            def fixture_state():
                return {
                    "sources": [source.read_bytes().hex()],
                    "metrics": app.state.revision_metrics_store.snapshot(),
                    "writes": writes,
                }

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
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() > deadline:
                            self.fail("Disposable revision server startup failed")
                        time.sleep(0.02)
                    run = subprocess.run(
                        [
                            "node",
                            str(ROOT / "tests/browser_revision_probe.mjs"),
                            browser_path(),
                            base,
                            mode,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    self.assertEqual(0, run.returncode, run.stderr or run.stdout)
                    evidence = json.loads(run.stdout)
                    evidence["source_sha"] = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10
                    ).strip()
                    evidence["os"] = platform.system()
                    self.assertTrue(
                        evidence["engine"].startswith(("Chrome/", "HeadlessChrome/"))
                    )
                    self.assertEqual(mode, evidence["mode"])
                    evidence_dir = os.environ.get("LIFETXT_REVISION_EVIDENCE_DIR")
                    if evidence_dir:
                        destination = Path(evidence_dir)
                        destination.mkdir(parents=True, exist_ok=True)
                        (destination / f"revision-{mode}.json").write_text(
                            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
                        )
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(
                        thread.is_alive(), "Revision server cleanup timed out"
                    )
