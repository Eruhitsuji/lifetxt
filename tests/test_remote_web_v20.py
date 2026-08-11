import datetime
import json
import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

from lifetxt.webapp import create_app


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteWebV20Tests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_ALICE_V20"] = "secret-v20"
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Fix_remote record:ticket id:T-1 project:web visibility:shared ticket_status:new\n"
            )
        self.config = {
            "api": {"token": "legacy-api-token"},
            "remote": {
                "enabled": True,
                "browser_ui": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "editor",
                        "token_env": "REMOTE_ALICE_V20",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    }
                ],
                "allow_loopback_http": True,
                "browser_session_ttl_seconds": 600,
                "browser_session_idle_seconds": 300,
            },
        }
        self.client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=self.config,
                read_only=True,
            )
        )
        self.v2 = {"X-Lifetxt-Remote-Version": "2"}
        self.bearer = dict(self.v2, Authorization="Bearer secret-v20")
        self.origin = "http://testserver"

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("REMOTE_ALICE_V20", None)

    def test_protocol_negotiation_and_legacy_v1(self):
        legacy = self.client.get(
            "/api/remote/v1/capabilities",
            headers={"Authorization": "Bearer secret-v20"},
        )
        self.assertEqual(200, legacy.status_code)
        self.assertEqual("remote-access-policy-v1.schema.json", legacy.json()["schema"])
        current = self.client.get("/api/remote/v1/capabilities", headers=self.bearer)
        self.assertEqual(200, current.status_code)
        self.assertEqual("remote-capability-v2.schema.json", current.json()["schema"])
        self.assertEqual("2", current.headers["X-Lifetxt-Remote-Version"])
        future = self.client.get(
            "/api/remote/v1/capabilities",
            headers={
                "Authorization": "Bearer secret-v20",
                "X-Lifetxt-Remote-Version": "99",
            },
        )
        self.assertEqual(426, future.status_code)
        self.assertEqual("REMOTE_VERSION_UNSUPPORTED", future.json()["error"])
        self.assertEqual("2", future.headers["X-Lifetxt-Remote-Version"])

    def test_remote_auth_is_independent_from_legacy_api_token(self):
        response = self.client.get("/api/remote/v1/session", headers=self.bearer)
        self.assertEqual(200, response.status_code)
        self.assertEqual("alice", response.json()["principal"]["id"])
        self.assertNotIn("token_env", response.json()["principal"])

    def test_browser_login_session_csrf_logout(self):
        login_headers = dict(self.v2, Origin=self.origin)
        response = self.client.post(
            "/api/remote/v1/browser/login",
            headers=login_headers,
            json={"token": "secret-v20"},
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=strict", response.headers["set-cookie"])
        csrf = response.json()["csrf_token"]

        session = self.client.get("/api/remote/v1/browser/session", headers=self.v2)
        self.assertEqual(200, session.status_code)
        self.assertEqual("alice", session.json()["principal"]["id"])
        snapshot = self.client.get("/api/remote/v1/snapshot", headers=self.v2)
        self.assertEqual(200, snapshot.status_code)

        revision = snapshot.json()["revision"]
        missing = self.client.post(
            "/api/remote/v1/write-check",
            headers=dict(self.v2, **{"If-Match": revision, "Origin": self.origin}),
            json={"operation": "test"},
        )
        self.assertEqual(403, missing.status_code)
        self.assertEqual("CSRF_REQUIRED", missing.json()["error"])

        accepted_headers = dict(
            self.v2,
            **{"If-Match": revision, "Origin": self.origin, "X-CSRF-Token": csrf},
        )
        accepted = self.client.post(
            "/api/remote/v1/write-check",
            headers=accepted_headers,
            json={"operation": "test"},
        )
        self.assertEqual(200, accepted.status_code, accepted.text)
        self.assertFalse(accepted.json()["authoritative_mutation"])

        logout = self.client.post(
            "/api/remote/v1/browser/logout",
            headers=dict(self.v2, **{"Origin": self.origin, "X-CSRF-Token": csrf}),
        )
        self.assertEqual(200, logout.status_code)
        self.assertEqual(
            401,
            self.client.get(
                "/api/remote/v1/browser/session", headers=self.v2
            ).status_code,
        )

    def test_browser_session_clock_decision_is_audited(self):
        audit_path = os.path.join(self.temp.name, "clock-audit.jsonl")
        config = dict(self.config)
        config["remote"] = dict(self.config["remote"], audit_log=audit_path)
        config["clock"] = {
            "require_remote_write_time": True,
            "skew_warning_seconds": 10,
            "skew_reject_seconds": 60,
        }
        client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=config,
                read_only=False,
            )
        )
        login = client.post(
            "/api/remote/v1/browser/login",
            headers=dict(self.v2, Origin=self.origin),
            json={"token": "secret-v20"},
        )
        self.assertEqual(200, login.status_code, login.text)
        csrf = login.json()["csrf_token"]
        revision = client.get("/api/remote/v1/snapshot", headers=self.v2).json()[
            "revision"
        ]
        response = client.post(
            "/api/remote/v1/write-check",
            headers=dict(
                self.v2,
                **{
                    "If-Match": revision,
                    "Origin": self.origin,
                    "X-CSRF-Token": csrf,
                    "X-Lifetxt-Client-Time": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                },
            ),
            json={"operation": "session-clock"},
        )
        self.assertEqual(200, response.status_code, response.text)
        with open(audit_path, encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle if line.strip()]
        event = [
            row for row in events if row["action"] == "POST /api/remote/v1/write-check"
        ][-1]
        self.assertEqual("alice", event["principal"])
        self.assertEqual("browser-session", event["detail"]["authentication"])
        self.assertEqual("active", event["detail"]["session"])
        self.assertEqual("ok", event["detail"]["clock"]["state"])

    def test_relogin_rotates_and_revokes_the_previous_cookie(self):
        login_headers = dict(self.v2, Origin=self.origin)
        first = self.client.post(
            "/api/remote/v1/browser/login",
            headers=login_headers,
            json={"token": "secret-v20"},
        )
        self.assertEqual(200, first.status_code)
        old_cookie = self.client.cookies.get("lifetxt_remote_session")
        second = self.client.post(
            "/api/remote/v1/browser/login",
            headers=login_headers,
            json={"token": "secret-v20"},
        )
        self.assertEqual(200, second.status_code)
        self.assertNotEqual(
            old_cookie, self.client.cookies.get("lifetxt_remote_session")
        )
        old_client = TestClient(self.client.app)
        old_client.cookies.set(
            "lifetxt_remote_session", old_cookie, path="/api/remote/"
        )
        expired = old_client.get("/api/remote/v1/browser/session", headers=self.v2)
        self.assertEqual(401, expired.status_code)

    def test_login_origin_and_browser_flag_are_enforced(self):
        missing_origin = self.client.post(
            "/api/remote/v1/browser/login",
            headers=self.v2,
            json={"token": "secret-v20"},
        )
        self.assertEqual(403, missing_origin.status_code)
        self.assertEqual("ORIGIN_REQUIRED", missing_origin.json()["error"])

    def test_resource_diagnostics_and_browser_page(self):
        resources = self.client.get("/api/remote/v1/resources", headers=self.bearer)
        self.assertEqual(200, resources.status_code)
        self.assertIn("items", [row["name"] for row in resources.json()["resources"]])
        items = self.client.get("/api/remote/v1/resources/items", headers=self.bearer)
        self.assertEqual(1, items.json()["data"]["count"])
        diagnostics = self.client.get("/api/remote/v1/diagnostics", headers=self.bearer)
        self.assertEqual(
            "remote-diagnostics-v1.schema.json", diagnostics.json()["schema"]
        )
        page = self.client.get("/remote")
        self.assertEqual(200, page.status_code)
        self.assertIn("Content-Security-Policy", page.headers)
        self.assertIn("Tokens are exchanged once", page.text)


