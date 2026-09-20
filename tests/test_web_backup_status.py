import json
import os
import tempfile
import unittest
from unittest import mock

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - optional Web dependency
    TestClient = None

from lifetxt.backup_cli import run_create


@unittest.skipIf(TestClient is None, "web extras unavailable")
class WebBackupStatusApiTests(unittest.TestCase):
    def _client(self, config=None):
        from lifetxt.webapp import create_app

        return TestClient(create_app(paths=[], config=config or {}))

    def _write_status(self, destination, **fields):
        os.makedirs(destination, exist_ok=True)
        path = os.path.join(destination, ".lifetxt-backup-status.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(fields, handle)

    def _config(self, root, **backup_overrides):
        source = os.path.join(root, "life.txt")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Backup API fixture id:backup-api\n")
        backup = {
            "enabled": True,
            "sources": [source],
            "destination": os.path.join(root, "backups"),
        }
        backup.update(backup_overrides)
        return {"backup": backup}

    def test_unconfigured_is_a_normal_read_only_state(self):
        response = self._client().get("/api/backup/status")
        self.assertEqual(200, response.status_code)
        self.assertEqual("unconfigured", response.json()["state"])
        self.assertFalse(response.json()["configured"])
        self.assertEqual(405, self._client().post("/api/backup/status").status_code)

    def test_disabled_and_never_run_states_are_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            disabled = self._config(root, enabled=False)
            with mock.patch(
                "lifetxt.server_backup_status.run_status",
                side_effect=AssertionError("disabled configuration must not be read"),
            ):
                payload = self._client(disabled).get("/api/backup/status").json()
            self.assertEqual("disabled", payload["state"])
            self.assertTrue(payload["configured"])

        with tempfile.TemporaryDirectory() as root:
            payload = self._client(self._config(root)).get("/api/backup/status").json()
            self.assertEqual("never_run", payload["state"])
            self.assertEqual("never_run", payload["local"]["last_attempt_result"])

    def test_success_uses_cli_listing_without_exposing_absolute_paths(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            destination = config["backup"]["destination"]
            result = run_create(config["backup"]["sources"], destination)
            self._write_status(
                destination,
                last_attempt_at="2026-09-20T01:00:00Z",
                last_attempt_ok=True,
                last_success_at="2026-09-20T01:00:00Z",
                last_success_path=result.path,
            )

            payload = self._client(config).get("/api/backup/status").json()
            self.assertEqual("healthy", payload["state"])
            self.assertEqual(1, payload["backup_count"])
            self.assertEqual(
                os.path.basename(result.path), payload["latest_local_backup"]
            )
            self.assertEqual(
                os.path.basename(result.path), payload["local"]["last_success_backup"]
            )
            self.assertNotIn(root, json.dumps(payload))

    def test_local_failure_and_remote_failure_remain_independent(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            destination = config["backup"]["destination"]
            self._write_status(
                destination,
                last_attempt_at="2026-09-20T01:00:00Z",
                last_attempt_ok=False,
            )
            payload = self._client(config).get("/api/backup/status").json()
            self.assertEqual("local_failure", payload["state"])
            self.assertEqual("failure", payload["local"]["last_attempt_result"])
            self.assertEqual("not_configured", payload["remote"]["last_upload_result"])

        with tempfile.TemporaryDirectory() as root:
            secret_target = "private-remote:secret/bucket"
            config = self._config(
                root,
                remote={"backend": "rclone", "target": secret_target},
            )
            destination = config["backup"]["destination"]
            self._write_status(
                destination,
                last_attempt_at="2026-09-20T01:00:00Z",
                last_attempt_ok=True,
                last_success_at="2026-09-20T01:00:00Z",
                last_success_path=os.path.join(destination, "safe.ltbackup"),
                last_remote_upload_at="2026-09-20T01:01:00Z",
                last_remote_upload_ok=False,
                last_remote_error=(
                    "rclone failed for %s with token=do-not-disclose" % secret_target
                ),
            )
            payload = self._client(config).get("/api/backup/status").json()
            serialized = json.dumps(payload)
            self.assertEqual("remote_failure", payload["state"])
            self.assertTrue(payload["local"]["last_attempt_ok"])
            self.assertFalse(payload["remote"]["last_upload_ok"])
            self.assertNotIn(secret_target, serialized)
            self.assertNotIn("do-not-disclose", serialized)
            self.assertNotIn(destination, serialized)

    def test_partial_config_is_not_inspected_and_status_strings_are_validated(self):
        partial = {
            "backup": {
                "enabled": True,
                "destination": "/operator/private/partial-value",
            }
        }
        with mock.patch(
            "lifetxt.server_backup_status.run_status",
            side_effect=AssertionError("partial configuration must not be read"),
        ):
            payload = self._client(partial).get("/api/backup/status").json()
        self.assertEqual("unconfigured", payload["state"])

        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            destination = config["backup"]["destination"]
            self._write_status(
                destination,
                last_attempt_at="/secret/path/not-a-timestamp",
                last_attempt_ok=True,
                last_success_at="2026-09-20T01:00:00Z",
                last_success_path="C:\\secret\\customer-name.ltbackup",
                next_scheduled_run="token=do-not-disclose",
            )
            payload = self._client(config).get("/api/backup/status").json()
            serialized = json.dumps(payload)
            self.assertIsNone(payload["local"]["last_attempt_at"])
            self.assertEqual(
                "2026-09-20T01:00:00Z", payload["local"]["last_success_at"]
            )
            self.assertIsNone(payload["local"]["last_success_backup"])
            self.assertIsNone(payload["next_scheduled_run"])
            self.assertNotIn("secret", serialized)
            self.assertNotIn("do-not-disclose", serialized)


if __name__ == "__main__":
    unittest.main()
