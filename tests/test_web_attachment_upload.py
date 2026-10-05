"""Security and transaction contracts of the bounded browser upload endpoint."""

import asyncio
import hashlib
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from lifetxt import mutation
from lifetxt.attachments import split_value
from lifetxt.parser import parse_text
from lifetxt.web_attachment_upload import (
    MANAGED_DIRECTORY,
    UPLOAD_PATH,
    WEB_MAX_BYTES,
    UploadError,
    content_type,
    read_upload,
    upload_filename,
    upload_limit,
)

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


class UploadValidationTests(unittest.TestCase):
    def test_limit_uses_existing_policy_and_fixed_web_cap(self):
        self.assertEqual(WEB_MAX_BYTES, upload_limit({}))
        self.assertEqual(7, upload_limit({"attachments": {"max_file_bytes": 7}}))
        self.assertEqual(9, upload_limit({"attachments": {"max_bytes": 9}}))

    def test_unicode_filename_is_metadata_only(self):
        self.assertEqual("報告.pdf", upload_filename(quote("報告.pdf", safe="")))

    def test_filename_attacks(self):
        for name in (
            "../a",
            "/a",
            "C:\\a",
            "\\\\host\\a",
            "a:b",
            ".",
            "..",
            "a\x00",
            "a\n",
            "a\u202e.txt",
            "a\u2066.txt",
            "CON.txt",
            "a.",
            " a",
            "a/../b",
            "a\\b",
        ):
            with self.subTest(name=repr(name)), self.assertRaises(UploadError):
                upload_filename(quote(name, safe=""))
        for encoded in ("%ff", "%ZZ", "x" * 256):
            with self.subTest(encoded=encoded), self.assertRaises(UploadError):
                upload_filename(encoded)

    def test_binary_executable_magic_cannot_hide_behind_txt(self):
        for payload in (
            b"MZ...",
            b"\x7fELF...",
            b"#!/bin/sh",
            b"\xfe\xed\xfa\xcf...",
            b"\xcf\xfa\xed\xfe...",
        ):
            with self.subTest(payload=payload), self.assertRaises(UploadError):
                content_type("safe.txt", payload, {})

    def test_mime_policy_checks_observed_and_filename_mime(self):
        from lifetxt.attachment_transactions import AttachmentTransactionError

        for name, payload, policy in (
            ("safe.pdf", b"%PDF-1.7", {"blocked_mime": ["application/pdf"]}),
            ("safe.html", b"text", {"blocked_mime": ["text/html"]}),
            ("safe.txt", b"\x00\xff", {"allowed_mime": ["text/plain"]}),
        ):
            with self.subTest(name=name), self.assertRaises(AttachmentTransactionError):
                content_type(name, payload, {"attachments": policy})

    def test_stream_stops_at_first_overflow_without_consuming_rest(self):
        class Incoming:
            headers = {}
            count = 0

            async def stream(self):
                for value in (b"12", b"34", b"do not consume"):
                    self.count += 1
                    yield value

        request = Incoming()
        with self.assertRaises(UploadError) as result:
            asyncio.run(read_upload(request, 3))
        self.assertEqual("UPLOAD_TOO_LARGE", result.exception.code)
        self.assertEqual(2, request.count)

    def test_known_oversize_does_not_read_stream(self):
        class Incoming:
            headers = {"content-length": "4"}

            async def stream(self):
                raise AssertionError("Must reject before reading body")
                yield b""

        with self.assertRaises(UploadError):
            asyncio.run(read_upload(Incoming(), 3))

    def test_length_mismatch(self):
        class Incoming:
            headers = {"content-length": "2"}

            async def stream(self):
                yield b"1"

        with self.assertRaises(UploadError) as result:
            asyncio.run(read_upload(Incoming(), 3))
        self.assertEqual("INVALID_LENGTH", result.exception.code)

    def test_many_tiny_chunks(self):
        class Incoming:
            headers = {}

            async def stream(self):
                for _ in range(10000):
                    yield b"a"

        self.assertEqual(b"a" * 10000, asyncio.run(read_upload(Incoming(), 10000)))


