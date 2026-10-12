"""Real loopback reverse-proxy faults and process-restart telemetry evidence."""

import datetime
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen

from tests.test_web_planner_browser import browser_path
from tests import test_web_revision_browser as support

ROOT = support.ROOT


class RevisionProxyBrowserTests(support.RevisionBrowserTests):
    # Inherit the existing mode matrix and mandatory browser dependency guard.
    def run_probe(self, mode):
        support.require_revision_browser(self)
        with tempfile.TemporaryDirectory(prefix="lifetxt-proxy-") as directory:
            root = Path(directory)
            life = root / "life.txt"
            life.write_text('[ ] T "Proxy fixture" id:t1\n', encoding="utf-8")
            metrics = root / "metrics.json"
            from lifetxt.revision_telemetry import initial_metrics

            old = initial_metrics(
                mode, now=datetime.datetime(2031, 2, 3, tzinfo=datetime.timezone.utc)
            )
            old.update(
                schema_version=0,
                legacy_fallback_total=2,
                legacy_fallback_by_path={"/api/items": 2},
                obsolete_counter=99,
            )
            metrics.write_text(json.dumps(old), encoding="utf-8")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            config_path = root / "fixture.json"
            config_path.write_text(
                json.dumps(
                    {
                        "life": str(life),
                        "metrics": str(metrics),
                        "mode": mode,
                        "port": port,
                    }
                )
            )
            upstream = None
            fault = "none"
            wire = []
            log = (root / "server.log").open("w+", encoding="utf-8")

            def stop():
                nonlocal upstream
                if upstream is None:
                    return
                upstream.terminate()
                try:
                    upstream.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    upstream.kill()
                    upstream.wait(timeout=5)
                upstream = None

            def start():
                nonlocal upstream
                upstream = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "tests.test_web_revision_proxy_browser",
                        "--serve",
                        str(config_path),
                    ],
                    cwd=ROOT,
                    stdout=log,
                    stderr=log,
                )
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if upstream.poll() is not None:
                        log.flush()
                        raise AssertionError(
                            "Fixture server exited: "
                            + (root / "server.log").read_text()
                        )
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{port}/api/health", timeout=1
                        ) as response:
                            if response.status == 200:
                                return
                    except OSError:
                        time.sleep(0.05)
                raise AssertionError("Fixture server startup timed out")

            class Proxy(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.1"

                def log_message(self, *_args):
                    pass

                def do_GET(self):
                    self.forward()

                def do_POST(self):
                    self.forward()

                def forward(self):
                    nonlocal fault
                    self.connection.settimeout(10)
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 65536:
                        self.send_error(413)
                        return
                    body = self.rfile.read(length)
                    if self.path.startswith("/__test/"):
                        if self.path.startswith("/__test/fault/"):
                            fault = self.path.rsplit("/", 1)[1]
                            assert fault in {
                                "none",
                                "strip",
                                "strip-all",
                                "rewrite",
                                "missing",
                            }
                        elif self.path == "/__test/restart":
                            before_pid = upstream.pid
                            stop()
                            start()
                            self.respond(
                                200,
                                json.dumps(
                                    {
                                        "before_pid": before_pid,
                                        "after_pid": upstream.pid,
                                    }
                                ).encode(),
                            )
                            return
                        if self.path == "/__test/state":
                            connection = http.client.HTTPConnection(
                                "127.0.0.1", port, timeout=5
                            )
                            try:
                                connection.request("GET", "/api/revision-metrics")
                                metric_response = connection.getresponse()
                                assert metric_response.status == 200
                                report = json.loads(metric_response.read(65536))
                            finally:
                                connection.close()
                            self.respond(
                                200,
                                json.dumps(
                                    {
                                        "sources": [life.read_bytes().hex()],
                                        "metrics": report,
                                        "wire": wire,
                                    }
                                ).encode(),
                            )
                            return
                        self.respond(200, b'{"ok":true}')
                        return
                    headers = {
                        k: v
                        for k, v in self.headers.items()
                        if k.lower() not in {"host", "connection", "content-length"}
                    }
                    if (
                        fault == "missing"
                        and self.command == "POST"
                        and self.path == "/api/items"
                    ):
                        for key in list(headers):
                            if key.lower() in {
                                "if-match",
                                "x-lifetxt-expected-revision",
                                "cookie",
                            }:
                                del headers[key]
                    if self.command == "POST" and self.path == "/api/items":
                        wire.append(
                            {
                                "fault": fault,
                                "precondition": next(
                                    (
                                        v
                                        for k, v in headers.items()
                                        if k.lower() == "if-match"
                                    ),
                                    None,
                                ),
                            }
                        )
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", port, timeout=10
                    )
                    try:
                        connection.request(self.command, self.path, body, headers)
                        response = connection.getresponse()
                        payload = response.read(1024 * 1024 + 1)
                        assert len(payload) <= 1024 * 1024
                        response_headers = []
                        for key, value in response.getheaders():
                            if key.lower() in {
                                "content-length",
                                "transfer-encoding",
                                "connection",
                            }:
                                continue
                            if self.command == "GET" and self.path.startswith("/api/"):
                                if (
                                    fault in {"strip", "strip-all"}
                                    and key.lower() == "etag"
                                ):
                                    continue
                                if (
                                    fault == "strip-all"
                                    and key.lower() == "x-lifetxt-revision"
                                ):
                                    continue
                                if fault == "rewrite" and key.lower() == "etag":
                                    value = '"' + "a" * 64 + '"'
                            response_headers.append((key, value))
                        self.respond(response.status, payload, response_headers)
                    finally:
                        connection.close()

                def respond(self, status, body, headers=()):
                    self.send_response(status)
                    for key, value in headers:
                        self.send_header(key, value)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
            proxy.daemon_threads = True
            thread = threading.Thread(target=proxy.serve_forever, daemon=True)
            try:
                start()
                thread.start()
                run = subprocess.run(
                    [
                        "node",
                        str(ROOT / "tests/browser_revision_proxy_probe.mjs"),
                        browser_path(),
                        f"http://127.0.0.1:{proxy.server_port}",
                        mode,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(0, run.returncode, run.stderr or run.stdout)
                evidence = json.loads(run.stdout)
                evidence["source_sha"] = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip()
                output = os.environ.get("LIFETXT_REVISION_EVIDENCE_DIR")
                if output:
                    destination = Path(output)
                    destination.mkdir(parents=True, exist_ok=True)
                    (destination / f"proxy-{mode}.json").write_text(
                        json.dumps(evidence, indent=2) + "\n"
                    )
            finally:
                if thread.is_alive():
                    proxy.shutdown()
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())
                proxy.server_close()
                stop()
                log.close()


def serve(config_path):
    import uvicorn
    from fastapi.responses import Response
    from lifetxt import bootstrap_legacy_surfaces
    from lifetxt.timezone_policy import clock_context

    bootstrap_legacy_surfaces()
    from lifetxt.webapp import create_app

    fixture = json.loads(Path(config_path).read_text())
    app = create_app(
        paths=[fixture["life"]],
        writable_path=fixture["life"],
        config={
            "web": {
                "revision_mode": fixture["mode"],
                "revision_metrics_path": fixture["metrics"],
            },
            "defaults": {"timezone": "UTC"},
        },
    )

    @app.get("/favicon.ico", status_code=204)
    def favicon():
        return Response(status_code=204)

    @app.middleware("http")
    async def frozen_clock(request, call_next):
        with clock_context(
            datetime.datetime(2031, 2, 3, 12, tzinfo=datetime.timezone.utc)
        ):
            return await call_next(request)

    uvicorn.run(
        app, host="127.0.0.1", port=fixture["port"], log_level="error", ws="none"
    )


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--serve":
    serve(sys.argv[2])
