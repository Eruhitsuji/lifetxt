import json
import os
import tempfile
import unittest
from collections import OrderedDict
from unittest import mock

from lifetxt import atomic
from lifetxt.config_validation import (
    CONFIG_SCHEMA_VERSION,
    config_version,
    is_supported_version,
    validate_config,
    validation_report,
)
from lifetxt import mutation
from lifetxt.config_registry import explain_key
from lifetxt.config_writer import (
    MISSING_REVISION,
    ConfigRevisionRequired,
    ConfigWriteError,
    StaleConfigRevision,
    config_revision,
    rejected_candidates,
    serialize_config,
    write_config,
)
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

    def test_registry_describes_config_write_require_revision(self):
        entry = explain_key("config.write.require_revision")
        self.assertIsNotNone(entry)
        self.assertEqual("boolean", entry["type"])
        self.assertFalse(entry["default"])
        self.assertFalse(entry["secret"])
        self.assertFalse(entry["restart_required"])

    def test_registry_describes_new_ticketing_keys(self):
        for dotted, expected_type, expected_default in (
            (
                "ticketing.trackers",
                "array<string>",
                ["bug", "feature", "task", "support"],
            ),
            (
                "ticketing.priorities",
                "array<string>",
                ["low", "normal", "high", "urgent", "immediate"],
            ),
            (
                "ticketing.severities",
                "array<string>",
                ["trivial", "minor", "major", "critical", "blocker"],
            ),
            ("ticketing.components", "array<string>", []),
            ("ticketing.defaults.tracker", "string", "task"),
            ("ticketing.defaults.priority", "string", "normal"),
        ):
            entry = explain_key(dotted)
            self.assertIsNotNone(entry, dotted)
            self.assertEqual(expected_type, entry["type"], dotted)
            self.assertEqual(expected_default, entry["default"], dotted)

    def test_ticketing_config_template_keys_are_all_registered(self):
        """Every ticketing.* key config_template() defines must have registry metadata.

        This is a coverage gate: it fails the moment a new ticketing setting
        (custom fields, workflow, watchers, versions/sprints, ...) is added to
        the template without also registering it, instead of letting the gap
        grow silently the way it did for the six keys this test was added
        alongside.
        """
        from lifetxt.config import config_template

        def leaf_paths(mapping, prefix):
            paths = []
            for key, value in mapping.items():
                dotted = "%s.%s" % (prefix, key)
                if isinstance(value, dict):
                    paths.extend(leaf_paths(value, dotted))
                else:
                    paths.append(dotted)
            return paths

        ticketing = config_template()["ticketing"]
        missing = [
            path
            for path in leaf_paths(ticketing, "ticketing")
            if explain_key(path) is None
        ]
        self.assertEqual([], missing)

    def test_config_schema_declares_config_write_require_revision(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Draft 2020-12 jsonschema validation not available")
        from lifetxt.safety_foundation import schema_bundle

        schema = schema_bundle()["config-v1.schema.json"]
        validator = Draft202012Validator(schema)
        valid = {"config": {"write": {"require_revision": True}}}
        self.assertEqual([], [e.message for e in validator.iter_errors(valid)])
        invalid = {"config": {"write": {"require_revision": "yes"}}}
        self.assertTrue([e.message for e in validator.iter_errors(invalid)])


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
            [
                ("config_version", 1),
                ("web", {"port": 9000}),
                ("_path", self.path),
                ("_active_workspace", "default"),
            ]
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
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 8000 + index}},
                max_backups=2,
            )
        backups = [n for n in os.listdir(self.temp.name) if ".bak" in n]
        self.assertLessEqual(len(backups), 2)

    def test_serialize_is_stable_json(self):
        text = serialize_config({"config_version": 1, "_path": "x"})
        self.assertIn("config_version", text)
        self.assertNotIn("_path", text)