@unittest.skipIf(TestClient is None, "Web extras are not installed")
class UploadAPITests(unittest.TestCase):
    def setUp(self):
        from lifetxt.webapp import create_app

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "life.txt"
        self.before = b"[ ] T Upload id:t1\n"
        self.path.write_bytes(self.before)
        self.root = Path(self.tmp.name) / "attachments"
        self.config = {
            "attachments": {"root": str(self.root)},
            "api": {"token": "test-only"},
        }
        self.app = create_app(
            [str(self.path)], writable_path=str(self.path), config=self.config
        )
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.revision = hashlib.sha256(self.before).hexdigest()

    def headers(self, **overrides):
        value = {
            "Authorization": "Bearer test-only",
            "Content-Type": "application/octet-stream",
            "X-Lifetxt-Upload": "1",
            "X-Lifetxt-Item-Id": "t1",
            "X-Lifetxt-Filename": "report.txt",
            "X-Lifetxt-Expected-Revision": self.revision,
        }
        for key, override in overrides.items():
            if override is None:
                value.pop(key, None)
            else:
                value[key] = override
        return value

    def post(self, content=b"hello", **overrides):
        return self.client.post(
            UPLOAD_PATH, content=content, headers=self.headers(**overrides)
        )

    def test_tls_proxy_origin_uses_explicit_immediate_peer_trust(self):
        from lifetxt.webapp import create_app

        self.config["remote"] = {"trusted_proxies": ["127.0.0.1/32"]}
        app = create_app(
            [str(self.path)], writable_path=str(self.path), config=self.config
        )
        with TestClient(app, client=("127.0.0.1", 12345)) as client:
            response = client.post(
                UPLOAD_PATH,
                content=b"hello",
                headers=self.headers(
                    **{
                        "Host": "backend.internal:8000",
                        "X-Forwarded-Host": "life.example.test:8443",
                        "X-Forwarded-Proto": "https",
                        "Origin": "https://life.example.test:8443",
                    }
                ),
            )
        self.assertEqual(201, response.status_code, response.text)
        self.assertNotEqual(self.before, self.path.read_bytes())

    def test_spoofed_and_ambiguous_proxy_origins_never_mutate(self):
        from lifetxt.webapp import create_app

        self.config["remote"] = {"trusted_proxies": ["127.0.0.1/32"]}
        app = create_app(
            [str(self.path)], writable_path=str(self.path), config=self.config
        )
        for peer, forwarded in (
            ("192.0.2.1", [("X-Forwarded-Proto", "https")]),
            ("127.0.0.1", [("X-Forwarded-Proto", "https,http")]),
            (
                "127.0.0.1",
                [("X-Forwarded-Proto", "https"), ("X-Forwarded-Proto", "http")],
            ),
            (
                "127.0.0.1",
                [("X-Forwarded-Proto", "https"), ("X-Forwarded-Host", "other.test")],
            ),
        ):
            with (
                self.subTest(peer=peer, forwarded=forwarded),
                TestClient(app, client=(peer, 12345)) as client,
            ):
                response = client.post(
                    UPLOAD_PATH,
                    content=b"hello",
                    headers=[
                        *self.headers(**{"Origin": "https://testserver"}).items(),
                        *forwarded,
                    ],
                )
            self.assertEqual(403, response.status_code, response.text)
            self.assertEqual(self.before, self.path.read_bytes())
            self.assertFalse(self.root.exists())

    def assert_safe(self, response):
        text = response.text
        for sensitive in (
            self.tmp.name,
            str(self.path),
            str(self.root),
            "journal_path",
            "stored_path",
            "file:",
            "web-uploads/",
            "<script>",
        ):
            self.assertNotIn(sensitive, text)
        self.assertEqual("no-store", response.headers["cache-control"])

    def assert_no_upload(self):
        self.assertEqual(self.before, self.path.read_bytes())
        self.assertFalse(list(self.root.glob("web-uploads/*")))

    def test_success_transaction_receipt_and_current_etag(self):
        response = self.post()
        self.assertEqual(201, response.status_code, response.text)
        self.assert_safe(response)
        data = response.json()
        if importlib.util.find_spec("jsonschema") is not None:
            from jsonschema import Draft202012Validator
            from lifetxt.schema_extensions_v32 import upload_receipt_schema

            Draft202012Validator(upload_receipt_schema()).validate(data)
        self.assertEqual(
            {
                "contract_version",
                "attachment_id",
                "display_name",
                "size_bytes",
                "media_type",
                "source_revision",
                "attachment_revision",
            },
            set(data),
        )
        self.assertEqual("text/plain", data["media_type"])
        self.assertEqual(
            hashlib.sha256(b"hello").hexdigest(), data["attachment_revision"]
        )
        self.assertEqual(
            hashlib.sha256(self.path.read_bytes()).hexdigest(), data["source_revision"]
        )
        self.assertEqual('"' + data["source_revision"] + '"', response.headers["etag"])
        items, _ = parse_text(self.path.read_text())
        stored, short_digest = split_value(items[0].details["file"][0])
        target = self.path.parent / stored
        self.assertEqual(b"hello", target.read_bytes())
        self.assertEqual(16, len(short_digest))
        self.assertTrue(target.name.startswith(data["attachment_id"]))
        self.assertNotIn("report", target.name)
        self.assertTrue(list(Path(self.tmp.name).rglob("journal.json")))

    def test_unicode_and_html_like_display_names_are_plain_json(self):
        response = self.post(**{"X-Lifetxt-Filename": quote("報告<img>.txt", safe="")})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual("報告<img>.txt", response.json()["display_name"])

    def test_safe_policy_discovery_and_limit(self):
        self.config["attachments"]["max_file_bytes"] = 7
        response = self.client.get(
            UPLOAD_PATH, headers={"Authorization": "Bearer test-only"}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(7, response.json()["max_upload_bytes"])
        self.assert_safe(response)

    def test_openapi_describes_raw_upload_and_path_free_receipt(self):
        operation = self.app.openapi()["paths"][UPLOAD_PATH]["post"]
        self.assertIn("application/octet-stream", operation["requestBody"]["content"])
        self.assertEqual(4, len(operation["parameters"]))
        schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("path", schema["properties"])

    def test_auth_and_read_only_prevent_consumption_and_writes(self):
        response = self.post(**{"Authorization": None})
        self.assertEqual(401, response.status_code)
        self.app.state.read_only = True
        response = self.post()
        self.assertEqual(403, response.status_code)
        self.assert_no_upload()

    def test_actual_read_only_instance(self):
        from lifetxt.webapp import create_app

        with TestClient(
            create_app([str(self.path)], config=self.config, read_only=True)
        ) as client:
            response = client.post(
                UPLOAD_PATH, content=b"hello", headers=self.headers()
            )
            self.assertEqual(403, response.status_code)
            self.assertFalse(
                client.get(UPLOAD_PATH, headers=self.headers()).json()["upload_enabled"]
            )
        self.assert_no_upload()

    def test_missing_and_malformed_revision(self):
        for value, status in (
            (None, 428),
            ("", 400),
            ("*", 400),
            ("a" * 16, 400),
            ('"' + self.revision + '"', 400),
        ):
            with self.subTest(value=value):
                response = self.post(**{"X-Lifetxt-Expected-Revision": value})
                self.assertEqual(status, response.status_code, response.text)
                self.assert_safe(response)
        self.assert_no_upload()

    def test_stale_revision_fails_without_creating_namespace(self):
        response = self.post(**{"X-Lifetxt-Expected-Revision": "0" * 64})
        self.assertEqual(409, response.status_code)
        self.assert_safe(response)
        self.assert_no_upload()
        self.assertFalse(self.root.exists())

    def test_missing_item_and_generated_target(self):
        self.assertEqual(404, self.post(**{"X-Lifetxt-Item-Id": "other"}).status_code)
        self.config["sync_ics"] = {"generated_paths": [str(self.path)]}
        self.assertEqual(403, self.post().status_code)
        self.assertFalse(
            self.client.get(UPLOAD_PATH, headers=self.headers()).json()[
                "upload_enabled"
            ]
        )
        self.assert_no_upload()

    def test_unsupported_format_and_id_ambiguity_fail_closed(self):
        for content in (
            b"#! format_version: 2\n[ ] T Future id:t1\n",
            b"[ ] T First id:t1\n[ ] T Second id:t1\n",
        ):
            self.path.write_bytes(content)
            self.revision = hashlib.sha256(content).hexdigest()
            response = self.post()
            self.assertIn(response.status_code, (404, 409), response.text)
            self.assert_safe(response)
            self.assertEqual(content, self.path.read_bytes())
            self.assertFalse(self.root.exists())

    def test_upload_requires_marker_and_same_origin(self):
        for headers in (
            {"X-Lifetxt-Upload": None},
            {"Origin": "https://evil.example"},
            {"Origin": "null"},
            {"Origin": "http://testserver/"},
            {"Origin": "http://testserver", "Sec-Fetch-Site": "cross-site"},
            {
                "Origin": "https://evil.example",
                "X-Forwarded-Host": "evil.example",
                "X-Forwarded-Proto": "https",
            },
        ):
            with self.subTest(headers=headers):
                response = self.post(**headers)
                self.assertEqual(403, response.status_code, response.text)
                self.assert_safe(response)
        self.assert_no_upload()
        response = self.post(**{"Origin": "http://testserver"})
        self.assertEqual(201, response.status_code, response.text)

    def test_duplicate_headers_refused(self):
        headers = list(self.headers().items()) + [("X-Lifetxt-Filename", "second.txt")]
        response = self.client.post(UPLOAD_PATH, content=b"hello", headers=headers)
        self.assertEqual(400, response.status_code)
        self.assert_no_upload()

    def test_no_permissive_cors_preflight(self):
        response = self.client.options(
            UPLOAD_PATH,
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
                "Authorization": "Bearer test-only",
            },
        )
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_body_formats_and_encoding_refused(self):
        for overrides in (
            {"Content-Type": "application/json"},
            {"Content-Type": "multipart/form-data"},
            {"Content-Encoding": "gzip"},
        ):
            response = self.post(**overrides)
            self.assertEqual(415, response.status_code)
            self.assert_safe(response)
        response = self.client.post(
            UPLOAD_PATH + "?path=life.txt&allow_executable=true",
            content=b"hello",
            headers=self.headers(),
        )
        self.assertEqual(400, response.status_code)
        self.assert_no_upload()

    def test_filename_and_content_policy_failures_do_not_write(self):
        for name, content in (
            ("../report.txt", b"hello"),
            ("C:\\report.txt", b"hello"),
            ("test.sh", b"echo hi"),
            ("safe.txt", b"\x7fELFbad"),
            ("safe.txt", b"#!/bin/sh"),
        ):
            with self.subTest(name=name):
                response = self.post(
                    content, **{"X-Lifetxt-Filename": quote(name, safe="")}
                )
                self.assertIn(response.status_code, (400, 415), response.text)
                self.assert_safe(response)
        self.config["attachments"]["allowed_mime"] = ["image/png"]
        self.assertEqual(415, self.post().status_code)
        self.assert_no_upload()

    def test_oversize_known_length_and_chunked_are_bounded(self):
        self.config["attachments"]["max_file_bytes"] = 4
        self.assertEqual(413, self.post().status_code)
        response = self.client.post(
            UPLOAD_PATH, content=iter([b"123", b"456"]), headers=self.headers()
        )
        self.assertEqual(413, response.status_code, response.text)
        self.assert_safe(response)
        self.assert_no_upload()
        self.assertEqual(201, self.post(b"1234").status_code)

    def test_collision_regular_directory_symlink_and_fifo_are_never_read(self):
        namespace = self.root / MANAGED_DIRECTORY
        namespace.mkdir(parents=True)
        target = namespace / ("a" * 32 + ".txt")
        for kind in ("file", "directory", "symlink", "fifo"):
            with self.subTest(kind=kind):
                if kind == "file":
                    target.write_bytes(b"preserve")
                elif kind == "directory":
                    target.mkdir()
                elif kind == "symlink":
                    try:
                        target.symlink_to(self.path)
                    except OSError:
                        continue
                elif hasattr(os, "mkfifo"):
                    os.mkfifo(target)
                else:
                    continue
                with patch("lifetxt.web_attachment_upload.uuid.uuid4") as random:
                    random.return_value.hex = "a" * 32
                    response = self.post()
                self.assertEqual(409, response.status_code, response.text)
                self.assert_safe(response)
                self.assertEqual(self.before, self.path.read_bytes())
                if kind == "file":
                    self.assertEqual(b"preserve", target.read_bytes())
                if kind == "directory":
                    target.rmdir()
                else:
                    target.unlink()

    def test_symlinked_namespace_is_rejected(self):
        self.root.mkdir()
        try:
            (self.root / MANAGED_DIRECTORY).symlink_to(
                self.path.parent, target_is_directory=True
            )
        except OSError as exc:
            self.skipTest("Host cannot create a symlink: %s" % exc)
        response = self.post()
        self.assertEqual(409, response.status_code)
        self.assert_safe(response)
        self.assertEqual(self.before, self.path.read_bytes())

    def test_source_changes_during_receive_is_rejected(self):
        changed = self.before + b"[ ] T Added id:t2\n"

        def body():
            self.path.write_bytes(changed)
            yield b"hello"

        response = self.client.post(UPLOAD_PATH, content=body(), headers=self.headers())
        self.assertEqual(409, response.status_code, response.text)
        self.assert_safe(response)
        self.assertEqual(changed, self.path.read_bytes())
        self.assertFalse(list(self.root.glob("web-uploads/*")))

    def test_commit_time_conflict_is_redacted(self):
        conflict = mutation.MutationConflict(str(self.path), self.revision, "0" * 64)
        with patch(
            "lifetxt.web_attachment_upload.attachments.put_attachment",
            side_effect=conflict,
        ):
            response = self.post()
        self.assertEqual(409, response.status_code)
        self.assert_safe(response)
        self.assert_no_upload()

    def test_partial_transaction_failure_is_compensated_and_redacted(self):
        from lifetxt import multi_target

        original = multi_target._commit_staged

        def fail_source(row, operation):
            if row["plan"].path == str(self.path):
                raise OSError("private failure at " + str(self.path))
            return original(row, operation)

        with patch("lifetxt.multi_target._commit_staged", side_effect=fail_source):
            response = self.post()
        self.assertEqual(503, response.status_code, response.text)
        self.assert_safe(response)
        self.assert_no_upload()
        journals = list(Path(self.tmp.name).rglob("journal.json"))
        self.assertTrue(journals)
        self.assertEqual("compensated", json.loads(journals[0].read_text())["state"])
        self.assertFalse(list(Path(self.tmp.name).rglob("*.tmp")))
        self.assertEqual(201, self.post().status_code)

    def test_timeout_and_disconnect_release_slot_without_writes(self):
        from starlette.requests import ClientDisconnect

        for error in (asyncio.TimeoutError(), ClientDisconnect()):

            async def incomplete(*args):
                raise error

            with patch(
                "lifetxt.web_attachment_upload.read_upload", side_effect=incomplete
            ):
                response = self.post()
            self.assertEqual(408, response.status_code)
            self.assert_safe(response)
            self.assert_no_upload()

        async def stalled(*args):
            await asyncio.Event().wait()

        with (
            patch("lifetxt.web_attachment_upload.RECEIVE_TIMEOUT_SECONDS", 0.01),
            patch("lifetxt.web_attachment_upload.read_upload", side_effect=stalled),
        ):
            response = self.post()
        self.assertEqual(408, response.status_code)
        self.assert_no_upload()
        self.assertEqual(201, self.post().status_code)

    def test_concurrent_commit_work_is_bounded(self):
        from lifetxt.web_attachment_upload import commit_upload

        started = threading.Barrier(3)
        release = threading.Event()
        responses = []

        def held(*args):
            started.wait(timeout=5)
            release.wait(timeout=5)
            return commit_upload(*args)

        def upload():
            responses.append(self.post())

        with patch("lifetxt.web_attachment_upload.commit_upload", side_effect=held):
            workers = [threading.Thread(target=upload) for _ in range(2)]
            for worker in workers:
                worker.start()
            try:
                started.wait(timeout=5)
                self.assertEqual(429, self.post().status_code)
            finally:
                release.set()
                for worker in workers:
                    worker.join(timeout=5)
        self.assertEqual([201, 409], sorted(r.status_code for r in responses))

    def test_cancelled_request_keeps_slot_until_commit_finishes(self):
        from starlette.requests import Request

        endpoint = next(
            r.endpoint
            for r in self.app.routes
            if r.path == UPLOAD_PATH and "POST" in r.methods
        )
        started = threading.Barrier(3)
        release = threading.Event()

        def held(*args):
            started.wait(timeout=5)
            release.wait(timeout=5)
            return {"completed": True}

        def request():
            async def receive():
                return {"type": "http.request", "body": b"hello", "more_body": False}

            scope = {
                "type": "http",
                "scheme": "http",
                "path": UPLOAD_PATH,
                "query_string": b"",
                "server": ("testserver", 80),
                "headers": [
                    (k.lower().encode(), v.encode()) for k, v in self.headers().items()
                ],
            }
            return Request(scope, receive)

        async def scenario():
            workers = [asyncio.create_task(endpoint(request())) for _ in range(2)]
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: started.wait(timeout=5)
                )
                for worker in workers:
                    worker.cancel()
                outcomes = await asyncio.gather(*workers, return_exceptions=True)
                self.assertTrue(
                    all(isinstance(e, asyncio.CancelledError) for e in outcomes)
                )
                self.assertEqual(429, (await endpoint(request())).status_code)
            finally:
                release.set()
                pending = [
                    t
                    for t in asyncio.all_tasks()
                    if t is not asyncio.current_task() and not t.done()
                ]
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True), 5
                )

        with patch("lifetxt.web_attachment_upload.commit_upload", side_effect=held):
            asyncio.run(scenario())
        self.assert_no_upload()
        self.assertEqual(201, self.post().status_code)


if __name__ == "__main__":
    unittest.main()
