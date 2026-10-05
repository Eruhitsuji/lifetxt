"""Real Chromium/native file selection against the bounded upload server.

Authentication/error UI statuses and pending timing use test-only middleware;
normal upload, executable rejection and stale revision use the real contract.
"""

import asyncio
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
    from fastapi.responses import JSONResponse
except ImportError:
    uvicorn = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(uvicorn, "Web extras unavailable")
@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(browser_path(), "Chrome/Chromium unavailable")
class AttachmentUploadBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Match `lifetxt serve`: install revision/clock compatibility contracts.
        from lifetxt import bootstrap_legacy_surfaces

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = root / "life.txt"
            records.write_text(
                '[ ] T "Upload fixture" id:upload-test\n', encoding="utf-8"
            )
            selected = root / "report-日本語.txt"
            selected.write_bytes(b"fixture content")
            attachments = root / "attachments"
            app = create_app(
                paths=[str(records)],
                writable_path=str(records),
                config={
                    "attachments": {"root": str(attachments), "max_file_bytes": 64},
                    "clock": {
                        "require_remote_write_time": True,
                        "client_time_header": "X-Test-Time",
                    },
                },
            )
            mode = "normal"

            @app.post("/__test/mode/{value}")
            def set_mode(value: str):
                nonlocal mode
                mode = value
                app.state.read_only = value == "readonly"
                return {"ok": True}

            @app.middleware("http")
            async def fixture_faults(request, call_next):
                if (
                    request.url.path == "/api/attachments/upload"
                    and request.method == "POST"
                ):
                    if mode == "pending":
                        await asyncio.sleep(0.35)
                    if mode in ("401", "403", "503"):
                        return JSONResponse(
                            status_code=int(mode),
                            content={"message": "<img>UNTRUSTED /private/path"},
                        )
                return await call_next(request)

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
                            str(ROOT / "tests/browser_attachment_upload_probe.mjs"),
                            browser_path(),
                            base_url,
                            str(selected),
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=120,
                    )
                finally:
                    server.should_exit = True
                    thread.join(timeout=10)
            if run.returncode:
                raise AssertionError(run.stderr or run.stdout)
            cls.evidence = json.loads(run.stdout)["viewports"]
            cls.stored_files = [
                p.read_bytes() for p in (attachments / "web-uploads").iterdir()
            ]
            cls.source = records.read_text(encoding="utf-8")

    def test_desktop_and_phone_english_and_japanese(self):
        self.assertEqual(
            [(1280, "en"), (1280, "ja"), (390, "en"), (390, "ja")],
            [(x["width"], x["lang"]) for x in self.evidence],
        )
        for case in self.evidence:
            with self.subTest(width=case["width"], lang=case["lang"]):
                self.assertGreaterEqual(case["layout"]["buttonHeight"], 44)
                self.assertTrue(case["oversized"])
                self.assertTrue(case["safeName"])
                self.assertTrue(case["bidi"])

    def test_native_file_upload_refresh_and_safe_receipt(self):
        for case in self.evidence:
            self.assertEqual(201, case["success"]["status"])
            self.assertTrue(case["success"]["noPath"])
            self.assertTrue(case["success"]["cleared"])
            self.assertTrue(case["hostileReceipt"])
            self.assertIn("report-日本語.txt", case["success"]["receipt"])
        self.assertEqual(4, self.stored_files.count(b"fixture content"))
        self.assertIn("file:", self.source)

    def test_real_conflict_and_content_validation(self):
        for case in self.evidence:
            self.assertEqual(409, case["conflict"]["status"])
            self.assertEqual(1, case["conflict"]["count"])
            self.assertTrue(case["conflict"]["disabled"])
            self.assertEqual(415, case["validation"])

    def test_auth_readonly_uncertain_pending_and_storage(self):
        for case in self.evidence:
            self.assertEqual([401, 403, 503], [x["status"] for x in case["failures"]])
            self.assertTrue(all(x["disabled"] and x["safe"] for x in case["failures"]))
            for key in (
                "pending",
                "onePost",
                "readonly",
                "readonlyItem",
                "noStoredUpload",
            ):
                self.assertTrue(case[key], key)
