from __future__ import unicode_literals

import json
import unittest
from unittest import mock

from lifetxt.tui_remote_client import (
    RemoteAuthError,
    RemoteConnectionError,
    RemoteInsecureHttpRequired,
    RemoteMutationConflict,
    RemoteTuiConnection,
)


class _FakeHTTPResponse(object):
    def __init__(self, status, body, headers=None):
        self._status = status
        self._body = body
        self.headers = headers or {}

    def getcode(self):
        return self._status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class TransportSecurityTests(unittest.TestCase):
    def test_https_to_any_host_is_always_allowed(self):
        RemoteTuiConnection("https://example.internal")

    def test_plain_http_to_loopback_is_allowed(self):
        RemoteTuiConnection("http://127.0.0.1:8765")
        RemoteTuiConnection("http://localhost:8765")

    def test_plain_http_to_non_loopback_is_refused_without_opt_in(self):
        with self.assertRaises(RemoteInsecureHttpRequired):
            RemoteTuiConnection("http://example.internal:8080")

    def test_plain_http_to_non_loopback_is_allowed_with_explicit_opt_in(self):
        RemoteTuiConnection("http://example.internal:8080", allow_insecure_http=True)

    def test_invalid_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            RemoteTuiConnection("ftp://example.internal")


class DescribeTests(unittest.TestCase):
    def test_describe_never_includes_the_password(self):
        connection = RemoteTuiConnection(
            "https://example.internal", username="alice", password="hunter2"
        )
        description = connection.describe()
        self.assertIn("alice", description)
        self.assertNotIn("hunter2", description)


class RequestTests(unittest.TestCase):
    def _connection(self):
        return RemoteTuiConnection(
            "http://127.0.0.1:8765", username="alice", password="s3cret"
        )

    def test_basic_auth_header_is_sent_when_username_configured(self):
        connection = self._connection()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            return _FakeHTTPResponse(
                200, b'{"items": []}', {"X-Lifetxt-Revision": "abc"}
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            connection.request("GET", "/api/items")

        self.assertIn("Authorization", captured["headers"])
        self.assertTrue(captured["headers"]["Authorization"].startswith("Basic "))
        # The raw secret must never appear verbatim in the header value.
        self.assertNotIn("s3cret", captured["headers"]["Authorization"])

    def test_no_auth_header_without_a_configured_username(self):
        connection = RemoteTuiConnection("http://127.0.0.1:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            return _FakeHTTPResponse(200, b"{}", {})

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            connection.request("GET", "/api/revision")

        self.assertNotIn("Authorization", captured["headers"])

    def test_if_match_header_is_forwarded(self):
        connection = self._connection()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            return _FakeHTTPResponse(200, b"{}", {})

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            connection.request("PUT", "/api/items/id/t1", json_body={}, if_match="rev1")

        self.assertEqual(captured["headers"].get("If-match"), "rev1")

    def test_successful_response_updates_file_revision(self):
        connection = self._connection()

        def fake_urlopen(req, timeout=None):
            return _FakeHTTPResponse(
                200,
                json.dumps({"ok": True}).encode("utf-8"),
                {"X-Lifetxt-Revision": "rev2"},
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            connection.request("GET", "/api/items")

        self.assertEqual(connection.file_revision, "rev2")

    def test_401_response_raises_remote_auth_error(self):
        connection = self._connection()

        import urllib.error

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RemoteAuthError):
                connection.request("GET", "/api/items")

    def test_409_response_raises_conflict_with_current_item(self):
        connection = self._connection()

        import io
        import urllib.error

        detail = {
            "error": "CONFLICT",
            "message": "Item changed since it was last read.",
            "current_revision": "rev-new",
            "current_item": {"id": "t1", "status": "[/]"},
        }
        body = json.dumps(detail).encode("utf-8")

        def fake_urlopen(req, timeout=None):
            exc = urllib.error.HTTPError(
                req.full_url, 409, "Conflict", {}, io.BytesIO(body)
            )
            raise exc

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RemoteMutationConflict) as ctx:
                connection.request(
                    "PUT", "/api/items/id/t1", json_body={}, if_match="stale"
                )

        self.assertEqual(ctx.exception.current_revision, "rev-new")
        self.assertEqual(ctx.exception.current_item["status"], "[/]")

    def test_connection_failure_raises_remote_connection_error(self):
        connection = self._connection()

        import urllib.error

        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RemoteConnectionError):
                connection.request("GET", "/api/items")


if __name__ == "__main__":
    unittest.main()
