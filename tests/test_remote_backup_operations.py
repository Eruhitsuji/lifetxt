import os
import tempfile
import time
import unittest
from unittest import mock

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

from lifetxt.webapp import create_app


class _Result(object):
    returncode = 0


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteBackupOperationTests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_BACKUP_TEST"] = "backup-secret"
        self.temp = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp.name, "life.txt")
        self.destination = os.path.join(self.temp.name, "backups")
        self.audit = os.path.join(self.temp.name, "audit.jsonl")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Backup_test id:T-1\n")
        self.config = {
            "backup": {
                "enabled": True,
                "sources": [self.life],
                "destination": self.destination,
            },
            "remote": {
                "enabled": True,
                "browser_ui": True,
                "allow_loopback_http": True,
                "audit_log": self.audit,
                "backup_run": {
                    "enabled": True,
                    "service_command": ["test-service-control"],
                    "cooldown_seconds": 900,
                },
                "principals": [
                    {
                        "id": "operator",
                        "role": "owner",
                        "scopes": ["backup:run"],
                        "token_env": "REMOTE_BACKUP_TEST",
                    }
                ],
            },
        }
        self.client = TestClient(
            create_app(
                paths=[self.life],
                writable_path=self.life,
                config=self.config,
                read_only=False,
            )
        )
        self.calls = []

        def runner(command, **kwargs):
            self.calls.append((command, kwargs))
            return _Result()

        self.client.app.state.remote_backup_run_store._runner = runner
        self.headers = {
            "Authorization": "Bearer backup-secret",
            "X-Lifetxt-Remote-Version": "2",
        }

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("REMOTE_BACKUP_TEST", None)

    def _post(self, key="key-1", headers=None):
        values = dict(self.headers)
        values["Idempotency-Key"] = key
        values.update(headers or {})
        return self.client.post("/api/remote/v1/operations/backup-runs", headers=values)

    def test_capability_is_advertised_only_when_available(self):
        value = self.client.get(
            "/api/remote/v1/capabilities", headers=self.headers
        ).json()
        self.assertTrue(value["operations"]["backup_run"]["available"])
        self.assertEqual(
            "backup:run", value["operations"]["backup_run"]["required_scope"]
        )

    def test_requires_explicit_scope_and_v2(self):
        self.config["remote"]["principals"][0]["scopes"] = []
        denied = self._post()
        self.assertEqual(403, denied.status_code)
        self.assertEqual("FORBIDDEN", denied.json()["error"])
        self.config["remote"]["principals"][0]["scopes"] = ["backup:run"]
        v1 = self._post(headers={"X-Lifetxt-Remote-Version": "1"})
        self.assertEqual(426, v1.status_code)

    def test_accepts_once_and_idempotent_retry_returns_same_operation(self):
        first = self._post()
        self.assertEqual(202, first.status_code, first.text)
        duplicate = self._post()
        self.assertEqual(202, duplicate.status_code, duplicate.text)
        self.assertEqual(first.json()["operation_id"], duplicate.json()["operation_id"])
        for _ in range(50):
            if self.calls:
                break
            time.sleep(0.01)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(
            ["test-service-control", "start", "lifetxt-backup.service"],
            self.calls[0][0],
        )
        self.assertEqual(-3, self.calls[0][1]["stdout"])

    def test_cooldown_and_missing_idempotency_fail_closed(self):
        missing = self.client.post(
            "/api/remote/v1/operations/backup-runs", headers=self.headers
        )
        self.assertEqual(400, missing.status_code)
        accepted = self._post("first")
        self.assertEqual(202, accepted.status_code)
        for _ in range(50):
            status = self.client.get(
                accepted.json()["status_url"], headers=self.headers
            ).json()["status"]
            if status in ("completed", "failed"):
                break
            time.sleep(0.01)
        limited = self._post("second")
        self.assertEqual(429, limited.status_code)
        self.assertEqual("BACKUP_RUN_RATE_LIMITED", limited.json()["error"])

    def test_browser_requires_csrf_and_page_contains_scoped_control(self):
        login = self.client.post(
            "/api/remote/v1/browser/login",
            headers={"X-Lifetxt-Remote-Version": "2", "Origin": "http://testserver"},
            json={"token": "backup-secret"},
        )
        self.assertEqual(200, login.status_code)
        denied = self.client.post(
            "/api/remote/v1/operations/backup-runs",
            headers={
                "X-Lifetxt-Remote-Version": "2",
                "Origin": "http://testserver",
                "Idempotency-Key": "browser-key",
            },
        )
        self.assertEqual(403, denied.status_code)
        page = self.client.get("/remote")
        self.assertIn("Run backup now", page.text)
        self.assertIn("backup:run", page.text)

    def test_status_separates_local_success_from_remote_failure(self):
        self.config["backup"]["remote"] = {
            "backend": "rclone",
            "target": "example:private-target",
        }
        with mock.patch(
            "lifetxt.remote_backup_operations.run_status",
            side_effect=[
                {"last_attempt_at": "before"},
                {
                    "last_attempt_at": "after",
                    "last_attempt_ok": True,
                    "last_remote_upload_ok": False,
                    "last_success_path": "/private/path/backup.zip",
                    "last_remote_error": "secret raw adapter output",
                },
            ],
        ):
            accepted = self._post("split-result")
            for _ in range(50):
                result = self.client.get(
                    accepted.json()["status_url"], headers=self.headers
                ).json()
                if result["status"] in ("completed", "failed"):
                    break
                time.sleep(0.01)
        self.assertEqual("completed", result["status"])
        self.assertEqual("succeeded", result["local"]["status"])
        self.assertEqual("failed", result["remote"]["status"])
        self.assertNotIn("private", str(result))
        self.assertNotIn("secret", str(result))

    def test_unavailable_audit_or_runner_is_not_advertised(self):
        self.config["remote"].pop("audit_log")
        capability = self.client.get(
            "/api/remote/v1/capabilities", headers=self.headers
        ).json()
        self.assertFalse(capability["operations"]["backup_run"]["available"])
        refused = self._post()
        self.assertEqual(503, refused.status_code)
        self.assertEqual([], self.calls)

    def test_audit_write_failure_rolls_back_before_dispatch(self):
        self.config["remote"]["audit_log"] = self.temp.name
        refused = self._post("audit-failure")
        self.assertEqual(503, refused.status_code)
        self.assertEqual("AUDIT_UNAVAILABLE", refused.json()["error"])
        self.assertEqual([], self.calls)