@unittest.skipIf(TestClient is None, "web extras unavailable")
class SingleWorkerGuardWiringTests(unittest.TestCase):
    """Covers #171: the guard fires through the real create_app(), not just
    the standalone validate_single_worker_deployment function."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Item id:I-1 project:web visibility:shared\n")
        self.config = {
            "remote": {"enabled": True, "allow_loopback_http": True},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_create_app_raises_under_a_detected_multi_worker_deployment(self):
        from lifetxt.remote_access import RemoteAccessError

        os.environ["WEB_CONCURRENCY"] = "3"
        try:
            with self.assertRaises(RemoteAccessError) as caught:
                create_app(
                    paths=[self.path],
                    writable_path=self.path,
                    config=self.config,
                    read_only=True,
                )
            self.assertEqual("REMOTE_MULTI_WORKER_UNSUPPORTED", caught.exception.code)
        finally:
            os.environ.pop("WEB_CONCURRENCY", None)

    def test_create_app_succeeds_without_the_multi_worker_signal(self):
        os.environ.pop("WEB_CONCURRENCY", None)
        app = create_app(
            paths=[self.path],
            writable_path=self.path,
            config=self.config,
            read_only=True,
        )
        self.assertTrue(app.state.remote_enabled)


if __name__ == "__main__":
    unittest.main()
