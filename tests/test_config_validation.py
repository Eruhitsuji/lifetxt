import json
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt.config_validation import (
    CONFIG_SCHEMA_VERSION,
    config_version,
    is_supported_version,
    validate_config,
    validation_report,
)
from lifetxt.config_writer import ConfigWriteError, write_config, serialize_config
from lifetxt.config_migration import migrate_config


class ValidationTests(unittest.TestCase):
    def codes(self, config):
        return {row["code"] for row in validate_config(config)}

    def test_clean_config_has_no_errors(self):
        config = {"config_version": 1, "defaults": {"timezone": "UTC"}}
        report = validation_report(config)
        self.assertTrue(report["ok"])
        self.assertTrue(report["writable"])

    def test_unsupported_version_is_error_and_not_writable(self):
        config = {"config_version": CONFIG_SCHEMA_VERSION + 5}
        self.assertIn("C001", self.codes(config))
        self.assertFalse(is_supported_version(config))
        self.assertFalse(validation_report(config)["writable"])

    def test_non_integer_version_rejected(self):
        self.assertIn("C002", self.codes({"config_version": "one"}))

    def test_plaintext_secret_detected(self):
        config = {"notifications": {"email": {"password": "hunter2"}}}
        self.assertIn("C003", self.codes(config))

    def test_env_reference_is_allowed(self):
        config = {"notifications": {"email": {"smtp_pass_env": "LIFETXT_SMTP_PASS"}}}
        self.assertNotIn("C003", self.codes(config))

    def test_malformed_workspace_reported(self):
        self.assertIn("C006", self.codes({"workspaces": {"w": {"sources": [123]}}}))
        self.assertIn("C006", self.codes({"workspaces": {"w": {}}}))
        self.assertIn("C005", self.codes({"workspaces": "nope"}))

    def test_deprecated_key_warns(self):
        codes = self.codes({"generated_paths": [".generated/x.txt"]})
        self.assertIn("C007", codes)

    def test_version_default(self):
        self.assertEqual(1, config_version({}))


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, ".lifetxt.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_write_creates_backup_and_strips_runtime_keys(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write('{"config_version": 1}\n')
        data = OrderedDict(
            [("config_version", 1), ("web", {"port": 9000}), ("_path", self.path), ("_active_workspace", "default")]
        )
        report = write_config(self.path, data)
        self.assertTrue(os.path.exists(report["backup"]))
        with open(self.path, "r", encoding="utf-8") as handle:
            written = json.load(handle)
        self.assertNotIn("_path", written)
        self.assertNotIn("_active_workspace", written)
        self.assertEqual(9000, written["web"]["port"])

    def test_write_refuses_invalid_config(self):
        data = {"config_version": 1, "notifications": {"email": {"token": "abc"}}}
        with self.assertRaises(ConfigWriteError):
            write_config(self.path, data)

    def test_write_refuses_unsupported_version(self):
        with self.assertRaises(ConfigWriteError):
            write_config(self.path, {"config_version": CONFIG_SCHEMA_VERSION + 1})

    def test_backup_rotation_bounded(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write('{"config_version": 1}\n')
        for index in range(5):
            write_config(self.path, {"config_version": 1, "web": {"port": 8000 + index}}, max_backups=2)
        backups = [n for n in os.listdir(self.temp.name) if ".bak" in n]
        self.assertLessEqual(len(backups), 2)

    def test_serialize_is_stable_json(self):
        text = serialize_config({"config_version": 1, "_path": "x"})
        self.assertIn("config_version", text)
        self.assertNotIn("_path", text)


class MigrationTests(unittest.TestCase):
    def test_legacy_to_workspaces_default(self):
        config = {"paths": ["life.txt", ".generated/cal.txt"], "write_file": "life.txt",
                  "generated_paths": [".generated/cal.txt"]}
        migrated, changes = migrate_config(config)
        self.assertTrue(changes)
        self.assertEqual(CONFIG_SCHEMA_VERSION, migrated["config_version"])
        default = migrated["workspaces"]["default"]
        self.assertEqual("life.txt", default["write_file"])
        roles = [s.get("role") if isinstance(s, dict) else None for s in default["sources"]]
        self.assertIn("generated", roles)

    def test_migration_is_idempotent(self):
        config = {"paths": ["life.txt"], "write_file": "life.txt"}
        migrated, _ = migrate_config(config)
        migrated["_path"] = "/tmp/x"
        migrated2, changes2 = migrate_config(migrated)
        self.assertEqual([], changes2)

    def test_existing_workspaces_only_bumps_version(self):
        config = {"workspaces": {"w": {"sources": ["a.txt"]}}}
        migrated, changes = migrate_config(config)
        self.assertEqual(CONFIG_SCHEMA_VERSION, migrated["config_version"])
        self.assertIn("w", migrated["workspaces"])
        self.assertNotIn("default", migrated["workspaces"])


if __name__ == "__main__":
    unittest.main()