class ConfigRevisionTests(unittest.TestCase):
    """Compare-and-set behaviour for configuration writes."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, ".lifetxt.json")

    def tearDown(self):
        self.temp.cleanup()

    def seed(self, port=8000):
        return write_config(self.path, {"config_version": 1, "web": {"port": port}})

    def read_bytes(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def test_missing_file_reports_missing_revision(self):
        self.assertEqual(MISSING_REVISION, config_revision(self.path))

    def test_revision_is_stable_for_unchanged_content(self):
        report = self.seed()
        self.assertEqual(report["revision"], config_revision(self.path))
        self.assertEqual(config_revision(self.path), config_revision(self.path))

    def test_missing_precondition_creates_then_blocks_second_create(self):
        report = write_config(
            self.path, {"config_version": 1}, expected_revision=MISSING_REVISION
        )
        self.assertTrue(report["written"])
        with self.assertRaises(StaleConfigRevision):
            write_config(
                self.path, {"config_version": 1}, expected_revision=MISSING_REVISION
            )

    def test_matching_revision_writes_and_reports_both_revisions(self):
        first = self.seed()
        second = write_config(
            self.path,
            {"config_version": 1, "web": {"port": 8100}},
            expected_revision=first["revision"],
        )
        self.assertEqual(first["revision"], second["before_revision"])
        self.assertNotEqual(second["before_revision"], second["revision"])
        self.assertEqual(second["revision"], config_revision(self.path))

    def test_stale_revision_is_refused_and_leaves_the_file_untouched(self):
        first = self.seed()
        # A concurrent writer commits between our read and our write.
        self.seed(port=9999)
        current = self.read_bytes()
        with self.assertRaises(StaleConfigRevision) as caught:
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 8100}},
                expected_revision=first["revision"],
            )
        self.assertEqual(current, self.read_bytes())
        self.assertEqual(first["revision"], caught.exception.expected)
        self.assertEqual(config_revision(self.path), caught.exception.current)

    def test_refused_write_retains_the_rejected_candidate(self):
        first = self.seed()
        self.seed(port=9999)
        with self.assertRaises(StaleConfigRevision) as caught:
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 8100}},
                expected_revision=first["revision"],
            )
        retained = caught.exception.retained
        self.assertTrue(retained and os.path.exists(retained))
        with open(retained, "r", encoding="utf-8") as handle:
            self.assertEqual(8100, json.load(handle)["web"]["port"])

    def test_rejected_rotation_is_bounded(self):
        first = self.seed()
        for index in range(5):
            self.seed(port=9000 + index)
            with self.assertRaises(StaleConfigRevision):
                write_config(
                    self.path,
                    {"config_version": 1, "web": {"port": 8100 + index}},
                    expected_revision=first["revision"],
                    max_rejected=2,
                )
        rejected = [n for n in os.listdir(self.temp.name) if ".rejected" in n]
        self.assertLessEqual(len(rejected), 2)

    def test_backup_rotation_recovers_from_transient_replace_permission_error(self):
        self.seed(port=1)
        self.seed(port=2)  # creates .bak1 = port 1; no shift yet
        real_replace = os.replace
        attempts = []

        def selective_replace(source, destination):
            if str(destination).endswith(".bak2"):
                attempts.append((source, destination))
                if len(attempts) <= 2:
                    raise PermissionError(5, "simulated WinError 5")
            real_replace(source, destination)

        with (
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_OS_NAMES", frozenset((os.name,))
            ),
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS", (0.0, 0.0, 0.0)
            ),
            mock.patch("lifetxt.atomic.os.replace", side_effect=selective_replace),
            mock.patch.object(atomic.time, "sleep"),
        ):
            self.seed(port=3)  # triggers the .bak1 -> .bak2 shift

        self.assertEqual(3, len(attempts))
        with open(self.path + ".bak2", "r", encoding="utf-8") as handle:
            self.assertEqual(1, json.load(handle)["web"]["port"])

    def test_backup_rotation_retry_exhaustion_stays_silent(self):
        self.seed(port=1)
        self.seed(port=2)
        real_replace = os.replace

        def always_fail_bak2(source, destination):
            if str(destination).endswith(".bak2"):
                raise PermissionError(5, "simulated WinError 5")
            real_replace(source, destination)

        with (
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_OS_NAMES", frozenset((os.name,))
            ),
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS", (0.0, 0.0)
            ),
            mock.patch("lifetxt.atomic.os.replace", side_effect=always_fail_bak2),
            mock.patch.object(atomic.time, "sleep"),
        ):
            report = self.seed(port=3)  # must not raise

        self.assertTrue(report["written"])
        self.assertFalse(os.path.exists(self.path + ".bak2"))
        with open(self.path + ".bak1", "r", encoding="utf-8") as handle:
            self.assertEqual(2, json.load(handle)["web"]["port"])
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertEqual(3, json.load(handle)["web"]["port"])

    def test_rejected_rotation_recovers_from_transient_replace_permission_error(self):
        first = self.seed(port=1)
        self.seed(port=2)
        with self.assertRaises(StaleConfigRevision):
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 101}},
                expected_revision=first["revision"],
            )  # creates .rejected1
        real_replace = os.replace
        attempts = []

        def selective_replace(source, destination):
            if str(destination).endswith(".rejected2"):
                attempts.append((source, destination))
                if len(attempts) <= 2:
                    raise PermissionError(5, "simulated WinError 5")
            real_replace(source, destination)

        with (
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_OS_NAMES", frozenset((os.name,))
            ),
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS", (0.0, 0.0, 0.0)
            ),
            mock.patch("lifetxt.atomic.os.replace", side_effect=selective_replace),
            mock.patch.object(atomic.time, "sleep"),
        ):
            with self.assertRaises(StaleConfigRevision):
                write_config(
                    self.path,
                    {"config_version": 1, "web": {"port": 102}},
                    expected_revision=first["revision"],
                )  # triggers the .rejected1 -> .rejected2 shift

        self.assertEqual(3, len(attempts))
        with open(self.path + ".rejected2", "r", encoding="utf-8") as handle:
            self.assertEqual(101, json.load(handle)["web"]["port"])
        with open(self.path + ".rejected1", "r", encoding="utf-8") as handle:
            self.assertEqual(102, json.load(handle)["web"]["port"])

    def test_rejected_rotation_retry_exhaustion_stays_silent(self):
        first = self.seed(port=1)
        self.seed(port=2)
        with self.assertRaises(StaleConfigRevision):
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 101}},
                expected_revision=first["revision"],
            )
        real_replace = os.replace

        def always_fail_rejected2(source, destination):
            if str(destination).endswith(".rejected2"):
                raise PermissionError(5, "simulated WinError 5")
            real_replace(source, destination)

        with (
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_OS_NAMES", frozenset((os.name,))
            ),
            mock.patch.object(
                atomic, "_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS", (0.0, 0.0)
            ),
            mock.patch("lifetxt.atomic.os.replace", side_effect=always_fail_rejected2),
            mock.patch.object(atomic.time, "sleep"),
        ):
            # The refusal itself (StaleConfigRevision) is the write's normal
            # compare-and-set outcome, unrelated to the rotation replace
            # failure. What this asserts is that candidate retention still
            # completes silently despite the rotation shift being exhausted.
            with self.assertRaises(StaleConfigRevision) as caught:
                write_config(
                    self.path,
                    {"config_version": 1, "web": {"port": 102}},
                    expected_revision=first["revision"],
                )

        self.assertTrue(caught.exception.retained)
        self.assertFalse(os.path.exists(self.path + ".rejected2"))
        with open(self.path + ".rejected1", "r", encoding="utf-8") as handle:
            self.assertEqual(102, json.load(handle)["web"]["port"])

    def test_dry_run_predicts_the_revision_without_writing(self):
        first = self.seed()
        before = self.read_bytes()
        report = write_config(
            self.path,
            {"config_version": 1, "web": {"port": 8100}},
            expected_revision=first["revision"],
            dry_run=True,
        )
        self.assertFalse(report["written"])
        self.assertEqual(before, self.read_bytes())
        self.assertNotEqual(report["revision"], config_revision(self.path))
        # Committing the same document must produce exactly the predicted value.
        committed = write_config(
            self.path,
            {"config_version": 1, "web": {"port": 8100}},
            expected_revision=first["revision"],
        )
        self.assertEqual(report["revision"], committed["revision"])

    def test_dry_run_on_a_stale_revision_refuses_without_retaining(self):
        first = self.seed()
        self.seed(port=9999)
        before = sorted(os.listdir(self.temp.name))
        with self.assertRaises(StaleConfigRevision) as caught:
            write_config(
                self.path,
                {"config_version": 1},
                expected_revision=first["revision"],
                dry_run=True,
            )
        self.assertIsNone(caught.exception.retained)
        self.assertEqual(before, sorted(os.listdir(self.temp.name)))

    def test_require_revision_refuses_a_write_without_one(self):
        self.seed()
        with self.assertRaises(ConfigRevisionRequired):
            write_config(self.path, {"config_version": 1}, require_revision=True)

    def test_hand_edited_file_is_detected(self):
        first = self.seed()
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("\n")
        with self.assertRaises(StaleConfigRevision):
            write_config(
                self.path, {"config_version": 1}, expected_revision=first["revision"]
            )

    def test_invalid_document_is_refused_as_invalid_not_retained(self):
        first = self.seed()
        self.seed(port=9999)
        before = sorted(os.listdir(self.temp.name))
        # Validation runs before the revision check, so an invalid document is
        # never retained as a recoverable candidate.
        with self.assertRaises(ConfigWriteError) as caught:
            write_config(
                self.path,
                {"config_version": 1, "notifications": {"email": {"token": "abc"}}},
                expected_revision=first["revision"],
            )
        self.assertNotIsInstance(caught.exception, StaleConfigRevision)
        self.assertEqual(before, sorted(os.listdir(self.temp.name)))

    def test_unsupported_version_is_refused_before_the_revision_check(self):
        first = self.seed()
        self.seed(port=9999)
        with self.assertRaises(ConfigWriteError) as caught:
            write_config(
                self.path,
                {"config_version": CONFIG_SCHEMA_VERSION + 1},
                expected_revision=first["revision"],
            )
        self.assertNotIsInstance(caught.exception, StaleConfigRevision)

    def test_write_without_a_revision_still_works(self):
        """The precondition is opt-in; existing callers must not break."""
        self.seed()
        report = write_config(self.path, {"config_version": 1, "web": {"port": 8100}})
        self.assertTrue(report["written"])
        self.assertEqual(report["revision"], config_revision(self.path))

    def test_precondition_is_delegated_to_the_locked_mutation_layer(self):
        """The comparison must happen inside the lock, not before the write.

        Checking the revision here and writing afterwards leaves a window in
        which another writer commits between the two and is silently
        overwritten, which is the failure the precondition exists to stop. This
        asserts the expected hash actually reaches the locked layer.
        """
        first = self.seed()
        seen = {}
        original = mutation.write_text

        def recording_write_text(path, *args, **kwargs):
            seen["expected_hash"] = kwargs.get("expected_hash")
            seen["operation"] = kwargs.get("operation")
            return original(path, *args, **kwargs)

        mutation.write_text = recording_write_text
        try:
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 8100}},
                expected_revision=first["revision"],
            )
        finally:
            mutation.write_text = original
        self.assertEqual(first["revision"], seen.get("expected_hash"))
        self.assertEqual("config.write", seen.get("operation"))

    def test_refused_write_does_not_churn_the_backup_chain(self):
        """A write that never happened must not consume a backup generation."""
        first = self.seed()
        self.seed(port=9999)
        backups = sorted(n for n in os.listdir(self.temp.name) if ".bak" in n)
        payloads = {
            name: open(os.path.join(self.temp.name, name), "rb").read()
            for name in backups
        }
        with self.assertRaises(StaleConfigRevision):
            write_config(
                self.path,
                {"config_version": 1, "web": {"port": 8100}},
                expected_revision=first["revision"],
            )
        after = sorted(n for n in os.listdir(self.temp.name) if ".bak" in n)
        self.assertEqual(backups, after)
        for name in backups:
            self.assertEqual(
                payloads[name], open(os.path.join(self.temp.name, name), "rb").read()
            )

    def test_non_ascii_round_trips(self):
        """The write bypasses atomic_write_text, so encoding is worth pinning."""
        report = write_config(
            self.path,
            {
                "config_version": 1,
                "defaults": {"timezone": "Asia/Tokyo"},
                "web": {"title": "生活記録"},
            },
        )
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertEqual("生活記録", json.load(handle)["web"]["title"])
        self.assertEqual(report["revision"], config_revision(self.path))

    def test_rejected_candidates_are_discoverable(self):
        self.assertEqual([], rejected_candidates(self.path))
        first = self.seed()
        self.seed(port=9999)
        with self.assertRaises(StaleConfigRevision):
            write_config(
                self.path, {"config_version": 1}, expected_revision=first["revision"]
            )
        found = rejected_candidates(self.path)
        self.assertEqual(1, len(found))
        self.assertTrue(found[0].endswith(".rejected1"))


class MigrationTests(unittest.TestCase):
    def test_legacy_to_workspaces_default(self):
        config = {
            "paths": ["life.txt", ".generated/cal.txt"],
            "write_file": "life.txt",
            "generated_paths": [".generated/cal.txt"],
        }
        migrated, changes = migrate_config(config)
        self.assertTrue(changes)
        self.assertEqual(CONFIG_SCHEMA_VERSION, migrated["config_version"])
        default = migrated["workspaces"]["default"]
        self.assertEqual("life.txt", default["write_file"])
        roles = [
            s.get("role") if isinstance(s, dict) else None for s in default["sources"]
        ]
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

    def test_config_write_require_revision_survives_migration(self):
        config = {
            "paths": ["life.txt"],
            "write_file": "life.txt",
            "config": {"write": {"require_revision": True}},
        }
        migrated, changes = migrate_config(config)
        self.assertTrue(changes)
        self.assertTrue(migrated["config"]["write"]["require_revision"])


if __name__ == "__main__":
    unittest.main()
