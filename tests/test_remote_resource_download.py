import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

from tests.test_resource_reference_resolution import ResourceResolutionTests
from lifetxt.remote_resource_download import (
    ResourceApplication,
    _ADMISSION,
    PREFIX,
    envelope,
    Admission,
)
from lifetxt.resource_reference_resolution import ReadContext, ResourceFailure
from lifetxt.resource_reference_store import BindingUnavailable


@unittest.skipUnless(
    importlib.util.find_spec("starlette"),
    "optional Web transport dependency unavailable",
)
class ResourceHTTPTests(unittest.TestCase):
    setUpClass = classmethod(ResourceResolutionTests.setUpClass.__func__)
    tearDownClass = classmethod(ResourceResolutionTests.tearDownClass.__func__)
    context = ResourceResolutionTests.context

    def setUp(self):
        ResourceResolutionTests.setUp(self)
        self.store.close()
        self.config["remote"]["principals"][0]["token_env"] = "RESOURCE_HTTP_FIXTURE"
        env = patch.dict(os.environ, {"RESOURCE_HTTP_FIXTURE": "synthetic-bearer"})
        env.start()
        self.addCleanup(env.stop)
        self.app = ResourceApplication(self.config)
        asyncio.run(self.app.start())
        self.addCleanup(lambda: self.app.store.close())
        _ADMISSION.rates.clear()
        self.base = {
            "contract_version": "1",
            "workspace_id": self.workspace,
            "source_id": self.source_id,
            "item_id": "task",
        }

    def request(
        self,
        operation="discover",
        body=None,
        method="POST",
        headers=None,
        path=None,
        on_send=None,
        scheme="https",
        query=b"",
    ):
        async def run():
            raw = (
                json.dumps(self.base if body is None else body).encode()
                if not isinstance(body, bytes)
                else body
            )
            h = {
                "host": "localhost",
                "authorization": "Bearer synthetic-bearer",
                "content-type": "application/json",
                "x-lifetxt-remote-version": "2",
                "x-lifetxt-resource-contract": "resource-reference-v1",
                "content-length": str(len(raw)),
            }
            h.update(headers or {})
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "scheme": scheme,
                "method": method,
                "path": path or PREFIX + operation,
                "raw_path": (path or PREFIX + operation).encode(),
                "query_string": query,
                "headers": [(k.encode(), v.encode()) for k, v in h.items()],
                "client": ("127.0.0.1", 23456),
                "server": ("localhost", 443),
            }
            messages = []
            first = True

            async def receive():
                nonlocal first
                if first:
                    first = False
                    return {"type": "http.request", "body": raw, "more_body": False}
                await asyncio.Event().wait()

            async def send(message):
                messages.append(message)
                if on_send:
                    await on_send(message)

            await self.app(scope, receive, send)
            response = next(m for m in messages if m["type"] == "http.response.start")
            return (
                response["status"],
                dict((k.decode(), v.decode()) for k, v in response["headers"]),
                b"".join(m.get("body", b"") for m in messages),
            )

        return asyncio.run(run())

    def descriptor(self):
        status, _, raw = self.request()
        self.assertEqual(200, status, raw)
        return json.loads(raw)["resources"][0]

    def action(self, descriptor):
        return dict(
            contract_version="1",
            workspace_id=self.workspace,
            **{
                k: descriptor[k]
                for k in ("resource_ref", "source_revision", "resource_revision")
            },
        )

    def test_discover_full_chunk_read_only_security_headers(self):
        descriptor = self.descriptor()
        body = self.action(descriptor)
        status, headers, raw = self.request("full", body)
        self.assertEqual((200, b"AAAAAAA"), (status, raw))
        self.assertEqual(
            'attachment; filename="download.bin"', headers["content-disposition"]
        )
        self.assertEqual("application/octet-stream", headers["content-type"])
        self.assertEqual("private, no-store", headers["cache-control"])
        self.assertEqual("nosniff", headers["x-content-type-options"])
        for forbidden in (
            "etag",
            "last-modified",
            "location",
            "content-range",
            "access-control-allow-origin",
        ):
            self.assertNotIn(forbidden, headers)
        body.update(offset=2, length=3)
        status, headers, raw = self.request("chunk", body)
        self.assertEqual((200, b"AAA"), (status, raw))
        self.assertEqual("5", headers["x-lifetxt-next-offset"])
        body["offset"] = 7
        self.assertEqual(b"", self.request("chunk", body)[2])
        body["offset"] = 8
        self.assertEqual(400, self.request("chunk", body)[0])

    def test_all_alternate_routes_methods_wrappers_and_no_downgrade(self):
        for path in (
            "/",
            "/api/items",
            "/api/export",
            "/api/remote/v1/snapshot",
            "/api/remote/v1/historical",
            "/api/remote/v1/resources/search",
            "/api/remote/v1/audit",
            "/api/remote/v1/capabilities",
            "/api/remote/v1/browser/login",
            "/mcp",
            "/docs",
            "/openapi.json",
            PREFIX + "discover/",
        ):
            for method in ("GET", "POST", "HEAD", "OPTIONS"):
                _ADMISSION.rates.clear()
                status, _, raw = self.request(
                    path=path, method=method, headers={"x-lifetxt-remote-version": "1"}
                )
                self.assertEqual(404, status, (path, method, raw))
                self.assertEqual(
                    "RESOURCE_UNAVAILABLE", json.loads(raw)["error"]["code"]
                )
        self.assertEqual(405, self.request(method="GET")[0])
        self.assertEqual(
            406, self.request(headers={"x-lifetxt-remote-version": "1"})[0]
        )
        self.assertEqual(
            406, self.request(headers={"x-lifetxt-resource-contract": ""})[0]
        )

    def test_bounds_unknown_fields_duplicate_keys_boolean_and_range(self):
        body = self.action(self.descriptor())
        for operation, raw in [
            ("full", dict(body, path="/synthetic")),
            ("chunk", dict(body, offset=True, length=1)),
            ("chunk", dict(body, offset=0, length=65537)),
            ("full", b'{"contract_version":"1","contract_version":"1"}'),
            ("full", b" " * 2049),
        ]:
            self.assertEqual(400, self.request(operation, raw)[0])
        self.assertEqual(
            400,
            self.request(
                "full", {k: v for k, v in body.items() if k != "source_revision"}
            )[0],
        )
        for key in ("range", "if-range", "cookie", "origin", "x-lifetxt-principal"):
            self.assertEqual(
                400, self.request("full", body, headers={key: "synthetic"})[0]
            )
        self.assertEqual(400, self.request(query=b"ref=synthetic")[0])

    def test_authentication_tls_untrusted_proxy_and_uniform_unavailable(self):
        self.assertEqual(401, self.request(headers={"authorization": ""})[0])
        self.assertEqual(
            406, self.request(scheme="http", headers={"x-forwarded-proto": "https"})[0]
        )
        descriptor = self.descriptor()
        body = self.action(descriptor)
        body["resource_ref"] = "att:v1:" + "0" * 32
        a = self.request("full", body)
        self.config = self.app.state.config
        self.app.state.config["remote"]["principals"][0]["scopes"] = []
        b = self.request("full", self.action(descriptor))
        self.assertEqual((404, a[2]), (b[0], b[2]))
        self.assertNotIn(b"payload", a[2])

    def test_stale_wrong_workspace_and_credential_rotation(self):
        body = self.action(self.descriptor())
        self.file.write_bytes(b"BBBBBBB")
        self.assertEqual(409, self.request("full", body)[0])
        body["workspace_id"] = "f" * 64
        self.assertEqual(404, self.request("full", body)[0])
        with patch.dict(os.environ, {"RESOURCE_HTTP_FIXTURE": "rotated-fixture"}):
            self.assertNotEqual(200, self.request()[0])

    def test_revoke_after_first_chunk_aborts_without_json(self):
        self.file.write_bytes(b"A" * 70000)
        body = self.action(self.descriptor())
        sent = []

        async def revoke(message):
            if message["type"] == "http.response.body" and message.get("body"):
                sent.append(message["body"])
                self.app.state.config["remote"]["principals"][0]["scopes"] = []

        with self.assertRaises(ConnectionAbortedError):
            self.request("full", body, on_send=revoke)
        self.assertEqual(65536, len(b"".join(sent)))
        self.assertNotIn(b"error", b"".join(sent))

    def test_admission_rate_and_stuck_physical_worker_slot(self):
        gate = Admission()
        context = ReadContext("alice", time.monotonic() + 30)
        gate.reserve(context, {"active_process": 2})
        gate.identify(context)
        other = ReadContext("alice", time.monotonic() + 30)
        gate.reserve(other, {"active_process": 2})
        with self.assertRaises(ResourceFailure):
            gate.identify(other)
        gate.release_when_stopped(other)
        physical = threading.Event()
        context.workers.append(physical)
        gate.release_when_stopped(context)
        self.assertIn(context.admission_key, gate.active)
        physical.set()
        deadline = time.monotonic() + 1
        while gate.active and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual({}, gate.active)
        gate.rate("test", 1)
        with self.assertRaises(ResourceFailure):
            gate.rate("test", 1)

    def test_deadline_includes_send_and_aborts_after_headers(self):
        self.app.state.config["remote"]["resource_references"]["limits"] = {
            "deadline_seconds": 1
        }
        self.app.startup_config = copy.deepcopy(self.app.state.config)

        async def slow(message):
            if message["type"] == "http.response.body":
                await asyncio.sleep(2)

        start = time.monotonic()
        with self.assertRaises(ConnectionAbortedError):
            self.request(on_send=slow)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_dedicated_factory_has_no_generic_routes(self):
        from lifetxt.webapp import create_app

        app = create_app(config=self.config, read_only=True)
        self.assertIsInstance(app, ResourceApplication)
        self.assertFalse(hasattr(app, "routes"))

    def test_protected_config_file_reload_before_auth_and_revocation(self):
        config_path = self.root / "config.json"
        config_path.write_text(json.dumps(self.config))
        config_path.chmod(0o600)
        self.app.state.config["_path"] = str(config_path)
        descriptor = self.descriptor()
        changed = copy.deepcopy(self.config)
        changed["remote"]["principals"][0]["scopes"] = []
        config_path.write_text(json.dumps(changed))
        self.assertEqual(404, self.request("full", self.action(descriptor))[0])

    def test_audit_cannot_alias_source_resource_config_or_index(self):
        for path in (self.source, self.file, self.root / "store.sqlite"):
            changed = copy.deepcopy(self.config)
            changed["remote"]["audit_log"] = str(path)
            with self.assertRaises(ValueError):
                ResourceApplication(changed)
        audit = self.root / "audit.jsonl"
        audit.write_text("")
        audit.chmod(0o600)
        changed = copy.deepcopy(self.config)
        changed["remote"]["audit_log"] = str(audit)
        application = ResourceApplication(changed)
        self.assertIsNotNone(application)
        audit.chmod(0o644)
        with self.assertRaises(BindingUnavailable):
            ResourceApplication(changed)

    def test_active_content_is_an_inert_binary_attachment(self):
        self.file.write_bytes(b"<svg onload='synthetic()'></svg>")
        body = self.action(self.descriptor())
        status, headers, payload = self.request("full", body)
        self.assertEqual(200, status)
        self.assertEqual("application/octet-stream", headers["content-type"])
        self.assertEqual(
            'attachment; filename="download.bin"', headers["content-disposition"]
        )
        self.assertIn("sandbox", headers["content-security-policy"])
        self.assertEqual(self.file.read_bytes(), payload)

    def test_server_factory_refuses_missing_state_helper_and_identity_overlap(self):
        changed = copy.deepcopy(self.config)
        changed["remote"]["principals"].append(
            {"id": "other", "role": "reader", "token_env": "RESOURCE_HTTP_FIXTURE"}
        )
        with self.assertRaises(BindingUnavailable):
            ResourceApplication(changed)
        with patch(
            "lifetxt.attachment_snapshot._helper_fd", side_effect=ValueError("fixture")
        ):
            application = ResourceApplication(self.config)
            self.app.store.close()
            with self.assertRaises(Exception):
                asyncio.run(application.start())
            self.assertIsNone(application.store)

    @unittest.skipUnless(
        importlib.util.find_spec("uvicorn"), "optional Uvicorn unavailable"
    )
    def test_real_socket_http_adapter(self):
        # Actual Uvicorn listener with trusted TLS terminator semantics, preserving
        # the immediate peer. Fixtures alone do not certify a deployed proxy.
        import uvicorn
        import http.client

        self.app.state.config["remote"]["trusted_proxies"] = ["127.0.0.1/32"]
        self.app.startup_config = copy.deepcopy(self.app.state.config)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(5)
        server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                lifespan="off",
                proxy_headers=False,
                log_level="critical",
                timeout_keep_alive=1,
            )
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [sock]}, daemon=True
        )
        thread.start()
        try:
            deadline = time.monotonic() + 3
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(server.started)
            client = http.client.HTTPConnection(
                "127.0.0.1", sock.getsockname()[1], timeout=3
            )
            client.request(
                "POST",
                PREFIX + "discover",
                json.dumps(self.base),
                headers={
                    "Authorization": "Bearer synthetic-bearer",
                    "Content-Type": "application/json",
                    "X-Lifetxt-Remote-Version": "2",
                    "X-Lifetxt-Resource-Contract": "resource-reference-v1",
                    "X-Forwarded-Proto": "https",
                },
            )
            response = client.getresponse()
            data = response.read()
            client.close()
            self.assertEqual(200, response.status, data)
            self.assertEqual(
                "Attachment", json.loads(data)["resources"][0]["display_name"]
            )
        finally:
            server.should_exit = True
            thread.join(3)
            sock.close()
            self.assertFalse(thread.is_alive())
