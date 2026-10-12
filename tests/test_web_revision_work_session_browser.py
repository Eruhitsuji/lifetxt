"""Real shipped work-session drawer against HTTP, with compound recovery evidence."""

import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import unittest
import tempfile

from tests.test_web_planner_browser import browser_path

ROOT = Path(__file__).resolve().parents[1]


class WorkSessionBrowserTests(unittest.TestCase):
    def test_observe(self):
        self.run_probe("observe")

    def test_required(self):
        self.run_probe("required")

    def run_probe(self, revision_mode):
        missing = not all(importlib.util.find_spec(x) for x in ("fastapi", "uvicorn"))
        if missing or not shutil.which("node") or not browser_path():
            if os.environ.get("LIFETXT_REQUIRE_REVISION_BROWSER") == "1":
                self.fail("Revision recovery browser dependencies unavailable")
            self.skipTest("Revision recovery browser dependencies unavailable")
        if subprocess.run(
            ["node", "-e", "process.exit(typeof WebSocket==='function'?0:1)"],
            timeout=10,
        ).returncode:
            if os.environ.get("LIFETXT_REQUIRE_REVISION_BROWSER") == "1":
                self.fail("Node native WebSocket unavailable")
            self.skipTest("Node native WebSocket unavailable")

        import uvicorn
        from fastapi.responses import Response
        from lifetxt import bootstrap_legacy_surfaces
        from lifetxt.timezone_policy import clock_context
        from lifetxt.transaction_journal import list_journals, resume
        from lifetxt.transaction_policy import fault_injection

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        with tempfile.TemporaryDirectory(prefix="lifetxt-recovery-") as directory:
            root = Path(directory)
            life = root / "life.txt"
            life.write_text(
                '[ ] T "Recovery fixture" id:upload-test\n[ ] T Other id:other\n',
                encoding="utf-8",
            )
            attachments = root / "attachments"
            journals = root / "journals"
            app = create_app(
                paths=[str(life)],
                writable_path=str(life),
                config={
                    "web": {"revision_mode": revision_mode},
                    "attachments": {"root": str(attachments), "max_file_bytes": 64},
                    "timer": {"state_file": str(root / "timer.json")},
                    "transactions": {"journal_dir": str(journals)},
                    "defaults": {"timezone": "UTC"},
                    "clock": {"require_remote_write_time": True},
                },
            )

            class FixtureWorkInterruption(RuntimeError):
                pass

            @app.exception_handler(FixtureWorkInterruption)
            async def expected_interruption(_request, _error):
                return Response(
                    '{"detail":"Synthetic interruption"}',
                    status_code=500,
                    media_type="application/json",
                )

            mode = "normal"
            fault_points = []
            requests = []

            @app.get("/favicon.ico", status_code=204)
            def favicon():
                return Response(status_code=204)

            @app.post("/__test/mode/{value}")
            def set_mode(value: str):
                nonlocal mode
                assert value in {"normal", "interrupt", "readonly"}
                mode = value
                app.state.read_only = value == "readonly"
                return {"ok": True}

            def interrupt(point, details):
                nonlocal mode
                if mode == "interrupt" and point == "after_journal_publish":
                    mode = "normal"
                    fault_points.append(
                        {"point": point, "transaction_id": details["transaction_id"]}
                    )
                    raise FixtureWorkInterruption(
                        "Synthetic interruption after journal publication"
                    )

            @app.middleware("http")
            async def fixture_context(request, call_next):
                if request.url.path == "/api/work-session" and request.method == "POST":
                    requests.append({"revision": request.headers.get("if-match")})
                with (
                    clock_context(
                        datetime.datetime(2031, 2, 3, 12, tzinfo=datetime.timezone.utc)
                    ),
                    fault_injection(interrupt),
                ):
                    return await call_next(request)

            @app.get("/__test/state")
            def state():
                # Return exact source/blob bytes; omit journal paths from evidence.
                rows = list_journals(str(journals))
                return {
                    "source": life.read_bytes().hex(),
                    "timer": (root / "timer.json").read_bytes().hex()
                    if (root / "timer.json").exists()
                    else None,
                    "metrics": app.state.revision_metrics_store.snapshot(),
                    "attachments": {
                        p.name: p.read_bytes().hex()
                        for p in attachments.rglob("*")
                        if p.is_file()
                    },
                    "journals": [
                        {
                            "id": r["transaction_id"],
                            "state": r["state"],
                            "recovery_required": r["recovery_required"],
                        }
                        for r in rows
                    ],
                    "fault_points": fault_points,
                    "requests": requests,
                }

            @app.post("/__test/operator-resume")
            def operator_resume():
                pending = [
                    r for r in list_journals(str(journals)) if r["recovery_required"]
                ]
                assert len(pending) == 1
                result = resume(pending[0]["journal_path"])
                return {"state": result["state"], "id": result["transaction_id"]}

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
                            self.fail("Recovery server startup timed out")
                        time.sleep(0.02)
                    result = subprocess.run(
                        [
                            "node",
                            str(ROOT / "tests/browser_revision_work_session_probe.mjs"),
                            browser_path(),
                            base,
                            revision_mode,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    self.assertEqual(
                        0, result.returncode, result.stderr or result.stdout
                    )
                    evidence = json.loads(result.stdout)
                    self.assertTrue(evidence["work_session_frontend_verified"])
                    self.assertEqual("after_journal_publish", evidence["fault_point"])
                    evidence["source_sha"] = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10
                    ).strip()
                    output = os.environ.get("LIFETXT_REVISION_EVIDENCE_DIR")
                    if output:
                        destination = Path(output)
                        destination.mkdir(parents=True, exist_ok=True)
                        (destination / f"work-session-{revision_mode}.json").write_text(
                            json.dumps(evidence, indent=2) + "\n"
                        )
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(
                        thread.is_alive(), "Recovery server cleanup timed out"
                    )
