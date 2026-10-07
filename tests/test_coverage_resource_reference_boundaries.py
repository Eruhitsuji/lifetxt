"""Dependency-free security boundary evidence for resource-reference recovery."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lifetxt

lifetxt.bootstrap_legacy_surfaces()

from lifetxt.remote_resource_download import envelope
from lifetxt.resource_reference_policy import (
    LIMITS,
    fingerprint,
    policy,
    safe_text,
    validate_principals,
)
from lifetxt.resource_reference_resolution import ResourceFailure
from lifetxt.resource_reference_store import BindingStore, BindingUnavailable


class ResourceEnvelopeBoundaryTests(unittest.TestCase):
    def body(self, operation):
        data = {"contract_version": "1", "workspace_id": "a" * 64}
        if operation == "discover":
            data.update(source_id="b" * 64, item_id="task")
        else:
            data.update(
                resource_ref="att:v1:" + "c" * 32,
                source_revision="rev:v1:" + "d" * 32,
                resource_revision="rev:v1:" + "e" * 32,
            )
        if operation == "chunk":
            data.update(offset=0, length=65536)
        return data

    def reject(self, data, operation="discover", code="INVALID_REQUEST"):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        with self.assertRaises(ResourceFailure) as result:
            envelope(raw, operation)
        self.assertEqual(code, result.exception.code)

    def test_valid_operations_preserve_exact_selected_identity(self):
        for operation in ("discover", "full", "chunk"):
            data = self.body(operation)
            self.assertEqual(data, envelope(json.dumps(data).encode(), operation))

    def test_non_object_malformed_oversized_and_ambiguous_json(self):
        for raw in (
            b"[]",
            b"null",
            b"true",
            b"1",
            b'"text"',
            b"{",
            b"\xff",
            b"\xef\xbb\xbf{}",
            b" " * 2049,
            b'{"contract_version":"1","contract_version":"1"}',
            b'{"contract_version":"1","extra":NaN}',
            b'{"contract_version":"1","extra":Infinity}',
            b"[" * 1000 + b"]" * 1000,
        ):
            with self.subTest(raw=raw[:60]):
                self.reject(raw)

    def test_contract_versions_never_downgrade(self):
        for version in (None, True, 1, "", "v1", "1000"):
            self.reject(dict(self.body("discover"), contract_version=version))
        for version in ("0", "2", "999"):
            self.reject(
                dict(self.body("discover"), contract_version=version),
                code="UNSUPPORTED_CONTRACT",
            )

    def test_unknown_missing_and_invalid_discovery_fields(self):
        body = self.body("discover")
        self.reject(dict(body, path="/outside"))
        self.reject({k: v for k, v in body.items() if k != "item_id"})
        for key in ("workspace_id", "source_id"):
            for value in (None, True, "A" * 64, "a" * 63, "a" * 64 + "\n"):
                self.reject(dict(body, **{key: value}))
        for value in (None, "", "x" * 129, "task\n", "task\u202e"):
            self.reject(dict(body, item_id=value))

    def test_read_requires_both_revisions_and_exact_fields(self):
        body = self.body("full")
        for key in ("source_revision", "resource_revision"):
            self.reject(
                {k: v for k, v in body.items() if k != key},
                "full",
                "REVISION_REQUIRED",
            )
        self.reject(dict(body, offset=0), "full")

    def test_reference_namespaces_and_supported_versions(self):
        body = self.body("full")
        for key, prefix in (
            ("resource_ref", "att:"),
            ("source_revision", "rev:"),
            ("resource_revision", "rev:"),
        ):
            for value in (None, 1, "x" * 65, "", prefix + "v1:" + "A" * 32):
                self.reject(dict(body, **{key: value}), "full", "INVALID_REFERENCE")
            self.reject(
                dict(body, **{key: prefix + "v2:" + "a" * 32}),
                "full",
                "UNSUPPORTED_CONTRACT",
            )

    def test_chunk_integer_bounds_reject_boolean_negative_and_oversize(self):
        body = self.body("chunk")
        for key, invalid in (
            ("offset", (True, 0.0, -1, 10485761)),
            ("length", (False, 1.0, 0, 65537)),
        ):
            for value in invalid:
                self.reject(dict(body, **{key: value}), "chunk")
        for offset in (0, 10485760):
            for length in (1, 65536):
                data = dict(body, offset=offset, length=length)
                self.assertEqual(data, envelope(json.dumps(data).encode(), "chunk"))


class ResourceOperatorPolicyBoundaryTests(unittest.TestCase):
    def enabled(self):
        return {
            "remote": {
                "enabled": True,
                "resource_references": {
                    "enabled": True,
                    "workspace_id": "a" * 64,
                    "store_path": "/synthetic/bindings.sqlite",
                },
            }
        }

    def test_enabled_requires_isolated_single_worker_and_absolute_store(self):
        mutations = (
            {"workspace_id": None},
            {"workspace_id": "A" * 64},
            {"store_path": None},
            {"store_path": "relative.sqlite"},
        )
        for fields in mutations:
            config = self.enabled()
            config["remote"]["resource_references"].update(fields)
            with self.assertRaises(BindingUnavailable):
                policy(config)
        for fields in (
            {"enabled": False},
            {"browser_ui": True},
            {"allow_multi_worker": True},
        ):
            config = self.enabled()
            config["remote"].update(fields)
            with self.assertRaises(BindingUnavailable):
                policy(config)
        with patch.dict(os.environ, {"WEB_CONCURRENCY": "1"}):
            self.assertTrue(policy(self.enabled())["enabled"])
        with patch.dict(os.environ, {"WEB_CONCURRENCY": "2"}):
            with self.assertRaises(BindingUnavailable):
                policy(self.enabled())

    def test_nested_policy_shapes_and_every_limit_are_strict(self):
        for fields in (
            {"metadata": []},
            {"metadata": {"extra": False}},
            {"limits": None},
            {"limits": {"extra": 1}},
            {"enrolled_items": {}},
            {"enrolled_items": [{}] * 10001},
        ):
            with self.assertRaises(BindingUnavailable):
                policy({"remote": {"resource_references": fields}})
        for key, maximum in LIMITS.items():
            for value in (True, 0, maximum + 1):
                with self.assertRaises(BindingUnavailable):
                    policy(
                        {"remote": {"resource_references": {"limits": {key: value}}}}
                    )
            for value in (1, maximum):
                self.assertEqual(
                    value,
                    policy(
                        {"remote": {"resource_references": {"limits": {key: value}}}}
                    )["limits"][key],
                )

    def test_selectors_are_unique_exact_and_bounded(self):
        entry = dict(source_id="b" * 64, item_id="task", attachment="payload.txt")
        for entries in (
            [dict(entry, source_id=None)],
            [dict(entry, source_id="z" * 64)],
            [dict(entry, item_id="")],
            [dict(entry, attachment=None)],
            [dict(entry, attachment="")],
            [dict(entry, attachment="x" * 4096)],
            [entry, entry],
        ):
            with self.assertRaises(BindingUnavailable):
                policy({"remote": {"resource_references": {"enrolled_items": entries}}})
        config = {"remote": {"resource_references": {"enrolled_items": [entry]}}}
        self.assertEqual([entry], policy(config)["enrolled_items"])

    def test_text_rejects_controls_bidi_and_invalid_unicode(self):
        for text in (
            None,
            "",
            "x" * 129,
            "\ud800",
            "\x00",
            "\x7f",
            "\x9f",
            "\u061c",
            "\u200e",
            "\u200f",
            "\u2028",
            "\u2029",
            "\u202a",
            "\u202e",
            "\u2066",
            "\u2069",
        ):
            self.assertFalse(safe_text(text), repr(text))
        for text in ("task", "日本語", "😀" * 128):
            self.assertTrue(safe_text(text))

    def test_defaults_are_independent_and_policy_fingerprint_ignores_only_path(self):
        changed = policy({})
        changed["limits"]["file_bytes"] = 1
        changed["metadata"]["size"] = True
        self.assertEqual(LIMITS["file_bytes"], policy({})["limits"]["file_bytes"])
        self.assertFalse(policy({})["metadata"]["size"])
        config = self.enabled()
        self.assertEqual(fingerprint(config), fingerprint(dict(config, _path="other")))
        altered = copy.deepcopy(config)
        altered["remote"]["resource_references"]["metadata"] = {"size": True}
        self.assertNotEqual(fingerprint(config), fingerprint(altered))

    def test_principal_modes_duplicates_and_missing_credentials_fail_closed(self):
        for principals in (
            [{"id": "alice"}, {"id": "alice"}],
            [{"id": "alice", "disclosure_mode": "invalid"}],
            [{"id": "alice", "disclosure_mode": "restricted-resource"}],
            [{"id": "alice", "token_env": "RESOURCE_BOUNDARY_TOKEN"}],
        ):
            config = self.enabled()
            config["remote"]["principals"] = principals
            with patch.dict(
                os.environ, {"RESOURCE_BOUNDARY_TOKEN": "synthetic-bearer"}
            ):
                with self.assertRaises(BindingUnavailable):
                    validate_principals(config)
        config = self.enabled()
        config["remote"]["principals"] = [
            {
                "id": "alice",
                "disclosure_mode": "restricted-resource",
                "token_env": "RESOURCE_BOUNDARY_TOKEN",
            }
        ]
        with patch.dict(os.environ, {"RESOURCE_BOUNDARY_TOKEN": "synthetic-bearer"}):
            self.assertIn("alice", validate_principals(config))


@unittest.skipUnless(os.name == "posix", "private POSIX binding store")
class ResourceBindingBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "bindings.sqlite"
        BindingStore.provision(self.path)
        self.store = BindingStore(self.path)
        self.addCleanup(self.store.close)
        self.values = dict(
            workspace="a" * 64,
            source="b" * 64,
            item="task",
            association="file.txt",
            source_hash="c" * 64,
            source_identity=(1, 2, 3, 4),
            resource_identity=(1, 2, 5, 6),
            policy="d" * 64,
        )

    def test_constructor_quota_types_and_bounds(self):
        for fields in (
            {"max_active": True},
            {"max_total": 1.0},
            {"max_active": 0},
            {"max_active": 10001},
            {"max_active": 2, "max_total": 1},
            {"max_total": 50001},
        ):
            with self.assertRaises(BindingUnavailable):
                BindingStore(self.path, **fields)

    def test_enrollment_validation_does_not_allocate_partial_bindings(self):
        for key, invalid in (
            ("workspace", None),
            ("source", "z" * 64),
            ("source_hash", "short"),
            ("policy", 1),
            ("item", None),
            ("item", ""),
            ("item", "x" * 129),
            ("association", None),
            ("association", ""),
            ("association", "x" * 4096),
        ):
            with self.subTest(key=key, invalid=invalid):
                with self.assertRaises(BindingUnavailable):
                    self.store.enroll(**dict(self.values, **{key: invalid}))
        self.assertEqual([], self.store.item_bindings("a" * 64, "b" * 64, "task"))
        self.assertEqual(
            0,
            self.store.connection.execute("SELECT count(*) FROM bindings").fetchone()[
                0
            ],
        )

    def test_invalid_references_and_revision_hashes_are_rejected(self):
        for reference in (None, "", "att:v2:" + "a" * 32, "att:v1:" + "A" * 32):
            with self.assertRaises(BindingUnavailable):
                self.store.get("a" * 64, reference)
        reference = self.store.enroll(**self.values)
        row = self.store.get("a" * 64, reference)
        for hashes in (
            (None, "c" * 64, "d" * 64),
            ("c" * 64, "invalid", "d" * 64),
            ("c" * 64, "c" * 64, True),
        ):
            with self.assertRaises(BindingUnavailable):
                self.store.revisions(row, *hashes)
        self.assertEqual(
            0,
            self.store.connection.execute("SELECT count(*) FROM tokens").fetchone()[0],
        )

    def test_active_quota_detach_and_changed_policy_retire_old_tokens(self):
        self.store.max_active = 1
        reference = self.store.enroll(**self.values)
        row = self.store.get("a" * 64, reference)
        old = self.store.revisions(row, "c" * 64, "e" * 64, "d" * 64)
        fresh = self.store.revisions(row, "c" * 64, "e" * 64, "f" * 64)
        self.assertNotEqual(old, fresh)
        self.assertEqual(
            2,
            self.store.connection.execute(
                "SELECT count(*) FROM tokens WHERE live=1"
            ).fetchone()[0],
        )
        with self.assertRaises(BindingUnavailable):
            self.store.enroll(**dict(self.values, item="other"))
        self.store.detach(reference)
        self.assertEqual(
            0,
            self.store.connection.execute(
                "SELECT count(*) FROM tokens WHERE live=1"
            ).fetchone()[0],
        )
        self.assertNotEqual(reference, self.store.enroll(**self.values))

    def test_foreign_sidecar_and_database_replacement_fail_closed(self):
        reference = self.store.enroll(**self.values)
        sidecar = Path(str(self.path) + "-wal")
        sidecar.write_bytes(b"foreign")
        with self.assertRaises(BindingUnavailable):
            self.store.get("a" * 64, reference)
        sidecar.unlink()
        replacement = self.path.with_name("replacement.sqlite")
        replacement.write_bytes(self.path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(self.path)
        with self.assertRaises(BindingUnavailable):
            self.store.get("a" * 64, reference)
