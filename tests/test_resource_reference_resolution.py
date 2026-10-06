import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

import lifetxt

lifetxt.bootstrap_legacy_surfaces()

from lifetxt import attachment_snapshot
from lifetxt.remote_backend import _opaque_id
from lifetxt.resource_reference_policy import policy
from lifetxt.resource_reference_resolution import (
    ResourceResolver,
    ReadContext,
    ResourceFailure,
)
from lifetxt.resource_reference_store import BindingStore
from scripts.build_attachment_snapshot_helper import build_helper, NAME


class ResourceResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            platform.system() != "Linux"
            or platform.machine() != "x86_64"
            or not shutil.which("cc")
        ):
            raise unittest.SkipTest("Reviewed Linux helper compiler unavailable")
        cls.package = tempfile.TemporaryDirectory()
        build_helper(Path(cls.package.name) / NAME)

    @classmethod
    def tearDownClass(cls):
        cls.package.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "life.txt"
        self.file = self.root / "payload.txt"
        self.file.write_bytes(b"AAAAAAA")
        self.source.write_text("[ ] T Task id:task file:payload.txt\n")
        self.workspace = _opaque_id("workspace", "test")
        self.source_id = _opaque_id("source", self.workspace, 0, 0, "primary")
        self.config = {
            "default_workspace": "test",
            "workspaces": {
                "test": {
                    "sources": [{"path": str(self.source), "writable": False}],
                    "collaboration": {
                        "members": {
                            "alice": {"role": "viewer"},
                            "owner": {"role": "owner"},
                        }
                    },
                }
            },
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "reader",
                        "disclosure_mode": "restricted-resource",
                        "scopes": ["attachment:read"],
                    }
                ],
                "resource_references": {
                    "enabled": True,
                    "workspace_id": self.workspace,
                    "store_path": str(self.root / "store.sqlite"),
                    "enrolled_items": [
                        {
                            "source_id": self.source_id,
                            "item_id": "task",
                            "attachment": "payload.txt",
                        }
                    ],
                },
            },
        }
        BindingStore.provision(self.root / "store.sqlite")
        self.store = BindingStore(self.root / "store.sqlite")
        self.addCleanup(self.store.close)
        p = patch.object(
            attachment_snapshot,
            "_package_directory",
            return_value=Path(self.package.name),
        )
        p.start()
        self.addCleanup(p.stop)
        self.resolver = ResourceResolver(
            self.store, lambda context: copy.deepcopy(self.config)
        )
        self.reference = self.resolver.enroll_selected(self.context())[0]

    def context(self):
        return ReadContext("alice", time.monotonic() + 30)

    def discover(self):
        return self.resolver.discover(
            self.workspace, self.source_id, "task", self.context()
        )

    def read(self, descriptor):
        return self.resolver.read(
            self.workspace,
            descriptor["resource_ref"],
            descriptor["source_revision"],
            descriptor["resource_revision"],
            self.context(),
        )

    def test_real_helper_read_only_generic_descriptor_exact_bytes(self):
        before = self.source.read_bytes()
        descriptor = self.discover()["resources"][0]
        self.assertEqual("Attachment", descriptor["display_name"])
        self.assertEqual(
            set(descriptor),
            {
                "contract_version",
                "resource_ref",
                "kind",
                "display_name",
                "source_revision",
                "resource_revision",
            },
        )
        self.assertEqual(b"AAAAAAA", self.read(descriptor).data)
        self.assertEqual(before, self.source.read_bytes())

    def test_current_resource_hash_not_short_hash(self):
        descriptor = self.discover()["resources"][0]
        self.file.write_bytes(b"BBBBBBB")
        with self.assertRaises(ResourceFailure) as result:
            self.read(descriptor)
        self.assertEqual("STALE_REVISION", result.exception.code)
        fresh = self.discover()["resources"][0]
        self.assertEqual(descriptor["resource_ref"], fresh["resource_ref"])
        self.assertNotEqual(descriptor["resource_revision"], fresh["resource_revision"])
        self.assertEqual(b"BBBBBBB", self.read(fresh).data)

    def test_revocation_precedes_stale_and_regrant_rechecks(self):
        descriptor = self.discover()["resources"][0]
        self.file.write_bytes(b"BBBBBBB")
        self.config["remote"]["principals"][0]["scopes"] = []
        with self.assertRaises(ResourceFailure) as result:
            self.read(descriptor)
        self.assertEqual("RESOURCE_UNAVAILABLE", result.exception.code)
        self.config["remote"]["principals"][0]["scopes"] = ["attachment:read"]
        with self.assertRaises(ResourceFailure) as result:
            self.read(descriptor)
        self.assertEqual("STALE_REVISION", result.exception.code)

    def test_permission_mode_membership_visibility_wrong_workspace(self):
        descriptor = self.discover()["resources"][0]
        base = copy.deepcopy(self.config)
        mutations = [
            lambda c: c["remote"]["principals"][0].update(disabled=True),
            lambda c: c["remote"]["principals"][0].update(disclosure_mode="trusted"),
            lambda c: c["workspaces"]["test"]["collaboration"]["members"].pop("alice"),
            lambda c: c["workspaces"]["test"].pop("collaboration"),
        ]
        for mutation in mutations:
            self.config = copy.deepcopy(base)
            mutation(self.config)
            with self.assertRaises(ResourceFailure):
                self.read(descriptor)
        self.config = base
        with self.assertRaises(ResourceFailure):
            self.resolver.discover("e" * 64, self.source_id, "task", self.context())
        self.source.write_text(
            "[ ] T Task id:task file:payload.txt visibility:private owner:bob\n"
        )
        with self.assertRaises(ResourceFailure):
            self.discover()

    def test_idless_duplicate_and_source_edit_invalidates(self):
        descriptor = self.discover()["resources"][0]
        self.source.write_text("[ ] T Task file:payload.txt\n")
        with self.assertRaises(ResourceFailure):
            self.discover()
        self.source.write_text(
            "[ ] T Task id:task file:payload.txt\n[ ] T Duplicate id:task\n"
        )
        with self.assertRaises(ResourceFailure):
            self.discover()
        self.source.write_text("[ ] T Renamed id:task file:payload.txt\n")
        with self.assertRaises(ResourceFailure) as result:
            self.read(descriptor)
        self.assertEqual("RESOURCE_UNAVAILABLE", result.exception.code)
        self.source.write_text("[ ] T Task id:task file:payload.txt\n")
        with self.assertRaises(ResourceFailure):
            self.read(descriptor)

    def test_source_restore_same_bytes_cannot_resurrect_unobserved_edit(self):
        descriptor = self.discover()["resources"][0]
        original = self.source.read_bytes()
        self.source.write_text("[ ] T Changed id:task file:payload.txt\n")
        self.source.write_bytes(original)
        with self.assertRaises(ResourceFailure) as result:
            self.read(descriptor)
        self.assertEqual("RESOURCE_UNAVAILABLE", result.exception.code)

    def test_detach_and_symlink_replacement_never_serve(self):
        descriptor = self.discover()["resources"][0]
        self.file.unlink()
        self.file.symlink_to(self.source)
        with self.assertRaises(ResourceFailure):
            self.read(descriptor)
        self.file.unlink()
        self.file.write_bytes(b"AAAAAAA")
        with self.assertRaises(ResourceFailure):
            self.read(descriptor)

    def test_disclosure_policy_tokens_and_full_digest(self):
        old = self.discover()["resources"][0]
        self.config["remote"]["resource_references"]["metadata"] = {
            "size": True,
            "mime": True,
            "digest": True,
        }
        with self.assertRaises(ResourceFailure) as result:
            self.read(old)
        self.assertEqual("STALE_REVISION", result.exception.code)
        fresh = self.discover()["resources"][0]
        self.assertEqual(7, fresh["size_bytes"])
        self.assertEqual(
            hashlib.sha256(b"AAAAAAA").hexdigest(), fresh["content_digest"]["value"]
        )
        self.assertEqual("application/octet-stream", fresh["media_type"])

    def test_missing_byte_grant_allows_metadata_only(self):
        self.config["remote"]["principals"][0]["scopes"] = []
        descriptor = self.discover()["resources"][0]
        with self.assertRaises(ResourceFailure):
            self.read(descriptor)

    def test_unenrolled_source_change_and_quota_limits(self):
        self.config["remote"]["resource_references"]["enrolled_items"] = []
        self.assertEqual([], self.discover()["resources"])
        self.assertEqual(
            0, len(self.store.item_bindings(self.workspace, self.source_id, "task"))
        )

    def test_bound_snapshot_and_cancel(self):
        descriptor = self.discover()["resources"][0]
        self.config["attachments"] = {"max_file_bytes": 4}
        with self.assertRaises(ResourceFailure):
            self.read(descriptor)
        context = self.context()
        context.cancel.set()
        with self.assertRaises(ResourceFailure):
            self.resolver.discover(self.workspace, self.source_id, "task", context)
