"""Focused tests for the internal workspace context snapshot (#1187)."""

import os
import tempfile
import unittest
from unittest.mock import patch

from lifetxt import mutation
from lifetxt.workspace_context_snapshot import (
    WorkspaceContextUnavailable,
    describe_workspace_context_change,
    read_workspace_context,
)


class WorkspaceContextSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.primary = os.path.join(self.folder.name, "a.life.txt")
        self.secondary = os.path.join(self.folder.name, "b.life.txt")
        self.write(self.primary, "[ ] T Primary id:one\n")
        self.write(self.secondary, "[ ] T Other id:two\n")

    @staticmethod
    def write(path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def snapshot(self, paths=None, **kwargs):
        return read_workspace_context(
            [self.primary, self.secondary] if paths is None else paths,
            self.primary, **kwargs
        )

    def test_stable_single_and_multiple_sources_and_captured_bytes(self):
        one = self.snapshot([self.primary])
        self.assertEqual(one.fingerprint, self.snapshot([self.primary]).fingerprint)
        self.assertEqual(one.source_revisions[0][2], mutation.read_text_snapshot(
            self.primary
        ).content_hash)
        self.assertIn("Primary", one.text_for_path(self.primary))
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            one.text_for_path(self.secondary)
        self.assertEqual(error.exception.reason, "source_not_in_snapshot")
        multiple = self.snapshot()
        self.assertEqual(multiple.fingerprint, self.snapshot().fingerprint)
        self.assertNotEqual(one.fingerprint, multiple.fingerprint)
        self.assertEqual(len(multiple.source_revisions), 2)
        self.assertNotIn(self.folder.name, repr(multiple))
        self.assertNotIn("Primary", repr(multiple))

    def test_other_source_content_changed_without_writable_revision(self):
        before = self.snapshot()
        self.write(self.secondary, "[ ] T Updated id:two\n")
        after = self.snapshot()
        self.assertEqual(before.writable_revision, after.writable_revision)
        self.assertNotEqual(before.fingerprint, after.fingerprint)
        self.assertEqual(
            describe_workspace_context_change(before, after),
            ("source_content_changed",),
        )

    def test_writable_file_changes_and_fixed_source_order(self):
        old = self.snapshot()
        self.write(self.primary, "[ ] T Changed id:one\n")
        new = self.snapshot()
        self.assertIn("writable_changed", describe_workspace_context_change(old, new))
        reordered = self.snapshot([self.secondary, self.primary])
        self.assertIn(
            "source_membership_changed",
            describe_workspace_context_change(new, reordered),
        )

    def test_relative_path_and_symlink_alias_identify_same_source(self):
        current = os.getcwd()
        try:
            os.chdir(self.folder.name)
            relative = read_workspace_context("a.life.txt", "a.life.txt")
            absolute = self.snapshot([self.primary])
        finally:
            os.chdir(current)
        self.assertEqual(relative.fingerprint, absolute.fingerprint)
        self.assertEqual(relative.text_for_path(self.primary), absolute.text_for_path(self.primary))
        alias = os.path.join(self.folder.name, "alias.life.txt")
        try:
            os.symlink(self.primary, alias)
        except (OSError, NotImplementedError):
            pass
        else:
            same = self.snapshot([alias])
            self.assertEqual(absolute.fingerprint, same.fingerprint)
            with self.assertRaises(WorkspaceContextUnavailable) as error:
                self.snapshot([self.primary, alias])
            self.assertEqual(error.exception.reason, "duplicate_source")

    def test_explicit_optional_missing_and_creation_removal(self):
        os.unlink(self.secondary)
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot()
        self.assertEqual(error.exception.reason, "source_unavailable")
        before = self.snapshot(optional_paths=[self.secondary])
        self.assertFalse(before.source_revisions[1][1])
        self.write(self.secondary, "[ ] T Returned id:two\n")
        after = self.snapshot(optional_paths=[self.secondary])
        self.assertIn("source_presence_changed", describe_workspace_context_change(before, after))
        os.unlink(self.secondary)
        self.assertEqual(
            before.fingerprint,
            self.snapshot(optional_paths=[self.secondary]).fingerprint,
        )

    def test_validation_config_changes_fingerprint(self):
        a = self.snapshot(config={"ids": {"key": "id"}})
        b = self.snapshot(config={"ids": {"key": "ticket"}})
        self.assertNotEqual(a.fingerprint, b.fingerprint)
        self.assertIn("validation_config_changed", describe_workspace_context_change(a, b))
        self.assertNotIn("ticket", repr(b))

    def test_configured_manifest_detects_glob_addition_and_deletion(self):
        config = {
            "workspaces": {"default": {
                "sources": [{"path": os.path.join(self.folder.name, "*.life.txt")}],
                "write_file": self.primary,
            }},
        }
        start = self.snapshot(config=config, check_manifest=True)
        self.assertEqual(start.scope, "checked_manifest")
        extra = os.path.join(self.folder.name, "c.life.txt")
        self.write(extra, "[ ] T Extra id:three\n")
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(config=config, check_manifest=True)
        self.assertEqual(error.exception.reason, "source_membership_changed")
        # The newly resolved list is a valid *different* effective scope.
        expanded = self.snapshot(
            paths=[self.primary, self.secondary, extra],
            config=config, check_manifest=True,
        )
        self.assertNotEqual(start.fingerprint, expanded.fingerprint)
        os.unlink(extra)
        self.assertEqual(
            start.fingerprint, self.snapshot(config=config, check_manifest=True).fingerprint
        )
        os.unlink(self.secondary)
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(config=config, check_manifest=True)
        self.assertEqual(error.exception.reason, "source_membership_changed")

    def test_invalid_manifest_and_unexpanded_globs_fail_closed(self):
        pattern = os.path.join(self.folder.name, "*.life.txt")
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(paths=[pattern])
        self.assertEqual(error.exception.reason, "source_resolution_required")
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(check_manifest=True, config={
                "workspaces": {"default": {"sources": [self.primary]}}
            })
        self.assertEqual(error.exception.reason, "source_membership_changed")
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(paths=[self.folder.name])
        self.assertEqual(error.exception.reason, "source_resolution_required")

    def test_permission_and_invalid_utf8_are_safe_errors(self):
        original = mutation.read_text_snapshot

        def refuse(path, **kwargs):
            if os.path.realpath(path) == os.path.realpath(self.secondary):
                raise PermissionError("private " + path)
            return original(path, **kwargs)

        with patch(
            "lifetxt.workspace_context_snapshot.mutation.read_text_snapshot",
            side_effect=refuse,
        ):
            with self.assertRaises(WorkspaceContextUnavailable) as error:
                self.snapshot()
        self.assertEqual(error.exception.reason, "source_unavailable")
        self.assertNotIn(self.folder.name, str(error.exception))
        with open(self.secondary, "wb") as handle:
            handle.write(b"\xff\xfe\x81")
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot()
        self.assertEqual(error.exception.reason, "source_unavailable")

    def test_byte_identity_not_mtime_and_size_bounds(self):
        before = self.snapshot()
        stat = os.stat(self.secondary)
        with open(self.secondary, "rb") as handle:
            text = handle.read()
        with open(self.secondary, "wb") as handle:
            handle.write(text.replace(b"Other", b"Hello"))
        os.utime(self.secondary, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        after = self.snapshot()
        self.assertNotEqual(before.fingerprint, after.fingerprint)
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(max_bytes=8)
        self.assertEqual(error.exception.reason, "source_too_large")
        with self.assertRaises(WorkspaceContextUnavailable) as error:
            self.snapshot(max_bytes=os.stat(self.primary).st_size + 1)
        self.assertEqual(error.exception.reason, "workspace_too_large")

    def test_repeated_reads_retry_and_fail_closed(self):
        original = mutation.read_text_snapshot
        calls = [0]

        def unstable(path, **kwargs):
            shot = original(path, **kwargs)
            if os.path.realpath(path) == os.path.realpath(self.secondary):
                calls[0] += 1
                if calls[0] % 2 == 1:
                    return shot._replace(content_hash="simulated-other-revision")
            return shot

        with patch(
            "lifetxt.workspace_context_snapshot.mutation.read_text_snapshot",
            side_effect=unstable,
        ):
            with self.assertRaises(WorkspaceContextUnavailable) as error:
                self.snapshot(attempts=2)
        self.assertEqual(error.exception.reason, "snapshot_unstable")
        self.assertEqual(calls[0], 4)

        calls = [0]

        def settling(path, **kwargs):
            shot = original(path, **kwargs)
            if os.path.realpath(path) == os.path.realpath(self.secondary):
                calls[0] += 1
                if calls[0] == 1:
                    return shot._replace(content_hash="initial-transient-revision")
            return shot

        with patch(
            "lifetxt.workspace_context_snapshot.mutation.read_text_snapshot",
            side_effect=settling,
        ):
            self.assertEqual(self.snapshot(attempts=2).fingerprint, self.snapshot().fingerprint)

    def test_invalid_inputs_are_rejected(self):
        for paths in ([], ["-"], [self.primary, self.primary]):
            with self.assertRaises(WorkspaceContextUnavailable):
                self.snapshot(paths=paths)
        with self.assertRaises(WorkspaceContextUnavailable):
            self.snapshot(config={"ids": {"key": {"not": {"serializable"}}}})
        with self.assertRaises(ValueError):
            self.snapshot(attempts=4)
        with self.assertRaises(ValueError):
            self.snapshot(max_bytes=0)


if __name__ == "__main__":
    unittest.main()
